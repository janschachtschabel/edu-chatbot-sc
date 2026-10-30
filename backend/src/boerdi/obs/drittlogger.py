"""Fremd-Logger deckeln (Paket 18C/D, Phase 2).

Laufzeitprobe 2026-10-29 (``docs/plans/2026-10-29-paket-18cd-datenbedarf.md`` §5.1): auf DEBUG
schreiben LiteLLM ganze Anfragen samt Prompt, das OpenAI-SDK die Request-Optionen und der
MCP-Client die JSON-RPC-Nachrichten samt Argumenten und Ergebnissen. Ohne ``LOG_CONTENT`` stehen
diese Logger deshalb auf WARNING; mit dem Schalter folgen sie der Wurzel. ``instructor`` steht
höher: er schreibt den Anbieterfehler per f-String auf ERROR (Review Paket 18E-2).

Rauschen und Adressen bleiben auch mit Schalter gedeckelt: ``httpx`` meldet jede Anfrage mit
voller Adresse samt Abfrage (Review Paket 6), ``httpcore``/``h11`` Verbindungsdetails,
``uvicorn.access`` IP und rohen Pfad, ``slowapi`` jede Drosselung mit der IP als Schlüssel,
SQLAlchemy auf DEBUG Ergebniszeilen samt Nachrichtentexten. Der
Schalter gilt Inhalten zur Fehlersuche, nicht IPs.
"""

from __future__ import annotations

import logging

#: Tragen auf DEBUG Prompts, Argumente und Ergebnisse (``instructor``: die Anfrage des
#: Klassifikators samt Nachrichten und seine rohe Antwort).
INHALT_LOGGER: tuple[str, ...] = (
    "LiteLLM", "LiteLLM Router", "LiteLLM Proxy", "openai", "mcp", "instructor",
    # ``mcp/client/session.py`` loggt unter dem Namen „client“ (Review 2026-10-30).
    "client",
)
#: Immer gedeckelt, mit der Stufe.
GEDECKELT: dict[str, int] = {
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
    "h11": logging.WARNING,
    "uvicorn.access": logging.WARNING,
    "slowapi": logging.ERROR,
    # Ergebniszeilen samt Nachrichtentexten auf DEBUG; SQLAlchemy deckelt sich beim Import
    # selbst auf WARN — hier ausdrücklich, damit ``LOG_LEVEL=DEBUG`` es nie öffnet.
    "sqlalchemy": logging.WARNING,
}
#: Ohne Schalter höher als WARNING: ``instructor`` schreibt „API call failed on attempt 1: {e}“
#: auf ERROR, vorformatiert — der Anbietertext wiederholt die Eingabe, und die Schwärzung im
#: Formatierer greift nur bei Argumenten. Was der Klassifikator braucht, meldet ``classify``.
_INHALT_STUFE: dict[str, int] = {"instructor": logging.CRITICAL}
_LITELLM = ("LiteLLM", "LiteLLM Router", "LiteLLM Proxy")


class _MCPWurzelzeilen(logging.Filter):
    """Zeilen, die das MCP-SDK über die WURZEL schreibt (``logging.warning(f"…{e}")`` in
    ``mcp/shared/session.py``) — am Deckel der Logger vorbei, der Text vorformatiert
    (Review 2026-10-30). Ohne ``LOG_CONTENT``: unter WARNING verworfen, sonst nur der Satzanfang.
    Sitzt am Wurzel-Logger und sieht damit nur dessen eigene Zeilen, keine weitergereichten."""

    def filter(self, record: logging.LogRecord) -> bool:
        pfad = record.pathname.replace("\\", "/")
        if "/site-packages/mcp/" not in pfad:
            return True
        if record.levelno < logging.WARNING:
            return False
        # Nur ein Satzanfang vor dem Doppelpunkt (Review 2026-10-30) — ohne ihn ist die ganze
        # Zeile vorformatiert, dann nur der Ort.
        kopf, trenner, _ = str(record.msg).partition(":")
        ort = f"MCP-SDK {pfad.rsplit('/', 1)[-1]}:{record.lineno}"
        record.msg = (f"{kopf[:80]}: ‹ausgelassen› ({ort})" if trenner else
                      f"{ort}: ‹ausgelassen›")
        record.args = ()
        return True


_MCP_WURZEL = _MCPWurzelzeilen()


def drittlogger_einstellen(log_content: bool) -> None:
    """Die Fremd-Logger auf ihre Stufen setzen; aufgerufen von ``main._configure_logging``."""
    wurzel = logging.getLogger()
    wurzel.removeFilter(_MCP_WURZEL)
    if not log_content:
        wurzel.addFilter(_MCP_WURZEL)
    # LiteLLM hängt beim Import einen eigenen stderr-Handler an seine Logger: jede Zeile kam
    # doppelt, einmal am JSON-Format und an jeder Deckelung vorbei. Erst importieren, dann
    # entfernen — sonst käme der Handler mit einem späteren Import zurück.
    import litellm._logging  # noqa: F401

    for name in _LITELLM:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
    for name in INHALT_LOGGER:
        logging.getLogger(name).setLevel(
            logging.NOTSET if log_content else _INHALT_STUFE.get(name, logging.WARNING))
    for name, stufe in GEDECKELT.items():
        logging.getLogger(name).setLevel(stufe)
