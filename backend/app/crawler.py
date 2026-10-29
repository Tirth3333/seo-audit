"""Breadth-first, same-site crawler with robots.txt, depth, page, time and concurrency limits."""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from urllib.parse import urlsplit, urlunsplit

from .fetcher import FetchResult, SafeFetcher
from .parser import ParsedPage, parse_html
from .robots import RobotsPolicy, load_robots
from .security import same_site

NON_HTML_EXT = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".zip", ".gz", ".mp4", ".mp3",
    ".avi", ".mov", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".css", ".js", ".json", ".xml",
    ".woff", ".woff2", ".ttf", ".exe", ".dmg", ".rss",
)

ProgressCb = Callable[[dict], Awaitable[None]]


@dataclass
class CrawledPage:
    url: str
    depth: int
    fetch: FetchResult
    parsed: ParsedPage | None = None
    crawled: bool = True  # False = link-checked only


@dataclass
class CrawlOutcome:
    start_url: str
    pages: dict[str, CrawledPage] = field(default_factory=dict)
    link_checked: dict[str, CrawledPage] = field(default_factory=dict)
    inlinks: dict[str, list[dict]] = field(default_factory=lambda: defaultdict(list))  # target -> [{source, text}]
    robots: RobotsPolicy | None = None
    blocked_by_robots: list[str] = field(default_factory=list)
    sitemap: FetchResult | None = None
    sitemap_url: str | None = None
    stopped_reason: str | None = None
    fatal_error: str | None = None

    def status_of(self, url: str) -> CrawledPage | None:
        return self.pages.get(url) or self.link_checked.get(url)


def looks_like_html(url: str) -> bool:
    return not urlsplit(url).path.lower().endswith(NON_HTML_EXT)


@dataclass
class CrawlConfig:
    max_pages: int
    max_depth: int
    concurrency: int
    delay_s: float
    max_duration_s: float
    link_check_limit: int
    check_uncrawled_links: bool = True


class Crawler:
    def __init__(self, fetcher: SafeFetcher, cfg: CrawlConfig,
                 progress: ProgressCb | None = None, is_cancelled: Callable[[], bool] | None = None):
        self.fetcher = fetcher
        self.cfg = cfg
        self.progress = progress
        self.is_cancelled = is_cancelled or (lambda: False)

    async def _report(self, outcome: CrawlOutcome, phase: str, current: str | None, queued: int):
        if self.progress:
            await self.progress({
                "phase": phase,
                "pages_crawled": len(outcome.pages),
                "links_checked": len(outcome.link_checked),
                "queued": queued,
                "current_url": current,
                "max_pages": self.cfg.max_pages,
            })

    async def run(self, start_url: str) -> CrawlOutcome:
        out = CrawlOutcome(start_url=start_url)
        deadline = time.monotonic() + self.cfg.max_duration_s
        await self._report(out, "robots", start_url, 0)

        out.robots = await load_robots(self.fetcher, start_url)
        delay = self.cfg.delay_s
        if out.robots.crawl_delay is not None:
            delay = max(delay, min(out.robots.crawl_delay, 5.0))
        if not out.robots.can_fetch(start_url):
            out.fatal_error = (out.robots.reason or "robots.txt disallows crawling the start URL for this crawler.")
            out.blocked_by_robots.append(start_url)
            return out

        sem = asyncio.Semaphore(self.cfg.concurrency)
        seen: set[str] = {start_url}
        frontier: list[str] = [start_url]
        depth = 0

        async def crawl_one(url: str, d: int) -> CrawledPage:
            async with sem:
                await self._report(out, "crawling", url, len(frontier))
                res = await self.fetcher.fetch(url)
                if delay:
                    await asyncio.sleep(delay)
            page = CrawledPage(url=url, depth=d, fetch=res)
            if res.ok and res.is_html and same_site(res.final_url, start_url):
                page.parsed = parse_html(res.text, res.final_url)
            return page

        while frontier and depth <= self.cfg.max_depth:
            if self.is_cancelled():
                out.stopped_reason = "cancelled"
                break
            if time.monotonic() > deadline:
                out.stopped_reason = "time limit reached"
                break
            remaining = self.cfg.max_pages - len(out.pages)
            if remaining <= 0:
                out.stopped_reason = "page limit reached"
                break
            batch, frontier = frontier[:remaining], frontier[remaining:]
            results = await asyncio.gather(*(crawl_one(u, depth) for u in batch))
            next_frontier: list[str] = []
            for page in results:
                out.pages[page.url] = page
                seen.add(page.fetch.final_url)  # avoid re-crawling a redirect target
                if page.url == start_url and page.fetch.error:
                    out.fatal_error = f"Could not fetch the start URL: {page.fetch.error}"
                if not page.parsed:
                    continue
                for link in page.parsed.links:
                    target = link["href"]
                    if not same_site(target, start_url):
                        continue
                    out.inlinks[target].append({"source": page.url, "text": link["text"]})
                    if target in seen:
                        continue
                    seen.add(target)
                    if not looks_like_html(target):
                        continue
                    if not out.robots.can_fetch(target):
                        out.blocked_by_robots.append(target)
                        continue
                    next_frontier.append(target)
            if frontier:  # leftover from page limit
                out.stopped_reason = "page limit reached"
                frontier.extend(next_frontier)
                break
            frontier = next_frontier
            depth += 1
        if frontier and out.stopped_reason is None:
            out.stopped_reason = "depth limit reached"

        if out.fatal_error and len(out.pages) <= 1:
            return out

        await self._check_links(out, sem, deadline, start_url)
        await self._check_sitemap(out, start_url)
        await self._report(out, "analyzing", None, 0)
        return out

    async def _check_links(self, out: CrawlOutcome, sem, deadline: float, start_url: str):
        if not self.cfg.check_uncrawled_links:
            return
        targets = [t for t in out.inlinks
                   if t not in out.pages and t not in out.blocked_by_robots and out.robots.can_fetch(t)]
        targets = targets[: self.cfg.link_check_limit]

        async def probe(url: str):
            async with sem:
                if time.monotonic() > deadline or self.is_cancelled():
                    return
                await self._report(out, "checking links", url, 0)
                res = await self.fetcher.fetch(url, method="HEAD", read_body=False)
                if res.status in (405, 501) or (res.error and res.error_kind == "network"):
                    res = await self.fetcher.fetch(url, read_body=False)
                out.link_checked[url] = CrawledPage(url=url, depth=-1, fetch=res, crawled=False)

        await asyncio.gather(*(probe(t) for t in targets))

    async def _check_sitemap(self, out: CrawlOutcome, start_url: str):
        p = urlsplit(start_url)
        declared = [s for s in (out.robots.sitemaps if out.robots else []) if same_site(s, start_url)]
        url = declared[0] if declared else urlunsplit((p.scheme, p.netloc, "/sitemap.xml", "", ""))
        out.sitemap_url = url
        res = await self.fetcher.fetch(url, read_body=True)
        out.sitemap = res
