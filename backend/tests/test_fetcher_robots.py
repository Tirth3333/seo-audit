import ipaddress

import httpx

from app.fetcher import FetchResult
from app.robots import policy_from_fetch
from tests.conftest import make_fetcher


def mock(handler):
    return httpx.MockTransport(handler)


async def test_redirect_to_private_ip_is_blocked():
    def h(req):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.error_kind == "blocked" and r.status is None
    assert r.redirect_chain[0]["location"] == "http://127.0.0.1/admin"


async def test_redirect_to_metadata_hostname_is_blocked():
    def h(req):
        return httpx.Response(301, headers={"location": "http://169.254.169.254/latest/meta-data/"})
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.error_kind == "blocked"


async def test_redirect_to_hostname_resolving_private_is_blocked():
    async def resolver(host, port):
        return [ipaddress.ip_address("10.0.0.8" if host == "evil.example.com" else "93.184.215.14")]

    def h(req):
        return httpx.Response(302, headers={"location": "https://evil.example.com/"})
    async with make_fetcher(mock(h), resolver=resolver) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.error_kind == "blocked"


async def test_redirect_loop_detected():
    def h(req):
        return httpx.Response(301, headers={"location": "/b" if req.url.path == "/a" else "/a"})
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/a")
    assert r.error_kind == "redirect_loop"


async def test_too_many_redirects():
    def h(req):
        n = int(req.url.path.strip("/") or 0)
        return httpx.Response(301, headers={"location": f"/{n + 1}"})
    async with make_fetcher(mock(h), max_redirects=3) as f:
        r = await f.fetch("https://shop.example.com/0")
    assert r.error_kind == "too_many_redirects"
    assert len(r.redirect_chain) == 4


async def test_redirect_chain_recorded():
    def h(req):
        if req.url.path == "/a":
            return httpx.Response(301, headers={"location": "/b"})
        if req.url.path == "/b":
            return httpx.Response(302, headers={"location": "/c"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<p>ok</p>")
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/a")
    assert r.ok and r.final_url == "https://shop.example.com/c"
    assert [x["status"] for x in r.redirect_chain] == [301, 302]


async def test_timeout_is_reported():
    def h(req):
        raise httpx.ReadTimeout("slow", request=req)
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.error_kind == "timeout" and not r.ok


async def test_network_error_is_reported():
    def h(req):
        raise httpx.ConnectError("refused", request=req)
    async with make_fetcher(mock(h)) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.error_kind == "network"


async def test_unresolvable_host():
    async def resolver(host, port):
        from app.security import UnsafeURLError
        raise UnsafeURLError(f"Could not resolve hostname '{host}'.")
    async with make_fetcher(mock(lambda r: httpx.Response(200)), resolver=resolver) as f:
        r = await f.fetch("https://does-not-exist.example.com/")
    assert r.error_kind == "blocked" and "resolve" in r.error


async def test_response_size_limit_truncates():
    big = b"<html><body>" + b"a" * 50_000 + b"</body></html>"
    async with make_fetcher(mock(lambda r: httpx.Response(200, headers={"content-type": "text/html"}, content=big)),
                            max_bytes=1000) as f:
        r = await f.fetch("https://shop.example.com/")
    assert r.truncated and len(r.body) == 1000


def _res(status=None, text="", error=None):
    return FetchResult(requested_url="x", final_url="x", status=status, text=text, error=error)


def test_robots_404_allows_all():
    p = policy_from_fetch("https://a.com/robots.txt", _res(404))
    assert p.allow_all and p.can_fetch("https://a.com/anything") and not p.found


def test_robots_5xx_disallows_all():
    p = policy_from_fetch("https://a.com/robots.txt", _res(503))
    assert p.disallow_all and not p.can_fetch("https://a.com/")


def test_robots_unreachable_disallows_all():
    p = policy_from_fetch("https://a.com/robots.txt", _res(error="Request timed out."))
    assert not p.can_fetch("https://a.com/")


def test_robots_rules_and_sitemaps():
    txt = ("User-agent: *\nDisallow: /private\n\nUser-agent: RankwiseSEOAuditBot\nDisallow: /nobots\n"
           "Crawl-delay: 2\nSitemap: https://a.com/sm.xml\n")
    p = policy_from_fetch("https://a.com/robots.txt", _res(200, txt))
    assert p.found and p.sitemaps == ["https://a.com/sm.xml"]
    assert not p.can_fetch("https://a.com/nobots/x")
    assert p.can_fetch("https://a.com/private")  # our UA group overrides '*'
    assert p.crawl_delay == 2
