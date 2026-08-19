"""Assemble node — P20-24 adapter (R4g).

Thin adapter that wraps the verbatim ``turn_assembly._assemble_cards_and_qrs``
(P20-24: card enrichment + ``_build_cards`` + pagination + the QR cascade +
guide-marker strip + ``page_action``) as a graph node. It reads the raw cards and
routing decision off ``ctx`` — respond produced ``wlo_cards_raw`` + ``response_text``,
route produced the pattern/QR/canvas fields — calls the service, and writes the
finished ``(cards, quick_replies, page_action, pagination, response_text)`` back.

Two NEU seams: the service takes a ``winner`` object but reads only ``winner.id``
(the discovery-pattern check), while route stores ``winner_id``/``winner_label`` as
plain strings on ``ctx`` — so a one-field ``SimpleNamespace`` shim carries the id.
``classification_dict`` is ``classification.model_dump()`` (ALT parity). No
session/DB is reached here (the QR LLM call needs none), so the node takes no
injected deps. The service is a top-level import so tests patch it on this module.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Final

from boerdi.domain.skill_precedence import merke_skill_sammlung
from boerdi.graph.state import TurnContext
from boerdi.services.turn_assembly import _assemble_cards_and_qrs

logger = logging.getLogger(__name__)

#: Wie viele erzwungene Chips ein Gastgeber höchstens setzen darf (O-B). Der
#: Deckel gilt der ANZAHL, nie dem Text: ein Chip trägt die Nachricht, die der
#: Klick sendet — ein gekürzter Chip schickte eine andere Frage, als er
#: verspricht. Sechs, weil die Chip-Leiste darüber hinaus umbricht und der
#: Gastgeber dann nicht mehr sieht, was er gesetzt hat.
MAX_ERZWUNGENE_CHIPS: Final = 6


def _erzwungene_chips(ctx: TurnContext) -> list[str]:
    """Die Chips DIESES Zuges: Gastgeber vor Canvas.

    „Hart überschreiben" (Nutzer-Entscheid 2026-08-18) heißt auch: gegen die
    eigene Mechanik. Ein Browser-Plugin, das gezielte Antworten abfangen will,
    kommt sonst gegen einen Canvas-Zustand nicht an.

    Der Rückgabewert reist im vorhandenen ``_canvas_forced_quick_replies``-Slot
    weiter — das spart nicht nur eine Weiche, sondern auch den Generator-Zug für
    die Chips (die Montage bricht ihn ab, wenn die Liste steht).
    """
    gesetzt = [c.strip() for c in (ctx.req.environment.forced_quick_replies or [])
               if c and c.strip()]
    if not gesetzt:
        return ctx.canvas_forced_quick_replies
    if len(gesetzt) > MAX_ERZWUNGENE_CHIPS:
        logger.info("Gastgeber setzte %d Chips — auf %d gekürzt (Anzahl, nicht Text)",
                    len(gesetzt), MAX_ERZWUNGENE_CHIPS)
        gesetzt = gesetzt[:MAX_ERZWUNGENE_CHIPS]
    return gesetzt


async def assemble(ctx: TurnContext) -> TurnContext:
    """Karten + Quick-Replies + ``page_action`` bauen (P20-24). Mutiert ``ctx``
    in-place und gibt ihn zurück."""
    cards, quick_replies, page_action, pagination, response_text = (
        await _assemble_cards_and_qrs(
            req=ctx.req,
            env=ctx.env,
            session_state=ctx.session_state,
            usage_acc=ctx.usage,
            classification=ctx.classification,
            classification_dict=ctx.classification.model_dump(),
            # turn_assembly liest nur ``winner.id`` (Discovery-Pattern-Check);
            # route hält id/label als Strings → 1-Feld-Shim.
            winner=SimpleNamespace(id=ctx.winner_id),
            pattern_output=ctx.pattern_output,
            _canvas_payload_out=ctx.canvas_payload,
            _canvas_forced_quick_replies=_erzwungene_chips(ctx),
            _qr_mode=ctx.qr_mode,
            _qr_max=ctx.qr_max,
            _qr_spec_task=ctx.qr_spec_task,
            _effective_pattern_id=ctx.effective_pattern_id,
            response_text=ctx.response_text,
            wlo_cards_raw=ctx.wlo_cards_raw,
        )
    )
    # Zeigte dieser Zug eine Sammlung mit freigegebenen Anleitungen? Dann für
    # die FOLGEZÜGE merken. Hier, weil an dieser Stelle beides vorliegt: die
    # fertigen Karten und der Zustand, den ``persist`` gleich schreibt
    # (``build_debug_and_update_session`` ist der einzige Schreibvorgang des
    # Zuges und läuft NACH diesem Knoten). Ohne die Notiz greift der
    # Skill-Vorrang nur bei Nutzern, die schon auf der Sammlung stehen.
    merke_skill_sammlung((ctx.session_state or {}).get("entities"), cards)
    ctx.cards = cards
    ctx.quick_replies = quick_replies
    ctx.page_action = page_action
    ctx.pagination = pagination
    ctx.response_text = response_text
    return ctx
