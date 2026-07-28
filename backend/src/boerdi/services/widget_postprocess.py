"""Async widget-modes postprocess orchestrator — verbatim port of ALT
``chat_postprocess._postprocess_response_for_widget_modes`` (P4-5).

I/O sibling of the pure sync ``domain/widget_postprocess._apply_widget_modes_postprocess``:
same ``domain/`` (pure) ↔ ``services/`` (I/O) split as ``guide_markers``. Wraps a
response AFTER the graph + direct-action handlers so host display-flags, the
inline-mode safety-net fallback search, auto-augmentation, card-pipeline-v2 curation,
guide-url re-annotation, canvas-sync and the web-links re-extraction all apply. The
module constant ``_LLM_DELIVERY_CLAIM_RE`` moved with it (sole user is this wrapper).

**NEU-Portierung:** the async fn is AST byte-identical to ALT modulo the 5 sanctioned
in-function import-path swaps (ALT bundled card-pipeline + guide-mode-service helpers
under ``app.services.*``; NEU resolves each to its real home — ``summarize_pipeline_result``
splits off to ``domain/cards/select``, the guide-mode helpers to ``domain/guide_mode``).
The two ``not modes["cards_enabled"]`` branches (auto-augment + ``_selection_collapses``)
are DEAD given the all-``True`` compat-echo of ``_widget_modes`` but are preserved
verbatim for parity + the AST-fidelity gate; simplification is deferred to a later
deliberate pass (search ``simplify:`` in the sync sibling).
"""

from __future__ import annotations

import logging
import re as _re
from typing import Any

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.content_types import (
    _card_matches_wanted_types,
    _resolve_wanted_content_types,
)
from boerdi.domain.quick_reply_policy import _qr_policy
from boerdi.domain.search_intent import _looks_like_search_query
from boerdi.domain.url_helpers import (
    _extract_web_links_from_text,
    _rewrite_external_urls_to_repo,
)
from boerdi.domain.widget_modes import _widget_modes
from boerdi.domain.widget_postprocess import _apply_widget_modes_postprocess
from boerdi.services.config_loader import card_pipeline_v2_enabled
from boerdi.services.prefetch import _fallback_inline_search

logger = logging.getLogger(__name__)


_LLM_DELIVERY_CLAIM_RE = _re.compile(
    r"\b("
    r"hab(?:e)?\s+dir|hab\s+rausgefischt|hab(?:e)?\s+gefunden|"
    r"rausgefischt|rausgezogen|rausgesucht|rausgelegt|rausgepickt|"
    r"hier\s+sind\s+(?:die\s+)?(?:passende|treffer)|"
    r"hab\s+direkt\s+(?:was|ein)|"
    r"passende\s+(?:sammlung|themenseite|treffer|material|inhalte)|"
    r"kuratierte?\s+(?:sammlung|auswahl|treffer)|"
    r"hab\s+dir\s+was\s+passend|"
    r"hab\s+ein\s+paar\s+passend|"
    r"schau\s+(?:dir|mal)|zeig\s+(?:dir|ich)"
    r")\b",
    _re.IGNORECASE,
)


async def _postprocess_response_for_widget_modes(
    req: ChatRequest, resp: ChatResponse,
    classification_entities: dict | None = None,
) -> ChatResponse:
    """Wrap response through widget-modes postprocess.

    Greift NACH ``_chat_impl`` und allen ``_handle_*``-Action-Handlern,
    damit auch direct-action-Responses (Canvas-Create, Lernpfad usw.)
    die Display-Flags des Hosts berücksichtigen.

    Idempotent: wenn alle Modes default sind (Pydantic-None → True),
    ist das ein No-Op. Bei einem Bestand-Frontend ohne neue Flags
    bleibt das Verhalten 1:1 wie vorher.

    **Inline-Mode-Safety-Net**: wenn ``cards_enabled=false`` UND die Cards
    der Response leer sind UND der LLM-Antworttext eine Liefer-Aussage
    enthält („hab dir rausgefischt", „hier sind die Treffer", …), startet
    das Backend einen Fallback-``search_wlo_content``-Aufruf mit der
    User-Frage als Query. So sieht der User die versprochenen Treffer auch
    dann, wenn der LLM-Tool-Loop sie aus irgendeinem Grund nicht
    durchgereicht hat (typisches Symptom: bot sagt „ich habe gefunden"
    aber keine Inline-Links erscheinen).
    """
    # Webseiten-Tour-Antworten sind deterministisch vorgebaut (Texte +
    # __guide__-Nav-QRs + Gruppen-QRs). Sie dürfen NICHT durch den
    # Widget-Modes-Postprocess (Card-Filter, QR-Trim auf max_count) laufen,
    # sonst würden z.B. die 7 Gruppen-Quick-Replies auf 4 gekürzt.
    if getattr(resp, "tour", None):
        return resp
    try:
        modes = _widget_modes(req)
        env = req.environment
        # Welle E (2026-05-23): Default-Flip auf True. Selbst wenn das
        # Environment-Modell aus irgendeinem Code-Pfad ohne ``guide_mode``-
        # Attribut kommt, bleibt der Lotsen-Modus an. Repo-Links sind
        # jetzt der Standard.
        guide_mode_on = bool(getattr(env, "guide_mode", True))

        # Vom LLM (via select_top_cards-Tool) gewählte IDs aus debug holen.
        # _chat_impl stasht sie in phase3_modulations.selected_card_ids.
        # Bei direct-action-Handlern (Canvas-Create etc.) ist die Liste leer
        # und wir fallen auf algorithmische Sortierung zurück — kein Bruch.
        selected_card_ids: list[str] = []
        try:
            dbg = resp.debug
            if dbg is not None:
                p3 = getattr(dbg, "phase3_modulations", None) or {}
                raw_ids = p3.get("selected_card_ids") or []
                if isinstance(raw_ids, list):
                    selected_card_ids = [str(x) for x in raw_ids if isinstance(x, str) and x.strip()]  # noqa: E501
        except Exception:
            selected_card_ids = []

        cards_for_postprocess: list[Any] = list(resp.cards or [])

        # ── Universal Medientyp-Filter (Welle C Sprint 6 Hotfix) ──────
        #
        # Bei expliziter medientyp-Vorgabe ("nur Videos", "nur Audio",
        # ``entities.medientyp=Video`` aus dem Classifier oder aus vorigen
        # Turns) raus mit Sammlungen + Themenseiten + Cards anderen
        # Typs — modus-agnostisch (also auch im Kacheln-Mode mit
        # ``cards_enabled=true``, nicht nur Inline).
        #
        # WICHTIG: ``session_state`` und ``classification`` sind im Scope
        # dieser Funktion NICHT verfügbar (nur ``req`` + ``resp`` werden
        # übergeben — Wrapper-Pattern für die Postprocess). Wir lesen die
        # finalen entities deshalb aus ``resp.debug.entities`` ab; die
        # Engine hat sie dort hingelegt, inkl. session-akkumulierter Slots.
        _debug_entities: dict[str, Any] = {}
        try:
            _dbg_obj = resp.debug
            if _dbg_obj is not None:
                _dbg_ents = getattr(_dbg_obj, "entities", None)
                if isinstance(_dbg_ents, dict):
                    _debug_entities = {
                        k: v for k, v in _dbg_ents.items()
                        if not str(k).startswith("_")
                    }
        except Exception:
            _debug_entities = {}
        _universal_wanted = _resolve_wanted_content_types(
            req.message or "",
            session_entities=_debug_entities,
            classification_entities=classification_entities,
        )
        if _universal_wanted and cards_for_postprocess:
            _before = len(cards_for_postprocess)
            cards_for_postprocess = [
                c for c in cards_for_postprocess
                if (
                    (c.get("node_type") if isinstance(c, dict)
                     else getattr(c, "node_type", None)) == "content"
                    and _card_matches_wanted_types(c, _universal_wanted)
                )
            ]
            if _before != len(cards_for_postprocess):
                logger.info(
                    "universal type-filter: %d → %d cards (medientyp=%s)",
                    _before, len(cards_for_postprocess), sorted(_universal_wanted),
                )

        # Safety-Net: bei Liefer-Aussage + Suchanfrage, aber KEINE Cards in
        # der Response (oder LLM-IDs matchen 0 Cards = Selection-Collapse).
        # Klassischer LLM-Bug: Modell behauptet etwas geliefert zu haben
        # ohne Tools gerufen zu haben (oder mit falschen IDs).
        #
        # Greift MODUS-AGNOSTISCH — vorher war's auf ``cards_enabled=false``
        # (Inline-Modus) beschränkt, dann war der Kacheln-/Canvas-Modus
        # ungeschützt: bei Liefer-Behauptung ohne Tools sah der User „habe
        # dir was gezogen" aber leere Kacheln-Lane. Lotsen-Modus verstärkte
        # das, weil dort die Lotsen-Inline-Links als Ersatz-Anker greifen.
        # Selection-Collapse bleibt Inline-spezifisch (im Kacheln-Modus
        # filtert das Frontend nicht nach IDs, alle Cards werden gezeigt).
        _claim = _LLM_DELIVERY_CLAIM_RE.search(resp.content or "")
        _query_like = _looks_like_search_query(req.message or "")
        _selection_collapses = (
            (not modes["cards_enabled"])  # nur im Inline-Pfad relevant
            and bool(selected_card_ids)
            and bool(cards_for_postprocess)
            and not any(
                (c.get("node_id") if isinstance(c, dict) else getattr(c, "node_id", None))
                in set(selected_card_ids)
                for c in cards_for_postprocess
            )
        )
        # Welle C Sprint 6 Hotfix — Pattern-Gate gegen RAG-only Patterns.
        # Wenn das aktive Pattern explizit ``tools=[]`` oder eine reine
        # RAG-Source-Konfig hat (M15 Orientierungs-Guide, M04
        # Fakten-Bulletin in Pure-RAG-Mode), darf das Safety-Net KEINE
        # MCP-Fallback-Search auslösen. User-Bug: "Was ist WirLernenOnline?"
        # → M15 (RAG-only) → LLM-Antwort enthält "zeig ich dir direkt"
        # → Delivery-Claim matched → Fallback-Search wirft 5 Content-Cards
        # in eine Definition-Antwort, die gar keine Cards haben sollte.
        _is_rag_only_pattern = False
        try:
            _dbg_obj = resp.debug
            if _dbg_obj is not None:
                _p3 = getattr(_dbg_obj, "phase3_modulations", None) or {}
                _src = _p3.get("sources") or []
                _tools = _p3.get("tools") or []
                # Reine RAG: sources enthält 'rag' UND keine MCP-Tools
                # Pure no-tools: explizit leere Tool-Liste (M15)
                if isinstance(_tools, list) and len(_tools) == 0:
                    _is_rag_only_pattern = True
                elif (
                    isinstance(_src, list)
                    and "rag" in _src
                    and "mcp" not in _src
                ):
                    _is_rag_only_pattern = True
        except Exception:
            _is_rag_only_pattern = False
        if _is_rag_only_pattern and not cards_for_postprocess:
            # Bewusster Skip — RAG-Pattern liefert per Definition keine
            # Cards. Wenn der LLM "zeig ich dir direkt" o.ä. sagt, ist das
            # ein Conversation-Hook, kein Liefer-Statement.
            logger.info(
                "safety-net skipped: RAG-only pattern (tools=%s, sources=%s) for msg=%r",
                _tools, _src, (req.message or "")[:60],
            )
            _claim = None  # Safety-Net unten greift damit nicht
        if (
            _claim
            and _query_like
            and (not cards_for_postprocess or _selection_collapses)
        ):
            _mode_label = "inline" if not modes["cards_enabled"] else "kacheln"
            logger.info(
                "safety-net (%s): %s — Fallback-Search auf '%s'",
                _mode_label,
                "leere Cards" if not cards_for_postprocess else "LLM-IDs matchen 0 Cards",
                (req.message or "")[:60],
            )
            # Fix 2026-06-10: kein Aufrufer übergibt classification_entities —
            # Fallback auf die Turn-Entities aus resp.debug, damit die
            # fach/stufe-Filter der Fallback-Suche wie designed greifen.
            fb_cards = await _fallback_inline_search(
                req.message or "",
                classification_entities or _debug_entities or {},
            )
            if fb_cards:
                logger.info("safety-net (%s): %d Cards aus Fallback",
                            _mode_label, len(fb_cards))
                cards_for_postprocess = fb_cards
                # Fallback-Cards haben frische IDs, die LLM-Auswahl ist
                # ungültig dafür — sonst würde der Filter wieder auf 0
                # zusammenklappen. Algorithmische Sortierung übernimmt.
                selected_card_ids = []

        # ── Auto-Augmentation v2: wenn LLM nur 1-2 Sammlungen/Themenseiten
        # gepickt hat, automatisch Einzelinhalte dazuholen, damit der User
        # bis zu 5 Optionen sieht. Deterministisch im Backend, statt den
        # LLM mit Mix-Logik zu belasten (zu komplex/inkonsistent).
        # Trigger:
        #   - Inline-Modus aktiv
        #   - LLM hat explizit IDs gewählt (kein Fallback-Pfad)
        #   - Selection ist < 5
        #   - ALLE gewählten Cards sind collection (Sammlung oder Themenseite)
        # Dann: search_wlo_content auf User-Frage, bis zu (5 - selection)
        # Einzelinhalte anhängen, IDs dedupen.
        if (
            not modes["cards_enabled"]
            and selected_card_ids
            and cards_for_postprocess
            and not _selection_collapses  # nur wenn die LLM-Auswahl gültig ist
        ):
            _user_msg = req.message or ""
            # session_state nicht im Scope — debug.entities ist der Snapshot.
            _wanted_types = _resolve_wanted_content_types(
                _user_msg,
                session_entities=_debug_entities,
                classification_entities=classification_entities,
            )
            _wants_specific_type = bool(_wanted_types)

            # Type-Fokus-Strict-Filter: bei „Nur Videos zu X" wählt der LLM
            # trotz Prompt-Hinweis regelmäßig auch Sammlungen oder andere
            # Typen mit (`reasoning: Zwei Videos zuerst, danach zwei Samm-
            # lungen`). Backend-seitig hier hart filtern — nur Cards mit
            # matching ``learning_resource_types`` bleiben in der Auswahl.
            # Augmentation füllt danach mit weiteren matching-Cards auf.
            if _wants_specific_type:
                _strict_ids = set()
                for _i in selected_card_ids:
                    _c = next(
                        (c for c in cards_for_postprocess
                         if (c.get("node_id") if isinstance(c, dict)
                             else getattr(c, "node_id", None)) == _i),
                        None,
                    )
                    if _c is not None and _card_matches_wanted_types(_c, _wanted_types):
                        _strict_ids.add(_i)
                if _strict_ids:
                    _before = len(selected_card_ids)
                    selected_card_ids = [i for i in selected_card_ids if i in _strict_ids]
                    if _before != len(selected_card_ids):
                        logger.info(
                            "inline-mode type-strict filter: %d → %d IDs "
                            "(Typ: %s)",
                            _before, len(selected_card_ids),
                            sorted(_wanted_types),
                        )

            _selected_set = set(selected_card_ids)
            _picked = [
                c for c in cards_for_postprocess
                if (c.get("node_id") if isinstance(c, dict)
                    else getattr(c, "node_id", None)) in _selected_set
            ]
            # Augmentations-Bedingung: LLM hat weniger als 5 gepickt UND
            # der In-Memory-Pool enthält noch ungenutzte Einzelinhalte.
            #
            # Vorher: bei Typ-Fokus ("nur Videos") wurde Augmentation komplett
            # übersprungen — das führte zu 1-Treffer-Antworten, obwohl 5+
            # Videos im Pool waren. Jetzt: bei Typ-Fokus läuft Augmentation,
            # filtert aber strikt auf die gewünschten ``learning_resource_types``,
            # damit nur Cards des angefragten Typs angehängt werden (kein
            # Audio zwischen Videos).
            _has_extra_content_in_pool = any(
                (c.get("node_type") if isinstance(c, dict)
                 else getattr(c, "node_type", None)) != "collection"
                and (c.get("node_id") if isinstance(c, dict)
                     else getattr(c, "node_id", None)) not in _selected_set
                and _card_matches_wanted_types(c, _wanted_types)
                for c in cards_for_postprocess
            )
            if (
                _picked
                and len(_picked) < 5
                and _has_extra_content_in_pool
            ):
                _needed = 5 - len(_picked)
                logger.info(
                    "inline-mode auto-augment: %d gepickt (LLM), "
                    "ergänze bis zu %d Einzelinhalte aus Pool für '%s'",
                    len(_picked), _needed, _user_msg[:60],
                )
                _existing_ids = {
                    (c.get("node_id") if isinstance(c, dict)
                     else getattr(c, "node_id", None))
                    for c in _picked
                }
                # SCHRITT 1: Bereits geladene Einzelinhalte aus
                # cards_for_postprocess nehmen (durch speculative extra-spec
                # parallel zum primary tool oft schon vorhanden). Spart MCP-
                # Round-Trip + ist konsistent mit der Card-Reihenfolge die
                # der LLM gesehen hat.
                _added = 0
                for _c in cards_for_postprocess:
                    if _added >= _needed:
                        break
                    _nid = (_c.get("node_id") if isinstance(_c, dict)
                            else getattr(_c, "node_id", None))
                    _ntype = (_c.get("node_type") if isinstance(_c, dict)
                              else getattr(_c, "node_type", None))
                    if not _nid or _nid in _existing_ids or _ntype == "collection":
                        continue
                    # Bei Typ-Fokus ("nur Videos") nur Cards des gewünschten
                    # Typs anhängen — sonst landet ein Audio zwischen Videos.
                    if not _card_matches_wanted_types(_c, _wanted_types):
                        continue
                    selected_card_ids.append(_nid)
                    _existing_ids.add(_nid)
                    _added += 1
                logger.info(
                    "inline-mode auto-augment: %d Einzelinhalte aus "
                    "vorhandenen Cards ergänzt%s",
                    _added,
                    f" (Typ-Filter: {sorted(_wanted_types)})" if _wanted_types else "",
                )
                # SCHRITT 2: Reicht der In-Memory-Pool noch nicht? Fallback
                # auf frischen search_wlo_content-Call.
                if _added < _needed:
                    try:
                        _extra = await _fallback_inline_search(
                            _user_msg, classification_entities or {},
                        )
                    except Exception as _aug_err:
                        logger.warning("auto-augment fallback failed: %s", _aug_err)
                        _extra = []
                    for _c in _extra:
                        if _added >= _needed:
                            break
                        _nid = (_c.get("node_id") if isinstance(_c, dict)
                                else getattr(_c, "node_id", None))
                        _ntype = (_c.get("node_type") if isinstance(_c, dict)
                                  else getattr(_c, "node_type", None))
                        if not _nid or _nid in _existing_ids or _ntype == "collection":
                            continue
                        if not _card_matches_wanted_types(_c, _wanted_types):
                            continue
                        cards_for_postprocess.append(_c)
                        selected_card_ids.append(_nid)
                        _existing_ids.add(_nid)
                        _added += 1
                    if _extra:
                        logger.info(
                            "inline-mode auto-augment: nach Fallback insgesamt "
                            "%d Einzelinhalte ergänzt",
                            _added,
                        )

        # ── Lotsen-URL-Rewrite VOR v2 Curation ────────────────────────
        # MUSS vor ``run_pipeline_v2`` laufen, weil v2 intern
        # ``annotate_cards_with_link`` aufruft und dabei ``card.url``
        # von der externen Provider-URL auf die Repo-Render-URL
        # überschreibt. Danach wäre die ``{external→repo}``-Map leer
        # und der LLM-Text behielte die externen URLs.
        if guide_mode_on and resp.content and cards_for_postprocess:
            try:
                _rewritten_text = _rewrite_external_urls_to_repo(
                    resp.content, cards_for_postprocess, guide_mode_on,
                )
                if _rewritten_text != resp.content:
                    resp = resp.model_copy(update={"content": _rewritten_text})
            except Exception as _rw_err:
                logger.debug("pre-v2 response_text URL rewrite skipped: %s", _rw_err)

        # Welle E (2026-05-23) — Repo-Link annotieren AUCH wenn v2-Pipeline
        # nicht aktiv ist. Vorher: ``card.link`` blieb leer im v1-Pfad,
        # Frontend fiel auf externe ``card.url`` (z.B. YouTube), das passte
        # nicht zum "Repo immer als Default"-Ziel. Jetzt: immer Repo-Link
        # auf ``card.link`` setzen, Frontend nimmt das als SSOT via
        # ``getCardPrimaryUrl``.
        if cards_for_postprocess:
            try:
                from boerdi.services.card_pipeline import (
                    annotate_cards_with_link as _v1_attach_link,
                )
                _v1_attach_link(
                    cards_for_postprocess,
                    guide_mode=guide_mode_on,
                    search_query=(req.message or ""),
                    require_allowed=guide_mode_on,
                )
            except Exception as _v1_link_err:
                logger.debug("v1 card.link annotation skipped: %s", _v1_link_err)

        # ── Option C v2 — Curation-Layer auf v1-Cards ────────────────
        # Wenn ``CARD_PIPELINE_V2=1`` aktiv UND keine direct-action UND
        # v1 hat Cards beschafft: v2 läuft als reine Curation-Schicht auf
        # v1's Pool — keine eigenen MCP-Calls. Das spart Latenz, vermeidet
        # Pool-Divergenz und greift LLM-Re-Rank konsistent.
        #
        # Aktivierungsbedingungen (alle müssen erfüllt sein):
        #   1. ``CARD_PIPELINE_V2`` aktiv
        #   2. Keine direct-action (LP, Canvas, browse-collection bauen
        #      Cards selbst und kuratieren nicht)
        #   3. v1 hat Cards beschafft (sonst ist's ein Klärungs-Turn —
        #      v2 darf da keine Cards reinhalluzinieren)
        #
        # Was v2 macht:
        #   * normalize_cards: Host-Rewrite + node_type + Dedup
        #   * select_final_cards: Mix + Relevance-Filter + LLM-Re-Rank
        #   * annotate_cards_with_link: link-Feld setzen
        #
        # Phase 10 wird v2 zur Default-Beschaffung machen — bis dahin ist
        # v1's Pool die Eingabe für v2 (gleiche Pool-Größe, gleiche IDs).
        _is_direct_action = bool((getattr(req, "action", "") or "").strip())
        if (
            card_pipeline_v2_enabled()
            and not _is_direct_action
            and cards_for_postprocess  # v1 hat Cards → v2 läuft als Curation
        ):
            try:
                from boerdi.services.card_pipeline import (  # noqa: I001
                    run_pipeline_v2 as _v2_run,
                )
                from boerdi.domain.cards.select import (
                    summarize_pipeline_result as _v2_summary,
                )
                # Welle C Sprint 6 Hotfix — Filter-Persistenz via Resolver.
                # Vorher: ``_wanted_types`` wurde NUR aus der aktuellen
                # User-Nachricht ermittelt. Folge: "nur Videos" als
                # Folge-Turn ohne nochmaliges Thema → wanted=set() (kein
                # Match) → Sammlungen/Themenseiten blieben drin, obwohl
                # User klar Einzelinhalte wollte.
                _wanted_types = _resolve_wanted_content_types(
                    req.message or "",
                    session_entities=_debug_entities,
                    classification_entities=classification_entities,
                )
                _page_ctx = (
                    getattr(req.environment, "page_context", None) or {}
                )
                _coll_id = (
                    str(_page_ctx.get("collection_id") or "").strip()
                    if isinstance(_page_ctx, dict) else ""
                ) or None
                _v2 = await _v2_run(
                    user_message=req.message or "",
                    guide_mode=guide_mode_on,
                    wanted_content_types=_wanted_types or None,
                    collection_id=_coll_id,
                    selected_node_ids=selected_card_ids or None,
                    prefetched_pool=cards_for_postprocess,  # ← v1-Pool curieren
                )
                # A/B-Log: erst v1-IDs, dann v2-Output — leicht diff-bar.
                _v1_ids = [
                    (c.get("node_id") if isinstance(c, dict)
                     else getattr(c, "node_id", ""))
                    for c in cards_for_postprocess
                ]
                logger.info(
                    "[v1] cards=%d ids=%s", len(_v1_ids), _v1_ids,
                )
                logger.info(_v2_summary(_v2))
                # Cards austauschen — v2 ist jetzt Quelle der Wahrheit.
                # selected_card_ids spiegelt die v2-Reihenfolge wider, damit
                # der Inline-Sort in _apply_widget_modes_postprocess sie
                # nicht umstellt.
                #
                # Type-Fokus ist STRICT: auch leeres v2-Ergebnis wird
                # durchgereicht — der User hat einen konkreten Inhaltstyp
                # verlangt (z.B. Arbeitsblätter), und Sammlungen/Themenseiten
                # in der Antwort wären verwirrend. Lieber "keine Treffer"
                # als falsche Mix-Cards. Bei "general" / "collection-contents"
                # gilt der alte Sicherheitsfallback (v1 bleibt, wenn v2 0
                # liefert), weil dort der Relevance-Filter manchmal zu strikt
                # ist.
                v2_intent = _v2.get("intent_kind", "")
                v2_cards = _v2.get("cards") or []
                if v2_intent == "type-focus":
                    # Strict: v2 entscheidet final.
                    cards_for_postprocess = v2_cards
                    selected_card_ids = [
                        str(c.get("node_id") or "") for c in v2_cards
                        if isinstance(c, dict) and c.get("node_id")
                    ]
                    _selection_collapses = False
                    if not v2_cards:
                        logger.info(
                            "v2 type-focus lieferte 0 Cards — leere Card-Liste "
                            "wird durchgereicht (User-Anfrage forderte "
                            "spezifischen Inhaltstyp, keine Mix-Cards).",
                        )
                elif v2_cards:
                    cards_for_postprocess = v2_cards
                    selected_card_ids = [
                        str(c.get("node_id") or "") for c in v2_cards
                        if isinstance(c, dict) and c.get("node_id")
                    ]
                    _selection_collapses = False
                else:
                    # general/collection-contents mit 0 v2-Cards: vermutlich
                    # Relevance-Filter zu strikt → v1's Cards behalten als
                    # Fallback.
                    logger.warning(
                        "v2 curation (intent=%s) lieferte 0 Cards, "
                        "behalte v1's %d Cards als Fallback.",
                        v2_intent, len(cards_for_postprocess),
                    )
            except Exception as _v2_err:
                logger.warning(
                    "v2 Curation-Layer fehlgeschlagen, bleibe bei v1: %s",
                    _v2_err,
                )

        # ── Re-Annotation der ``guide_url``-Felder für den Lotsen-Pfad ──
        # _chat_impl macht ``_attach_guide_urls`` einmal vor Response-Return.
        # Default-Limit dort ist ``max_guide_targets_per_turn`` (=5) — damit
        # bekommen Cards an Position 6+ KEIN ``guide_url``.
        #
        # Greift sowohl im Inline-Modus (cards-enabled=false) als auch im
        # Kacheln-Modus (cards-enabled=true), weil Safety-Net und Auto-
        # Augmentation in BEIDEN Modi Cards nachreichen können, die
        # zwischen _chat_impl-Run und _apply_widget_modes_postprocess
        # entstanden sind. Diese frischen Cards haben sonst keine
        # ``guide_url``, womit der Lotsen-Button („Bring mich hin") im
        # Frontend fehlt — auch bei Kacheln. Idempotent, weil
        # ``pick_guide_url`` deterministisch ist.
        if guide_mode_on and cards_for_postprocess:
            try:
                _host = (getattr(req.environment, "host", "") or "").strip()
                if _host:
                    from boerdi.domain.guide_mode import (  # noqa: I001
                        annotate_cards_with_guide_url as _annotate,
                        host_is_allowed as _host_ok,
                    )
                    if _host_ok(_host):
                        _annotate(
                            cards_for_postprocess, enabled=True, host=_host,
                            max_targets=20,
                        )
            except Exception as _ann_err:
                logger.warning("inline-mode re-annotate guide_url failed: %s", _ann_err)

        # ── Phase 4a: Card-Pipeline v2 — card.link setzen ─────────
        # ``annotate_cards_with_link`` ist idempotent: wenn v2 sie schon
        # gerufen hat, ist das hier ein no-op. Ohne v2 (Feature-Toggle
        # aus, direct-action, keine Cards) setzt dieser Aufruf card.link
        # erstmalig. Danach kann ``_build_inline_card_links`` direkt auf
        # ``card.link`` zugreifen (Single Source of Truth).
        #
        # Hinweis: der ``_rewrite_external_urls_to_repo``-Aufruf wurde
        # BEWUSST nach oben (vor v2 Curation) verschoben, weil v2 intern
        # ``annotate_cards_with_link`` ruft und dabei ``card.url`` von der
        # externen Provider-URL auf die Repo-URL überschreibt. Stünde der
        # Rewrite hier, wäre ``card.url == card.link`` (beides Repo) und
        # die ``{extern→repo}``-Map leer → no-op → LLM-Text behielte
        # externe URLs.
        try:
            from boerdi.services.card_pipeline import (
                annotate_cards_with_link as _v2_attach_link,
            )
            # ``q=``-Param der Collection-Browse-URL: bevorzugt das extrahierte
            # ``thema`` aus den Entities (z.B. "Klimawandel"), fällt nur dann
            # auf die volle User-Message zurück, wenn der Classifier noch kein
            # Thema isoliert hat. Verhindert dass die Browse-URL die ganze
            # User-Frage als Filter trägt ("Welche Materialien hast du zu
            # Klimawandel?") — was praktisch kein Repo-Match liefert.
            # Fix 2026-06-10: ``session_state`` existiert in dieser Funktion
            # nicht (NameError wurde vom except still geschluckt → die
            # thema-basierte q=-Annotation lief nie). Entities kommen hier
            # aus resp.debug (_debug_entities, oben aus dem Turn extrahiert).
            _sq_topic = (_debug_entities or {}).get("thema") or ""
            _v2_attach_link(
                cards_for_postprocess or [],
                guide_mode=guide_mode_on,
                search_query=(str(_sq_topic).strip() or (req.message or "")),
                require_allowed=guide_mode_on,
            )
        except Exception as _link_err:  # pragma: no cover — additiv, darf nicht crashen
            logger.debug("card.link annotation skipped: %s", _link_err)

        # ── Canvas-Sync: page_action.payload.cards auf v2-gecurated angleichen ──
        # Hintergrund: ``_chat_impl`` baut die ``page_action`` mit Cards
        # BEVOR der v2-Curation-Layer läuft. Wenn v2 die Card-Liste
        # filtert/umordnet (z.B. type-focus wirft Sammlungen raus), würde
        # die Canvas-Komponente noch die alte v1-Liste sehen, die Chat-Cards
        # aber die neue v2-Liste. → Inkonsistenz: User sieht im Chat die
        # Videos, im Canvas weiterhin Sammlungen.
        # Fix: nach v2-Curation + Link-Annotation die page_action-Cards
        # mit cards_for_postprocess synchronisieren.
        try:
            _pa = resp.page_action
            _pa_dict = (_pa if isinstance(_pa, dict)
                        else (_pa.model_dump() if _pa else None))
            if (
                _pa_dict
                and _pa_dict.get("action") in ("show_results", "canvas_show_cards")
                and isinstance(_pa_dict.get("payload"), dict)
                and "cards" in _pa_dict["payload"]
            ):
                _synced_cards = []
                for _c in (cards_for_postprocess or []):
                    if isinstance(_c, dict):
                        _synced_cards.append(_c)
                    elif hasattr(_c, "model_dump"):
                        try:
                            _synced_cards.append(_c.model_dump())
                        except Exception:
                            logger.debug("card model_dump failed during payload sync", exc_info=True)  # noqa: E501
                _pa_dict["payload"]["cards"] = _synced_cards
                resp = resp.model_copy(update={"page_action": _pa_dict})
                logger.debug(
                    "page_action.payload.cards synced with v2-curated cards (%d)",
                    len(_synced_cards),
                )
        except Exception as _sync_err:  # pragma: no cover — Defensiv
            logger.debug("page_action cards-sync skipped: %s", _sync_err)

        qrs, cards_out, pa, txt = _apply_widget_modes_postprocess(
            modes=modes,
            quick_replies=list(resp.quick_replies or []),
            cards=cards_for_postprocess,
            page_action=resp.page_action if isinstance(resp.page_action, dict)
                        else (resp.page_action.model_dump() if resp.page_action else None),
            response_text=resp.content or "",
            guide_mode_on=guide_mode_on,
            user_message=req.message or "",
            selected_card_ids=selected_card_ids,
        )

        # Re-Extraktion: ``_apply_widget_modes_postprocess`` kann Guide-QRs
        # (``__guide__|Label|URL``) als Bullet-Markdown an ``response_text``
        # anhängen — siehe ``_guide_inline_lines`` — und im Inline-Mode
        # (``cards-enabled=false``) zusätzlich die Treffer-Cards als Inline-
        # Markdown-Links. Beide sind im NORMALEN Layout die einzige Anzeige-
        # form für Treffer/Lotsen (sichtbare Bullets/Links im Bot-Text) und
        # MÜSSEN dort bleiben.
        #
        # Seit dem Default-Flip 2026-05-21 ist die gruppierte Box-Darstellung
        # Standard. Re-Extraktion läuft per Default, außer im LEGACY-Inline-
        # Mode:
        #   - cards_enabled=False + inline_result_grouping=False → Legacy:
        #     Cards werden als Markdown-Bullets im Text inline angehängt,
        #     die müssen sichtbar bleiben. Re-Extraktion AUS.
        #   - cards_enabled=False + inline_result_grouping=True/None →
        #     Welle-C.5-Refactor: Cards bleiben im Array, Frontend rendert
        #     sie in Boxen. Keine Inline-Bullets im Text. Re-Extraktion AN
        #     (für LLM-flowing-text-Links + Lotsen-QRs in web_links).
        #   - inline_result_grouping=False (egal cards_enabled): Legacy-
        #     Layout → Re-Extraktion AUS.
        env = req.environment
        _ig_flag = getattr(env, "inline_result_grouping", None)
        _ce_flag = getattr(env, "cards_enabled", None)
        _legacy_inline_mode = (_ce_flag is False) and (_ig_flag is False)
        _grouping_on = (_ig_flag is not False) and (not _legacy_inline_mode)

        if _grouping_on:
            _existing_links = [l.model_dump() if hasattr(l, "model_dump") else dict(l)
                               for l in (resp.web_links or [])]  # noqa: E741
            _final_txt, _new_links = _extract_web_links_from_text(txt, cards=cards_out)
            # Merge: bestehende web_links bleiben (mit ihrer Reihenfolge),
            # neue aus dem appended-Bullet-Lauf werden ergänzt, dedupliziert
            # nach URL.
            _seen_urls = {l.get("url") for l in _existing_links if isinstance(l, dict)}  # noqa: E741
            for nl in _new_links:
                if nl.get("url") not in _seen_urls:
                    _existing_links.append(nl)
                    _seen_urls.add(nl.get("url"))
        else:
            _final_txt = txt
            _existing_links = [l.model_dump() if hasattr(l, "model_dump") else dict(l)
                               for l in (resp.web_links or [])]  # noqa: E741

        # Welle E (2026-05-23) — Quick-Replies-Limit aus display-rules
        # auch im Postprocess anwenden. Sonst kann _attach_guide_qr /
        # Auto-Followup das Studio-Setting overrunnen.
        try:
            from boerdi.services.config_loader import load_display_rules_config as _ldr
            _qr_max = int((_ldr().get("quick_replies") or {}).get("max_count", 4) or 0)
            _qr_max = max(0, min(6, _qr_max))
            # QR-Policy (2026-06-10): per-Pattern-Anzahl überschreibt den
            # globalen Deckel. Pattern-ID aus dem Debug-Label ("M09 (…)").
            try:
                _dbg = resp.debug
                _dbg_pattern = (
                    getattr(_dbg, "pattern", None)
                    or (_dbg.get("pattern") if isinstance(_dbg, dict) else "")
                    or ""
                )
                _, _p_qr_max = _qr_policy(_dbg_pattern)
                if _p_qr_max is not None:
                    _qr_max = _p_qr_max
            except Exception:
                logger.debug("pattern QR-policy lookup failed", exc_info=True)
            if qrs and len(qrs) > _qr_max:
                qrs = qrs[:_qr_max]
        except Exception:
            logger.debug("quick-reply cap enforcement failed", exc_info=True)

        # ChatResponse rekonstruieren — Pydantic-Modell aufgrund von
        # Validierungsregeln kopieren wir per model_copy(update=...).
        return resp.model_copy(update={
            "content": _final_txt,
            "cards": cards_out,
            "quick_replies": qrs,
            "page_action": pa,
            "web_links": _existing_links,
        })
    except Exception as _e:  # pragma: no cover — postprocess darf nie blockieren
        logger.warning("widget-modes postprocess failed: %s", _e)
        return resp
