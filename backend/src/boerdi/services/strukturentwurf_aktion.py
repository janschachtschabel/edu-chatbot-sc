"""Direktaktion ``edit_collection_as_draft`` (Paket U2, Plan 2026-11-04 T-13).

„Als Entwurf bearbeiten“ im Themenbaum.

Der Bestandsbaum (``ui_themenbaum``) zeigt nur, was es in WLO gibt. Diese Aktion macht aus der
Sammlung seiner Wurzel einen bearbeitbaren Strukturentwurf (``ui_strukturentwurf``, Quelle
``wlo``) — ohne LLM: das Baum-Werkzeug mit den Vorgaben des Themenbaums
(``datenquelle.laden``), dann ``strukturentwurf_bestand.aus_bestand``. Drosselung und
Sicherheitsprüfung laufen davor in ``graph/nodes/preflight`` wie bei jeder Direktaktion.

**Bewusst** (T-13): Die Garantie „Bestandsknoten nie an die KI“ gilt für den Themenbaum weiter.
Den Entwurf sieht die KI, sobald die Person ihn übernimmt oder dazu schreibt — als
Kompaktfassung (``strukturentwurf_antwort``); der Text dieser Blase nennt keine Punkte.

Angeboten nur, wenn der Entwurf im Studio aktiv ist, das Widget ihn meldet und das Werkzeug in
diesem Zug angeboten wäre (Sperren, Studio, Modus der Einbettung — wie ``themenbaum_aktion``).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Collection
from typing import TYPE_CHECKING, Final

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.ui_bloecke import DEBUG_KEY, fuer_den_debug_block, neuer_block
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services.agent_tools import angebotene_mcp_werkzeuge
from boerdi.services.db_sessions import save_message, update_session
from boerdi.services.direct_actions import _wiederholen_chip
from boerdi.ui_module import datenquelle, katalog, schalter
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.antwort import merke_frage
from boerdi.ui_module.namen import STRUKTURENTWURF, THEMENBAUM
from boerdi.ui_module.strukturentwurf_bestand import aus_bestand
from boerdi.ui_module.themenbaum import KNOTEN_UUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

AKTION: Final = "edit_collection_as_draft"
_KENNUNG: Final = re.compile(KNOTEN_UUID)
_TITEL_ZEICHEN: Final = 160


def _antwort(req: ChatRequest, text: str, debug: DebugInfo, *, chip: bool = False
             ) -> ChatResponse:
    lang = resolve_locale(req.environment.locale)
    return ChatResponse(session_id=req.session_id, content=text, debug=debug,
                        quick_replies=[_wiederholen_chip(req, lang)] if chip else [])


async def handle_edit_collection_as_draft(session: AsyncSession, req: ChatRequest,
                                          session_state: dict, *,
                                          blocked_tools: Collection[str]) -> ChatResponse:
    """Entwurf aus der Sammlung ``action_params.collection_id`` (Titel ``title``)."""
    lang = resolve_locale(req.environment.locale)
    params = req.action_params or {}
    kennung, roh_titel = params.get("collection_id"), params.get("title")
    titel = " ".join(roh_titel.split())[:_TITEL_ZEICHEN] if isinstance(roh_titel, str) else ""
    if not isinstance(kennung, str) or not _KENNUNG.match(kennung):
        return ChatResponse(session_id=req.session_id,
                            content=bot_text(lang, "action.missingCollectionId"))
    anzeige = titel or bot_text(lang, "action.collectionFallbackTitle")
    debug = DebugInfo(persona=session_state.get("persona_id", ""), intent="I03", state="S3",
                      pattern=f"ACTION: {AKTION}", tools_called=[],
                      entities=session_state.get("entities", {}))

    gemeldet = STRUKTURENTWURF in (req.environment.ui_module or [])
    if not (gemeldet and schalter.aktiv(STRUKTURENTWURF)):
        logger.info("%s: Entwurf nicht gemeldet oder im Studio abgeschaltet", AKTION)
        text = bot_text(lang, "action.draft.inactive", title=anzeige)
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
        return _antwort(req, text, debug)
    werkzeug = datenquelle.werkzeug(katalog.katalog()[THEMENBAUM]) or ""
    angeboten = angebotene_mcp_werkzeuge(allow_curation=False, blocked_tools=list(blocked_tools),
                                         tool_mode=req.environment.tool_mode)
    daten = None
    abgelehnt = False
    if werkzeug in angeboten:
        geladen = await datenquelle.laden(THEMENBAUM, {"nodeId": kennung})
        # N5 (Review, Befund 6): nicht zugänglich — eigener Satz, kein „Erneut versuchen“.
        abgelehnt = geladen.art == datenquelle.ABGELEHNT
        daten = aus_bestand(geladen.payload, titel,
                            ersatz_titel=bot_text(lang, "action.draft.ohneTitel")
                            ) if geladen.payload is not None else None
        manifest = katalog.katalog()[STRUKTURENTWURF]
        if daten is not None and (katalog.daten_fehler(manifest, daten) or se.fehler(daten)):
            logger.info("%s: Umformung passt nicht zum Vertrag", AKTION)
            daten = None
    else:
        logger.info("%s: %s in diesem Zug nicht angeboten", AKTION, werkzeug)
    if daten is None:
        text = bot_text(lang, "action.tree.notReadable" if abgelehnt
                        else "action.draft.loadFailed", title=anzeige)
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
        return _antwort(req, text, debug, chip=werkzeug in angeboten and not abgelehnt)

    manifest = katalog.katalog()[STRUKTURENTWURF]
    block = neuer_block(STRUKTURENTWURF, manifest["version"], manifest["art"], daten,
                        st.textfassung(daten))
    entities = session_state.setdefault("entities", {})
    merke_frage(entities, block)
    # Gegenreview 2026-11-05: ein älterer gemerkter KI-Entwurf gehört nicht mehr zum Gespräch —
    # sonst nähme der Folgezug ihn als Vorlage statt des Bestands-Entwurfs.
    entities.pop(entwurf_merken.KEY, None)
    await update_session(session, req.session_id, entities=entities)
    debug.tools_called = [STRUKTURENTWURF]
    text = bot_text(lang, "action.draft.header", title=anzeige)
    await save_message(session, req.session_id, "assistant", text,
                       debug={**debug.model_dump(), DEBUG_KEY: fuer_den_debug_block([block])})
    return ChatResponse(session_id=req.session_id, content=text, debug=debug, quick_replies=[],
                        ui=UiInfo(ui_bloecke=[block]))
