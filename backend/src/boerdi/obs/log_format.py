"""Log-Formate (Paket 17, D4): JSON für den Betrieb, Klartext für die Entwicklung.

Leitfaden „Übergabe an Team 6“: Logs nach stdout, strukturiert (JSON), umschaltbar auf
Klartext, Level per Env. ``LOG_FORMAT=json|text`` (Vorgabe ``text``), ``LOG_LEVEL``.
Jede Zeile trägt die Trace-ID der Anfrage (``obs/trace_id.TraceIdFilter``).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

_TEXT = "%(asctime)s %(levelname)s %(name)s [%(trace_id)s]: %(message)s"
_DATUM = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Eine JSON-Zeile je Eintrag: Zeit (UTC, ISO 8601), Level, Logger, Nachricht, Trace-ID."""

    def format(self, record: logging.LogRecord) -> str:
        zeit = datetime.fromtimestamp(record.created, tz=UTC)
        eintrag = {
            "time": zeit.strftime("%Y-%m-%dT%H:%M:%S.") + f"{zeit.microsecond // 1000:03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": getattr(record, "trace_id", "-"),
        }
        if record.exc_info:
            eintrag["exc"] = self.formatException(record.exc_info)
        # ASCII: gültiges JSON, auf jeder Konsole schreibbar (Prozess-Probe 2026-10-20).
        return json.dumps(eintrag, ensure_ascii=True)


def text_formatter() -> logging.Formatter:
    """Klartext mit Datum (vorher nur die Uhrzeit) und Trace-ID."""
    return logging.Formatter(_TEXT, datefmt=_DATUM)


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
