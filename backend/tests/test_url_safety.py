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
    with pytest.raises(UnsafeUrlError) as fehler:
        assert_public_url("http://definitely-not-real.example/mcp")
    # Paket 9: der Grund reist mit — der Router bildet daraus den Satz in der
    # Sprache des Studios, statt den englischen Text einzusetzen.
    assert (fehler.value.grund, fehler.value.host) == ("unbekannt", "definitely-not-real.example")


def test_eine_interne_adresse_ist_nicht_erlaubt():
    with pytest.raises(UnsafeUrlError) as fehler:
        assert_public_url("http://127.0.0.1/mcp")
    assert fehler.value.grund == "nicht_erlaubt"


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


# ── Paket 4, C5 und Paket 6, B2: begrenzt holen (externes Audit F17b) ─────
#
# markitdown holte mit ``requests`` ohne Frist und las den ganzen Rumpf in den
# Speicher. Seit C5 holt ``hole_begrenzt`` mit Bytedeckel und Gesamtfrist; die
# Frist erreichte aber Kopfzeilen und Umleitungen nicht (``requests`` im Thread,
# es gab noch keine Antwort zum Abschalten). Seit B2 läuft der Abruf über
# ``httpx`` unter ``asyncio.timeout`` — die Frist gilt für alles. Die Tests laufen
# gegen echte Sockets: eine Attrappe sähe nicht, wann ``httpx`` wirklich wartet.


def _lokaler_server(antwort) -> tuple[str, list[bytes]]:
    """Ein echter Server auf 127.0.0.1 für EINE Verbindung.

    ``antwort(verbindung)`` schreibt die Antwort; die Anfrage landet in der Liste.
    """
    lauscher = socket.socket()
    lauscher.bind(("127.0.0.1", 0))
    lauscher.listen(1)
    port = lauscher.getsockname()[1]
    anfragen: list[bytes] = []

    def bedienen():
        verbindung, _ = lauscher.accept()
        try:
            anfragen.append(verbindung.recv(65536))
            antwort(verbindung)
        except OSError:
            pass  # der Abruf hat aufgelegt — oft genau das, was der Test will
        finally:
            verbindung.close()
            lauscher.close()

    threading.Thread(target=bedienen, daemon=True).start()
    return f"http://127.0.0.1:{port}/", anfragen


def _nur_der_testserver_ist_erlaubt(monkeypatch, url: str) -> None:
    """Den Testserver zulassen; jedes andere Ziel prüft der echte Wächter."""
    from boerdi.services import url_safety

    echt = url_safety.assert_public_url

    def pruefe(ziel: str) -> None:
        if not ziel.startswith(url):
            echt(ziel)

    monkeypatch.setattr(url_safety, "assert_public_url", pruefe)


def _tropfen(kopf: bytes, tropfen: bytes, pause: float = 0.05, dauer: float = 3.0):
    def antwort(verbindung):
        verbindung.sendall(kopf)
        ende = time.monotonic() + dauer
        while time.monotonic() < ende:
            verbindung.sendall(tropfen)
            time.sleep(pause)
    return antwort


def _holen(url: str, *, max_bytes: int = 0, frist_s: float = 5.0):
    import asyncio

    from boerdi.services.url_safety import hole_begrenzt

    return asyncio.run(hole_begrenzt(url, max_bytes=max_bytes, frist_s=frist_s))


_CRLF = b"\r\n"


def _kopf(*zeilen: bytes) -> bytes:
    return _CRLF.join(zeilen) + _CRLF + _CRLF


def test_hole_begrenzt_holt_rumpf_und_typ(monkeypatch):
    rumpf = b"<h1>Hallo</h1>"
    url, anfragen = _lokaler_server(lambda v: v.sendall(_kopf(
        b"HTTP/1.1 200 OK", b"Content-Type: text/html; charset=utf-8",
        b"Content-Length: " + str(len(rumpf)).encode()) + rumpf))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    roh, typ = _holen(url, max_bytes=1000)
    assert (roh, typ) == (rumpf, "text/html; charset=utf-8")
    # Markdown-Vorliebe wie markitdowns eigene Sitzung.
    assert b"text/markdown" in anfragen[0]


def test_ein_zu_grosser_header_bricht_vor_dem_lesen_ab(monkeypatch):
    from boerdi.services.url_safety import DownloadAbgebrochen

    url, _ = _lokaler_server(lambda v: v.sendall(
        _kopf(b"HTTP/1.1 200 OK", b"Content-Length: 5000") + b"x" * 10))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    with pytest.raises(DownloadAbgebrochen) as err:
        _holen(url, max_bytes=1000)
    assert err.value.grund == "zu_gross"


def test_ein_zu_grosser_rumpf_bricht_ab(monkeypatch):
    # Ohne Content-Length zählt der Rumpf.
    from boerdi.services.url_safety import DownloadAbgebrochen

    url, _ = _lokaler_server(lambda v: v.sendall(
        _kopf(b"HTTP/1.1 200 OK", b"Connection: close") + b"x" * 1200))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    with pytest.raises(DownloadAbgebrochen) as err:
        _holen(url, max_bytes=1000)
    assert err.value.grund == "zu_gross"


def test_null_bytes_heisst_ohne_deckel(monkeypatch):
    # ``BOERDI_MAX_INGEST_MB=0`` bedeutet beim Datei-Upload „ohne Grenze“.
    url, _ = _lokaler_server(lambda v: v.sendall(
        _kopf(b"HTTP/1.1 200 OK", b"Content-Length: 5000") + b"x" * 5000))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    roh, _typ = _holen(url, max_bytes=0)
    assert len(roh) == 5000


def test_ein_tropfender_rumpf_wird_zur_frist_abgeschnitten(monkeypatch):
    # Prüfer 2026-10-04: jeder Empfang setzte die Lesefrist neu.
    from boerdi.services.url_safety import DownloadAbgebrochen

    url, _ = _lokaler_server(_tropfen(_kopf(
        b"HTTP/1.1 200 OK", b"Content-Type: text/plain", b"Connection: close"), b"x"))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    beginn = time.monotonic()
    with pytest.raises(DownloadAbgebrochen) as err:
        _holen(url, frist_s=0.3)
    assert err.value.grund == "zu_langsam"
    assert time.monotonic() - beginn < 1.5


def test_tropfende_kopfzeilen_werden_zur_frist_abgeschnitten(monkeypatch):
    # Paket 6, B2: Vorher erreichte die Gesamtfrist nur den Rumpf. Ein Server,
    # der die Kopfzeilen tröpfelt, hielt den Abruf, solange er wollte.
    from boerdi.services.url_safety import DownloadAbgebrochen

    url, _ = _lokaler_server(_tropfen(b"HTTP/1.1 200 OK" + _CRLF + b"X-Lang: ", b"a"))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    beginn = time.monotonic()
    with pytest.raises(DownloadAbgebrochen) as err:
        _holen(url, frist_s=0.3)
    assert err.value.grund == "zu_langsam"
    assert time.monotonic() - beginn < 1.5


def test_eine_umleitung_auf_eine_interne_adresse_wird_abgewiesen(monkeypatch):
    # N-2 auf dem neuen Weg: Jeder Schritt einer Umleitung geht durch den Wächter.
    url, _ = _lokaler_server(lambda v: v.sendall(_kopf(
        b"HTTP/1.1 302 Found", b"Location: http://169.254.169.254/latest",
        b"Content-Length: 0")))
    _nur_der_testserver_ist_erlaubt(monkeypatch, url)
    with pytest.raises(UnsafeUrlError):
        _holen(url)


def test_der_rumpf_einer_umleitung_wird_nicht_gelesen(monkeypatch):
    # Review Paket 6: ``httpx`` las bei ``follow_redirects`` jeden 3xx-Rumpf ganz
    # (``aread``), am Deckel vorbei — ein feindlicher Server konnte so den
    # Speicher füllen. Jetzt folgt der Abruf selbst und schließt jeden Schritt
    # ungelesen; hier tröpfelt der Rumpf der Umleitung länger als die Frist.
    from boerdi.services import url_safety

    ziel, _ = _lokaler_server(lambda v: v.sendall(_kopf(
        b"HTTP/1.1 200 OK", b"Content-Type: text/html", b"Content-Length: 5") + b"hallo"))
    umleitung, _ = _lokaler_server(_tropfen(_kopf(
        b"HTTP/1.1 302 Found", b"Location: " + ziel.encode(), b"Content-Length: 100000000"),
        b"x" * 1024))
    echt = url_safety.assert_public_url
    monkeypatch.setattr(url_safety, "assert_public_url",
                        lambda u: None if u.startswith((ziel, umleitung)) else echt(u))
    beginn = time.monotonic()
    rumpf, typ = _holen(umleitung, max_bytes=1024 * 1024, frist_s=2.0)
    assert (rumpf, typ) == (b"hallo", "text/html")
    assert time.monotonic() - beginn < 1.5


def test_der_abruf_schreibt_keine_adressen_ins_info_log():
    # ``httpx`` meldet jede Anfrage auf INFO mit voller Adresse samt Abfrage —
    # Import-Adressen und ihre Umleitungen standen damit im Log (Review Paket 6).
    import logging

    from boerdi.main import _configure_logging
    from boerdi.settings import Settings

    # LiteLLM setzt die Stufe beim Import schon (``litellm/_logging.py``); geprüft
    # wird hier die eigene Einstellung, die nicht an dieser Nebenwirkung hängt.
    logger = logging.getLogger("httpx")
    vorher = logger.level
    logger.setLevel(logging.NOTSET)
    try:
        _configure_logging(Settings(_env_file=None))
        assert logger.level >= logging.WARNING
    finally:
        logger.setLevel(vorher)



def test_folgeabrufe_von_markitdown_haben_eine_frist(monkeypatch):
    """Befundliste §1.4 (Paket 11): markitdown holt beim Umwandeln weitere Adressen über diese
    Sitzung — ohne Frist hielt ein hängender Abruf die ganze Umwandlung bis zur Gesamtfrist des
    Kindprozesses auf. Jetzt hat jeder Abruf eine eigene."""
    import requests
    from requests.adapters import HTTPAdapter

    from boerdi.services import url_safety

    gesehen: dict = {}

    def senden(self, request, **kwargs):
        gesehen.update(kwargs)
        antwort = requests.Response()
        antwort.status_code = 200
        antwort._content = b"ok"
        antwort.url = request.url
        return antwort

    monkeypatch.setattr(url_safety, "assert_public_url", lambda _url: None)
    monkeypatch.setattr(HTTPAdapter, "send", senden)
    make_ssrf_guarded_session().get("https://example.org/bild.png")
    assert gesehen.get("timeout") == url_safety.FOLGEABRUF_FRIST
    make_ssrf_guarded_session().get("https://example.org/x", timeout=3)
    assert gesehen.get("timeout") == 3, "eine ausdrückliche Frist bleibt"
