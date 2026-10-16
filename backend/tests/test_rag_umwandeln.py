"""Behavior pins for services/rag/umwandeln — file/URL→markdown conversion
(ALT-verbatim). Aus ``test_rag_ingest.py`` herausgelöst, als die Umwandler in ein
eigenes Modul zogen (Paket 6). Boundaries faked: markitdown (parser/fetcher) and
the bounded download; the url_safety guard runs real — numerische IPs braucht
kein echtes DNS, die URL-Tests sind damit offline und deterministisch.
"""

from __future__ import annotations

import asyncio

import pytest

import boerdi.services.rag.umwandeln as ri


async def _lokal(funktion, *args):
    """Die Umwandlung im Testprozess — dort wirken die Attrappen. Den Kindprozess
    selbst (Frist, Vorprüfung, einer zugleich) prüft ``test_rag_umwandeln_kind``."""
    return funktion(*args)


def _wandle(pfad):
    return ri.convert_to_markdown(pfad, ausfuehren=_lokal)


def _wandle_url(url):
    return ri.convert_url_to_markdown(url, ausfuehren=_lokal)


# ── convert_to_markdown (verbatim ALT) ───────────────────────────────────
class _FakeMid:
    def __init__(self, text="# MD", raise_exc=None):
        self.text, self.raise_exc = text, raise_exc

    def convert(self, path):
        if self.raise_exc:
            raise self.raise_exc
        from types import SimpleNamespace
        return SimpleNamespace(text_content=self.text)


def test_convert_returns_text_content(monkeypatch, tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("hallo", encoding="utf-8")
    monkeypatch.setattr("markitdown.MarkItDown", lambda: _FakeMid("# Ergebnis"))
    assert asyncio.run(_wandle(str(f))) == "# Ergebnis"


def test_ein_dokument_das_mit_fehler_beginnt_ist_kein_umwandlungsfehler(monkeypatch, tmp_path):
    """Paket 4b, A3: Der Router erkennt Fehler am Typ, nicht am Präfix."""
    f = tmp_path / "doc.txt"
    f.write_text("x", encoding="utf-8")
    monkeypatch.setattr("markitdown.MarkItDown", lambda: _FakeMid("Fehlerkultur im Unterricht"))
    out = asyncio.run(_wandle(str(f)))
    assert out == "Fehlerkultur im Unterricht"
    assert not isinstance(out, ri.Umwandlungsfehler)


def test_convert_error_becomes_fehler_string_not_raise(monkeypatch):
    monkeypatch.setattr(
        "markitdown.MarkItDown", lambda: _FakeMid(raise_exc=RuntimeError("kaputt")))
    out = asyncio.run(_wandle("fehlt.pdf"))
    assert out == "Fehler beim Konvertieren: RuntimeError: kaputt"
    assert (out.art, out.detail) == ("datei", "RuntimeError: kaputt")
    assert isinstance(out, ri.Umwandlungsfehler)  # der Router prüft den Typ (4b, A3)


def test_ein_fehlendes_markitdown_ist_ein_umwandlungsfehler(monkeypatch):
    """Fehlt markitdown im Image, darf der Fehlertext nicht als Dokument
    gespeichert werden (Review 4b: dieser Weg war ohne Test)."""
    import sys

    monkeypatch.setitem(sys.modules, "markitdown", None)  # Import scheitert
    out = asyncio.run(_wandle("a.txt"))
    assert out.startswith("Fehler beim Konvertieren (ImportError): ")
    assert out.art == "server"  # ein Paket fehlt im Image: Fehler des Servers (B6)
    assert isinstance(out, ri.Umwandlungsfehler)


def _gescheitert_an(ausnahme: Exception):
    """markitdowns Form: der Wandler scheiterte, die Ursache steht im Versuch."""
    import sys

    from markitdown._exceptions import FailedConversionAttempt, FileConversionException

    try:
        raise ausnahme
    except type(ausnahme):
        info = sys.exc_info()
    return FileConversionException(
        attempts=[FailedConversionAttempt(converter=object(), exc_info=info)])


@pytest.mark.parametrize("ursache", ["fehlende Abhängigkeit", "unbekanntes Format"])
def test_ein_nicht_lesbares_format_wird_als_solches_gemeldet(monkeypatch, ursache):
    """Paket 4, C5 (externes Audit F17a): Das Image enthält keine
    markitdown-Extras; DOCX, PDF, PPTX und XLSX scheitern mit
    ``MissingDependencyException``. Das ist keine kaputte Datei, sondern ein
    Format, das dieser Server nicht liest — der Router macht daraus 415."""
    from markitdown._exceptions import (
        MissingDependencyException,
        UnsupportedFormatException,
    )

    fehler = (_gescheitert_an(MissingDependencyException("docx fehlt"))
              if ursache == "fehlende Abhängigkeit"
              else UnsupportedFormatException("kein Wandler"))
    monkeypatch.setattr("markitdown.MarkItDown", lambda: _FakeMid(raise_exc=fehler))
    out = asyncio.run(_wandle("a.docx"))
    assert out.startswith(ri.FORMAT_NICHT_LESBAR)
    assert out.art == "format"
    assert isinstance(out, ri.Umwandlungsfehler)


# ── convert_url_to_markdown (SSRF-Guard via url_safety) ──────────────────
#
# Seit Paket 4 (C5) holt nicht mehr markitdown selbst, sondern
# ``url_safety.hole_begrenzt`` (Frist, Bytedeckel, dieselbe SSRF-Sitzung);
# markitdown wandelt nur noch den Rumpf (``convert_stream``). Die Attrappen
# sitzen deshalb an beiden Grenzen.
class _FakeUrlMid:
    def __init__(self, requests_session, text, raise_exc):
        self.requests_session = requests_session
        self.text, self.raise_exc = text, raise_exc
        self.gesehen: list[tuple[bytes, object]] = []

    def convert_stream(self, stream, *, stream_info=None):
        self.gesehen.append((stream.read(), stream_info))
        if self.raise_exc:
            raise self.raise_exc
        from types import SimpleNamespace
        return SimpleNamespace(text_content=self.text)


def _wire_url_markitdown(monkeypatch, text="# Seite", raise_exc=None,
                         rumpf=b"<h1>Seite</h1>", typ="text/html; charset=utf-8",
                         abruf_fehler=None):
    """Patch both boundaries — the bounded fetch and markitdown; return the list
    of constructed fakes (empty = never constructed = nothing was converted)."""
    from boerdi.services import url_safety

    built: list[_FakeUrlMid] = []

    def _factory(requests_session=None):
        built.append(_FakeUrlMid(requests_session, text, raise_exc))
        return built[-1]

    async def _abruf(url, *, max_bytes, frist_s):
        if abruf_fehler is not None:
            raise abruf_fehler
        return rumpf, typ

    monkeypatch.setattr("markitdown.MarkItDown", _factory)
    monkeypatch.setattr(url_safety, "hole_begrenzt", _abruf)
    return built


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",         # Loopback
        "http://localhost/x",         # interner Name
        "http://169.254.169.254/l",   # Cloud-Metadaten (link-local)
        "ftp://8.8.8.8/x",            # Nicht-http(s)-Schema
        "http://",                    # fehlender Host
    ],
)
def test_convert_url_guard_blocks_internal_and_bad_scheme(url):
    out = asyncio.run(_wandle_url(url))
    assert out.startswith("Fehler")
    assert isinstance(out, ri.Umwandlungsfehler)


def test_convert_url_guard_returns_before_any_fetch(monkeypatch):
    built = _wire_url_markitdown(monkeypatch)
    out = asyncio.run(_wandle_url("http://169.254.169.254/latest"))
    # Die exakte Meldung (statt nur des "Fehler"-Präfixes) beweist den frühen
    # Return: der markitdown-Pfad liefert "Fehler beim Konvertieren: …".
    assert out == "Fehler: Internal network URLs not allowed"
    assert isinstance(out, ri.Umwandlungsfehler)
    # Paket 9: kein englischer Grund mehr im Satz — die Art sagt alles.
    assert (out.art, out.detail) == ("adresse", "")
    assert built == []  # markitdown nie konstruiert → kein Netz-Fetch versucht


def test_ein_unbekannter_name_ist_ein_eigener_adressfehler(monkeypatch):
    # Paket 9: ein Tippfehler im Namen ist nicht „nicht erlaubt“.
    from boerdi.services import url_safety

    def _unbekannt(url):
        raise url_safety.UnsafeUrlError("Cannot resolve hostname: wlo.exmaple",
                                        grund="unbekannt", host="wlo.exmaple")

    monkeypatch.setattr(url_safety, "assert_public_url", _unbekannt)
    _wire_url_markitdown(monkeypatch)
    out = asyncio.run(_wandle_url("https://wlo.exmaple/seite"))
    assert isinstance(out, ri.Umwandlungsfehler)
    assert (out.art, out.detail) == ("adresse_unbekannt", "wlo.exmaple")


def test_convert_url_returns_text_content_via_guarded_session(monkeypatch):
    built = _wire_url_markitdown(monkeypatch, text="# Wikipedia")
    out = asyncio.run(_wandle_url("http://8.8.8.8/seite"))
    assert out == "# Wikipedia"
    # N-2: die Guard-Session MUSS durchgereicht werden — markitdown holt bei
    # manchen Formaten selbst nach, und einem 302 auf ein internes Ziel folgte
    # es sonst ungeprüft.
    adapter = built[0].requests_session.get_adapter("http://8.8.8.8/")
    assert type(adapter).__name__ == "_SsrfGuardAdapter"
    rumpf, info = built[0].gesehen[0]
    assert rumpf == b"<h1>Seite</h1>"
    assert (info.url, info.mimetype, info.charset) == (
        "http://8.8.8.8/seite", "text/html", "utf-8")


def test_convert_url_error_becomes_fehler_string_not_raise(monkeypatch):
    _wire_url_markitdown(monkeypatch, raise_exc=RuntimeError("timeout"))
    out = asyncio.run(_wandle_url("http://8.8.8.8/seite"))
    # ALT-Asymmetrie verbatim erhalten: der URL-Pfad formatiert OHNE
    # type(e).__name__ (der Datei-Pfad oben MIT).
    assert out == "Fehler beim Konvertieren: timeout"
    assert isinstance(out, ri.Umwandlungsfehler)
    assert (out.art, out.detail) == ("datei", "timeout")


def test_ein_abgebrochener_abruf_wird_benannt(monkeypatch):
    """Paket 4, C5: zu groß oder zu langsam — ein klarer Satz statt eines
    hängenden Threads oder eines vollen Speichers."""
    from boerdi.services.url_safety import DownloadAbgebrochen

    built = _wire_url_markitdown(
        monkeypatch, abruf_fehler=DownloadAbgebrochen("zu_gross", 25))
    out = asyncio.run(_wandle_url("http://8.8.8.8/riesig"))
    assert out == "Fehler: Die Seite ist größer als 25 MB."
    assert isinstance(out, ri.Umwandlungsfehler)
    assert (out.art, out.wert) == ("zu_gross", 25)
    assert built == []  # nichts umgewandelt


def test_ein_gescheiterter_abruf_ist_ein_umwandlungsfehler(monkeypatch):
    """Jeder andere Abruffehler (Verbindung, TLS …) ist ebenfalls ein
    Umwandlungsfehler, kein Dokument (Review 4b: dieser Weg war ohne Test)."""
    built = _wire_url_markitdown(
        monkeypatch, abruf_fehler=ConnectionError("Verbindung abgelehnt"))
    out = asyncio.run(_wandle_url("http://8.8.8.8/seite"))
    assert out == "Fehler beim Konvertieren: Verbindung abgelehnt"
    assert isinstance(out, ri.Umwandlungsfehler)
    assert (out.art, out.detail) == ("abruf", "Verbindung abgelehnt")
    assert built == []


def test_ein_fehlendes_markitdown_beim_url_import_ist_ein_umwandlungsfehler(monkeypatch):
    """Paket 4c, A1: wie beim Datei-Weg ein Umwandlungsfehler statt einer 500 —
    und ohne Abruf, denn umwandeln ließe sich ohnehin nichts."""
    import sys

    from boerdi.services import url_safety

    def _kein_abruf(*args, **kwargs):
        raise AssertionError("ohne markitdown darf nichts abgerufen werden")

    monkeypatch.setattr(url_safety, "hole_begrenzt", _kein_abruf)
    monkeypatch.setitem(sys.modules, "markitdown", None)  # Import scheitert
    out = asyncio.run(_wandle_url("http://8.8.8.8/seite"))
    assert out.startswith("Fehler beim Konvertieren (ImportError): ")
    assert isinstance(out, ri.Umwandlungsfehler)


def test_die_dns_pruefung_laeuft_nicht_im_event_loop(monkeypatch):
    """Paket 4, C5 (externes Audit F17c): ``getaddrinfo`` blockierte den
    Event-Loop — und damit jeden Chat-Zug auf diesem Worker, solange ein
    langsamer Nameserver brauchte."""
    import threading

    from boerdi.services import url_safety

    _wire_url_markitdown(monkeypatch)
    threads: list[str] = []
    monkeypatch.setattr(url_safety, "assert_public_url",
                        lambda url: threads.append(threading.current_thread().name))
    asyncio.run(_wandle_url("http://8.8.8.8/seite"))
    assert threads and threads[0] != threading.main_thread().name


def test_real_markitdown_honours_requests_session_kwarg():
    """Integrations-Pin gegen das ECHTE markitdown (kein Fetch, nur Konstruktion).

    ``MarkItDown.__init__`` nimmt ``requests_session`` nur über ``**kwargs``
    (0.1.6: ``(*, enable_builtins, enable_plugins, **kwargs)``) — ein Rename in
    einer künftigen Version würde das Kwarg STILL ignorieren und damit den
    N-2-Redirect-Guard lautlos abschalten, ohne dass die Fakes oben es merken.
    Der Griff auf das private ``_requests_session`` ist hier Absicht: genau
    dieser Durchstich ist die zu schützende Eigenschaft.
    """
    from markitdown import MarkItDown

    from boerdi.services.url_safety import make_ssrf_guarded_session
    guard = make_ssrf_guarded_session()
    mid = MarkItDown(requests_session=guard)
    assert mid._requests_session is guard
    assert type(guard.get_adapter("https://example.org/")).__name__ == "_SsrfGuardAdapter"


@pytest.mark.parametrize("ursache", ["fehlende Abhängigkeit", "unbekanntes Format"])
def test_eine_url_auf_ein_nicht_lesbares_format_wird_als_solches_gemeldet(monkeypatch, ursache):
    """Prüfer 2026-10-04: Der Datei-Weg meldete das seit C5, der URL-Weg gab
    weiter 400 mit der rohen markitdown-Meldung (etwa ein Link auf ein PDF)."""
    from markitdown._exceptions import (
        MissingDependencyException,
        UnsupportedFormatException,
    )

    fehler = (_gescheitert_an(MissingDependencyException("pdf fehlt"))
              if ursache == "fehlende Abhängigkeit"
              else UnsupportedFormatException("kein Wandler"))
    _wire_url_markitdown(monkeypatch, raise_exc=fehler, rumpf=b"%PDF-1.7",
                         typ="application/pdf")
    out = asyncio.run(_wandle_url("http://8.8.8.8/heft.pdf"))
    assert out.startswith(ri.FORMAT_NICHT_LESBAR)
    assert isinstance(out, ri.Umwandlungsfehler)


def test_eine_umleitung_auf_eine_interne_adresse_ist_ein_adressfehler(monkeypatch):
    """Paket 6, B2/B6: Der neue Abruf prüft jeden Umleitungs-Schritt; ein
    interner wird ein Adressfehler wie die Start-URL, nicht „nicht ladbar“."""
    from boerdi.services.url_safety import UnsafeUrlError

    built = _wire_url_markitdown(
        monkeypatch, abruf_fehler=UnsafeUrlError("Internal network URLs not allowed"))
    out = asyncio.run(_wandle_url("http://8.8.8.8/umweg"))
    assert (out.art, out.detail) == ("adresse", "")
    assert built == []
