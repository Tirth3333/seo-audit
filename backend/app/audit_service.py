"""Orchestrates one audit: crawl → rules → scoring → persisted AuditResult."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import httpx

from .config import Settings
from .crawler import CrawlConfig, Crawler, CrawlOutcome
from .fetcher import SafeFetcher
from .models import AuditRequest, AuditResult, PageResult, SiteChecks
from .rules import run_rules
from .scoring import build_action_plan, score_findings, summarize
from .security import registrable_host, validate_url_syntax
from .storage import AuditStore

log = logging.getLogger("seo_audit")

BASE_LIMITATIONS = [
    "Only raw HTML is analysed; JavaScript is never executed, so content rendered client-side may be missed.",
    "robots.txt is always respected; disallowed URLs are not crawled.",
    "Only pages on the same host as the start URL ('www.' treated as equivalent) are crawled.",
    "Severity, priority and health scores are transparent heuristics, not Google metrics or ranking factors.",
    "Length thresholds for titles and descriptions are approximations; search engines truncate by pixel width.",
    "Pages behind logins, paywalls or bot protection are not accessed; such pages may appear as errors.",
    "Results reflect a single point in time; transient server errors can appear and should be re-tested.",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_audit(req: AuditRequest, settings: Settings) -> AuditResult:
    start = validate_url_syntax(req.url)
    max_pages = min(req.max_pages or settings.default_max_pages, settings.max_pages_limit)
    max_depth = min(req.max_depth if req.max_depth is not None else settings.default_max_depth,
                    settings.max_depth_limit)
    return AuditResult(
        id=uuid.uuid4().hex[:16], start_url=start, domain=registrable_host(start), status="queued",
        created_at=now_iso(),
        config={"max_pages": max_pages, "max_depth": max_depth,
                "check_uncrawled_links": req.check_uncrawled_links,
                "concurrency": settings.concurrency, "timeout_s": settings.request_timeout_s,
                "max_response_bytes": settings.max_response_bytes,
                "link_check_limit": settings.link_check_limit, "user_agent": settings.user_agent},
        progress={"phase": "queued", "pages_crawled": 0, "queued": 0, "max_pages": max_pages},
    )


def _pages(outcome: CrawlOutcome) -> list[PageResult]:
    rows = []
    for p in list(outcome.pages.values()) + list(outcome.link_checked.values()):
        r, pp = p.fetch, p.parsed
        rows.append(PageResult(
            url=p.url, final_url=r.final_url, status=r.status, depth=p.depth, content_type=r.content_type,
            title=pp.title if pp else None, meta_description=pp.meta_description if pp else None,
            h1_count=len(pp.h1s) if pp else 0, word_count=pp.word_count if pp else 0,
            internal_links=len(pp.links) if pp else 0, redirect_chain=r.redirect_chain,
            elapsed_ms=r.elapsed_ms, error=r.error, crawled=p.crawled,
        ))
    return rows


def finalize(audit: AuditResult, outcome: CrawlOutcome) -> AuditResult:
    findings = score_findings(run_rules(outcome))
    crawled = len([p for p in outcome.pages.values() if p.parsed is not None])
    audit.findings = findings
    audit.action_plan = build_action_plan(findings)
    audit.summary = summarize(findings, crawled, len(outcome.link_checked))
    audit.pages = _pages(outcome)
    rb = outcome.robots
    audit.site = SiteChecks(
        robots_txt_status=rb.status if rb else None, robots_txt_found=bool(rb and rb.found),
        sitemaps_declared=rb.sitemaps if rb else [], sitemap_url_checked=outcome.sitemap_url,
        sitemap_status=outcome.sitemap.status if outcome.sitemap else None,
        sitemap_found=bool(outcome.sitemap and outcome.sitemap.ok),
        blocked_by_robots=sorted(set(outcome.blocked_by_robots))[:200],
    )
    lim = list(BASE_LIMITATIONS)
    if outcome.stopped_reason:
        lim.insert(0, f"Crawl stopped early: {outcome.stopped_reason}. Pages beyond the limit were not analysed.")
    if rb and rb.reason:
        lim.append(rb.reason)
    audit.limitations = lim
    return audit


class AuditRunner:
    """Runs audits as background asyncio tasks and persists progress."""

    def __init__(self, store: AuditStore, settings: Settings, transport: httpx.AsyncBaseTransport | None = None,
                 resolver=None, on_progress=None):
        self.on_progress = on_progress
        self.store = store
        self.settings = settings
        self.transport = transport
        self.resolver = resolver
        self.tasks: dict[str, asyncio.Task] = {}
        self.cancelled: set[str] = set()

    def start(self, audit: AuditResult) -> None:
        self.store.save(audit)
        self.tasks[audit.id] = asyncio.create_task(self.run(audit))

    def cancel(self, audit_id: str) -> bool:
        if audit_id in self.tasks and not self.tasks[audit_id].done():
            self.cancelled.add(audit_id)
            return True
        return False

    async def run(self, audit: AuditResult) -> AuditResult:
        s = self.settings
        audit.status, audit.started_at = "running", now_iso()
        self.store.save(audit)
        last_save = 0.0

        async def progress(p: dict):
            nonlocal last_save
            audit.progress = p
            if self.on_progress:
                self.on_progress(p)
            if time.monotonic() - last_save > 0.5:
                last_save = time.monotonic()
                self.store.save(audit)

        fetcher = SafeFetcher(
            user_agent=s.user_agent, timeout_s=s.request_timeout_s, max_bytes=s.max_response_bytes,
            max_redirects=s.max_redirects, allow_private=s.allow_private_hosts, use_env_proxy=s.use_env_proxy,
            transport=self.transport, resolver=self.resolver,
        )
        cfg = CrawlConfig(
            max_pages=audit.config["max_pages"], max_depth=audit.config["max_depth"], concurrency=s.concurrency,
            delay_s=s.crawl_delay_s, max_duration_s=s.max_audit_duration_s, link_check_limit=s.link_check_limit,
            check_uncrawled_links=audit.config.get("check_uncrawled_links", True),
        )
        try:
            async with fetcher:
                outcome = await Crawler(fetcher, cfg, progress, lambda: audit.id in self.cancelled).run(audit.start_url)
            crawled = [p for p in outcome.pages.values() if p.parsed is not None]
            if outcome.fatal_error and not crawled:
                audit.status, audit.error = "failed", outcome.fatal_error
                finalize(audit, outcome)
            else:
                finalize(audit, outcome)
                audit.status = "cancelled" if outcome.stopped_reason == "cancelled" else "completed"
                if not crawled:
                    audit.status = "failed"
                    audit.error = "No HTML pages could be analysed (the start URL may not return an HTML page)."
            audit.progress = {**audit.progress, "phase": "done", "pages_crawled": len(crawled), "current_url": None}
        except Exception as exc:  # never leave an audit stuck in 'running'
            log.exception("Audit %s failed", audit.id)
            audit.status, audit.error = "failed", f"Unexpected error: {type(exc).__name__}"
        finally:
            audit.finished_at = now_iso()
            self.store.save(audit)
            self.cancelled.discard(audit.id)
        return audit
