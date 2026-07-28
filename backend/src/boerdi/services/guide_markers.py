"""Guide-marker *attach* half (P4-5 assembly prerequisite; I/O sibling of the pure
``domain/guide_markers`` strip half). Port of ALT ``chat_guide_markers.py``'s attach
cluster:

* ``_attach_guide_qr`` — deterministically insert a "bring-me-there" guide QR at the
  head of the quick-replies (``guide_qr_injector.inject_guide_qr``), gated by
  guide-mode + host allow-list; falls back to ``_strip_guide_qrs`` when the gate is
  closed so a stray LLM-emitted ``__guide__|…`` never reaches the user.
* ``_attach_guide_urls`` — annotate ``card.guide_url`` on inline cards AND on a
  ``canvas_show_cards`` page-action payload (``annotate_cards_with_guide_url``).

Both touch services/config → this is the ``services/`` layer; the strip helpers stayed
pure in ``domain/guide_markers``. The two function bodies are byte-identical to ALT
modulo the documented import-root swaps (AST-diff gate): ``guide_mode_service`` ->
``boerdi.domain.guide_mode``, ``guide_qr_injector`` / ``config_loader`` ->
``boerdi.services``. ``_strip_guide_qrs`` is imported from ``domain/guide_markers``
(a same-module bare call in ALT) — an added module import, AST-neutral for the body.
ALT's ``import re`` is dropped: the regex lives only in the strip half.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from boerdi.domain.guide_markers import _strip_guide_qrs

if TYPE_CHECKING:  # nur für Typprüfer/IDE — die Annotationen sind Strings (PEP 563)
    from boerdi.api.schemas import ChatRequest

logger = logging.getLogger(__name__)


def _attach_guide_qr(
    req: ChatRequest,
    quick_replies: list[str],
    session_state: dict[str, Any] | None = None,
    response_text: str | None = None,
) -> list[str]:
    """Webseiten-Lotse: deterministisch einen Bring-mich-hin-QR an der
    Spitze der Quick-Replies einfügen.

    Trigger-Reihenfolge (siehe ``guide_qr_injector.inject_guide_qr``):
    1. LLM hat schon ``__guide__|...`` produziert → no-op.
    2. User-Frage matcht eine Regel aus ``guide_qr_injector._RULES``
       (z.B. "wie kann ich mitmachen" → /mitmachen).
    3. Bot hat ``query_knowledge(area=…)`` mit einer bekannten Area
       aufgerufen (verfolgt in ``session_state['_rag_areas_used']``)
       → URL der RAG-Quelle anbieten (z.B. WissenLebtOnline →
       wissenlebtonline.de).

    No-op wenn Guide-Mode aus oder Host nicht allow-listed. Fehler
    werden geschluckt — Quick-Replies sind Pure-UX-Sugar und dürfen
    einen erfolgreichen Antwort-Turn niemals blockieren.
    """
    try:
        env = req.environment
        # Hard gate: Lotsen-Modus AUS → ALLE Guide-QRs entfernen, nicht
        # nur Injektor überspringen. Das LLM kann eigenmächtig
        # ``__guide__|...``-Einträge erzeugen (Tool-Schema lädt es ein),
        # die dürfen aber nicht zum User durchschlagen, wenn der Toggle
        # bewusst aus ist. Gleiches gilt, wenn der Host nicht auf der
        # Allow-Liste steht.
        guide_on = bool(getattr(env, "guide_mode", False))
        host = (getattr(env, "host", "") or "").strip()
        if not guide_on or not host:
            return _strip_guide_qrs(quick_replies)
        from boerdi.domain.guide_mode import host_is_allowed  # noqa: I001 — verbatim ALT order
        from boerdi.services.guide_qr_injector import inject_guide_qr
        from boerdi.services.config_loader import load_guide_mode_config
        if not host_is_allowed(host):
            return _strip_guide_qrs(quick_replies)
        rag_areas: list[str] = []
        rag_top_sources: list[str] = []
        if isinstance(session_state, dict):
            v = session_state.get("_rag_areas_used")
            if isinstance(v, list):
                rag_areas = [a for a in v if isinstance(a, str)]
            s = session_state.get("_rag_top_sources")
            if isinstance(s, list):
                rag_top_sources = [x for x in s if isinstance(x, str)]
        # Anzahl Bring-mich-hin-Buttons pro Antwort aus guide-mode.yaml
        # lesen (1-3, default 2). Mehr als 3 würde keinen Platz für
        # Folge-Fragen-QRs lassen — config_loader clamped das.
        max_guide_qrs = int(load_guide_mode_config().get("max_guide_quick_replies", 2))
        return inject_guide_qr(
            req.message or "",
            quick_replies,
            rag_areas_used=rag_areas,
            response_text=response_text,
            rag_top_sources=rag_top_sources,
            max_guide_qrs=max_guide_qrs,
        )
    except Exception as e:
        logger.warning("guide-qr injection failed: %s", e)
        return quick_replies


def _attach_guide_urls(
    req: ChatRequest,
    cards: list[Any] | None,
    page_action: dict[str, Any] | None,
) -> None:
    """Webseiten-Guide-Modus: annotate ``card.guide_url`` on every card
    in the response that the widget will render, when (a) the user has
    the guide-mode toggle on AND (b) the widget runs on an allow-listed
    host.

    Annotates BOTH the inline ``cards`` list AND any cards inside a
    ``canvas_show_cards`` page_action payload — both reach the widget.

    No-op when guide-mode is off or the host isn't whitelisted, so
    callers can invoke this unconditionally.
    """
    try:
        env = req.environment
        if not getattr(env, "guide_mode", False):
            return
        host = (getattr(env, "host", "") or "").strip()
        if not host:
            return
        from boerdi.domain.guide_mode import (
            annotate_cards_with_guide_url,
            host_is_allowed,
        )
        if not host_is_allowed(host):
            return
        if cards:
            annotate_cards_with_guide_url(cards, enabled=True, host=host)
        if (
            page_action
            and isinstance(page_action, dict)
            and page_action.get("action") == "canvas_show_cards"
        ):
            payload_cards = (page_action.get("payload") or {}).get("cards") or []
            if isinstance(payload_cards, list):
                annotate_cards_with_guide_url(
                    payload_cards, enabled=True, host=host,
                )
    except Exception as e:
        # Guide-mode is optional UX — never let it break a chat turn
        logger.warning("guide_url annotation failed: %s", e)
