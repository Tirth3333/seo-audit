"""Safe HTTP fetching: manual redirects with per-hop SSRF validation, size and time limits."""
from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin

import httpx

from .security import UnsafeURLError, check_url_allowed, is_ip_blocked, normalize_url


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    content_type: str = ""
    body: bytes = b""
    text: str = ""
    redirect_chain: list[dict] = field(default_factory=list)  # [{url, status, location}]
    error: str | None = None
    error_kind: str | None = None  # timeout | network | blocked | too_large | redirect_loop | too_many_redirects
    elapsed_ms: int = 0
    truncated: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None and self.status is not None and 200 <= self.status < 300

    @property
    def is_html(self) -> bool:
        ct = self.content_type.lower()
        return "text/html" in ct or "application/xhtml" in ct


class SafeFetcher:
    def __init__(
        self,
        *,
        user_agent: str,
        timeout_s: float = 10.0,
        max_bytes: int = 3_000_000,
        max_redirects: int = 5,
        allow_private: bool = False,
        use_env_proxy: bool = False,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver=None,
    ) -> None:
        self.max_bytes = max_bytes
        self.max_redirects = max_redirects
        self.allow_private = allow_private
        self.resolver = resolver
        # The peer-IP check only makes sense when we connect directly (no proxy, real network).
        self.check_peer = not use_env_proxy and not allow_private and transport is None
        self.client = httpx.AsyncClient(
            follow_redirects=False,
            timeout=httpx.Timeout(timeout_s),
            headers={"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"},
            trust_env=use_env_proxy,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.aclose()

    def _peer_blocked(self, response: httpx.Response) -> bool:
        stream = response.extensions.get("network_stream")
        if stream is None:
            return False
        try:
            addr = stream.get_extra_info("server_addr")
        except Exception:  # pragma: no cover - transport specific
            return False
        if not addr:
            return False
        try:
            return is_ip_blocked(ipaddress.ip_address(addr[0]))
        except ValueError:
            return False

    async def fetch(self, url: str, *, method: str = "GET", read_body: bool = True) -> FetchResult:
        start = time.monotonic()
        current = normalize_url(url)
        result = FetchResult(requested_url=current, final_url=current)
        seen: set[str] = set()
        try:
            for _hop in range(self.max_redirects + 1):
                if current in seen:
                    result.error, result.error_kind = "Redirect loop detected.", "redirect_loop"
                    return result
                seen.add(current)
                await check_url_allowed(current, allow_private=self.allow_private, resolver=self.resolver)
                req = self.client.build_request(method, current)
                resp = await self.client.send(req, stream=True)
                try:
                    if self.check_peer and self._peer_blocked(resp):
                        raise UnsafeURLError("Connected peer address is private/reserved; request blocked.")
                    if resp.is_redirect and "location" in resp.headers:
                        location = resp.headers["location"]
                        nxt = normalize_url(urljoin(current, location))
                        result.redirect_chain.append({"url": current, "status": resp.status_code, "location": nxt})
                        current = nxt
                        continue
                    result.final_url = current
                    result.status = resp.status_code
                    result.headers = {k.lower(): v for k, v in resp.headers.items()}
                    result.content_type = resp.headers.get("content-type", "")
                    if read_body and method != "HEAD":
                        buf = bytearray()
                        async for chunk in resp.aiter_bytes():
                            buf.extend(chunk)
                            if len(buf) > self.max_bytes:
                                result.truncated = True
                                del buf[self.max_bytes:]
                                break
                        result.body = bytes(buf)
                        if result.is_html or "text/" in result.content_type or "xml" in result.content_type:
                            result.text = result.body.decode(resp.encoding or "utf-8", errors="replace")
                    return result
                finally:
                    await resp.aclose()
            result.error = f"Too many redirects (more than {self.max_redirects})."
            result.error_kind = "too_many_redirects"
            result.final_url = current
            return result
        except UnsafeURLError as exc:
            result.error, result.error_kind = str(exc), "blocked"
        except httpx.TimeoutException:
            result.error, result.error_kind = "Request timed out.", "timeout"
        except httpx.HTTPError as exc:
            result.error, result.error_kind = f"Network error: {type(exc).__name__}", "network"
        finally:
            result.elapsed_ms = int((time.monotonic() - start) * 1000)
        return result
