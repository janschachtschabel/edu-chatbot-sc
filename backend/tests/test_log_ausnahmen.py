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


# ── Review 2026-10-30 ──────────────────────────────────────────────────────────


def test_die_kurzform_behaelt_status_und_code():
    from boerdi.obs.log_format import ausnahme_text

    anbieter = litellm.BadRequestError(message=f"Invalid value: {MARKE}", model="gpt-x",
                                       llm_provider="openai")
    mcp = McpError(ErrorData(code=-32603, message=f"Interner Fehler bei {MARKE}"))
    assert ausnahme_text(anbieter) == "BadRequestError(status=400, ‹geschwärzt›)"
    assert ausnahme_text(mcp) == "McpError(code=-32603, ‹geschwärzt›)"


def test_ausnahme_text_loest_gruppen_auf_und_behaelt_eigene_texte():
    from boerdi.obs.log_format import ausnahme_text

    gruppe = ExceptionGroup("unhandled errors in a TaskGroup", [
        McpError(ErrorData(code=-32603, message=f"Fehler zu {MARKE}")),
        ConnectionError("Verbindung abgelehnt"),
    ])
    text = ausnahme_text(gruppe)
    assert text == "McpError(code=-32603, ‹geschwärzt›); Verbindung abgelehnt"
    assert MARKE not in text


def test_eine_huelle_von_instructor_wird_geschwaerzt():
    """``InstructorRetryException(str(e)) from e`` — so wirft instructor den Anbieterfehler."""
    from instructor.core import InstructorRetryException

    from boerdi.obs.log_format import ausnahme_text

    def ausloesen() -> None:
        try:
            _anbieterfehler()
        except litellm.BadRequestError as e:
            raise InstructorRetryException(str(e), n_attempts=1, total_usage=0) from e

    for formatierer in (text_formatter(), JsonFormatter()):
        text = formatierer.format(_record(ausloesen))
        assert MARKE not in text, type(formatierer).__name__
    try:
        ausloesen()
    except InstructorRetryException as e:
        assert MARKE not in ausnahme_text(e)


def test_eine_eigene_huelle_ohne_fremdtext_bleibt_lesbar():
    """Nur wer den Text der Ursache übernimmt, gilt als Hülle."""
    from boerdi.obs.log_format import ausnahme_text

    try:
        try:
            _anbieterfehler()
        except litellm.BadRequestError as e:
            raise RuntimeError("Klassifikation gescheitert") from e
    except RuntimeError as e:
        assert ausnahme_text(e) == "Klassifikation gescheitert"


def test_asyncpg_nennt_den_wert_eines_parameters_nicht():
    from boerdi.obs.log_format import geschwaerzt

    text = geschwaerzt(f"invalid input for query argument $2: '{MARKE} Optik' (expected int)")
    assert text == "invalid input for query argument $2: ‹geschwärzt›"  # samt Rest der Zeile


def test_wurzelzeilen_des_mcp_sdk_ohne_text(caplog):
    """``mcp/shared/session.py`` schreibt per ``logging.warning(f"…{e}")`` über die Wurzel."""
    from boerdi.obs.drittlogger import drittlogger_einstellen

    drittlogger_einstellen(False)
    try:
        record = logging.LogRecord(
            "root", logging.WARNING,
            "/app/.venv/lib/python3.12/site-packages/mcp/shared/session.py", 383,
            f"Failed to validate request: {MARKE} Optik", (), None)
        tief = logging.LogRecord(
            "root", logging.DEBUG,
            "/app/.venv/lib/python3.12/site-packages/mcp/shared/session.py", 384,
            f"Message that failed validation: {MARKE}", (), None)
        eigen = logging.LogRecord("root", logging.WARNING, "/app/src/boerdi/main.py", 1,
                                  f"eigene Zeile {MARKE}", (), None)
        wurzel = logging.getLogger()
        assert wurzel.filter(record) and not wurzel.filter(tief) and wurzel.filter(eigen)
        assert record.getMessage() == (
            "Failed to validate request: ‹ausgelassen› (MCP-SDK session.py:383)")
        assert MARKE in eigen.getMessage()
    finally:
        drittlogger_einstellen(False)



def test_instructor_steht_fuer_sich_in_der_liste():
    """Ohne Ursache: nur der Eintrag in ``_FREMDTEXTE`` schwärzt (Review 2026-10-30)."""
    from instructor.core import InstructorRetryException

    from boerdi.obs.log_format import ausnahme_text

    text = ausnahme_text(InstructorRetryException(f"Versuch scheiterte: {MARKE}", n_attempts=1,
                                                  total_usage=0))
    assert MARKE not in text and text.startswith("InstructorRetryException(")


def test_eine_eigene_huelle_mit_fremdtext_wird_geschwaerzt():
    """Die Hüllen-Regel für sich: ``RuntimeError(str(e)) from e``."""
    from boerdi.obs.log_format import ausnahme_text

    def ausloesen() -> None:
        try:
            _anbieterfehler()
        except litellm.BadRequestError as e:
            raise RuntimeError(str(e)) from e

    try:
        ausloesen()
    except RuntimeError as e:
        assert ausnahme_text(e) == "RuntimeError(‹geschwärzt›)"
        record = logging.LogRecord("probe", logging.ERROR, __file__, 1, "Fehler: %s", (e,), None)
        record.trace_id = "-"
        assert MARKE not in text_formatter().format(record)


def test_status_steht_auch_im_traceback():
    text = traceback_ohne_fremdtexte(_record(_anbieterfehler).exc_info)
    assert "status=400, ‹geschwärzt›" in text and MARKE not in text


@pytest.mark.parametrize("zeile", [
    f"invalid input for query argument $2: '{MARKE} (Klasse 7)' (expected int, got str)",
    f"invalid input for query argument $2 in element #3 of executemany() sequence: '{MARKE}'",
    f"invalid input for query argument $1: '{MARKE}' (invalid UUID '{MARKE}': length must be 32)",
])
def test_asyncpg_in_allen_formen(zeile):
    from boerdi.obs.log_format import geschwaerzt

    assert MARKE not in geschwaerzt(zeile)
