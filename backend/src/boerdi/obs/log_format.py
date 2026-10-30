"""Log-Formate (Paket 17, D4): JSON für den Betrieb, Klartext für die Entwicklung.

Leitfaden „Übergabe an Team 6“: Logs nach stdout, strukturiert (JSON), umschaltbar auf
Klartext, Level per Env. ``LOG_FORMAT=json|text`` (Vorgabe ``text``), ``LOG_LEVEL``.
Jede Zeile trägt die Trace-ID der Anfrage (``obs/trace_id.TraceIdFilter``).
"""

from __future__ import annotations

import json
import logging
import re
import sys
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_TEXT = "%(asctime)s %(levelname)s %(name)s [%(trace_id)s]: %(message)s"
_DATUM = "%Y-%m-%d %H:%M:%S"

# Paket 18C/D (Review Phase 2): Ausnahmetexte tragen Eingabewerte, ohne dass ein Aufrufer sie
# loggt. Postgres hängt ``DETAIL:`` an — beim Fremdschlüssel den Schlüssel (etwa die
# Sitzungs-ID), bei NOT NULL/CHECK die ganze Zeile —, Pydantic ``input_value=…``. Beides wird
# beim Formatieren geschwärzt, in Meldung und Traceback; Anweisung, Fehlerart und Ort bleiben.
_DB_DETAIL = re.compile(r"^(\s*DETAIL:).*$", re.MULTILINE)
_EINGABE = re.compile(r"input_value=.*?(?=, input_type=)")
_GESCHWAERZT = "‹geschwärzt›"


def geschwaerzt(text: str) -> str:
    """``text`` ohne Datenbank-DETAIL und ohne Eingabewerte aus Prüffehlern."""
    text = _DB_DETAIL.sub(rf"\1 {_GESCHWAERZT}", text)
    return _EINGABE.sub(f"input_value={_GESCHWAERZT}", text)


# Paket 18E (2.1): Ein Anbieter- oder MCP-Fehler wiederholt mitunter die Eingabe (OpenAI
# „Invalid value: …“, MCP ``-32602``) — von ihm steht nur der Typ im Log: im Traceback, auch
# verkettet oder in einer Gruppe, und als Argument einer Meldung (``logger.warning("… %s", e)``,
# über hundert Stellen). LiteLLM-Fehler erben von ``openai.OpenAIError``. Nach Namen statt per
# ``isinstance``, damit das Logging die SDKs nicht importiert.
_FREMDTEXTE = frozenset({"openai.OpenAIError", "mcp.shared.exceptions.McpError"})


def _fremdtext(exc: BaseException) -> bool:
    return any(f"{k.__module__}.{k.__qualname__}" in _FREMDTEXTE for k in type(exc).__mro__)


def _ohne_fremdtext(wert: object) -> object:
    if isinstance(wert, BaseException) and _fremdtext(wert):
        return f"{type(wert).__name__}({_GESCHWAERZT})"
    return wert


def _args_ohne_fremdtexte(args: Any) -> Any:
    """Die Argumente einer Meldung; Ausnahmen fremder Dienste nur mit ihrer Art."""
    if isinstance(args, tuple):
        return tuple(_ohne_fremdtext(a) for a in args)
    if isinstance(args, Mapping):
        return {k: _ohne_fremdtext(v) for k, v in args.items()}
    return args


def nachricht_ohne_fremdtexte(record: logging.LogRecord) -> str:
    """Wie ``record.getMessage()``, die Argumente ohne Texte fremder Dienste."""
    nachricht = str(record.msg)
    if record.args:
        nachricht = nachricht % _args_ohne_fremdtexte(record.args)
    return nachricht


def _schwaerze(te: traceback.TracebackException | None, exc: BaseException | None,
               gesehen: set[int]) -> None:
    """Geht Kette und Gruppen von ``exc`` und ``te`` gleichlaufend ab.

    Gemerkt wird der Knoten, nicht die Ausnahme: ``TracebackException`` legt Gruppenkinder ohne
    eigene Prüfung an — ein ausgepacktes, neu geworfenes Mitglied steht dann zweimal im Baum
    (Review 18E-2)."""
    if te is None or exc is None or id(te) in gesehen:
        return
    gesehen.add(id(te))
    if _fremdtext(exc):
        # ``_str`` ist privat, aber die einzige Stelle, aus der ``format`` den Text nimmt;
        # ``test_log_ausnahmen`` fällt, wenn eine Python-Version das ändert.
        te._str = _GESCHWAERZT
    _schwaerze(te.__cause__, exc.__cause__, gesehen)
    _schwaerze(te.__context__, exc.__context__, gesehen)
    for kind_te, kind in zip(te.exceptions or (), getattr(exc, "exceptions", ()), strict=False):
        _schwaerze(kind_te, kind, gesehen)


def traceback_ohne_fremdtexte(ei: Any) -> str:
    """Wie ``logging.Formatter.formatException``, Texte fremder Dienste geschwärzt."""
    te = traceback.TracebackException(ei[0], ei[1], ei[2], compact=True)
    _schwaerze(te, ei[1], set())
    return "".join(te.format()).removesuffix("\n")


class JsonFormatter(logging.Formatter):
    """Eine JSON-Zeile je Eintrag: Zeit (UTC, ISO 8601), Level, Logger, Nachricht, Trace-ID."""

    def format(self, record: logging.LogRecord) -> str:
        zeit = datetime.fromtimestamp(record.created, tz=UTC)
        eintrag = {
            "time": zeit.strftime("%Y-%m-%dT%H:%M:%S.") + f"{zeit.microsecond // 1000:03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": geschwaerzt(nachricht_ohne_fremdtexte(record)),
            "trace_id": getattr(record, "trace_id", "-"),
        }
        if hasattr(record, "ereignis"):
            # Paket 18C/D: Zeilen aus ``log_inhalt.ereignis`` tragen ihre Felder einzeln.
            eintrag["event"] = record.ereignis
            eintrag["fields"] = record.ereignis_felder
        if record.exc_info:
            eintrag["exc"] = geschwaerzt(self.formatException(record.exc_info))
        # ASCII: gültiges JSON, auf jeder Konsole schreibbar (Prozess-Probe 2026-10-20).
        # ``default=str``: ein Feld, das JSON nicht kennt, kostet nicht die ganze Zeile.
        return json.dumps(eintrag, ensure_ascii=True, default=str)

    def formatException(self, ei: Any) -> str:  # noqa: N802 — überschreibt logging
        return traceback_ohne_fremdtexte(ei)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # ``logging.Formatter.format`` übernähme ein ``exc_text``, das ein anderer Handler
        # schon roh gesetzt hat, und formatiert die Meldung aus ``args`` — beides für diesen
        # Aufruf ohne Fremdtexte; danach sehen die anderen Handler wieder ihre Fassung.
        args, exc_text = record.args, record.exc_text
        record.args, record.exc_text = _args_ohne_fremdtexte(args), None
        try:
            return geschwaerzt(super().format(record))
        finally:
            record.args, record.exc_text = args, exc_text

    def formatException(self, ei: Any) -> str:  # noqa: N802 — überschreibt logging
        return traceback_ohne_fremdtexte(ei)


def text_formatter() -> logging.Formatter:
    """Klartext mit Datum (vorher nur die Uhrzeit) und Trace-ID."""
    return _TextFormatter(_TEXT, datefmt=_DATUM)


def formatter_fuer(art: str) -> logging.Formatter:
    return JsonFormatter() if art == "json" else text_formatter()


class StdoutHandler(logging.StreamHandler):
    """stdout, ohne an der Kodierung des Stroms zu scheitern.

    Bis Paket 17 schrieb das Logging nach stderr — dort ersetzt Python nicht Darstellbares.
    stdout kodiert streng: auf einer Konsole ohne UTF-8 warf jede Zeile mit „⚠“ einen
    Logging-Fehler. Hier wird vorher auf die Kodierung des Stroms abgebildet.
    """

    def __init__(self) -> None:
        super().__init__(sys.stdout)

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        kodierung = getattr(self.stream, "encoding", None)
        if not kodierung:
            return text
        return text.encode(kodierung, "backslashreplace").decode(kodierung)
