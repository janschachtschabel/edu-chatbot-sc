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
import threading
import time
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


# ── Paket 4, C5: begrenzt holen (externes Audit F17b) ──────────────────────
#
# markitdown holte mit ``requests`` ohne Frist und las den ganzen Rumpf in den
# Speicher. Ein hängender Server hielt einen Thread unbegrenzt fest, eine große
# Antwort belegte RAM. ``hole_begrenzt`` holt über dieselbe SSRF-Sitzung, aber
# mit Frist und Bytedeckel.


class _Antwort:
    def __init__(self, stuecke, headers=None, pause=0.0):
        self.headers = headers or {}
        self._stuecke = stuecke
        self._pause = pause

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1):
        import time

        for stueck in self._stuecke:
            if self._pause:
                time.sleep(self._pause)
            yield stueck


class _Sitzung:
    def __init__(self, antwort):
        self.antwort = antwort
        self.aufrufe: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get(self, url, **kwargs):
        self.aufrufe.append((url, kwargs))
        return self.antwort


def _mit_sitzung(monkeypatch, antwort) -> _Sitzung:
    from boerdi.services import url_safety

    sitzung = _Sitzung(antwort)
    monkeypatch.setattr(url_safety, "make_ssrf_guarded_session", lambda: sitzung)
    return sitzung


def test_hole_begrenzt_holt_mit_frist_und_stream(monkeypatch):
    from boerdi.services.url_safety import hole_begrenzt

    sitzung = _mit_sitzung(monkeypatch, _Antwort([b"<h1>", b"Hallo</h1>"],
                                                 {"Content-Type": "text/html"}))
    roh, typ = hole_begrenzt("https://example.org/", max_bytes=1000, frist_s=5)
    assert (roh, typ) == (b"<h1>Hallo</h1>", "text/html")
    _url, kwargs = sitzung.aufrufe[0]
    assert kwargs["stream"] is True
    assert kwargs["timeout"] == (5, 30)


def test_ein_zu_grosser_header_bricht_vor_dem_lesen_ab(monkeypatch):
    from boerdi.services.url_safety import DownloadAbgebrochen, hole_begrenzt

    _mit_sitzung(monkeypatch, _Antwort([b"x"], {"Content-Length": "5000"}))
    with pytest.raises(DownloadAbgebrochen):
        hole_begrenzt("https://example.org/", max_bytes=1000, frist_s=5)


def test_ein_zu_grosser_rumpf_bricht_ab(monkeypatch):
    # Ohne Content-Length (oder mit falschem) zählt der Rumpf.
    from boerdi.services.url_safety import DownloadAbgebrochen, hole_begrenzt

    _mit_sitzung(monkeypatch, _Antwort([b"x" * 600, b"x" * 600]))
    with pytest.raises(DownloadAbgebrochen):
        hole_begrenzt("https://example.org/", max_bytes=1000, frist_s=5)


def test_ein_zu_langsamer_rumpf_bricht_ab(monkeypatch):
    # Die Lesefrist gilt je Lesevorgang; ein Server, der tröpfelt, unterliefe
    # sie. Die Gesamtfrist fängt ihn.
    from boerdi.services.url_safety import DownloadAbgebrochen, hole_begrenzt

    _mit_sitzung(monkeypatch, _Antwort([b"x"] * 10, pause=0.03))
    with pytest.raises(DownloadAbgebrochen):
        hole_begrenzt("https://example.org/", max_bytes=0, frist_s=0.05)


def test_null_bytes_heisst_ohne_deckel(monkeypatch):
    # ``BOERDI_MAX_INGEST_MB=0`` bedeutet beim Datei-Upload „ohne Grenze“.
    from boerdi.services.url_safety import hole_begrenzt

    _mit_sitzung(monkeypatch, _Antwort([b"x" * 5000]))
    roh, _typ = hole_begrenzt("https://example.org/", max_bytes=0, frist_s=5)
    assert len(roh) == 5000


def _tropfender_server(pause: float = 0.05, dauer: float = 3.0) -> str:
    """Ein echter lokaler HTTP-Server, der ein Byte je ``pause`` schickt."""
    lauscher = socket.socket()
    lauscher.bind(("127.0.0.1", 0))
    lauscher.listen(1)
    port = lauscher.getsockname()[1]

    def bedienen():
        verbindung, _ = lauscher.accept()
        try:
            verbindung.recv(65536)  # die Anfrage
            verbindung.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\n"
                               b"Connection: close\r\n\r\n")
            ende = time.monotonic() + dauer
            while time.monotonic() < ende:
                verbindung.sendall(b"x")
                time.sleep(pause)
        except OSError:
            pass  # der Abruf hat aufgelegt — genau das soll er
        finally:
            verbindung.close()
            lauscher.close()

    threading.Thread(target=bedienen, daemon=True).start()
    return f"http://127.0.0.1:{port}/"


def test_ein_tropfender_server_wird_zur_frist_abgeschnitten(monkeypatch):
    # Prüfer 2026-10-04: ``iter_content`` wartet auf volle 64 KB, und jeder
    # Empfang setzt die Lesefrist neu — die Gesamtfrist kam nie zum Zug. Echt
    # gegen einen Socket: die Attrappe oben liefert Ein-Byte-Stücke, die
    # ``requests`` so nie liefert.
    from boerdi.services import url_safety

    monkeypatch.setattr(url_safety, "assert_public_url", lambda _url: None)  # lokal erlaubt
    url = _tropfender_server()
    beginn = time.monotonic()
    with pytest.raises(url_safety.DownloadAbgebrochen):
        url_safety.hole_begrenzt(url, max_bytes=0, frist_s=0.3)
    assert time.monotonic() - beginn < 1.5
