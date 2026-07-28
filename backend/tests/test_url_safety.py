"""T8 (Audit 2026-07-05): ``assert_public_url`` blockt SSRF-Ziele (private/interne
Hosts, Loopback, Cloud-Metadaten 169.254.169.254), bevor eine URL registriert oder
abgefragt wird.

Numerische IP-Literale lässt ``socket.getaddrinfo`` ohne echtes DNS auflösen — die
Tests sind damit offline und deterministisch. Der einzige DNS-Pfad (nicht auflösbarer
Name) wird gemockt (externe Grenze).

NEU-Ergänzung ggü. ALT: Pins für ``make_ssrf_guarded_session`` (Redirect-Guard N-2)
— der Adapter raist VOR ``super().send``, der Block-Pfad ist also netz-frei testbar.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from boerdi.services.url_safety import (
    UnsafeUrlError,
    assert_public_url,
    make_ssrf_guarded_session,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/mcp",
        "http://127.0.0.1/mcp",
        "http://0.0.0.0/mcp",
        "http://[::1]/mcp",
        "http://foo.local/mcp",
        "http://10.0.0.1/mcp",          # private /8
        "http://192.168.1.1/mcp",       # private /16
        "http://172.16.5.4/mcp",        # private /12
        "http://169.254.169.254/meta",  # link-local (cloud metadata)
    ],
)
def test_blocks_internal_targets(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(url)


@pytest.mark.parametrize("url", ["", "not-a-url", "http://", "///path"])
def test_blocks_missing_host(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(url)


@pytest.mark.parametrize("url", ["http://8.8.8.8/mcp", "https://93.184.216.34/mcp"])
def test_allows_public_numeric_ip(url):
    # Öffentliche numerische IP → kein DNS, keine private Range → darf durch.
    assert assert_public_url(url) is None


def test_unresolvable_hostname_is_blocked(monkeypatch):
    def _boom(*_a, **_k):
        raise socket.gaierror("name resolution failed")

    monkeypatch.setattr(socket, "getaddrinfo", _boom)
    with pytest.raises(UnsafeUrlError):
        assert_public_url("http://definitely-not-real.example/mcp")


# ── T9: Schema-Allowlist (nur http/https) ──────────────────────────────────
@pytest.mark.parametrize(
    "url",
    ["ftp://8.8.8.8/x", "file://8.8.8.8/etc/passwd", "gopher://8.8.8.8:70/"],
)
def test_blocks_non_http_schemes(url):
    with pytest.raises(UnsafeUrlError):
        assert_public_url(url)


# ── N-2: Redirect-Guard-Session (in ALT ungetestet) ───────────────────────
def test_guard_adapter_blocks_internal_hop_before_network():
    import requests

    session = make_ssrf_guarded_session()
    adapter = session.get_adapter("http://example.org/")
    # Der Guard prüft request.url VOR super().send → kein Netz nötig; ein
    # 302-Ziel auf Cloud-Metadaten muss als InvalidURL abbrechen.
    with pytest.raises(requests.exceptions.InvalidURL):
        adapter.send(SimpleNamespace(url="http://169.254.169.254/meta"))


def test_guard_session_mounts_and_markdown_accept_header():
    session = make_ssrf_guarded_session()
    http = session.get_adapter("http://example.org/")
    https = session.get_adapter("https://example.org/")
    assert type(http).__name__ == "_SsrfGuardAdapter" and http is https is not None
    assert session.headers["Accept"].startswith("text/markdown")
