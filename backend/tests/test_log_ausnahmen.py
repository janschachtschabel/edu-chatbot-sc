"""Paket 18E, Aufgabe 2.1: Tracebacks tragen keine Texte fremder Dienste.

Ein Anbieter- oder MCP-Fehler wiederholt mitunter die Eingabe (OpenAI „Invalid value: …“,
MCP ``-32602``). Mit ``logger.exception`` stünde sein Text in der letzten Traceback-Zeile —
auch, wenn er nur verkettet (``raise … from``) oder in einer Gruppe (anyio) steckt. Die
Formatierer setzen für diese Typen nur den Typnamen; eigene Ausnahmetexte bleiben.
"""

from __future__ import annotations

import json
import logging
import sys

import litellm
import pytest
from mcp.shared.exceptions import McpError
from mcp.types import ErrorData

from boerdi.obs.log_format import JsonFormatter, text_formatter, traceback_ohne_fremdtexte

MARKE = "KANARIE7Q"


def _record(ausloesen) -> logging.LogRecord:
    try:
        ausloesen()
    except BaseException:  # noqa: BLE001 — die Probe nimmt jede Ausnahme auf
        ei = sys.exc_info()
    record = logging.LogRecord("probe", logging.ERROR, __file__, 1, "Aufruf gescheitert (%s)",
                               (type(ei[1]).__name__,), ei)
    record.trace_id = "-"  # sonst setzt es ``obs/trace_id.TraceIdFilter``
    return record


def _anbieterfehler() -> None:
    raise litellm.BadRequestError(
        message=f"OpenAIException - Invalid value for 'content': '{MARKE} Optik'",
        model="gpt-x", llm_provider="openai")


def _mcp_fehler() -> McpError:
    return McpError(ErrorData(code=-32602, message=f"Invalid arguments: query='{MARKE}'"))


def _verkettet() -> None:
    try:
        raise _mcp_fehler()
    except McpError as e:
        raise RuntimeError("Werkzeugaufruf gescheitert") from e


def _im_kontext() -> None:
    try:
        _anbieterfehler()
    except litellm.BadRequestError:
        # Ohne ``from``: der Anbieterfehler hängt als ``__context__`` daran.
        raise KeyError("antwort")  # noqa: B904


def _gruppe() -> None:
    raise ExceptionGroup("Aufgaben gescheitert", [_mcp_fehler(), ValueError("Rest")])


def _ausgaben(record: logging.LogRecord) -> dict[str, str]:
    json_zeile = json.loads(JsonFormatter().format(record))
    return {"json": json_zeile["exc"], "text": text_formatter().format(record)}


@pytest.mark.parametrize("ausloesen, typen", [
    (_anbieterfehler, ["litellm.exceptions.BadRequestError"]),
    (_verkettet, ["mcp.shared.exceptions.McpError", "RuntimeError: Werkzeugaufruf gescheitert"]),
    (_im_kontext, ["litellm.exceptions.BadRequestError", "KeyError: 'antwort'"]),
    (_gruppe, ["mcp.shared.exceptions.McpError", "ValueError: Rest"]),
], ids=["anbieter", "mcp_verkettet", "anbieter_im_kontext", "mcp_in_gruppe"])
def test_fremdtexte_stehen_nicht_im_traceback(ausloesen, typen):
    record = _record(ausloesen)

    for art, text in _ausgaben(record).items():
        assert MARKE not in text, f"{art}: Fremdtext im Traceback"
        assert "‹geschwärzt›" in text, art
        for typ in typen:
            assert typ in text, f"{art}: {typ} fehlt"
        assert "Traceback (most recent call last)" in text, art


def test_eigene_ausnahmetexte_bleiben():
    """Nur fremde Dienste werden geschwärzt — ``KeyError('antwort')`` sagt, was fehlt."""
    def eigener_fehler() -> None:
        raise KeyError("antwort")

    for art, text in _ausgaben(_record(eigener_fehler)).items():
        assert "KeyError: 'antwort'" in text, art
        assert "‹geschwärzt›" not in text, art


def test_klartext_nimmt_keinen_fremden_traceback_aus_dem_cache():
    """``logging.Formatter.format`` übernimmt ``record.exc_text``, wenn ein anderer
    Handler ihn schon gesetzt hat — der käme ungeschwärzt."""
    record = _record(_anbieterfehler)
    roh = logging.Formatter().formatException(record.exc_info)
    record.exc_text = roh
    assert MARKE in roh  # die Probe: ohne Schwärzung stünde das Wort im Log

    text = text_formatter().format(record)

    assert MARKE not in text
    assert record.exc_text == roh  # fremde Handler sehen weiter ihre Fassung


def test_traceback_ohne_fremdtexte_wie_formatexception():
    """Ohne Fremdtext dasselbe wie ``logging.Formatter.formatException``."""
    def eigener_fehler() -> None:
        raise ValueError("kaputt")

    record = _record(eigener_fehler)
    assert traceback_ohne_fremdtexte(record.exc_info) == (
        logging.Formatter().formatException(record.exc_info))


def _meldung(vorlage: str, args) -> logging.LogRecord:
    record = logging.LogRecord("probe", logging.WARNING, __file__, 1, vorlage, args, None)
    record.trace_id = "-"
    return record


def _anbieterfehler_objekt() -> BaseException:
    try:
        _anbieterfehler()
    except litellm.BadRequestError as e:
        return e
    raise AssertionError("unerreichbar")


def _meldungen(record: logging.LogRecord) -> dict[str, str]:
    return {"json": json.loads(JsonFormatter().format(record))["message"],
            "text": text_formatter().format(record)}


def test_fremdtexte_in_den_argumenten_der_meldung():
    """Review 18E-2 (Befund 1): ``logger.warning("… %s", e)`` setzte den Anbietertext in die
    Meldung selbst — an über hundert Stellen. Geschwärzt wird das Ausnahmeobjekt, die Art bleibt."""
    record = _meldung("Rechtsprüfung gescheitert: %s", (_anbieterfehler_objekt(),))

    for art, text in _meldungen(record).items():
        assert MARKE not in text, art
        assert "BadRequestError" in text and "‹geschwärzt›" in text, art
    assert MARKE in record.getMessage()  # der Record bleibt unverändert, für andere Handler


def test_fremdtexte_in_benannten_argumenten():
    record = _meldung("Werkzeug gescheitert: %(fehler)s", ({"fehler": _mcp_fehler()},))

    for art, text in _meldungen(record).items():
        assert MARKE not in text, art
        assert "McpError" in text, art


def test_eigene_ausnahmen_in_argumenten_bleiben():
    record = _meldung("Lader gescheitert: %s", (KeyError("antwort"),))

    for art, text in _meldungen(record).items():
        assert "'antwort'" in text, art
        assert "‹geschwärzt›" not in text, art


def _gruppenmitglied_wieder_geworfen() -> None:
    """anyio-Muster: das einzige Gruppenmitglied auspacken und neu werfen."""
    try:
        raise ExceptionGroup("Aufgaben gescheitert", [_mcp_fehler()])
    except ExceptionGroup as gruppe:
        raise gruppe.exceptions[0]  # noqa: B904


def test_wieder_geworfenes_gruppenmitglied():
    """Review 18E-2 (Befund 2): dieselbe Ausnahme steht zweimal im Baum — als Wurzel und als
    Kind ihres eigenen Kontexts. Beide Knoten werden geschwärzt."""
    record = _record(_gruppenmitglied_wieder_geworfen)

    for art, text in _ausgaben(record).items():
        assert MARKE not in text, art
        assert "mcp.shared.exceptions.McpError" in text, art
