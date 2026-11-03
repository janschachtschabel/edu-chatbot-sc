"""Direktaktion ``show_collection_tree`` (Paket U1-e, Plan §15 E-6): „Unterthemen öffnen“.

Der Themenbaum zeigt zwei Ebenen. Tiefer geht es wie im MCP-Widget ``browse`` über eine NEUE Karte
statt Nachladen im Block (``wlo-mcp-server-sc/src/apps/widgets/browse/main.ts:4-11``): Ein Knopf
im Baum schickt diese Aktion, und die Antwort trägt einen neuen Baum ab dem Knoten. Ohne KI;
Drosselung und Sicherheitsprüfung laufen davor in ``graph/nodes/preflight`` wie für
``browse_collection``.

Das Werkzeug der Datenquelle läuft nur, wenn ein Zug es angeboten bekäme (Review U1-e, Befund 3):
Studio-Schalter, Sperren der Sicherheitsprüfung, Modus der Einbettung — dieselbe Prüfung wie für
das Angebot des Moduls (``agent_tools.angebotene_mcp_werkzeuge``). Sonst kein Aufruf, sondern der
Hinweis „ließ sich nicht laden“. Ist der Themenbaum im Studio abgeschaltet (U1-f), ebenfalls kein
Aufruf, sondern der Satz „abgeschaltet“.

Gespeichert wird der Block (für den Verlauf) und nur der Begleitsatz als Text: Ein Folgezug liest
den Verlauf als Text — die Knoten gingen sonst doch an die KI.

**Seit U1-h** (Plan §18) klappt das Widget Unterthemen im selben Baum auf
(``POST /api/ui/themenbaum/zweig``, ``services/themenbaum_zweig``) und schickt diese Aktion nicht
mehr. Sie bleibt für zwischengespeicherte ältere Widget-Bündel und andere Aufrufer; das Angebot
(:func:`angebot`) teilen sich beide Wege.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection
from typing import TYPE_CHECKING, Final, Literal

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.ui_bloecke import DEBUG_KEY, fuer_den_debug_block
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services.agent_tools import angebotene_mcp_werkzeuge
from boerdi.services.db_sessions import save_message
from boerdi.services.direct_actions import _wiederholen_chip
from boerdi.ui_module import datenquelle, katalog, schalter
from boerdi.ui_module.namen import THEMENBAUM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

AKTION: Final = "show_collection_tree"
_KENNUNG: Final = re.compile(r"^[A-Za-z0-9-]{1,80}$")
_TITEL_ZEICHEN: Final = 160

Angebot = Literal["aus", "gesperrt", "ja"]


def _werkzeug() -> str:
    """Das Werkzeug der Datenquelle laut Manifest (Review U1-e, Befund 10)."""
    return datenquelle.werkzeug(katalog.katalog()[THEMENBAUM]) or ""


def angebot(*, blocked_tools: Collection[str], tool_mode: str | None) -> Angebot:
    """Darf der Themenbaum laden? ``aus`` (im Studio abgeschaltet, U1-f), ``gesperrt`` (das
    Werkzeug wäre in diesem Zug nicht angeboten: Studio-Schalter, Sperren, Modus der
    Einbettung — Review U1-e, Befund 3) oder ``ja``. Eine Stelle für die Direktaktion und das
    Aufklappen im Baum (U1-h, Plan §18 H-3)."""
    if not schalter.aktiv(THEMENBAUM):
        return "aus"
    angeboten = angebotene_mcp_werkzeuge(
        allow_curation=False, blocked_tools=list(blocked_tools), tool_mode=tool_mode)
    return "ja" if _werkzeug() in angeboten else "gesperrt"


async def handle_show_collection_tree(session: AsyncSession, req: ChatRequest,
                                      session_state: dict, *,
                                      blocked_tools: Collection[str]) -> ChatResponse:
    """Neuer Themenbaum ab ``action_params.collection_id`` (Überschrift ``title``).

    ``blocked_tools`` sind die Sperren der Sicherheitsprüfung dieses Zugs (``preflight``)."""
    lang = resolve_locale(req.environment.locale)
    kennung = (req.action_params or {}).get("collection_id")
    roh_titel = (req.action_params or {}).get("title")
    titel = " ".join(roh_titel.split())[:_TITEL_ZEICHEN] if isinstance(roh_titel, str) else ""
    if not isinstance(kennung, str) or not _KENNUNG.match(kennung):
        return ChatResponse(session_id=req.session_id,
                            content=bot_text(lang, "action.missingCollectionId"))

    werkzeug = _werkzeug()
    # Paket U1-f (Plan §16, F-2): ein im Studio abgeschalteter Themenbaum entsteht auch hier nicht.
    stand = angebot(blocked_tools=blocked_tools, tool_mode=req.environment.tool_mode)
    aktiv, angeboten = stand != "aus", stand == "ja"
    block = None
    if angeboten:
        block = (await datenquelle.aufruf(THEMENBAUM, {"nodeId": kennung}, titel=titel)).block
    elif aktiv:
        logger.info("show_collection_tree: %s in diesem Zug nicht angeboten", werkzeug)
    else:
        logger.info("show_collection_tree: Themenbaum im Studio abgeschaltet")
    anzeige_titel = titel or bot_text(lang, "action.collectionFallbackTitle")
    debug = DebugInfo(persona=session_state.get("persona_id", ""), intent="I03", state="S3",
                      pattern=f"ACTION: {AKTION}", tools_called=[werkzeug] if angeboten else [],
                      entities=session_state.get("entities", {}))
    if block is None:
        logger.info("show_collection_tree: kein Baum für die Sammlung")
        text = bot_text(lang, "action.tree.loadFailed" if aktiv else "action.tree.inactive",
                        title=anzeige_titel)
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
        return ChatResponse(session_id=req.session_id, content=text, debug=debug,
                            # Gesperrt hilft kein zweiter Versuch.
                            quick_replies=[_wiederholen_chip(req, lang)] if angeboten else [])

    # Der Begleitsatz ohne Titel (Review U1-e, Befund 11): die Überschrift trägt der Block.
    text = bot_text(lang, "action.tree.header")
    await save_message(session, req.session_id, "assistant", text,
                       debug={**debug.model_dump(), DEBUG_KEY: fuer_den_debug_block([block])})
    return ChatResponse(session_id=req.session_id, content=text, debug=debug,
                        ui=UiInfo(ui_bloecke=[block]))
