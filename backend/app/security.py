"""URL validation and SSRF protection.

Every URL the crawler requests (including each redirect hop) goes through
``check_url_allowed``: scheme must be http/https, no embedded credentials, and
every IP the hostname resolves to must be a public, globally routable address.
"""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urldefrag, urlsplit, urlunsplit

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
    "instance-data.ec2.internal",
}
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".intranet", ".lan", ".home.arpa")
# Explicit cloud metadata addresses (also covered by link-local checks, listed for clarity)
METADATA_IPS = {ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("fd00:ec2::254"),
                ipaddress.ip_address("100.100.100.200")}


class UnsafeURLError(ValueError):
    """Raised when a URL is invalid or points at a forbidden destination."""


def validate_url_syntax(raw: str) -> str:
    """Validate and normalise user input. Returns a normalised absolute URL."""
    if not isinstance(raw, str) or not raw.strip():
        raise UnsafeURLError("Please enter a website URL.")
    raw = raw.strip()
    if len(raw) > 2048:
        raise UnsafeURLError("URL is too long.")
    if "://" not in raw:
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise UnsafeURLError(f"Invalid URL: {exc}") from exc
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http:// and https:// URLs are allowed.")
    if parts.username or parts.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed.")
    host = (parts.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURLError("URL must include a hostname.")
    try:
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("Invalid port in URL.") from exc
    if port is not None and port not in (80, 443, 8080, 8443):
        raise UnsafeURLError("Only standard web ports (80, 443, 8080, 8443) are allowed.")
    if any(c in host for c in " <>\"'\\"):
        raise UnsafeURLError("Hostname contains invalid characters.")
    # Literal IPs are checked here; names are checked after DNS resolution.
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        if "." not in host:
            raise UnsafeURLError("Hostname must be a fully qualified domain name.")
    return normalize_url(raw)


def normalize_url(url: str) -> str:
    """Lower-case scheme/host, drop fragment and default port, keep path & query."""
    url, _ = urldefrag(url)
    p = urlsplit(url)
    scheme = p.scheme.lower()
    host = (p.hostname or "").rstrip(".").lower()
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = p.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = p.path or "/"
    return urlunsplit((scheme, netloc, path, p.query, ""))


def is_ip_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if ip in METADATA_IPS:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def check_hostname_name(host: str) -> None:
    host = host.rstrip(".").lower().strip("[]")
    if host in BLOCKED_HOSTNAMES or host.endswith(BLOCKED_SUFFIXES):
        raise UnsafeURLError(f"Destination '{host}' is an internal hostname and is blocked.")


async def resolve_host(host: str, port: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=5
        )
    except (socket.gaierror, asyncio.TimeoutError) as exc:
        raise UnsafeURLError(f"Could not resolve hostname '{host}'.") from exc
    return [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]


async def check_url_allowed(url: str, *, allow_private: bool = False, resolver=None) -> None:
    """Raise UnsafeURLError unless ``url`` is safe to request.

    ``resolver`` can be injected in tests: async (host, port) -> list[ip].
    """
    p = urlsplit(url)
    if p.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Only http:// and https:// URLs are allowed.")
    if p.username or p.password:
        raise UnsafeURLError("URLs with embedded credentials are not allowed.")
    host = (p.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsafeURLError("URL must include a hostname.")
    if allow_private:
        return
    check_hostname_name(host)
    port = p.port or (443 if p.scheme.lower() == "https" else 80)
    try:
        ips = [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        ips = await (resolver or resolve_host)(host, port)
    if not ips:
        raise UnsafeURLError(f"Hostname '{host}' did not resolve.")
    for ip in ips:
        if is_ip_blocked(ip):
            raise UnsafeURLError(
                f"Destination '{host}' resolves to a private or reserved address ({ip}) and is blocked."
            )


def registrable_host(url: str) -> str:
    """Host used for same-site scoping. 'www.' is treated as equivalent to the apex."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def same_site(url: str, root_url: str) -> bool:
    return registrable_host(url) == registrable_host(root_url)
