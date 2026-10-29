"""Extract SEO-relevant facts from (untrusted) HTML. No JavaScript is executed."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .security import normalize_url

WS = re.compile(r"\s+")


def clean(text: str | None, limit: int = 500) -> str:
    if text is None:
        return ""
    t = WS.sub(" ", text).strip()
    return t[:limit]


@dataclass
class ParsedPage:
    title: str | None = None  # None = no <title> tag; "" = empty tag
    title_count: int = 0
    meta_description: str | None = None
    meta_description_count: int = 0
    meta_robots: str | None = None
    canonicals: list[str] = field(default_factory=list)
    lang: str | None = None
    has_viewport: bool = False
    headings: list[tuple[int, str]] = field(default_factory=list)  # (level, text) in document order
    images: list[dict] = field(default_factory=list)  # {src, alt (None if absent)}
    links: list[dict] = field(default_factory=list)  # {href (absolute, normalised), text, nofollow}
    insecure_resources: list[str] = field(default_factory=list)
    word_count: int = 0

    @property
    def h1s(self) -> list[str]:
        return [t for lvl, t in self.headings if lvl == 1]


def parse_html(html: str, base_url: str) -> ParsedPage:
    soup = BeautifulSoup(html, "lxml")
    page = ParsedPage()

    base_tag = soup.find("base", href=True)
    base = urljoin(base_url, base_tag["href"]) if base_tag else base_url

    titles = soup.find_all("title")
    # Ignore <title> inside inline SVG
    titles = [t for t in titles if not t.find_parent("svg")]
    page.title_count = len(titles)
    if titles:
        page.title = clean(titles[0].get_text(), 1000)

    descs = soup.find_all("meta", attrs={"name": re.compile(r"^description$", re.I)})
    page.meta_description_count = len(descs)
    if descs:
        page.meta_description = clean(descs[0].get("content", ""), 1000)

    robots = soup.find_all("meta", attrs={"name": re.compile(r"^(robots|googlebot)$", re.I)})
    if robots:
        page.meta_robots = ", ".join(clean(r.get("content", ""), 200) for r in robots)

    for link in soup.find_all("link", href=True):
        rel = [r.lower() for r in (link.get("rel") or [])]
        if "canonical" in rel:
            page.canonicals.append(normalize_url(urljoin(base, link["href"].strip())))

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        page.lang = clean(html_tag.get("lang"), 40)
    page.has_viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)}) is not None

    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        page.headings.append((int(h.name[1]), clean(h.get_text(" "), 200)))

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        page.images.append({
            "src": urljoin(base, src.strip()) if src else "",
            "alt": img.get("alt"),  # None means the attribute is absent
        })

    is_https = urlsplit(base_url).scheme == "https"
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:", "data:")):
            continue
        absolute = urljoin(base, href)
        if urlsplit(absolute).scheme not in ("http", "https"):
            continue
        rel = [r.lower() for r in (a.get("rel") or [])]
        page.links.append({
            "href": normalize_url(absolute),
            "text": clean(a.get_text(" "), 120),
            "nofollow": "nofollow" in rel,
        })

    if is_https:
        for tag, attr in (("img", "src"), ("script", "src"), ("link", "href"), ("iframe", "src")):
            for el in soup.find_all(tag, attrs={attr: True}):
                if tag == "link" and not set(r.lower() for r in el.get("rel") or []) & {"stylesheet", "icon"}:
                    continue
                val = el[attr].strip()
                if val.lower().startswith("http://"):
                    page.insecure_resources.append(val[:300])

    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    body = soup.body or soup
    page.word_count = len(body.get_text(" ").split())
    return page
