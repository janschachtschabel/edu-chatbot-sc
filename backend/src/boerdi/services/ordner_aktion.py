"""„Als Themenbaum-Entwurf übernehmen“ in ``ui_upload`` (Paket U3-1b, Plan 2026-11-04 §16.5).

Die Person hat im Browser einen Ordner erfasst und will seine Struktur als Entwurf. Die geprüfte
Antwort (``aktion: ordner_als_entwurf``) trägt den Ordnerbaum; daraus entsteht hier — ohne LLM —
ein Strukturentwurf (``quelle: ordner``, ``ui_module/strukturentwurf_ordner``), der als offene Frage
unter der Antwort steht, genau wie die Brücke aus dem Bestand (``services/strukturentwurf_aktion``).
Gerufen in ``graph/nodes/preflight`` nach der Sicherheitsprüfung, die die Ordnernamen schon gelesen
hat (``upload_antwort.sicherheit``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.ui_bloecke import DEBUG_KEY, fuer_den_debug_block, neuer_block
from boerdi.i18n import bot_text, resolve_locale
from boerdi.services.db_sessions import save_message, update_session
from boerdi.ui_module import katalog, schalter
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_merken as entwurf_merken
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.antwort import merke_frage
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from boerdi.ui_module.rahmen import zeile
from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

AKTION = "folders_as_draft"


def ist_ordner_als_entwurf(geprueft: dict[str, Any] | None) -> bool:
    """Ist die geprüfte Antwort des Zugs „Ordnerstruktur als Entwurf“ aus ``ui_upload``?"""
    return bool(geprueft and geprueft.get("modul") == UPLOAD
                and (geprueft.get("daten") or {}).get("aktion") == "ordner_als_entwurf")


async def handle_folders_as_draft(session: AsyncSession | None, req: ChatRequest,
                                  session_state: dict, geprueft: dict[str, Any]) -> ChatResponse:
    lang = resolve_locale(req.environment.locale)
    struktur = (geprueft.get("daten") or {}).get("struktur") or {}
    anzeige = zeile(struktur.get("name"), 120) or bot_text(lang, "action.folderDraft.ohneTitel")
    debug = DebugInfo(persona=session_state.get("persona_id", ""), intent="I03", state="S3",
                      pattern=f"ACTION: {AKTION}", tools_called=[],
                      entities=session_state.get("entities", {}))

    async def nur_text(schluessel: str) -> ChatResponse:
        text = bot_text(lang, schluessel, title=anzeige)
        await save_message(session, req.session_id, "assistant", text, debug=debug.model_dump())
        return ChatResponse(session_id=req.session_id, content=text, debug=debug)

    gemeldet = STRUKTURENTWURF in (req.environment.ui_module or [])
    if not (gemeldet and schalter.aktiv(STRUKTURENTWURF)):
        logger.info("%s: Entwurf nicht gemeldet oder im Studio abgeschaltet", AKTION)
        return await nur_text("action.folderDraft.inactive")
    manifest = katalog.katalog()[STRUKTURENTWURF]
    daten = aus_ordnern(struktur, ersatz_titel=bot_text(lang, "action.folderDraft.ohneTitel"))
    if daten is not None and (katalog.daten_fehler(manifest, daten) or se.fehler(daten)):
        logger.info("%s: Umformung passt nicht zum Vertrag", AKTION)
        daten = None
    if daten is None:
        return await nur_text("action.folderDraft.empty")

    block = neuer_block(STRUKTURENTWURF, manifest["version"], manifest["art"], daten,
                        st.textfassung(daten))
    entities = session_state.setdefault("entities", {})
    merke_frage(entities, block)
    # Der Entwurf aus den Ordnern ersetzt den gemerkten (Querschnitts-Review 2026-11-06, Q4): ein
    # Folgezug mit ``vorlage`` nähme sonst einen älteren KI-Entwurf oder griffe auf einen alten
    # ``draft`` im Vorgang zurück. Anders als Bestandsknoten gingen die Ordnernamen schon durch die
    # Sicherheitsprüfung dieses Zugs (``sicherheits_text``).
    entwurf_merken.aus_bloecken(entities, [block])
    await update_session(session, req.session_id, entities=entities)
    debug.tools_called = [STRUKTURENTWURF]
    text = bot_text(lang, "action.folderDraft.header", title=anzeige)
    await save_message(session, req.session_id, "assistant", text,
                       debug={**debug.model_dump(), DEBUG_KEY: fuer_den_debug_block([block])})
    return ChatResponse(session_id=req.session_id, content=text, debug=debug, quick_replies=[],
                        ui=UiInfo(ui_bloecke=[block]))
