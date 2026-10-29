"""A small in-memory website with deliberate SEO problems, served via httpx.MockTransport.

Used by automated tests and to generate the clearly labelled SYNTHETIC demo report.
Domain: shop.example.com (the resolver is stubbed to a public documentation-safe address).
"""
from __future__ import annotations

import ipaddress

import httpx

HOST = "https://shop.example.com"
PUBLIC_IP = ipaddress.ip_address("93.184.215.14")


def page(title: str | None = "Default Page Title For Testing", desc: str | None = None, body: str = "",
         canonical: str | None = None, lang: str | None = "en", viewport: bool = True, extra_head: str = "") -> str:
    head = []
    if title is not None:
        head.append(f"<title>{title}</title>")
    if desc is not None:
        head.append(f'<meta name="description" content="{desc}">')
    if canonical:
        head.append(f'<link rel="canonical" href="{canonical}">')
    if viewport:
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    head.append(extra_head)
    lang_attr = f' lang="{lang}"' if lang else ""
    return f"<!doctype html><html{lang_attr}><head>{''.join(head)}</head><body>{body}</body></html>"


FILLER = " ".join(["Quality handmade goods shipped worldwide with care."] * 40)
GOOD_DESC = "Handmade ceramics and homeware, designed in small batches and shipped worldwide from our studio."

PAGES: dict[str, tuple[int, dict, str]] = {
    "/robots.txt": (200, {"content-type": "text/plain"},
                    "User-agent: *\nDisallow: /admin\nSitemap: https://shop.example.com/sitemap.xml\n"),
    "/sitemap.xml": (200, {"content-type": "application/xml"},
                     '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                     "<url><loc>https://shop.example.com/</loc></url></urlset>"),
    "/": (200, {"content-type": "text/html; charset=utf-8"}, page(
        "Handmade Ceramics & Homeware | Example Shop", GOOD_DESC, canonical=f"{HOST}/",
        body=f"<h1>Handmade ceramics</h1><h2>New in</h2><p>{FILLER}</p>"
             '<a href="/about">About us</a> <a href="/products">Products</a> <a href="/blog">Blog</a>'
             '<a href="/contact">Contact</a> <a href="/old-page">Old offer</a> <a href="/missing">Gift cards</a>'
             '<a href="/admin/login">Admin</a> <a href="/error">Status</a> <a href="/loop-a">Loop</a>'
             '<a href="https://external.example.org/">Partner</a> <a href="mailto:hi@example.com">Mail</a>'
             '<img src="/img/hero.jpg" alt="Ceramic bowls on a shelf">')),
    "/about": (200, {"content-type": "text/html"}, page(
        "Shop", None, body='<h2>Our story</h2><p>Short text.</p><img src="/img/team.jpg"><img src="/img/kiln.jpg" alt="">'
                           '<a href="/">Home</a>')),
    "/products": (200, {"content-type": "text/html"}, page(
        "Products and Contact | Example Shop", "Browse our full range.", canonical=f"{HOST}/products",
        body=f'<h1>Products</h1><h2>Bowls</h2><h4>Large bowls</h4><p>{FILLER}</p>'
             '<img src="http://cdn.example.net/bowl.jpg" alt="Bowl"><a href="/blog">Blog</a>')),
    "/blog": (200, {"content-type": "text/html"}, page(
        "The Example Shop Journal: Stories, Studio Notes, Glazing Experiments and Behind-the-Scenes Updates",
        "Browse our full range.", canonical=f"{HOST}/blog",
        body=f"<h1>Journal</h1><h1>Latest posts</h1><p>{FILLER}</p><a href='/missing'>Gift cards</a>")),
    "/contact": (200, {"content-type": "text/html", "x-robots-tag": "noindex"}, page(
        None, GOOD_DESC, canonical=f"{HOST}/contact", lang=None, viewport=False,
        body="<h1>Contact</h1><p>Email us.</p>")),
    "/missing": (404, {"content-type": "text/html"}, page("Not found", None, body="<h1>Not found</h1>")),
    "/error": (500, {"content-type": "text/html"}, "<h1>Internal Server Error</h1>"),
    "/admin/login": (200, {"content-type": "text/html"}, page("Admin")),
}
REDIRECTS = {"/old-page": "/redirect-mid", "/redirect-mid": "/about", "/loop-a": "/loop-b", "/loop-b": "/loop-a"}


def handler(request: httpx.Request) -> httpx.Response:
    if request.url.host == "shop.example.com":
        path = request.url.path
        if path in REDIRECTS:
            return httpx.Response(301, headers={"location": REDIRECTS[path]})
        if path in PAGES:
            status, headers, body = PAGES[path]
            content = b"" if request.method == "HEAD" else body.encode()
            return httpx.Response(status, headers=headers, content=content)
        return httpx.Response(404, headers={"content-type": "text/html"}, content=b"<h1>404</h1>")
    return httpx.Response(404)


def transport() -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def public_resolver(host: str, port: int):
    return [PUBLIC_IP]
