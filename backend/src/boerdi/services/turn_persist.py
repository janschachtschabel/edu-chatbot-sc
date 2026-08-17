"""Turn-Persistenz P25-26 + P29-33 (Port von ALT ``chat_turn_persist``).

``build_debug_and_update_session`` (P25-26): baut die ``DebugInfo`` zusammen
(Label-Auflösung, phase3_modulations, state-transition-Telemetrie, Outcomes/
Safety/Policy/Context/Token-Usage), echot ``_last_pattern`` in die Entities und
führt den EINEN ``update_session``-DB-Write des Turns aus. Läuft im
Kontrollfluss ZWISCHEN ``_assemble_cards_and_qrs`` (P20-24) und
``_finalize_links_and_metas`` (P27-28).

NEU-Deviationen ggü. ALT (frischer Port → Signatur selbst gewählt):
* ``session`` ist erster Parameter (pg-DI für ``update_session``).
* ``winner_id: str`` statt eines ``winner``-Objekts — NEU hält die Pattern-ID
  als String (kein ``PatternDef``); der einzige Zugriff war ``winner.id``.
* der Tracer ist in NEU gedroppt (assess/respond-Präzedenz) → ``trace`` bleibt
  leer statt ``tracer.entries``.
* ``update_session`` ist jsonb-nativ: ``entities`` (dict) und ``signal_history``
  (list) gehen DIREKT durch — KEIN ``json.dumps`` (ALT nutzte sqlite TEXT).

``persist_and_build_response`` (P29-33): reichert die DebugInfo für die
Persistenz an (_web_links/_query_metas/_type_focus), schreibt die Assistant-
Message, loggt das Quality-Event (config-/privacy-gated), hängt Guide-URLs an,
poliert die Quick-Replies (S3-Auto-Followup, Type-Focus-Filter, display_rules-
Gruppen-Trims, Facetten-Narrowing, max_count-Trim), routet Inline-Dokumente
(M09/M10/M11) und baut die finale ``ChatResponse``.

NEU-Deviationen ggü. ALT P29-33:
* ``session`` ist erster Parameter (pg-DI für ``save_message`` + Quality-Log).
* ``winner`` → ``winner_id: str``; ``tracer`` gedroppt (nur der M16-Resolver las
  ihn); ``env`` bleibt ein dict (``.get`` wie ALT).
* Quality-Log wird INLINE geawaitet statt ``_spawn_background`` — die Request-
  Session (``get_session``) schließt am Request-Ende, ein Fire-and-Forget liefe
  danach ins Leere (stiller Write-Verlust). +~10 ms, faithful im Effekt.
* der Haupt-Safety-Log (ALT ``chat_turn_setup``) gehört NICHT hierher, sondern in
  den turn_setup/merge-Bereich — P29-33 loggt keine Safety.
* der M16-Resolver (``_resolve_m16_topic_page_view``, ``services/topic_pages``)
  ist R6-verdrahtet: bei M16 rebindet er ``topic_page``/``cards``/``_final_text``,
  sonst no-op (``topic_page=None``, Inputs unverändert). Top-Import → Tests patchen
  ihn auf DIESEM Modul.
* ``_display_rules()`` → ``load_display_rules_config()`` direkt (NEU-Konvention).

Top-Imports (Tests patchen auf DIESEM Modul): ``update_session``, ``save_message``,
``_attach_guide_urls``, ``_apply_state_auto_followup``, ``_is_themenseite_card``,
``_build_inline_document``, ``load_display_rules_config``. LAZY funktionslokal
(Tests patchen an der Quelle): Label-Loader, ``load_quality_log_config``/
``load_privacy_config``, ``log_quality_event``, ``narrowing_quick_replies_from_metas``,
``unresolved_filter_note``.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, PreparedWriteOut
from boerdi.domain.cards.build import _is_themenseite_card
from boerdi.domain.inline_rendering import _build_inline_document
from boerdi.domain.prepared_write import single_prepared_write
from boerdi.domain.quick_reply_policy import _apply_state_auto_followup
from boerdi.domain.turn_frame import (
    CLARIFIER_PATTERN_ID,
    clear_frame,
    note_clarification,
)
from boerdi.domain.write_confirm import preview_for_display
from boerdi.i18n import CLAIM_WORDS, DEFAULT, resolve_locale
from boerdi.i18n.bot_text import bot_text
from boerdi.services.config_loader import load_display_rules_config
from boerdi.services.db_sessions import finalize_message, save_message, update_session
from boerdi.services.guide_markers import _attach_guide_urls
from boerdi.services.mcp.client import get_prepared_writes
from boerdi.services.topic_pages import _resolve_m16_topic_page_view
from boerdi.services.turn_quality import log_turn_quality

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _needs_finalize(
    cards_before: list, cards_after: list, debug_before: dict, debug_after: dict
) -> bool:
    """Did the group-trim or the M16 resolver change what the turn actually
    delivers (audit 2026-08-12, F-6)?

    Guards the follow-up write: on a normal turn nothing moves, and the hot path
    must not pay for a second UPDATE that would write the identical row.
    """
    return cards_before != cards_after or debug_before != debug_after


async def build_debug_and_update_session(
    session: AsyncSession,
    req: ChatRequest,
    session_state: dict,
    classification: Any,
    safety: Any,
    policy: Any,
    context_snapshot: Any,
    usage_acc: dict,
    winner_id: str,
    pattern_output: dict,
    new_state: str,
    new_signals: list,
    signal_history: list,
    _trans_check: dict,
    _effective_pattern_id: str,
    _effective_pattern_label: str,
    tools_called: list,
    eliminated: list,
    scores: Any,
    response_outcomes: list,
    final_confidence: Any,
) -> DebugInfo:
    """Phasen P25-26: DebugInfo-Zusammenbau + ``_last_pattern``-Echo + der einzige
    ``update_session``-DB-Write dieses Turns. Mutiert ``session_state`` in-place
    (entities._last_pattern). Returns ``debug``."""
    # 10. Debug info — resolve human-readable labels for IDs
    from boerdi.services.config_loader import (
        load_intents,
        load_persona_definitions,
        load_states,
    )
    _persona_labels = {p["id"]: p.get("label", p["id"]) for p in load_persona_definitions()}
    _intent_labels = {i["id"]: i.get("label", i["id"]) for i in load_intents()}
    _state_labels = {s["id"]: s.get("label", s["id"]) for s in load_states()}

    _pid = session_state["persona_id"]
    _iid = classification.intent_id

    debug = DebugInfo(
        persona=f"{_pid} ({_persona_labels.get(_pid, _pid)})",
        intent=f"{_iid} ({_intent_labels.get(_iid, _iid)})",
        state=f"{new_state} ({_state_labels.get(new_state, new_state)})",
        turn_type=classification.turn_type,
        signals=new_signals,
        pattern=f"{_effective_pattern_id} ({_effective_pattern_label})",
        entities={k: v for k, v in session_state["entities"].items()
                  if not k.startswith("_")},
        tools_called=tools_called,
        phase1_eliminated=eliminated,
        phase2_scores=scores,
        phase3_modulations={
            "tone": pattern_output.get("tone"),
            "formality": pattern_output.get("formality"),
            "length": pattern_output.get("length"),
            "detail_level": pattern_output.get("detail_level"),
            "max_items": pattern_output.get("max_items"),
            "card_text_mode": pattern_output.get("card_text_mode", "minimal"),
            "response_type": pattern_output.get("response_type"),
            "format_primary": pattern_output.get("format_primary"),
            "format_follow_up": pattern_output.get("format_follow_up"),
            "sources": pattern_output.get("sources", []),
            "rag_areas": pattern_output.get("rag_areas", []),
            "tools": pattern_output.get("tools", []),
            "skip_intro": pattern_output.get("skip_intro"),
            "one_option": pattern_output.get("one_option", False),
            "add_sources": pattern_output.get("add_sources", False),
            "degradation": pattern_output.get("degradation", False),
            "missing_slots": pattern_output.get("missing_slots", []),
            "blocked_patterns": pattern_output.get("blocked_patterns", []),
            "core_rule": pattern_output.get("core_rule", ""),
            # Welle C Sprint 6 — Conversation-State-Plausibilität (Telemetrie-only,
            # State wird NICHT automatisch korrigiert).
            "state_transition": {
                "prev": session_state.get("state_id") or "",
                "next": new_state,
                "plausible": _trans_check.get("plausible"),
                "reason": _trans_check.get("reason", ""),
                "expected_next_likely": _trans_check.get("prev_next_likely", []),
            },
            # Inline-Mode-Curation: vom LLM gewählte Card-IDs in Anzeige-Reihenfolge
            # (Quelle der Wahrheit für ``_apply_widget_modes_postprocess``).
            "selected_card_ids": session_state.get("_selected_card_ids") or [],
            "selected_card_reasoning": session_state.get("_selected_card_reasoning") or "",
        },
        # Triple-Schema v2
        outcomes=response_outcomes,
        safety=safety,
        confidence=final_confidence,
        policy=policy,
        context=context_snapshot,
        # NEU-Deviation: kein Tracer → trace bleibt leer (Default []).
        # Phase-1-Pattern-Hint (Shadow-Mode): LLM-Vorschlag + Engine-Match
        pattern_id_hint=getattr(classification, "pattern_id_hint", None),
        pattern_reasoning=getattr(classification, "pattern_reasoning", None),
        llm_engine_match=(
            getattr(classification, "pattern_id_hint", None) == winner_id
            if getattr(classification, "pattern_id_hint", None) else None
        ),
        # Phase-A2 Token-Cost-Tracking — aggregiert über alle LLM-Calls dieses Turns
        token_usage=usage_acc,
    )

    # Welle E — ``_last_pattern`` in entities persistieren.
    #
    # Der Satz hier nannte bis 2026-08-15 „die Routing-Rules R2/R2b/R2c" als
    # Leser. **Die gibt es in NEU nicht** (repo-weit geprüft): gelesen wird der
    # Schlüssel an genau einer Stelle, und die routet nichts —
    # ``services/eval/runner`` fragt nach einem I06-Anlauf, ob die Sitzung
    # überhaupt eine Spur trägt. Der Merker ist damit **Telemetrie und
    # Vorleistung**, nicht Steuerung; wer eine Folgeregel darauf bauen will,
    # baut den ersten Leser.
    #
    # ``_effective_pattern_id`` (nicht winner) — ein Fast-Path kann den
    # Engine-Winner überstimmt haben; wer immer liest, muss das AUSGEFÜHRTE sehen.
    try:
        _winner_id_for_persist = _effective_pattern_id or winner_id or ""
        if _winner_id_for_persist:
            session_state.setdefault("entities", {})["_last_pattern"] = _winner_id_for_persist
    except Exception:
        logger.debug("persisting _last_pattern in session state failed", exc_info=True)

    # B1–B3 — den offenen Vorgang (Frame) fortschreiben, gleiche Stelle und
    # gleiche Quelle wie ``_last_pattern``: das AUSGEFÜHRTE Muster, nicht der
    # Engine-Winner. Hat der Klärer geantwortet, zählt der Versuch; jedes andere
    # Muster schließt den Vorgang — daher verwirft ihn auch ein Themenwechsel,
    # ohne dass es dafür eine eigene Regel bräuchte.
    _entities = session_state.setdefault("entities", {})
    if (_effective_pattern_id or winner_id) == CLARIFIER_PATTERN_ID:
        note_clarification(_entities)
    else:
        clear_frame(_entities)

    # 11. Update session state in DB (jsonb-nativ: kein json.dumps).
    await update_session(
        session,
        req.session_id,
        persona_id=session_state["persona_id"],
        state_id=new_state,
        entities=session_state["entities"],
        signal_history=signal_history,
        turn_count=session_state["turn_count"] + 1,
    )
    return debug


def _boxen_erlaubt(display_rules: dict[str, Any]) -> bool:
    """Zeigt diese Anlage überhaupt Inline-Boxen?

    Derselbe Schlüssel, den ``inline_rendering._build_inline_document`` für den
    geratenen Weg liest. Hier eigens gelesen statt dort mitbenutzt: der
    Lieferweg braucht dessen Überschriften-Suche und Vorspann-Trennung gerade
    NICHT — er hat Titel und Rumpf schon getrennt vorliegen.
    """
    return bool((display_rules.get("inline_documents") or {}).get("enabled", True))


async def persist_and_build_response(
    session: AsyncSession,
    req: ChatRequest,
    env: dict,
    session_state: dict,
    classification: Any,
    winner_id: str,
    pattern_output: dict,
    spec_query: str,
    new_state: str,
    debug: DebugInfo,
    response_text: str,
    cards: list,
    quick_replies: list,
    page_action: dict | None,
    pagination: Any,
    _final_text: str,
    _web_links: list,
    _raw_metas: list,
    _query_meta_entries: list,
    _type_focus_label: str,
    _qr_mode: str,
    _qr_max: int | None,
    _effective_pattern_id: str,
    gelieferte_dokumente: list[dict[str, Any]] | None = None,
) -> ChatResponse:
    """Phasen P29-P33: DebugInfo-Anreicherung + Assistant-Persist + Quality-Log,
    guide_urls, finale QR-Politur + display_rules-Gruppen-Trims, Inline-Document-
    Routing, M16-Resolver (R6-Stub) + Unresolved-Filter-Hinweis, ChatResponse-Build.

    Rebinds von cards/quick_replies/page_action/_final_text/_web_links bleiben lokal
    — nach dem Return trägt die ChatResponse die Endwerte. Returns die fertige
    ``ChatResponse``. Deviationen: siehe Modul-Docstring.
    """
    # Widget-Sprache dieses Zuges. Einmal aufgelöst statt an jeder der vier
    # Stellen unten neu — sie ist für den ganzen Zug dieselbe (C1-f2b6a; vorher
    # stand die Zeile in f2b4 und f2b5 je einmal lokal).
    _lang = resolve_locale(getattr(req.environment, "locale", None))

    _debug_for_save = debug.model_dump()
    if _web_links:
        # Persistieren in debug_json, damit nach Refresh / Bubble-Reopen die
        # strukturierte Link-Liste via ``GET /messages`` wieder ans Frontend kommt.
        _debug_for_save["_web_links"] = _web_links
    if _query_meta_entries:
        # Analog: damit nach Restore die Search-CTA (search_url + search_term)
        # wieder erscheint.
        _debug_for_save["_query_metas"] = [m.model_dump() for m in _query_meta_entries]
    if _type_focus_label:
        # Type-Focus-Marker für die Frontend-Render-Logik (auch beim Restore).
        _debug_for_save["_type_focus"] = _type_focus_label

    # ``_final_text`` ist hier noch das ungestrippte Roh-Markdown (das Inline-
    # Document-Routing kürzt es erst weiter unten auf den Intro-Text) → wir
    # persistieren automatisch den vollen Material-Inhalt (für M11-Edit-Turns).
    _cards_for_save = [c.model_dump() for c in cards]
    _message_id = await save_message(
        session,
        req.session_id,
        "assistant",
        _final_text,
        cards=_cards_for_save,
        debug=_debug_for_save,
    )

    # 12. Quality logging (config-/privacy-gated). NEU-Deviation: INLINE geawaitet
    # statt _spawn_background — die Request-Session schließt am Request-End, ein
    # Fire-and-Forget-Task liefe danach ins Leere (stiller Write-Verlust).
    #
    # Tor und Aufruf wohnen seit 2026-08-15 in ``services/turn_quality``: sie
    # werden von den früh endenden Zügen mitbenutzt, die diesen Knoten nie
    # erreichen (Direkt-Aktionen, Schreib-Abnahme). Ein an fünf Stellen
    # kopiertes Tor wären fünf Gelegenheiten, den Aus-Schalter zu verfehlen.
    await log_turn_quality(
        session, req, debug,
        turn_count=session_state["turn_count"],
        response_length=len(response_text or ""),
        cards_count=len(cards),
        page=env.get("page", "/"),
        device=env.get("device", "desktop"),
    )

    # Webseiten-Guide-Modus: enrich cards with same-tab navigation URLs.
    _attach_guide_urls(req, cards, page_action)

    # Welle C Sprint 6 — Auto-Followup-Trigger pro Verlaufs-Phase (S3). QR-Policy
    # none unterdrückt auch das deterministische Auto-Followup.
    if _qr_mode != "none":
        quick_replies = _apply_state_auto_followup(
            state_id=new_state,
            quick_replies=quick_replies,
            has_cards=bool(cards),
            lang=_lang,
        )

    # Type-Focus QR-Filter: „Sammlungen"/„Themenseiten"-QRs sind widersprüchlich,
    # wenn der User sich gerade WEG davon (hin zu Material-Typ) bewegt hat.
    if _type_focus_label and quick_replies:
        import re as _re_qrf
        # Dieselbe Wortliste wie der Anti-Halluzinations-Wächter in
        # ``turn_links`` — sonst könnten Text und Chips nach einer
        # einseitigen Änderung Verschiedenes behaupten.
        _qr_block_re = _re_qrf.compile(
            CLAIM_WORDS.get(_lang, CLAIM_WORDS[DEFAULT]),
            _re_qrf.IGNORECASE,
        )
        _before_qr = list(quick_replies)
        quick_replies = [q for q in quick_replies if not _qr_block_re.search(q or "")]
        if len(quick_replies) < len(_before_qr):
            _dropped_qrs = [q for q in _before_qr if q not in quick_replies]
            logger.info(
                "type-focus QR-filter: dropped %d QRs (%r)",
                len(_dropped_qrs), _dropped_qrs,
            )

    # Welle E — Cards pro Box-Typ trimmen nach display_rules.groups.*; bei
    # single_content_box.enabled=false werden Materialien komplett entfernt.
    try:
        _dr = load_display_rules_config() or {}
        _dr_scb = _dr.get("single_content_box") or {}
        _dr_grp = _dr.get("groups") or {}
        if cards:
            _themenseiten = [c for c in cards if _is_themenseite_card(c)]
            _sammlungen = [
                c for c in cards
                if (getattr(c, "node_type", "") or "content") == "collection"
                   and not _is_themenseite_card(c)
            ]
            _materialien = [
                c for c in cards
                if (getattr(c, "node_type", "") or "content") == "content"
            ]

            def _trim(lst, key, default, lo=1, hi=20):
                limit = int(_dr_grp.get(key) or default)
                limit = max(lo, min(hi, limit))
                if len(lst) > limit:
                    dropped = len(lst) - limit
                    logger.info("groups.%s: kept %d, dropped %d", key, limit, dropped)
                    return lst[:limit]
                return lst

            _themenseiten = _trim(_themenseiten, "themenseiten_max", 3, 1, 20)
            _sammlungen = _trim(_sammlungen, "sammlungen_max", 3, 1, 20)

            if not _dr_scb.get("enabled", True):
                if _materialien:
                    logger.info(
                        "single_content_box DISABLED — dropped %d materials",
                        len(_materialien),
                    )
                _materialien = []
            elif _effective_pattern_id == "M09":
                # Lernpfad: die Box zeigt nur verlinkte Materialien; eigener
                # Studio-Deckel (Default 5) statt der Standard-3.
                _materialien = _trim(_materialien, "materialien_max_lernpfad", 5, 1, 8)
            else:
                _materialien = _trim(_materialien, "materialien_max", 3, 1, 8)

            # Reihenfolge: Themenseiten, dann Sammlungen, dann Materialien
            # (entspricht der visuellen Box-Reihenfolge im Frontend).
            cards = _themenseiten + _sammlungen + _materialien

        # Webseiten-Inhalte (RAG-Links) ebenfalls auf das Group-Limit trimmen.
        if _web_links:
            _wl_limit = int(_dr_grp.get("webseiten_max") or 3)
            _wl_limit = max(1, min(30, _wl_limit))
            if len(_web_links) > _wl_limit:
                logger.info(
                    "groups.webseiten_max: kept %d web_links, dropped %d",
                    _wl_limit, len(_web_links) - _wl_limit,
                )
                _web_links = _web_links[:_wl_limit]
    except Exception as _e:
        logger.warning("groups trim failed: %s", _e)

    # total_count muss die NACH dem Gruppen-Trim angezeigten Karten spiegeln
    # (PaginationInfo wurde in _assemble_cards_and_qrs VOR dem Trim gebaut).
    if pagination is not None:
        pagination = pagination.model_copy(update={"total_count": len(cards)})

    # Facetten-Eingrenzung: aus den MCP-Facetten deterministische „Nur <Typ> (N)"-
    # Quick-Replies bauen und VORNE einreihen (Self-gating: leer bei < 2 Typen).
    if cards:
        try:
            from boerdi.domain.facets import narrowing_quick_replies_from_metas
            _narrow_qrs = narrowing_quick_replies_from_metas(
                _raw_metas, max_options=2, lang=_lang)
            if _narrow_qrs:
                _existing_qrs = quick_replies or []
                quick_replies = _narrow_qrs + [
                    q for q in _existing_qrs if q not in _narrow_qrs
                ]
                logger.info(
                    "facet narrowing: prepended %d QR(s) %s",
                    len(_narrow_qrs), _narrow_qrs,
                )
        except Exception as _nf_err:
            logger.debug("facet narrowing QRs skipped: %s", _nf_err, exc_info=True)

    # S3: Steht eine Schreib-Abnahme an, ist die Zustimmung die kürzeste
    # mögliche Antwort — sie bekommt einen Knopf. Hier und nicht unten bei der
    # Box, damit der Deckel gleich darunter auch für sie gilt: ``max_count: 0``
    # heißt „keine Pillen" und ist eine Entscheidung der Redaktion, kein
    # Platzproblem. Gelesen und nicht verbraucht — verbraucht wird der Text
    # dort, wo die Box entsteht.
    if session_state.get("_write_preview"):
        _confirm_chip = bot_text(_lang, "action.write.confirmChip")
        quick_replies = [_confirm_chip, *(q for q in quick_replies if q != _confirm_chip)]

    # Welle E — Quick-Replies-Limit aus display_rules; per-Pattern ``_qr_max``
    # überschreibt den globalen Deckel. max_count: 0 → keine Pillen.
    try:
        _dr_qr = (load_display_rules_config() or {}).get("quick_replies") or {}
        _qr_trim_max = int(_dr_qr.get("max_count", 4) or 0)
        _qr_trim_max = max(0, min(6, _qr_trim_max))
        if _qr_max is not None:
            _qr_trim_max = _qr_max
        if quick_replies and len(quick_replies) > _qr_trim_max:
            logger.info(
                "quick_replies.max_count: trimmed %d → %d",
                len(quick_replies), _qr_trim_max,
            )
            quick_replies = quick_replies[:_qr_trim_max]
    except Exception as _e:
        logger.warning("quick_replies trim failed: %s", _e)

    # Welle E — Inline-Document-Routing: bei M09/M10/M11 wandert das große
    # Markdown in eine gerahmte Box (``inline_documents``); ``content`` bekommt
    # nur einen kurzen Begleittext.
    _display_rules_active = load_display_rules_config()
    inline_documents: list[dict[str, Any]] = []
    try:
        _winner_id = _effective_pattern_id or winner_id or pattern_output.get("id", "")
    except Exception:
        _winner_id = ""

    # D4: Was das Modell AUSDRÜCKLICH geliefert hat (``zeige_dokument``),
    # schlägt die Vermutung aus dem Antworttext. Der Unterschied ist nicht
    # Geschmack: der geratene Weg unten verlangt das richtige Muster, 200
    # Zeichen und ein H1 — vier Bedingungen, die zufällig zusammentreffen
    # müssen. Live gemessen 2026-08-17 stimmte nur das Muster, und ein fertiger
    # Verlaufsplan von 8.000 Zeichen fiel weg, weil das Modell den Text als
    # Zusammenfassung ohne Überschrift formuliert hatte.
    #
    # Der Rückfall bleibt vollständig erhalten: liefert das Modell nichts,
    # läuft alles wie bisher.
    if gelieferte_dokumente and not _boxen_erlaubt(_display_rules_active):
        # ``inline_documents.enabled: false`` ist die Ansage einer Anlage,
        # keine Boxen zu zeigen — sie galt bisher nur für den geratenen Weg
        # (``inline_rendering``), und eine gelieferte Box lief daran vorbei.
        # Der Inhalt darf dabei NICHT verschwinden: das Modell hat ihn nicht in
        # die Prosa geschrieben, weil das Werkzeug ihm genau das untersagt.
        logger.info("Inline-Boxen sind abgeschaltet — %d Ergebnis(se) wandern "
                    "in den Fließtext", len(gelieferte_dokumente))
        _final_text = "\n\n".join(
            [_final_text.strip(), *(d.get("content", "") for d in gelieferte_dokumente)]
        ).strip()
    elif gelieferte_dokumente:
        inline_documents = list(gelieferte_dokumente)
        logger.info("Inline-Box(en) vom Modell geliefert: %d — %s",
                    len(inline_documents),
                    ", ".join(d.get("kind", "?") for d in inline_documents))
    elif (
        _winner_id in {"M09", "M10", "M11"}
        and _final_text
        and len(_final_text.strip()) >= 200
    ):
        try:
            _topic_for_intro = (
                (session_state.get("entities") or {}).get("thema")
                or (classification.entities or {}).get("thema")
                or ""
            )
            # M09: eine leere ``## 📚 Passende Materialien``-Heading am Ende
            # strippen (die Materialien rendert das Frontend als separate Box).
            if _winner_id == "M09" and _final_text:
                import re as _re_lp_strip
                _final_text = _re_lp_strip.sub(
                    r"\n*##\s*📚\s*Passende\s*Materialien\s*\n*\Z",
                    "",
                    _final_text,
                ).rstrip()

            _docs, _intro = _build_inline_document(
                _winner_id, _final_text, _display_rules_active,
                topic=str(_topic_for_intro or "").strip(),
                extra_meta={
                    "material_type": (session_state.get("entities") or {}).get(
                        "_canvas_material_type", ""
                    ),
                },
                formality=pattern_output.get("formality", "") or "",
                lang=_lang,
            )
            if _docs:
                inline_documents = _docs
                _final_text = _intro or ""
                # Markdown steckt jetzt in der Box → daraus extrahierte Inline-
                # Links nicht zusätzlich als zweite Liste rendern.
                _web_links = []
                # Canvas-PageActions löschen, sonst packt der Postprocess das
                # Markdown zusätzlich in den Text → Doppelung Box + Text.
                if isinstance(page_action, dict) and page_action.get("action") in {
                    "canvas_open", "canvas_update", "canvas_show_cards",
                }:
                    logger.info(
                        "InlineDocument routing for %s — dropping canvas page_action (%s)",
                        _winner_id, page_action.get("action"),
                    )
                    page_action = None
        except Exception as _e:
            logger.warning("inline-document routing failed: %s", _e)

    # ── S2 (2026-08-11): die Schreib-Abnahme als eigene Box ───────────────
    # Getrennt von der Weiche oben, weil es ein anderer Vorgang ist: dort
    # wandert ERZEUGTER Text des Modells in eine Box, hier wird FREMDER Text
    # gezeigt, den der MCP-Server formuliert hat. Der Unterschied ist der
    # ganze Punkt — die Abnahme darf nicht durch das Modell hindurch.
    #
    # Verbraucht statt gelesen: die Vorschau gehört dem Zug, der sie erzeugt
    # hat. Bliebe sie stehen, zeigte jeder Folgezug sie erneut, auch einer,
    # der von etwas anderem handelt. ``pop`` macht das strukturell und nicht
    # per Konvention (vgl. ``_selected_card_ids``, das genau deshalb nur ins
    # Debug-Feld gehen darf).
    _write_preview = session_state.pop("_write_preview", "")
    if _write_preview:
        # Die Frage steht IN der Box und nicht im Fließtext: dort steht sie
        # auch dann, wenn das Modell sie vergisst. Genau das war der Befund —
        # eine Zusage, die nur im Prompt lebt, ist keine.
        _ask = bot_text(_lang, "inline.writePreview.ask")
        inline_documents = [*inline_documents, {
            "kind": "schreib_vorschau",
            "title": bot_text(_lang, "inline.title.writePreview"),
            "content": f"{preview_for_display(_write_preview)}\n\n{_ask}",
        }]

    # ── M16-Resolver (ALT chat_topic_pages._resolve_m16_topic_page_view) ──
    # Nur bei M16-Themenseiten-Turns: beste Themenseite finden → deren
    # Schwimmlinien-Inhalte als Swimlane-Boxen aufbereiten und die normalen
    # Sammlungs-/Inhalts-Boxen unterdrücken (cards=[]). Bei jedem anderen Pattern
    # kommen cards/_final_text unverändert zurück und _topic_page_view bleibt None.
    _topic_page_view, cards, _final_text = await _resolve_m16_topic_page_view(
        req, classification, winner_id, spec_query, cards, _final_text,
    )

    # Ignorierte Filter: konnte der MCP einen angefragten Filter nicht auflösen,
    # dem Nutzer ehrlich sagen, dass allgemeiner gesucht wurde (Self-gating).
    try:
        from boerdi.domain.facets import unresolved_filter_note
        _uf_note = unresolved_filter_note(_raw_metas, lang=_lang)
        if _uf_note:
            _final_text = (
                (_final_text.rstrip() + "\n\n" + _uf_note) if _final_text else _uf_note
            )
            logger.info("unresolved-filter hint appended: %s", _uf_note)
    except Exception as _uf_err:
        logger.debug("unresolved-filter note skipped: %s", _uf_err, exc_info=True)

    # E3: hat der MCP-Server die bestätigte Änderung beschrieben statt sie zu
    # schreiben, wandert sie hier in die Antwort — ausgeführt wird sie in der
    # Repository-Seite. Im Normalbetrieb ist die Liste leer.
    _writes = get_prepared_writes()
    _prepared = single_prepared_write(_writes)
    if _prepared is None and _writes:
        logger.warning(
            "%d vorbereitete Schreibzugriffe in einem Zug — keiner wird "
            "ausgeliefert, weil nicht feststellbar ist, welchem zugestimmt wurde",
            len(_writes))

    # F-6: Gespeichert wurde oben der Stand VOR Gruppen-Trim und M16-Auflösung —
    # bewusst, denn dort ist der Zug noch absturzsicher: ``_resolve_m16_topic_page_view``
    # trägt kein ``try/except``, und läge das Speichern dahinter, verlöre ein
    # Fehler dort den GANZEN Zug. Jetzt steht der ausgelieferte Endstand fest,
    # also wird die Zeile nachgezogen — sonst zeigt ``GET /messages`` nach einem
    # Reload eine andere Kartenmenge als das Gespräch und bei einem M16-Zug die
    # Schwimmlinien-Ansicht gar nicht.
    _cards_final = [c.model_dump() for c in cards]
    _debug_final = dict(_debug_for_save)
    if _topic_page_view is not None:
        _debug_final["_topic_page_view"] = _topic_page_view.model_dump()
    if _needs_finalize(_cards_for_save, _cards_final, _debug_for_save, _debug_final):
        await finalize_message(
            session, _message_id, cards=_cards_final, debug=_debug_final,
        )

    return ChatResponse(
        session_id=req.session_id,
        content=_final_text,
        cards=cards,
        follow_up=pattern_output.get("format_follow_up", "quick_replies"),
        quick_replies=quick_replies,
        debug=debug,
        page_action=page_action,
        pagination=pagination,
        query_metas=_query_meta_entries,
        web_links=_web_links,
        inline_documents=inline_documents,
        topic_page=_topic_page_view,
        display_rules=_display_rules_active,
        prepared_write=(
            PreparedWriteOut(
                method=_prepared.method,
                path=_prepared.path,
                body=_prepared.body,
                done_message=_prepared.done_message,
            )
            if _prepared is not None
            else None
        ),
    )
