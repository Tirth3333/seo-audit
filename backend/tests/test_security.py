import ipaddress

import pytest

from app.security import (UnsafeURLError, check_url_allowed, is_ip_blocked, normalize_url, same_site,
                          validate_url_syntax)


@pytest.mark.parametrize("raw,expected", [
    ("example.com", "https://example.com/"),
    ("HTTPS://Example.COM/Path?q=1#frag", "https://example.com/Path?q=1"),
    ("http://example.com:80/a", "http://example.com/a"),
    ("https://example.com:8443/", "https://example.com:8443/"),
])
def test_valid_urls_are_normalised(raw, expected):
    assert validate_url_syntax(raw) == expected


@pytest.mark.parametrize("raw", [
    "", "   ", "ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "gopher://x.com",
    "https://user:pass@example.com", "https://example.com:22/", "http://intranet/", "https://",
    "https://exa mple.com", "x" * 3000,
])
def test_invalid_urls_rejected(raw):
    with pytest.raises(UnsafeURLError):
        validate_url_syntax(raw)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.1", "169.254.169.254",
                                "0.0.0.0", "::1", "fc00::1", "fe80::1", "::ffff:127.0.0.1", "100.64.0.1",
                                "100.100.100.200", "224.0.0.1"])
def test_private_and_reserved_ips_blocked(ip):
    assert is_ip_blocked(ipaddress.ip_address(ip))


def test_public_ip_allowed():
    assert not is_ip_blocked(ipaddress.ip_address("93.184.215.14"))


@pytest.mark.parametrize("url", ["http://localhost/", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data",
                                 "http://metadata.google.internal/", "http://[::1]/", "http://foo.localhost/",
                                 "http://2130706433/"])
async def test_check_url_allowed_blocks_internal(url):
    async def resolver(host, port):
        return [ipaddress.ip_address("127.0.0.1")]
    with pytest.raises(UnsafeURLError):
        await check_url_allowed(url, resolver=resolver)


async def test_dns_resolving_to_private_is_blocked():
    async def resolver(host, port):
        return [ipaddress.ip_address("93.184.215.14"), ipaddress.ip_address("10.1.2.3")]
    with pytest.raises(UnsafeURLError, match="private"):
        await check_url_allowed("https://rebind.example.com/", resolver=resolver)


async def test_public_dns_allowed():
    async def resolver(host, port):
        return [ipaddress.ip_address("93.184.215.14")]
    await check_url_allowed("https://www.example.com/", resolver=resolver)


async def test_allow_private_flag_for_local_dev():
    await check_url_allowed("http://localhost:8080/", allow_private=True)


def test_same_site_treats_www_as_equivalent():
    assert same_site("https://www.a.com/x", "https://a.com/")
    assert not same_site("https://blog.a.com/", "https://a.com/")


def test_normalize_drops_fragment_and_default_port():
    assert normalize_url("https://A.com:443#top") == "https://a.com/"
