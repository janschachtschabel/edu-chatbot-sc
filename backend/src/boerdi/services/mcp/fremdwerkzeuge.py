"""Werkzeuge fremder MCP-Server anbieten und rufen (Paket 11, E).

Die Auswahl steht in ``domain/fremdwerkzeug``; hier liegen Registry und Netz. Der Aufruf geht einen
eigenen, schmalen Weg neben ``client.call_mcp_tool_status``, weil dort alles an WLO-Namen hängt
(Vokabular, Karten-Metadaten, vorbereitete Schreibanfragen, Cache):

- gerufen wird nur, was :func:`definitionen` anbietet — einen geratenen Namen nicht;
- die Adresse wird beim Aufruf erneut geprüft (``assert_public_url``): seit dem Speichern im Studio
  kann der Name auf eine interne Adresse zeigen;
- kein ``structuredContent``, also keine vorbereitete Schreibanfrage; kein Cache;
- kein Zugangsblock: ``transport._client_fabrik`` gibt ihn nur dem WLO-Server.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from boerdi.domain.fremdwerkzeug import FremdWerkzeug, angebotene
from boerdi.obs.log_inhalt import inhalt
from boerdi.services.mcp import transport
from boerdi.services.url_safety import UnsafeUrlError, assert_public_url

logger = logging.getLogger(__name__)

_PRIMARY_ID = "wlo-mcp"
#: Mehr Text bekommt das Modell von einem fremden Dienst nicht (Review Paket 11, #8): jede Antwort
#: reist in allen folgenden Runden mit.
HOECHSTENS_ZEICHEN = 30_000


def _registry() -> list[dict[str, Any]]:
    from boerdi.services import config_loader

    return config_loader.load_mcp_servers()


def _angebotene(*, auch_aus: bool = False) -> list[FremdWerkzeug]:
    return angebotene(_registry(), primaer_id=_PRIMARY_ID,
                      primaer_url=transport.resolve_mcp_url(), auch_aus=auch_aus)


def definitionen() -> list[dict[str, Any]]:
    """Die Definitionen für das Modell (OpenAI-Funktionsform)."""
    return [w.definition for w in _angebotene()]


def fuer_die_uebersicht() -> list[FremdWerkzeug]:
    """Auch die im Studio abgeschalteten — nur für die Werkzeugübersicht, die sie zeigen muss,
    damit man sie wieder einschalten kann (Paket 15). Nie ans Modell, nie an :func:`rufen`."""
    return _angebotene(auch_aus=True)


async def rufen(modellname: str, arguments: dict[str, Any]) -> tuple[str, str]:
    """``(text, art)`` wie ``client.call_mcp_tool_status`` — bei einem Fehler ist ``text`` die
    Meldung ohne Präfix (den setzt der Client), ``art`` aus ``tool``/``transport``/``timeout``."""
    werkzeug = next((w for w in _angebotene() if w.modellname == modellname), None)
    if werkzeug is None:
        logger.warning("Fremdwerkzeug %s nicht angeboten — nicht gerufen", modellname)
        return f"Werkzeug {modellname} ist nicht verfügbar", "tool"
    try:
        await asyncio.to_thread(assert_public_url, werkzeug.url)
    except UnsafeUrlError as grund:
        logger.warning("Fremdwerkzeug %s: Adresse abgewiesen (%s)", modellname, grund)
        return f"Der Dienst {werkzeug.server_id} ist nicht erreichbar", "tool"
    ergebnis = await transport.call_tool(werkzeug.name, arguments, url=werkzeug.url)
    if "error" in ergebnis:
        art = ergebnis["error"].get("kind")
        meldung = ergebnis["error"].get("message", "Unknown error")
        # Paket 18C/D: die Meldung kann die Eingabe wiederholen — sie steht in der Zugakte.
        logger.warning("Fremdwerkzeug %s @ %s: %s", modellname, werkzeug.url, inhalt(meldung))
        return meldung, art if art in ("tool", "timeout") else "transport"
    teile = (ergebnis.get("result") or {}).get("content") or []
    text = "\n".join(t.get("text", "") for t in teile
                     if isinstance(t, dict) and t.get("type") == "text")
    logger.info("Fremdwerkzeug %s lieferte %d Zeichen", modellname, len(text))
    if len(text) > HOECHSTENS_ZEICHEN:
        text = f"{text[:HOECHSTENS_ZEICHEN]}\n[… gekürzt: {len(text)} Zeichen insgesamt]"
    return text, ""
