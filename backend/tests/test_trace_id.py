"""Paket 17 (D4): Trace-ID und Log-Format nach dem Leitfaden „Übergabe an Team 6“.

Tracing B3-konform; ``x-client-trace-id`` wird durchgereicht, damit Logs dienstübergreifend
gefiltert werden können. Logs nach stdout, JSON umschaltbar auf Klartext, Level per Env.
"""

from __future__ import annotations

import json
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from boerdi.obs import trace_id
from boerdi.obs.log_format import JsonFormatter, text_formatter
from boerdi.settings import get_settings

HEX32 = "0af7651916cd43dd8448eb211c80319c"


# ── Quelle der ID ──────────────────────────────────────────────────────────

def test_client_trace_id_geht_vor() -> None:
    assert trace_id.aus_kopfzeilen({"x-client-trace-id": "abc-123",
                                    "x-b3-traceid": HEX32}) == "abc-123"


def test_b3_einzeln_und_als_kopf() -> None:
    assert trace_id.aus_kopfzeilen({"x-b3-traceid": HEX32}) == HEX32
    assert trace_id.aus_kopfzeilen({"b3": f"{HEX32}-e457b5a2e4d86bd1-1"}) == HEX32


@pytest.mark.parametrize("roh", ["", "a" * 200, "hat leerzeichen", "zeile\numbruch"])
def test_unbrauchbares_wird_ersetzt(roh) -> None:
    neu = trace_id.aus_kopfzeilen({"x-client-trace-id": roh})
    assert neu != roh
    assert len(neu) == 32 and int(neu, 16) >= 0


def test_ohne_kopf_eine_neue_id() -> None:
    a, b = trace_id.aus_kopfzeilen({}), trace_id.aus_kopfzeilen({})
    assert a != b and len(a) == 32


# ── Middleware: je Anfrage eine ID ─────────────────────────────────────────

def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/id")
    def id_() -> dict:
        return {"id": trace_id.aktuelle()}

    app.add_middleware(trace_id.TraceIdMiddleware)
    return app


def test_die_anfrage_traegt_ihre_id() -> None:
    client = TestClient(_app())
    assert client.get("/id", headers={"x-client-trace-id": "t-1"}).json()["id"] == "t-1"
    zweite = client.get("/id").json()["id"]
    assert zweite != "t-1" and len(zweite) == 32


def test_keine_id_in_der_antwort() -> None:
    """Leitfaden: Standard sind keine Header vom Dienst zurück."""
    r = TestClient(_app()).get("/id", headers={"x-client-trace-id": "t-1"})
    assert "x-client-trace-id" not in {k.lower() for k in r.headers}


# ── Ausgehende Köpfe ───────────────────────────────────────────────────────

def test_ausgehend_client_id_und_b3() -> None:
    token = trace_id.setze(HEX32)
    try:
        koepfe = trace_id.ausgehende_koepfe()
    finally:
        trace_id.zuruecksetzen(token)
    assert koepfe["x-client-trace-id"] == HEX32
    assert koepfe["X-B3-TraceId"] == HEX32
    assert len(koepfe["X-B3-SpanId"]) == 16


def test_ausgehend_ohne_b3_wenn_die_id_kein_hex_ist() -> None:
    token = trace_id.setze("abc-123")
    try:
        koepfe = trace_id.ausgehende_koepfe()
    finally:
        trace_id.zuruecksetzen(token)
    assert koepfe == {"x-client-trace-id": "abc-123"}


def test_ausserhalb_einer_anfrage_keine_koepfe() -> None:
    assert trace_id.ausgehende_koepfe() == {}


def test_llm_aufruf_traegt_die_id(monkeypatch) -> None:
    from boerdi.services import llm

    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    token = trace_id.setze(HEX32)
    try:
        kwargs = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}])
        llm.wire_transport(kwargs["model"], kwargs)
    finally:
        trace_id.zuruecksetzen(token)
    get_settings.cache_clear()
    assert kwargs["extra_headers"]["x-client-trace-id"] == HEX32


def test_openai_direkt_bekommt_keine_trace_koepfe(monkeypatch) -> None:
    """OpenAI ist ein externer Dritter, kein Dienst im Verbund — die ID bleibt bei uns."""
    from boerdi.services import llm

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    token = trace_id.setze(HEX32)
    try:
        assert llm.route("gpt-6-luna")[3] is None
    finally:
        trace_id.zuruecksetzen(token)
        get_settings.cache_clear()


def test_mcp_aufruf_traegt_die_id(monkeypatch) -> None:
    from pydantic import SecretStr

    from boerdi.services.mcp.http_fabrik import build_http_client_factory

    monkeypatch.setattr(get_settings(), "mcp_auth_token", SecretStr(""), raising=False)
    token = trace_id.setze("t-mcp")
    try:
        client = build_http_client_factory()()
    finally:
        trace_id.zuruecksetzen(token)
    assert client.headers.get("x-client-trace-id") == "t-mcp"


# ── Log-Format ─────────────────────────────────────────────────────────────

def _eintrag(formatter: logging.Formatter, nachricht: str = "hallo") -> str:
    rec = logging.LogRecord("boerdi.test", logging.WARNING, __file__, 1, nachricht, None, None)
    trace_id.TraceIdFilter().filter(rec)
    return formatter.format(rec)


def test_json_zeile_mit_trace_id_und_utc_zeit() -> None:
    token = trace_id.setze("t-log")
    try:
        zeile = json.loads(_eintrag(JsonFormatter()))
    finally:
        trace_id.zuruecksetzen(token)
    assert zeile["level"] == "WARNING"
    assert zeile["logger"] == "boerdi.test"
    assert zeile["message"] == "hallo"
    assert zeile["trace_id"] == "t-log"
    assert zeile["time"].endswith("Z") and "T" in zeile["time"]


def test_klartext_mit_datum_und_trace_id() -> None:
    token = trace_id.setze("t-text")
    try:
        zeile = _eintrag(text_formatter())
    finally:
        trace_id.zuruecksetzen(token)
    assert "t-text" in zeile
    assert zeile[:4].isdigit() and zeile[4] == "-"  # beginnt mit dem Datum


def test_log_format_aus_der_umgebung(monkeypatch) -> None:
    monkeypatch.setenv("LOG_FORMAT", "json")
    get_settings.cache_clear()
    assert get_settings().log_format == "json"
    monkeypatch.setenv("LOG_FORMAT", "quatsch")
    get_settings.cache_clear()
    assert get_settings().log_format == "text"
    get_settings.cache_clear()


def test_json_zeile_ist_reines_ascii() -> None:
    """Prozess-Probe 2026-10-20: auf einer Konsole ohne UTF-8 warf jede Zeile mit „⚠“ einen
    Logging-Fehler (stdout kodiert streng, stderr ersetzte bisher). ASCII-JSON ist gültiges
    JSON und überall schreibbar."""
    zeile = _eintrag(JsonFormatter(), "⚠ Größe")
    zeile.encode("ascii")  # wirft, wenn nicht
    assert json.loads(zeile)["message"] == "⚠ Größe"


def test_klartext_auf_stdout_bricht_nicht_an_sonderzeichen(monkeypatch, capsys) -> None:
    import io
    import sys

    from boerdi.main import _configure_logging

    roh = io.BytesIO()
    stdout = io.TextIOWrapper(roh, encoding="cp1252")  # strenge Kodierung wie Windows
    monkeypatch.setattr(sys, "stdout", stdout)
    wurzel = logging.getLogger()
    alte = wurzel.handlers[:]
    wurzel.handlers.clear()
    try:
        _configure_logging(get_settings())
        logging.getLogger("boerdi.test").warning("⚠ achtung")
        stdout.flush()
    finally:
        wurzel.handlers[:] = alte
    assert "achtung" in roh.getvalue().decode("cp1252")


@pytest.mark.parametrize("tid,erwartet", [
    ("4f2a9c01d3b7e6a8deadbeef00112233", "4f2a9c01d3b7"),
    ("abc", "abc"),
    ("", "-"),
])
def test_die_fehlernummer_ist_der_anfang_der_trace_id(tid, erwartet):
    """Paket 18C/D (3.4): kurz genug zum Vorlesen, lang genug für die Suche (ab 8 Zeichen
    per Präfix, kürzere genau)."""
    from boerdi.obs import trace_id

    token = trace_id.setze(tid)
    try:
        assert trace_id.fehlernummer() == erwartet
    finally:
        trace_id.zuruecksetzen(token)


def test_kein_text_nennt_die_fehlerklasse():
    """Paket 18C/D (3.4): Blasen nannten ``({kind})`` — die Klasse der Ausnahme sagt der Person
    nichts und verrät Innenleben; die Fehlernummer führt im Studio zum Zug."""
    from boerdi.i18n.bot_text import BOT_TEXT

    mit_klasse = [(sprache, k) for sprache, texte in BOT_TEXT.items()
                  for k, v in texte.items() if "{kind}" in v]
    assert mit_klasse == []


# ── Review 2026-10-30: keine Fehlernummer aus Nullen ──────────────────────────


@pytest.mark.parametrize("koepfe", [
    {"x-client-trace-id": "0" * 32},
    {"x-client-trace-id": "000000000000-zug-4711"},
    {"x-b3-traceid": "0" * 32},
    {"b3": "0" * 16 + "-e457b5a2e4d86bd1-1"},
], ids=["client-null", "client-nullen-vorn", "b3-null", "b3-einzeln-null"])
def test_eine_null_id_wird_ersetzt(koepfe) -> None:
    neu = trace_id.aus_kopfzeilen(koepfe)
    assert len(neu) == 32 and neu[:trace_id.FEHLERNUMMER_ZEICHEN].strip("0")


def test_eine_aufgefuellte_64_bit_id_gilt_in_kurzer_form() -> None:
    """Ohne das ergäben alle Züge eines 64-Bit-B3-Aufrufers die Nummer ``000000000000``."""
    assert trace_id.aus_kopfzeilen({"x-b3-traceid": "0" * 16 + "E457B5A2E4D86BD1"}) == (
        "e457b5a2e4d86bd1")
    assert trace_id.aus_kopfzeilen({"b3": "0" * 16 + "e457b5a2e4d86bd1-a2fb4a1d1a96d312-1"}) == (
        "e457b5a2e4d86bd1")



@pytest.mark.parametrize("roh", ["------------", "....abc", ":zug-4711", "0-0-0-0-0-0-",
                                 "00000000000.x"])
def test_eine_id_ohne_buchstabe_oder_ziffer_vorn_wird_ersetzt(roh) -> None:
    neu = trace_id.aus_kopfzeilen({"x-client-trace-id": roh})
    assert neu != roh and len(neu) == 32


def test_b3_greift_wenn_die_client_id_nichts_taugt() -> None:
    assert trace_id.aus_kopfzeilen({"x-client-trace-id": "0" * 32, "x-b3-traceid": HEX32}) == HEX32
