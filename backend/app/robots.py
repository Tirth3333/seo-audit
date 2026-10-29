"""robots.txt handling following RFC 9309 semantics."""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from .fetcher import FetchResult, SafeFetcher

UA_TOKEN = "RankwiseSEOAuditBot"


@dataclass
class RobotsPolicy:
    robots_url: str
    status: int | None
    found: bool
    allow_all: bool = False
    disallow_all: bool = False
    reason: str = ""
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    _parser: RobotFileParser | None = None

    def can_fetch(self, url: str) -> bool:
        if self.disallow_all:
            return False
        if self.allow_all or self._parser is None:
            return True
        return self._parser.can_fetch(UA_TOKEN, url)


def robots_url_for(url: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, "/robots.txt", "", ""))


def policy_from_fetch(robots_url: str, res: FetchResult) -> RobotsPolicy:
    if res.error or res.status is None:
        # Unreachable robots.txt: RFC 9309 says assume complete disallow.
        return RobotsPolicy(robots_url, None, False, disallow_all=True,
                            reason=f"robots.txt could not be fetched ({res.error}); crawling is not allowed.")
    if res.status >= 500:
        return RobotsPolicy(robots_url, res.status, False, disallow_all=True,
                            reason=f"robots.txt returned HTTP {res.status} (server error); crawling is not allowed.")
    if 400 <= res.status < 500:
        return RobotsPolicy(robots_url, res.status, False, allow_all=True,
                            reason=f"robots.txt returned HTTP {res.status}; treated as no restrictions (RFC 9309).")
    if not (200 <= res.status < 300):
        return RobotsPolicy(robots_url, res.status, False, allow_all=True, reason="Unexpected status; no restrictions applied.")
    rp = RobotFileParser()
    rp.parse(res.text.splitlines())
    delay = rp.crawl_delay(UA_TOKEN)
    return RobotsPolicy(
        robots_url, res.status, True,
        sitemaps=list(rp.site_maps() or []),
        crawl_delay=float(delay) if delay is not None else None,
        _parser=rp,
    )


async def load_robots(fetcher: SafeFetcher, start_url: str) -> RobotsPolicy:
    url = robots_url_for(start_url)
    res = await fetcher.fetch(url)
    return policy_from_fetch(url, res)
