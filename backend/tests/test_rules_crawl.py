"""End-to-end crawl of the fixture site, then rule detection and scoring."""
import httpx
import pytest

from app.crawler import CrawlConfig, Crawler
from app.models import Finding, Severity
from app.rules import RULES, run_rules
from app.scoring import build_action_plan, finding_priority, score_findings, summarize
from tests.conftest import make_fetcher
from tests.fixtures.site import HOST


def by_rule(findings: list[Finding]) -> dict[str, list[Finding]]:
    out: dict[str, list[Finding]] = {}
    for f in findings:
        out.setdefault(f.rule_id, []).append(f)
    return out


@pytest.fixture
async def outcome(crawl_fixture_site):
    return await crawl_fixture_site()


@pytest.fixture
def findings(outcome):
    return run_rules(outcome)


async def test_crawl_respects_robots_and_scope(outcome):
    crawled = set(outcome.pages)
    assert f"{HOST}/" in crawled and f"{HOST}/about" in crawled
    assert f"{HOST}/admin/login" not in crawled
    assert f"{HOST}/admin/login" in outcome.blocked_by_robots
    assert not any("external.example.org" in u for u in crawled)
    assert outcome.robots.found and outcome.sitemap.ok


async def test_page_limit(crawl_fixture_site):
    o = await crawl_fixture_site(max_pages=3)
    assert len(o.pages) == 3 and o.stopped_reason == "page limit reached"


async def test_depth_zero_only_crawls_start(crawl_fixture_site):
    o = await crawl_fixture_site(max_depth=0, check_links=False)
    assert list(o.pages) == [f"{HOST}/"]


def test_title_rules(findings):
    r = by_rule(findings)
    assert [f.url for f in r["TITLE_MISSING"]] == [f"{HOST}/contact"]
    assert any(f.url == f"{HOST}/about" for f in r["TITLE_TOO_SHORT"])
    assert any(f.url == f"{HOST}/blog" for f in r["TITLE_TOO_LONG"])


def test_duplicate_meta_descriptions(findings):
    dup = by_rule(findings)["META_DESC_DUPLICATE"]
    urls = {f.url for f in dup}
    assert {f"{HOST}/products", f"{HOST}/blog"} <= urls
    assert all("shared by" in f.evidence for f in dup)
    assert {f"{HOST}/", f"{HOST}/contact"} <= urls  # GOOD_DESC reused on two pages


def test_duplicate_titles():
    from app.crawler import CrawledPage, CrawlOutcome
    from app.fetcher import FetchResult
    from app.parser import parse_html
    o = CrawlOutcome(start_url="https://a.com/")
    for path in ("/x", "/y"):
        u = "https://a.com" + path
        o.pages[u] = CrawledPage(u, 1, FetchResult(u, u, 200, content_type="text/html"),
                                 parse_html("<title>Same Title For Both Pages</title>", u))
    dup = by_rule(run_rules(o))["TITLE_DUPLICATE"]
    assert len(dup) == 2 and dup[0].related_urls


def test_heading_rules(findings):
    r = by_rule(findings)
    assert [f.url for f in r["H1_MISSING"]] == [f"{HOST}/about"]
    assert [f.url for f in r["H1_MULTIPLE"]] == [f"{HOST}/blog"]
    assert any("H2" in f.evidence and "H4" in f.evidence for f in r["HEADING_SKIP"])


def test_image_alt_only_flags_absent_alt(findings):
    alt = by_rule(findings)["IMG_ALT_MISSING"]
    assert len(alt) == 1 and alt[0].url == f"{HOST}/about"
    assert "1 of 2 images" in alt[0].evidence and "team.jpg" in alt[0].evidence


def test_broken_links_and_http_errors(findings):
    r = by_rule(findings)
    broken = {f.url: f for f in r["BROKEN_INTERNAL_LINK"]}
    assert f"{HOST}/missing" in broken and "HTTP 404" in broken[f"{HOST}/missing"].evidence
    assert set(broken[f"{HOST}/missing"].related_urls) == {f"{HOST}/", f"{HOST}/blog"}
    assert broken[f"{HOST}/error"].severity == Severity.critical
    assert "HTTP_5XX" not in r  # linked error pages are reported once, as broken links


async def test_links_beyond_page_limit_are_link_checked(crawl_fixture_site):
    o = await crawl_fixture_site(max_pages=1)
    assert f"{HOST}/missing" in o.link_checked and not o.link_checked[f"{HOST}/missing"].crawled
    assert f"{HOST}/admin/login" not in o.link_checked  # robots-blocked URLs are never requested
    broken = by_rule(run_rules(o))["BROKEN_INTERNAL_LINK"]
    assert {f.url for f in broken} == {f"{HOST}/missing", f"{HOST}/error"}


async def test_unlinked_start_page_error_reported_as_http_status():
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(503, headers={"content-type": "text/html"}, content=b"down")
    async with make_fetcher(httpx.MockTransport(h)) as f:
        o = await Crawler(f, CrawlConfig(5, 2, 2, 0, 10, 10)).run("https://flaky.example.com/")
    assert "HTTP_5XX" in by_rule(run_rules(o))


def test_redirect_rules(findings):
    r = by_rule(findings)
    chain = [f for f in r["REDIRECT_CHAIN"] if f.url == f"{HOST}/old-page"]
    assert chain and "2 redirects" in chain[0].evidence
    assert any(f.url == f"{HOST}/loop-a" for f in r["REDIRECT_LOOP"])
    assert any(f.url == f"{HOST}/old-page" for f in r["LINK_TO_REDIRECT"])


def test_indexability_security_mobile(findings):
    r = by_rule(findings)
    noindex = r["NOINDEX"][0]
    assert noindex.url == f"{HOST}/contact" and "X-Robots-Tag" in noindex.evidence
    assert noindex.finding_type == "recommendation"
    assert [f.url for f in r["MIXED_CONTENT"]] == [f"{HOST}/products"]
    assert [f.url for f in r["VIEWPORT_MISSING"]] == [f"{HOST}/contact"]
    assert [f.url for f in r["LANG_MISSING"]] == [f"{HOST}/contact"]
    assert any(f.url == f"{HOST}/about" for f in r["CANONICAL_MISSING"])
    assert "ROBOTS_BLOCKED" in r
    assert "SITEMAP_MISSING" not in r and "ROBOTS_TXT_MISSING" not in r


def test_redirect_source_not_double_counted(findings):
    # /old-page resolves to /about; on-page rules should only report /about once
    assert not [f for f in findings if f.rule_id == "H1_MISSING" and f.url.endswith("/old-page")]


def test_every_finding_traceable(findings):
    assert findings
    for f in findings:
        assert f.rule_id in RULES and f.evidence and f.url.startswith("https://")
        assert 0 < f.confidence <= 1 and f.suggestion


def test_good_homepage_has_no_onpage_defects(findings):
    home = [f for f in findings if f.url == f"{HOST}/" and f.rule_id.startswith(("TITLE", "H1", "CANONICAL", "IMG"))]
    assert home == []


async def test_missing_robots_and_sitemap():
    def h(req):
        if req.url.path == "/":
            return httpx.Response(200, headers={"content-type": "text/html"},
                                  content=b"<html lang='en'><head><title>A reasonable title</title></head><body><h1>x</h1></body></html>")
        return httpx.Response(404)
    async with make_fetcher(httpx.MockTransport(h)) as f:
        o = await Crawler(f, CrawlConfig(5, 2, 2, 0, 10, 10)).run("https://bare.example.com/")
    r = by_rule(run_rules(o))
    assert "ROBOTS_TXT_MISSING" in r and "SITEMAP_MISSING" in r


async def test_robots_disallow_all_gives_empty_crawl():
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<title>x</title>")
    async with make_fetcher(httpx.MockTransport(h)) as f:
        o = await Crawler(f, CrawlConfig(5, 2, 2, 0, 10, 10)).run("https://closed.example.com/")
    assert o.fatal_error and not o.pages


async def test_unreachable_start_url():
    def h(req):
        raise httpx.ConnectError("down", request=req)
    async with make_fetcher(httpx.MockTransport(h)) as f:
        o = await Crawler(f, CrawlConfig(5, 2, 2, 0, 10, 10)).run("https://down.example.com/")
    assert o.fatal_error and "robots.txt could not be fetched" in o.fatal_error


async def test_non_html_start_url():
    def h(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF")
    async with make_fetcher(httpx.MockTransport(h)) as f:
        o = await Crawler(f, CrawlConfig(5, 2, 2, 0, 10, 10)).run("https://pdf.example.com/")
    assert not [p for p in o.pages.values() if p.parsed]


def test_priority_formula():
    f = Finding(id="1", rule_id="X", title="t", category="c", severity=Severity.high, finding_type="defect",
                url="u", evidence="e", explanation="x", suggestion="s", effort="medium", confidence=0.5)
    assert finding_priority(f) == round(100 * 0.75 * 1.0 * 0.5 * 0.8, 1)


def test_scoring_and_action_plan(findings, outcome):
    scored = score_findings(findings)
    assert scored == sorted(scored, key=lambda f: -f.priority_score) or scored[0].priority_score >= scored[-1].priority_score
    plan = build_action_plan(scored)
    assert len(plan) == len({f.rule_id for f in scored})
    assert plan[0].priority_score >= plan[-1].priority_score
    assert all(0 <= p.priority_score <= 100 for p in plan)
    s = summarize(scored, 5, 2)
    assert s.total_issues == len(scored) and sum(s.by_severity.values()) == len(scored)
    assert 0 < s.health_score < 100


def test_health_score_bounds():
    assert summarize([], 10, 0).health_score == 100
    assert summarize([], 0, 0).health_score == 0
