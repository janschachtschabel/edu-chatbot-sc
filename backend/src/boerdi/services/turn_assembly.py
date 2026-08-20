"""Turn-assembly (P4-5 Respond prerequisite; port of ALT ``chat_turn_assembly.py``):
``_assemble_cards_and_qrs`` — the P20–P24 turn tail that turns the raw MCP card dicts
+ routing decision into the final ``(cards, quick_replies, page_action, pagination,
response_text)`` the Respond node returns.

Phases: card enrichment (preview_url synthesis + topic-page default description) ->
``_build_cards`` + ``PaginationInfo`` (built BEFORE any group trims) + session refs
(``_last_collections``/``_last_contents``) -> the QR cascade (forced > inline > none >
speculative consistency-gate > exact ``generate_quick_replies`` call, incl. orphan-cancel
of an unused speculative task) -> ``_attach_guide_qr`` + guide-marker strip +
collection-relevance fallback QR -> ``page_action`` (canvas payload >
card-suppression-without-topic > show_results/canvas_show_cards).

Mutates ``session_state`` in-place; returns the 5-tuple (``response_text`` is in the
return because the guide-marker strip rebinds it). Home = ``services/`` (awaits the QR
LLM + the speculative task).

**NEU-Portierung:** verbatim body-port — every statement of ``_assemble_cards_and_qrs`` is
byte-identical to ALT (AST-diff gate). The only deviations are the 8 module-level import
roots (``app.`` -> ``boerdi.``): schemas -> ``api.schemas``; the cards cluster + ``PAGE_SIZE``
-> ``domain/cards/build``; ``_strip_guide_markers_from_text`` -> ``domain/guide_markers`` and
``_attach_guide_qr`` -> ``services/guide_markers`` (ALT's combined ``chat_guide_markers``
import is split across the two NEU homes); ``_qr_default_count`` -> ``domain/quick_reply_policy``;
``_retrieve_task_exception`` -> ``obs/tasks``; ``generate_quick_replies`` ->
``services/quick_replies_llm``; ``get_repo_base_url`` -> ``services/config_loader``. Boundaries
stay top-imports so tests patch them on THIS module (ALT convention).

**simplify:** ~300 lines / 6 phases — kept as one cohesive verbatim unit so the AST-diff gate
proves 0 logic divergence (precedent: lp_fast_path, canvas_fast_path, prefetch); a
behaviour-preserving split follows once the Respond node is wired.
"""

from __future__ import annotations

import asyncio  # in Annotationen genutzt (asyncio.Task, PEP 563)
import json
import logging
from typing import Any

from boerdi.api.schemas import ChatRequest, PaginationInfo
from boerdi.domain.agent_pattern import AGENT_PATTERN_ID, HYBRID_PATTERN_ID
from boerdi.domain.auth_qr import inject_auth_qr
from boerdi.domain.cards.build import (
    PAGE_SIZE,
    _build_cards,
    _collection_matches_topic,
    _is_themenseite_card,
)
from boerdi.domain.guide_markers import _strip_guide_markers_from_text
from boerdi.domain.quick_reply_policy import _qr_default_count
from boerdi.i18n import resolve_locale
from boerdi.obs.tasks import _retrieve_task_exception
from boerdi.services.config_loader import get_repo_base_url
from boerdi.services.guide_markers import _attach_guide_qr
from boerdi.services.quick_replies_llm import generate_quick_replies
from boerdi.services.response_tool_selection import curation_blocked_by_mode

logger = logging.getLogger(__name__)


async def _assemble_cards_and_qrs(
    req: ChatRequest,
    env: dict,
    session_state: dict,
    usage_acc: dict,
    classification: Any,
    classification_dict: dict,
    winner: Any,
    pattern_output: dict,
    _canvas_payload_out: dict | None,
    _canvas_forced_quick_replies: list | None,
    _qr_mode: str,
    _qr_max: int | None,
    _qr_spec_task: asyncio.Task | None,
    _effective_pattern_id: str,
    response_text: str,
    wlo_cards_raw: list,
    _host_qr_max: int | None = None,
) -> tuple:
    """Phasen P20–P24 von ``_chat_impl``: preview_url-Synthese +
    Themenseiten-Default-Description (Card-Enrichment), _build_cards +
    PaginationInfo (VOR den Gruppen-Trims — NOTE im Netz-Docstring) +
    Session-Refs (_last_collections/_last_contents), QR-Kaskade
    (forced > inline > none > spekulatives Konsistenz-Gate > exakter
    Nach-Call, inkl. Orphan-Cancel), _attach_guide_qr + Guide-Marker-
    Strip + Collection-Relevanz-Fallback-QR sowie page_action
    (Canvas-Payload > Card-Suppression ohne Thema > show_results/
    canvas_show_cards).

    Parameter-Reihenfolge: req, env, session_state, usage_acc,
    classification, classification_dict, winner, pattern_output,
    _canvas_payload_out, _canvas_forced_quick_replies, _qr_mode,
    _qr_max, _qr_spec_task, _effective_pattern_id, response_text,
    wlo_cards_raw, _host_qr_max (O-B2, additiv mit Default: die
    Chip-Gesamtzahl des Gastgeber-Mix, von assemble ueber
    ``domain.quick_reply_policy.host_qr_max`` geklammert).

    Mutiert ``session_state`` in-place (entities._last_collections/
    _last_contents; ``_inline_quick_replies``-Pop) — kein Rebind, keine
    Rückgabe nötig. ``_qr_spec_task`` wird hier nur konsumiert/gecancelt
    (kein Rebind; nach P24 gibt es keinen Leser mehr — AST-geprüft).

    Returns (5-Tupel): (cards, quick_replies, page_action, pagination,
    response_text). ``response_text`` wegen Guide-Marker-Strip (Rebind)
    in der Rückgabe.
    """
    # 6d. Synthesize a preview_url for any card that still lacks one.
    #     The edu-sharing preview endpoint accepts just the nodeId. Host
    #     wird zur Laufzeit aus ``REPO_BASE_URL`` aufgelöst, damit Staging-
    #     Nodes auf Staging-Previews zeigen (sonst 404).
    _PREVIEW_BASE = (
        f"{get_repo_base_url()}/edu-sharing/preview"
        "?nodeId={nid}&storeProtocol=workspace&storeId=SpacesStore"
    )
    for c in wlo_cards_raw:
        if not c.get("preview_url") and c.get("node_id"):
            c["preview_url"] = _PREVIEW_BASE.format(nid=c["node_id"])
        # Default description for bare topic-page cards so they don't look
        # empty in the UI. Only fills the gap, never overwrites real data.
        if c.get("topic_pages") and not (c.get("description") or "").strip():
            title = (c.get("title") or "").strip() or "das gewaehlte Thema"
            c["description"] = (
                f"Themenseite \"{title}\" — kuratierte Einstiegsseite mit "
                "Sammlungen, Materialien und weiterführenden Links, "
                "von der WLO-Fachredaktion zusammengestellt."
            )

    # 7. Build WloCard objects — send all, frontend limits display
    all_cards_raw = wlo_cards_raw
    cards = _build_cards(all_cards_raw, classification.persona_id)

    # Build pagination info so frontend knows to limit display.
    # All cards are already in the response — has_more=False because
    # there is nothing more to load from the server (client-side
    # "Mehr anzeigen" reveals the hidden ones).
    pagination = None
    if len(cards) > PAGE_SIZE:
        pagination = PaginationInfo(
            total_count=len(cards),
            skip_count=0,
            page_size=PAGE_SIZE,
            has_more=False,
        )

    # 7b. Store all shown cards in session for follow-up (learning paths, lesson prep)
    collection_refs = []
    content_refs = []
    for c in all_cards_raw:
        if c.get("node_type") == "collection" and c.get("node_id"):
            collection_refs.append({
                "node_id": c["node_id"],
                "title": c.get("title", ""),
            })
        elif c.get("node_id"):
            # Store enough fields that a later Lernpfad-rebuild (Priority 1
            # in the LP router) can reconstruct visually identical cards —
            # especially preview_url for thumbnails. Without this, LP cards
            # re-hydrated from session lose their previews and appear as
            # blank placeholders even though search results just had them.
            content_refs.append({
                "node_id": c["node_id"],
                "title": c.get("title", ""),
                "description": (c.get("description") or "")[:200],
                "url": c.get("url", ""),
                "wlo_url": c.get("wlo_url", ""),
                "preview_url": c.get("preview_url", ""),
                "learning_resource_types": c.get("learning_resource_types", []),
                "disciplines": c.get("disciplines", []),
                "educational_contexts": c.get("educational_contexts", []),
                "keywords": c.get("keywords", []),
                "license": c.get("license", ""),
                "publisher": c.get("publisher", ""),
            })
    if collection_refs:
        session_state["entities"]["_last_collections"] = json.dumps(
            collection_refs[:10]
        )
    if content_refs:
        session_state["entities"]["_last_contents"] = json.dumps(
            content_refs[:15]
        )

    # 8. Generate AI quick replies based on format_follow_up
    #    - "quick_replies": always generate (pattern expects clickable options)
    #    - "inline": pattern has conversational hooks in text, still generate
    #      quick replies as additional options
    #    - "none": skip quick replies (rare — only for terminal patterns)
    #    - Canvas degradation (material-type missing): use forced 12-chip list
    follow_up_mode = pattern_output.get("format_follow_up", "quick_replies")
    # Inline quick-replies (CHAT_INLINE_QUICK_REPLIES) — when generate_response()
    # produced both the answer AND quick_replies in a single LLM call via the
    # respond_to_user tool, the result lands here. Saves the separate ~1-2s
    # quick_replies LLM round-trip. Only honour it when at least one reply
    # came back; an empty list still falls through to the regular generator.
    _inline_qr = (
        session_state.get("_inline_quick_replies")
        if isinstance(session_state, dict) else None
    )
    if isinstance(_inline_qr, list) and _inline_qr:
        # Strip from session_state so the next turn doesn't reuse stale QR.
        session_state.pop("_inline_quick_replies", None)
    else:
        _inline_qr = None
    _qr_spec_consumed = False
    if _canvas_forced_quick_replies:
        quick_replies = list(_canvas_forced_quick_replies)
        # O-B2 (2026-08-20): nennt der Gastgeber zu seinen Chips eine
        # Gesamtzahl, füllt das Modell die restlichen Plätze — seine Chips
        # bleiben vorn und ungekürzt (gekappt wird die Anzahl). Inline-QRs
        # aus der Antwort sind die Gratis-Füllung; erst ohne sie zahlt der
        # Mix einen Generator-Call mit genau der Restzahl. Ohne Gesamtzahl
        # gilt weiter das harte Überschreiben (O-B-Vertrag).
        if _host_qr_max is not None:
            quick_replies = quick_replies[:_host_qr_max]
            _fill_n = _host_qr_max - len(quick_replies)
            _fill: list[str] | None = _inline_qr if _fill_n > 0 else []
            if _fill_n > 0 and _fill is None:
                try:
                    _fill = await generate_quick_replies(
                        message=req.message,
                        response_text=response_text,
                        classification=classification_dict,
                        session_state=session_state,
                        usage_acc=usage_acc,
                        count=_fill_n,
                    )
                except Exception as _mix_err:
                    # Wie beim exakten Nach-Call unten: QRs sind optionale
                    # UX — ein LLM-Schluckauf lässt die Host-Chips stehen.
                    logger.warning("mix quick_replies failed: %s", _mix_err)
                    _fill = []
            _kenne = {q.strip().casefold() for q in quick_replies}
            for _q in _fill or []:
                if len(quick_replies) >= _host_qr_max:
                    break
                if (_q or "").strip().casefold() in _kenne:
                    continue
                _kenne.add((_q or "").strip().casefold())
                quick_replies.append(_q)
    elif _inline_qr is not None:
        quick_replies = _inline_qr
    elif _qr_mode == "none":
        # QR-Policy none: kein Generator-Call (und unten kein Auto-
        # Followup). Deterministische System-QRs — forced Slot-Optionen
        # oben, Tour-Navigation, Lotsen-Button via _attach_guide_qr —
        # bleiben bewusst aktiv.
        logger.info(
            "quick_replies: mode=none (pattern %s) — Generator übersprungen",
            _effective_pattern_id,
        )
        quick_replies = []
    elif follow_up_mode != "none":
        _qr_result: list[str] | None = None
        if _qr_spec_task is not None:
            # Konsistenz-Gate (deterministisch): Die spekulativen QRs
            # wurden für eine inhaltliche Antwort gebaut. Wird die
            # Antwort unerwartet zur Rückfrage (außer bei M03, wo der
            # Spec-Prompt genau dafür Slot-Optionen liefert) oder ist
            # sie leer/Fehler, fällt der Pfad auf den exakten Call.
            _spec_gate_ok = bool((response_text or "").strip()) and not (
                (response_text or "").rstrip().endswith("?")
                and _effective_pattern_id not in ("M03",)
            )
            if _spec_gate_ok:
                try:
                    _spec_qrs = await _qr_spec_task
                    _qr_spec_consumed = True
                    if _spec_qrs:
                        _qr_result = _spec_qrs
                        logger.info(
                            "quick_replies: speculative angenommen "
                            "(pattern %s, %d Vorschläge — kein Nach-Call)",
                            _effective_pattern_id, len(_spec_qrs),
                        )
                except Exception as _sq_err:
                    logger.warning("speculative QR await failed: %s", _sq_err)
                    _qr_spec_consumed = True
            if _qr_result is None:
                logger.info(
                    "quick_replies: speculative verworfen (Gate/leer) — "
                    "exakter Nach-Call (pattern %s)", _effective_pattern_id,
                )
        if _qr_result is None:
            _qr_call_count = _qr_max if _qr_max is not None else _qr_default_count()
            if _qr_call_count <= 0:
                # Globale Anzahl 0 = keine generierten QRs (Anzeige-Tab).
                _qr_result = []
            else:
                try:
                    _qr_result = await generate_quick_replies(
                        message=req.message,
                        response_text=response_text,
                        classification=classification_dict,
                        session_state=session_state,
                        usage_acc=usage_acc,
                        count=_qr_call_count,
                    )
                except Exception as _qr_err:
                    # Quick replies are optional UX — never crash a successful main
                    # response on a B-API/LLM blip in the QR call. Degrade to none.
                    logger.warning("main flow quick_replies failed: %s", _qr_err)
                    _qr_result = []
        quick_replies = _qr_result
    else:
        quick_replies = []

    # Verwaisten Spec-Task aufräumen (forced/inline/none/Gate-Fail-Pfade):
    # canceln + Exception einsammeln, damit kein "never retrieved" entsteht.
    if _qr_spec_task is not None and not _qr_spec_consumed:
        logger.info(
            "quick_replies: speculative Task gecancelt — QRs kamen aus %s "
            "(pattern %s)",
            "forced-Liste" if _canvas_forced_quick_replies
            else "Inline-Antwort" if _inline_qr is not None
            else "Policy/Gate",
            _effective_pattern_id,
        )
        _qr_spec_task.cancel()
        _qr_spec_task.add_done_callback(_retrieve_task_exception)

    # Webseiten-Lotse: deterministisch einen Bring-mich-hin-QR an Position
    # 0 setzen, wenn die User-Frage zu einer bekannten WLO-Seite passt
    # UND noch kein Guide-QR vom LLM dabei ist. Greift nur, wenn der User
    # Guide-Mode aktiv hat — sonst No-op.
    quick_replies = _attach_guide_qr(req, quick_replies, session_state, response_text=response_text)

    # Welle C Sprint 6 Hotfix — Lotsen-Marker aus Bot-Text strippen.
    #
    # Bug-Report: Bei Lotsen-Modus AUS erschien im Chat-Text ein
    # roher ``guide|Label|URL``-String (Markdown frisst ``__`` davor zu
    # Bold-Markup, übrig bleibt ``guide|...``). Das Marker-Format gehört
    # AUSSCHLIESSLICH in ``quick_replies``, niemals in den Antwort-Text.
    # Das LLM schmuggelt es trotzdem hin und wieder rein, weil das Tool-
    # Schema den Marker als Beispiel referenziert.
    #
    # Defensiv: bei jeder Antwort die Marker aus dem Response-Text
    # entfernen — sicher, weil das Marker-Format nie legitim im Bot-Text
    # auftaucht (Lotsen-Buttons werden ausschließlich über quick_replies
    # gerendert).
    response_text = _strip_guide_markers_from_text(response_text)

    # Collection-Relevanz: wenn nur Sammlungen geliefert wurden und keine
    # davon das Topic im Titel traegt, biete prominent den Wechsel zu
    # Einzelmaterialien an. Der User erkennt so sofort, dass die Sammlung
    # nur am Rand passt, und kann mit einem Klick tiefer suchen.
    _topic_for_check = (session_state.get("entities", {}).get("thema") or "").strip()
    if _topic_for_check and cards and not _canvas_forced_quick_replies:
        _all_coll = all(c.node_type == "collection" for c in cards)
        if _all_coll and not _collection_matches_topic(cards, _topic_for_check):
            _fallback_reply = f"Zeig mir stattdessen Einzelmaterialien zu {_topic_for_check}"
            if _fallback_reply not in (quick_replies or []):
                # Insert at position 0, trim list to <=4 to stay within UI
                quick_replies = [_fallback_reply] + (quick_replies or [])
                quick_replies = quick_replies[:4]

    # C5-c2: Wollte das Muster kuratieren, ohne dass für diesen Zug ein
    # Zugangsblock gilt, bekam die Person bisher nur den ehrlichen Satz des
    # Bots (E3) und keine Handhabe. Die zwei Chips geben ihr die Wahl:
    # anmelden — oder ausdrücklich ohne weitersuchen.
    #
    # Absichtlich als LETZTE Station: der Relevanz-Rückfall darüber setzt
    # ebenfalls an Position 0 und kürzt auf vier; davor eingesetzt wanderte
    # die Anmeldung wieder nach hinten oder fiele ganz heraus.
    quick_replies = inject_auth_qr(
        quick_replies,
        blocked=curation_blocked_by_mode(pattern_output),
        lang=resolve_locale(getattr(req.environment, "locale", None)),
    )

    # 9. Build page_action
    #    Priority:
    #     1. Canvas-open/update (M10 or action handler) — dominates
    #     2. Host-page integration (/suche etc.) — legacy show_results
    #     3. Widget-context with cards — canvas_show_cards (Phase 1: move tiles to canvas)
    page_action = None
    if _canvas_payload_out:
        page_action = _canvas_payload_out
    elif cards:
        # Sicherheitsfilter: wenn die Suche ohne konkretes Thema/Fach lief,
        # sind die "Treffer" in aller Regel Müll (z.B. "Wortschatz" oder
        # "Startseite Mathematik" für eine Anfrage "Ich suche etwas zu
        # einem Thema"). Cards leeren — Engine fragt erst nach dem Thema.
        _has_real_topic = bool(
            (session_state.get("entities", {}).get("thema") or "").strip()
            or (session_state.get("entities", {}).get("fach") or "").strip()
        )
        # Ausnahme: Discovery-Pattern (Fachportale-Übersicht / Themen-
        # Drilldown / Themenseiten-Übersicht) zeigen per Definition eine
        # globale Liste — Filterung wäre falsch, weil der User EXPLIZIT
        # genau diese Übersicht angefragt hat. Auch reine Themenseiten-
        # Cards (mit topic_pages-Eigenschaft) gelten als "echte Treffer"
        # und werden nicht unterdrückt.
        _is_discovery_pattern = winner.id in ("M07", "M08")
        _has_topic_page_cards = any(_is_themenseite_card(c) for c in cards)
        # Ausnahme 2 (H6, live gemessen): die Schleifen-Maschinen. Der Filter
        # schliesst von „kein Slot" auf „die Suche lief ohne Thema". Im Bestand
        # stimmt das, denn dort füllt der Klassifikator die Slots und die Suche
        # wird daraus gebaut. ``agent``/``hybrid`` klassifizieren nicht: dort
        # wählt das MODELL Suchbegriff und Filter selbst und übergibt sie als
        # Werkzeug-Argumente (gemessen: ``search_wlo_content(query='Optik',
        # educationalContext=…, discipline=…)``). Die Slots sind dann leer,
        # obwohl die Suche sehr wohl ein Thema hatte — der Schluss geht ins
        # Leere und löschte acht bereits geerntete Karten.
        #
        # ``agent`` kam bisher nur ZUFÄLLIG durch: sein Modell greift meist zu
        # ``search_wlo_all``, dessen Themenseiten-Karten die Ausnahme darüber
        # treffen. Wählt es ``search_wlo_content``, fielen die Karten genauso
        # weg. Ein Verhalten, das nur aus der Werkzeugwahl eines Laufs folgt,
        # ist geliehen und nicht zugesichert.
        _ist_schleifen_lauf = winner.id in (AGENT_PATTERN_ID, HYBRID_PATTERN_ID)
        _wuerde_greifen = (not _has_real_topic and not _is_discovery_pattern
                           and not _has_topic_page_cards)
        if _wuerde_greifen and not _ist_schleifen_lauf:
            logger.info(
                "Cards unterdrückt — kein konkretes Thema/Fach im Slot "
                "(pattern=%s)", winner.id,
            )
            cards = []
        elif _wuerde_greifen:
            # Der Handel wird gezählt statt stillschweigend eingegangen: die
            # Ausnahme rettet die Karten einer Suche, die das MODELL formuliert
            # hat, nimmt dafür aber den Müllkarten-Schutz ganz heraus. Wie oft
            # das gut oder schlecht ausgeht, entscheidet sich an Zügen wie
            # diesem — ohne diese Zeile wären sie in den Protokollen nicht
            # auffindbar.
            logger.info(
                "Cards behalten trotz leerem Thema/Fach-Slot — Schleifen-Lauf, "
                "die Suchbegriffe kamen vom Modell (pattern=%s, %d Karten)",
                winner.id, len(cards),
            )
        # Re-prüfen ob nach Filterung noch Cards übrig sind
    if page_action is None and cards:
        _widget_active = bool((env.get("page_context") or {}).get("widget"))
        _host_page = (not _widget_active) and env.get("page") in ("/suche", "/startseite", "/")
        if _host_page:
            page_action = {
                "action": "show_results",
                "payload": {
                    "cards": [c.model_dump() for c in cards[:pattern_output.get("max_items", 5)]],
                    "query": session_state["entities"].get("thema", req.message),
                },
            }
        else:
            # Widget-Kontext: Kacheln ins Canvas statt in den Chat.
            # Wichtig: gleiche Kachel-Liste wie die Chat-Response (cards),
            # damit die Anzeige zwischen Chat-Unterdrueckung und Canvas
            # konsistent bleibt — sonst sieht der User unterschiedliche
            # Counts je nachdem ob Canvas offen ist.
            page_action = {
                "action": "canvas_show_cards",
                "payload": {
                    "cards": [c.model_dump() for c in cards],
                    "query": session_state["entities"].get("thema", req.message),
                    "pagination": pagination.model_dump() if pagination else None,
                    "append": False,
                },
            }
    return (cards, quick_replies, page_action, pagination, response_text)
