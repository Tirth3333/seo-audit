"""SEO rules. Each rule is declared once in RULES and every finding carries its rule_id,
the observed evidence (HTML values or HTTP responses), and whether it is a confirmed defect
or a best-practice recommendation. None of these are official Google ranking factors."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

from .crawler import CrawledPage, CrawlOutcome
from .models import Finding, Severity
from .security import same_site

TITLE_MAX, TITLE_MIN = 60, 15
DESC_MAX, DESC_MIN = 160, 50
THIN_WORDS = 150


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    category: str
    severity: Severity
    finding_type: str  # defect | recommendation | informational
    effort: str
    confidence: float
    explanation: str
    suggestion: str


S = Severity
_R = [
    # Crawlability & indexing
    Rule("ROBOTS_TXT_MISSING", "robots.txt not found", "Crawlability", S.low, "recommendation", "low", 0.9,
         "No robots.txt file was found. Crawlers will assume everything may be crawled; this is valid, but a robots.txt is the standard place to declare sitemaps and crawl rules.",
         "Add a /robots.txt file (it can simply allow all crawling) and reference your XML sitemap with a 'Sitemap:' line."),
    Rule("SITEMAP_MISSING", "XML sitemap not found", "Crawlability", S.low, "recommendation", "low", 0.8,
         "No XML sitemap was found at the location declared in robots.txt or at /sitemap.xml. Sitemaps help search engines discover pages, especially on larger sites.",
         "Generate an XML sitemap of canonical, indexable URLs and reference it in robots.txt and in Google Search Console."),
    Rule("SITEMAP_ERROR", "Declared sitemap returns an error", "Crawlability", S.medium, "defect", "low", 0.95,
         "robots.txt declares a sitemap, but requesting it did not return a successful response.",
         "Fix the sitemap URL in robots.txt or make sure the sitemap file is served with HTTP 200."),
    Rule("ROBOTS_BLOCKED", "Internal URLs blocked by robots.txt", "Crawlability", S.info, "informational", "low", 1.0,
         "Some internal links point to URLs disallowed by robots.txt. These were not crawled. This is often intentional (e.g. cart or admin pages).",
         "Confirm that each blocked path is meant to be hidden from crawlers; unblock any that should be indexed."),
    Rule("NOINDEX", "Page is set to noindex", "Indexability", S.high, "recommendation", "low", 0.6,
         "A robots meta tag or X-Robots-Tag header tells search engines not to index this page. If unintentional, the page cannot appear in search results.",
         "If the page should rank, remove 'noindex' from the robots meta tag / X-Robots-Tag header. If intentional, no action is needed."),
    Rule("NOFOLLOW_META", "Page-level nofollow", "Indexability", S.low, "recommendation", "low", 0.6,
         "The page's robots directives include 'nofollow', so search engines are asked not to follow any link on it.",
         "Remove page-level 'nofollow' unless you deliberately want links on this page ignored."),
    # HTTP status & redirects
    Rule("HTTP_5XX", "Page returns a server error (5xx)", "HTTP Status", S.critical, "defect", "medium", 0.9,
         "The server returned a 5xx error. Users and crawlers cannot access the page; repeated errors can lead to de-indexing. It may be transient, so re-test.",
         "Check server logs for this URL, fix the underlying error, and re-test."),
    Rule("HTTP_4XX", "Internal page returns a client error (4xx)", "HTTP Status", S.high, "defect", "medium", 1.0,
         "An internal URL reached by following site links returned a 4xx status (e.g. 404 Not Found).",
         "Restore the page, 301-redirect it to the most relevant live page, or remove links pointing to it."),
    Rule("FETCH_ERROR", "Page could not be fetched", "HTTP Status", S.medium, "defect", "medium", 0.5,
         "The request failed (timeout or network error). This may be transient or caused by bot protection.",
         "Re-test the URL. If it consistently fails, check server performance and firewall/bot rules."),
    Rule("REDIRECT_CHAIN", "Redirect chain", "Redirects", S.medium, "defect", "low", 1.0,
         "The URL passes through two or more redirects before reaching the final page. Chains slow users down and waste crawl budget.",
         "Point the first URL (and any internal links to it) directly at the final destination with a single 301 redirect."),
    Rule("REDIRECT_LOOP", "Redirect loop or excessive redirects", "Redirects", S.high, "defect", "medium", 1.0,
         "The URL redirects in a loop or exceeds the redirect limit, so it never resolves to a page.",
         "Fix the redirect rules so the URL resolves to a single final page in one hop."),
    Rule("LINK_TO_REDIRECT", "Internal links point to redirecting URLs", "Links", S.low, "recommendation", "low", 0.9,
         "Internal links point to a URL that redirects. It works, but costs an extra request for every visit and crawl.",
         "Update the internal links to point directly at the final URL."),
    Rule("BROKEN_INTERNAL_LINK", "Broken internal link", "Links", S.high, "defect", "low", 0.95,
         "One or more pages link to an internal URL that returned an error status.",
         "Update or remove the broken links on the linking pages, or redirect the broken URL to a relevant live page."),
    # Titles
    Rule("TITLE_MISSING", "Missing title tag", "Titles", S.high, "defect", "low", 1.0,
         "The page has no <title> element. Titles are a primary source for the clickable headline in search results.",
         "Add a unique, descriptive <title> (roughly 30–60 characters) that includes the page's main topic."),
    Rule("TITLE_EMPTY", "Empty title tag", "Titles", S.high, "defect", "low", 1.0,
         "The <title> element exists but contains no text.",
         "Write a unique, descriptive title for the page."),
    Rule("TITLE_MULTIPLE", "Multiple title tags", "Titles", S.low, "defect", "low", 0.9,
         "The page contains more than one <title> element. Browsers and search engines use only one, so the result can be unpredictable.",
         "Keep exactly one <title> element in the <head>."),
    Rule("TITLE_TOO_LONG", "Title may be truncated in results", "Titles", S.low, "recommendation", "low", 0.6,
         f"The title is longer than {TITLE_MAX} characters. Search engines truncate by pixel width, so this is an approximation, not a hard limit.",
         "Move the most important words to the front and aim for roughly 30–60 characters."),
    Rule("TITLE_TOO_SHORT", "Very short title", "Titles", S.low, "recommendation", "low", 0.5,
         f"The title is shorter than {TITLE_MIN} characters, which may not describe the page well.",
         "Expand the title to describe the page's topic (and brand, if useful)."),
    Rule("TITLE_DUPLICATE", "Duplicate title across pages", "Titles", S.medium, "defect", "low", 0.9,
         "Several crawled pages share exactly the same title, making them hard to distinguish in search results and possibly signalling duplicate content.",
         "Give each page a unique title reflecting its specific content."),
    # Meta descriptions
    Rule("META_DESC_MISSING", "Missing meta description", "Meta Descriptions", S.medium, "recommendation", "low", 0.9,
         "No meta description was found. Search engines may generate a snippet from page text instead; a written description gives you more control over the snippet.",
         "Add a unique meta description (roughly 50–160 characters) summarising the page and its value."),
    Rule("META_DESC_EMPTY", "Empty meta description", "Meta Descriptions", S.medium, "defect", "low", 1.0,
         "A meta description tag exists but its content is empty.",
         "Fill in the meta description or remove the empty tag."),
    Rule("META_DESC_MULTIPLE", "Multiple meta descriptions", "Meta Descriptions", S.low, "defect", "low", 0.9,
         "The page contains more than one meta description tag.",
         "Keep a single meta description tag."),
    Rule("META_DESC_LENGTH", "Meta description length outside typical range", "Meta Descriptions", S.low, "recommendation", "low", 0.5,
         f"The description is outside the commonly displayed range of about {DESC_MIN}–{DESC_MAX} characters. This is guidance only; snippet length varies.",
         f"Aim for roughly {DESC_MIN}–{DESC_MAX} characters with the key message first."),
    Rule("META_DESC_DUPLICATE", "Duplicate meta description across pages", "Meta Descriptions", S.low, "defect", "low", 0.85,
         "Several crawled pages share exactly the same meta description.",
         "Write a distinct description for each page."),
    # Headings
    Rule("H1_MISSING", "Missing H1 heading", "Headings", S.medium, "recommendation", "low", 0.9,
         "No <h1> was found in the HTML. A clear main heading helps users and search engines understand the page topic. (Content rendered only by JavaScript is not visible to this crawler.)",
         "Add one visible <h1> that states the page's main topic."),
    Rule("H1_EMPTY", "Empty H1 heading", "Headings", S.medium, "defect", "low", 0.9,
         "An <h1> element exists but contains no text (it may contain only an image without alt text).",
         "Put descriptive text in the H1, or give the image inside it meaningful alt text."),
    Rule("H1_MULTIPLE", "Multiple H1 headings", "Headings", S.low, "recommendation", "low", 0.5,
         "The page has more than one <h1>. This is valid HTML and not a confirmed problem, but a single main heading usually gives a clearer structure.",
         "Consider keeping one H1 for the main topic and using H2/H3 for sections."),
    Rule("HEADING_SKIP", "Skipped heading level", "Headings", S.low, "recommendation", "low", 0.7,
         "The heading hierarchy skips a level (for example an H2 followed directly by an H4). This mainly affects accessibility and document structure.",
         "Use heading levels in order (H1 → H2 → H3) to reflect the content outline."),
    # Canonical
    Rule("CANONICAL_MISSING", "Missing canonical tag", "Canonicalization", S.low, "recommendation", "low", 0.9,
         "No rel=\"canonical\" link was found. Canonicals help consolidate duplicate URLs (e.g. with tracking parameters).",
         "Add a self-referencing <link rel=\"canonical\"> with the preferred absolute URL."),
    Rule("CANONICAL_MULTIPLE", "Multiple canonical tags", "Canonicalization", S.medium, "defect", "low", 0.9,
         "More than one canonical link was found. Conflicting canonicals may cause search engines to ignore them.",
         "Keep exactly one canonical link per page."),
    Rule("CANONICAL_OFFSITE", "Canonical points to another domain", "Canonicalization", S.info, "informational", "low", 0.8,
         "The canonical URL is on a different host. This is correct for syndicated content but a serious error if accidental.",
         "Confirm the cross-domain canonical is intentional."),
    Rule("CANONICAL_BROKEN", "Canonical target returns an error or redirects", "Canonicalization", S.medium, "defect", "low", 0.9,
         "The canonical URL, when requested, did not return HTTP 200 directly.",
         "Point the canonical at the final, indexable URL that returns 200."),
    # Images
    Rule("IMG_ALT_MISSING", "Images missing alt attribute", "Images", S.medium, "defect", "medium", 0.95,
         "Some <img> elements have no alt attribute at all. Alt text is needed for screen readers and helps image search. (Empty alt=\"\" is correct for decorative images and is not flagged.)",
         "Add descriptive alt text to meaningful images, and alt=\"\" to purely decorative ones."),
    # Security / mobile / content
    Rule("NOT_HTTPS", "Page served over HTTP, not HTTPS", "Security", S.high, "defect", "medium", 0.95,
         "The page was served without HTTPS. Browsers mark such pages as 'Not secure' and HTTPS is a lightweight ranking signal.",
         "Serve the site over HTTPS and 301-redirect all HTTP URLs to their HTTPS versions."),
    Rule("MIXED_CONTENT", "Insecure (HTTP) resources on HTTPS page", "Security", S.medium, "defect", "low", 0.85,
         "This HTTPS page loads images, scripts, stylesheets or frames over plain HTTP. Browsers may block them or show warnings.",
         "Load these resources over HTTPS (or use protocol-relative/relative URLs)."),
    Rule("VIEWPORT_MISSING", "Missing viewport meta tag", "Mobile", S.medium, "defect", "low", 0.85,
         "No <meta name=\"viewport\"> was found, so mobile browsers may render the page at desktop width.",
         "Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."),
    Rule("LANG_MISSING", "Missing html lang attribute", "Accessibility", S.low, "recommendation", "low", 0.8,
         "The <html> element has no lang attribute, which helps screen readers and language detection.",
         "Add the page language, e.g. <html lang=\"en\">."),
    Rule("THIN_CONTENT", "Low word count", "Content", S.low, "recommendation", "medium", 0.4,
         f"Fewer than {THIN_WORDS} words of text were found in the HTML. Word count is not a ranking factor by itself, and pages rendered with JavaScript may appear thin to this crawler.",
         "Check whether the page fully answers its visitors' needs; add useful content if it does not."),
    Rule("PAGE_TRUNCATED", "Page exceeded size limit", "Performance", S.info, "informational", "low", 1.0,
         "The HTML response was larger than the crawler's size limit, so only the first part was analysed.",
         "Very large HTML documents load slowly; consider reducing inline scripts/styles and page weight."),
]
RULES: dict[str, Rule] = {r.id: r for r in _R}


def _fid(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]


def make(rule_id: str, url: str, evidence: str, related: list[str] | None = None, **override) -> Finding:
    r = RULES[rule_id]
    data = dict(
        id=_fid(rule_id, url, evidence[:200]), rule_id=r.id, title=r.title, category=r.category,
        severity=r.severity, finding_type=r.finding_type, url=url, evidence=evidence[:2000],
        explanation=r.explanation, suggestion=r.suggestion, effort=r.effort, confidence=r.confidence,
        related_urls=(related or [])[:50],
    )
    data.update(override)
    return Finding(**data)


def _q(s: str | None, n: int = 160) -> str:
    s = s or ""
    return f'"{s[:n]}{"…" if len(s) > n else ""}"'


def analyzable_pages(outcome: CrawlOutcome) -> list[CrawledPage]:
    """Parsed HTML pages, de-duplicated by final URL (redirect sources are skipped)."""
    seen, pages = set(), []
    for p in outcome.pages.values():
        if p.parsed is None:
            continue
        final = p.fetch.final_url
        if final in seen:
            continue
        seen.add(final)
        pages.append(p)
    return pages


def page_rules(p: CrawledPage) -> list[Finding]:
    f: list[Finding] = []
    pp, url = p.parsed, p.fetch.final_url
    assert pp is not None

    # Titles
    if pp.title_count == 0:
        f.append(make("TITLE_MISSING", url, "No <title> element found in the HTML <head>."))
    elif not pp.title:
        f.append(make("TITLE_EMPTY", url, "<title></title> is present but empty."))
    else:
        if len(pp.title) > TITLE_MAX:
            f.append(make("TITLE_TOO_LONG", url, f"Title ({len(pp.title)} chars): {_q(pp.title, 200)}"))
        elif len(pp.title) < TITLE_MIN:
            f.append(make("TITLE_TOO_SHORT", url, f"Title ({len(pp.title)} chars): {_q(pp.title)}"))
    if pp.title_count > 1:
        f.append(make("TITLE_MULTIPLE", url, f"{pp.title_count} <title> elements found."))

    # Meta description
    if pp.meta_description_count == 0:
        f.append(make("META_DESC_MISSING", url, 'No <meta name="description"> tag found.'))
    elif not pp.meta_description:
        f.append(make("META_DESC_EMPTY", url, '<meta name="description" content=""> is empty.'))
    elif not (DESC_MIN <= len(pp.meta_description) <= DESC_MAX):
        f.append(make("META_DESC_LENGTH", url,
                      f"Meta description ({len(pp.meta_description)} chars): {_q(pp.meta_description, 220)}"))
    if pp.meta_description_count > 1:
        f.append(make("META_DESC_MULTIPLE", url, f"{pp.meta_description_count} meta description tags found."))

    # Headings
    h1s = pp.h1s
    if not h1s:
        f.append(make("H1_MISSING", url, "No <h1> element found in the HTML."))
    else:
        if any(not t for t in h1s):
            f.append(make("H1_EMPTY", url, "An <h1> element has no text content."))
        if len(h1s) > 1:
            f.append(make("H1_MULTIPLE", url, f"{len(h1s)} H1 headings: " + "; ".join(_q(t, 60) for t in h1s[:5])))
    prev = None
    for lvl, text in pp.headings:
        if prev is not None and lvl > prev[0] + 1:
            f.append(make("HEADING_SKIP", url, f"H{prev[0]} {_q(prev[1], 60)} is followed by H{lvl} {_q(text, 60)}."))
            break  # one finding per page is enough
        prev = (lvl, text)

    # Canonical
    if not pp.canonicals:
        f.append(make("CANONICAL_MISSING", url, 'No <link rel="canonical"> found.'))
    elif len(set(pp.canonicals)) > 1:
        f.append(make("CANONICAL_MULTIPLE", url, "Canonicals: " + ", ".join(sorted(set(pp.canonicals))[:5])))
    elif not same_site(pp.canonicals[0], url):
        f.append(make("CANONICAL_OFFSITE", url, f"Canonical: {pp.canonicals[0]}"))

    # Robots directives
    directives = " ".join(filter(None, [pp.meta_robots, p.fetch.headers.get("x-robots-tag")])).lower()
    tokens = set(directives.replace(",", " ").replace(":", " ").split())
    if "noindex" in tokens or "none" in tokens:
        src = []
        if pp.meta_robots and ("noindex" in pp.meta_robots.lower()):
            src.append(f'meta robots="{pp.meta_robots}"')
        if "noindex" in (p.fetch.headers.get("x-robots-tag") or "").lower():
            src.append(f'X-Robots-Tag: {p.fetch.headers.get("x-robots-tag")}')
        f.append(make("NOINDEX", url, "; ".join(src) or f"Directives: {directives}"))
    elif "nofollow" in tokens:
        f.append(make("NOFOLLOW_META", url, f"Robots directives: {directives}"))

    # Images
    missing = [i["src"] or "(no src)" for i in pp.images if i["alt"] is None]
    if missing:
        f.append(make("IMG_ALT_MISSING", url,
                      f"{len(missing)} of {len(pp.images)} images have no alt attribute. Examples: " + ", ".join(missing[:5]),
                      related=missing))

    # Security, mobile, content
    if url.startswith("http://"):
        f.append(make("NOT_HTTPS", url, f"Final URL uses http:// ({url})."))
    if pp.insecure_resources:
        f.append(make("MIXED_CONTENT", url,
                      f"{len(pp.insecure_resources)} insecure resource(s), e.g. " + ", ".join(pp.insecure_resources[:3]),
                      related=pp.insecure_resources))
    if not pp.has_viewport:
        f.append(make("VIEWPORT_MISSING", url, 'No <meta name="viewport"> tag found.'))
    if not pp.lang:
        f.append(make("LANG_MISSING", url, "<html> element has no lang attribute."))
    if pp.word_count < THIN_WORDS:
        f.append(make("THIN_CONTENT", url, f"{pp.word_count} words of visible text found in the HTML."))
    if p.fetch.truncated:
        f.append(make("PAGE_TRUNCATED", url, f"Response exceeded {len(p.fetch.body):,} bytes and was truncated."))
    return f


def _status_findings(outcome: CrawlOutcome) -> list[Finding]:
    f: list[Finding] = []
    for p in outcome.pages.values():
        res = p.fetch
        sources = [s["source"] for s in outcome.inlinks.get(p.url, [])]
        if res.error_kind in ("redirect_loop", "too_many_redirects"):
            hops = " → ".join(h["url"] for h in res.redirect_chain) or p.url
            f.append(make("REDIRECT_LOOP", p.url, f"{res.error} Hops: {hops}", related=sources))
        elif res.error:
            if res.error_kind != "blocked":
                f.append(make("FETCH_ERROR", p.url, f"{res.error} (after {res.elapsed_ms} ms)", related=sources))
        # Error pages that are linked internally are reported once, as BROKEN_INTERNAL_LINK.
        elif res.status and res.status >= 500 and not sources:
            f.append(make("HTTP_5XX", p.url, f"HTTP {res.status} returned."))
        elif res.status and 400 <= res.status < 500 and not sources:
            f.append(make("HTTP_4XX", p.url, f"HTTP {res.status} returned."))
        if len(res.redirect_chain) >= 2 and not res.error:
            chain = " → ".join(f'{h["url"]} ({h["status"]})' for h in res.redirect_chain) + f" → {res.final_url} ({res.status})"
            f.append(make("REDIRECT_CHAIN", p.url, f"{len(res.redirect_chain)} redirects: {chain}", related=sources))
    return f


def _link_findings(outcome: CrawlOutcome) -> list[Finding]:
    f: list[Finding] = []
    for target, links in outcome.inlinks.items():
        page = outcome.status_of(target)
        if page is None:
            continue
        sources = sorted({link["source"] for link in links})
        res = page.fetch
        if res.status is not None and res.status >= 400:
            anchor = next((link["text"] for link in links if link["text"]), "")
            f.append(make(
                "BROKEN_INTERNAL_LINK", target,
                f"{target} returned HTTP {res.status}. Linked from {len(sources)} page(s)"
                + (f", anchor text {_q(anchor, 60)}" if anchor else "") + ": " + ", ".join(sources[:5]),
                related=sources,
                severity=S.critical if res.status >= 500 else S.high,
            ))
        elif res.redirect_chain and not res.error and res.status and res.status < 400:
            f.append(make("LINK_TO_REDIRECT", target,
                          f"{target} redirects ({res.redirect_chain[0]['status']}) to {res.final_url}. "
                          f"Linked from {len(sources)} page(s): " + ", ".join(sources[:5]),
                          related=sources))
    return f


def _duplicate_findings(pages: list[CrawledPage]) -> list[Finding]:
    f: list[Finding] = []
    for rule_id, attr in (("TITLE_DUPLICATE", "title"), ("META_DESC_DUPLICATE", "meta_description")):
        groups: dict[str, list[str]] = defaultdict(list)
        for p in pages:
            val = getattr(p.parsed, attr)
            if val:
                groups[val.strip().lower()].append(p.fetch.final_url)
        for urls in groups.values():
            if len(urls) < 2:
                continue
            original = getattr(next(p.parsed for p in pages if p.fetch.final_url == urls[0]), attr)
            for u in urls:
                others = [o for o in urls if o != u]
                f.append(make(rule_id, u, f"{_q(original)} is shared by {len(urls)} pages: " + ", ".join(urls[:5]),
                              related=others))
    return f


def _canonical_target_findings(pages: list[CrawledPage], outcome: CrawlOutcome) -> list[Finding]:
    f = []
    for p in pages:
        if len(set(p.parsed.canonicals)) != 1:
            continue
        canon = p.parsed.canonicals[0]
        if canon == p.fetch.final_url or not same_site(canon, outcome.start_url):
            continue
        target = outcome.status_of(canon)
        if target is None:
            continue
        r = target.fetch
        if r.error or (r.status or 0) >= 300 or r.redirect_chain:
            observed = r.error or (f"HTTP {r.status}" + (f" after redirect to {r.final_url}" if r.redirect_chain else ""))
            f.append(make("CANONICAL_BROKEN", p.fetch.final_url, f"Canonical {canon} → {observed}"))
    return f


def _site_findings(outcome: CrawlOutcome) -> list[Finding]:
    f = []
    rb = outcome.robots
    root = outcome.start_url
    if rb and rb.status == 404:
        f.append(make("ROBOTS_TXT_MISSING", rb.robots_url, f"GET {rb.robots_url} → HTTP 404."))
    sm = outcome.sitemap
    if sm is not None and outcome.sitemap_url:
        declared = bool(rb and outcome.sitemap_url in rb.sitemaps)
        ok = sm.ok and ("xml" in sm.content_type.lower() or sm.text.lstrip().startswith("<?xml") or "<urlset" in sm.text[:2000] or "<sitemapindex" in sm.text[:2000])
        if not ok:
            observed = sm.error or f"HTTP {sm.status}, content-type '{sm.content_type or 'n/a'}'"
            if declared:
                f.append(make("SITEMAP_ERROR", outcome.sitemap_url, f"Declared in robots.txt; GET returned {observed}."))
            else:
                f.append(make("SITEMAP_MISSING", root,
                              f"No Sitemap: line in robots.txt and GET {outcome.sitemap_url} returned {observed}."))
    if outcome.blocked_by_robots:
        blocked = sorted(set(outcome.blocked_by_robots))
        f.append(make("ROBOTS_BLOCKED", root, f"{len(blocked)} internal URL(s) disallowed, e.g. " + ", ".join(blocked[:5]),
                      related=blocked))
    return f


def run_rules(outcome: CrawlOutcome) -> list[Finding]:
    pages = analyzable_pages(outcome)
    findings: list[Finding] = []
    for p in pages:
        findings.extend(page_rules(p))
    findings.extend(_status_findings(outcome))
    findings.extend(_link_findings(outcome))
    findings.extend(_duplicate_findings(pages))
    findings.extend(_canonical_target_findings(pages, outcome))
    findings.extend(_site_findings(outcome))
    # De-duplicate by id
    unique: dict[str, Finding] = {}
    for fi in findings:
        unique.setdefault(fi.id, fi)
    return list(unique.values())
