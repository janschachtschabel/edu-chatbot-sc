"""Die Nachrichtenkette für den Tool-Loop bauen (P12/P14, Port aus ALT).

Fidelity-Port-Ausnahme zur ~300-Zeilen-Regel (Spec §0.7): das Modul kann nicht kleiner
werden als die eine Funktion darin — ``_assemble_messages`` hat 333 Zeilen und ist per
AST-Gate abgenommen (29/29). Erlischt mit dem Cutover.

Aus ``tool_loop`` herausgelöst. Eigene Aufgabe, eigener Änderungsgrund: hier
entsteht, WAS das Modell zu sehen bekommt — System-Prompt, Verlauf, RAG-Kontext,
vorgeholte Karten, gerahmter Fremdtext. Wie daraufhin Werkzeuge gerufen werden,
steht in ``tool_loop``; der Abschluss-Fallback in ``tool_loop_fallback``.

Die Importe im Funktionsrumpf sind ALT-treu aufgeschoben und bleiben dort.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from boerdi.domain.inline_grouping import (
    _redact_search_content_for_llm,
    _ui_box_state_footer,
)
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.services.mcp.parsers import parse_wlo_cards

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)


async def _assemble_messages(
    session: AsyncSession,
    message: str,
    history: list[dict],
    pattern_output: dict[str, Any],
    pattern_label: str,
    session_state: dict,
    available_rag_areas: list[str] | None,
    rag_config: dict[str, Any] | None,
    blocked_tools: list[str],
    prefetched_tool: dict[str, Any] | None,
    prefetched_extras: list[dict[str, Any]] | None,
    canvas_state: dict | None,
    system: str,
    _inline_grouping_mode: bool,
    _pattern_sources_decl: Any,
    _rag_allowed_for_pattern: bool,
) -> tuple[
    list[dict], list[dict], list[str], list, bool, list[str], bool,
    int, float, int,
]:
    """Baut den Messages-Stack fuer ``generate_response`` auf (Phasen
    P12+P14: System + Canvas-Kontext + history[-10:], RAG-Always-Prefetch
    als simulierter Tool-Call, MCP-Prefetch-Injektion primary/extras,
    Card-Dedupe per node_id, UI-Box-Status-Message,
    tools_called/outcomes-Seeding).

    NEU-Deviationen ggue. ALT llm_tool_loop.py:239-563: ``session`` ist als
    erster Parameter vorangestellt (pg-DI fuer ``get_rag_context`` — ALT
    holte sich die sqlite-Verbindung im rag_service selbst), und die
    ``resolve_discipline_labels``-Aufrufe sind gedroppt (ALT-No-op-Stub,
    Praezedenz lp_fast_path). Rest verbatim modulo Import-Pfade.

    Returns ``(messages, all_cards, tools_called, outcomes,
    knowledge_prefetched, always_areas, mcp_prefetched, _RAG_TOP_K,
    _RAG_MIN_SCORE, _RAG_MAX_CHARS_PER_AREA)`` — Stack + Akkumulatoren
    plus die vom Tool-Loop weitergelesenen Prefetch-Flags und
    Retrieval-Settings.
    """
    messages = [{"role": "system", "content": system}]

    # Inject the current canvas state as an additional system context.
    # This lets the LLM reference or modify what the user currently sees
    # in the canvas pane (material text, card grid), not just the chat history.
    if canvas_state and canvas_state.get("mode") and canvas_state.get("mode") != "empty":
        c_mode = canvas_state.get("mode")
        c_title = (canvas_state.get("title") or "").strip()
        c_type = (canvas_state.get("material_type") or "").strip()
        c_md = (canvas_state.get("markdown") or "").strip()
        c_cards = canvas_state.get("cards_count") or 0
        parts = [
            f"Canvas-Modus: {c_mode}",
        ]
        if c_title:
            parts.append(f"Titel: {c_title}")
        if c_type:
            parts.append(f"Material-Typ: {c_type}")
        if c_mode == "cards":
            parts.append(f"Angezeigte Kacheln: {c_cards}")
        if c_md and c_mode != "cards":
            parts.append("Aktueller Canvas-Inhalt (Markdown):\n" + c_md[:4000])
        canvas_ctx = (
            "[Kontext: Canvas-Pane rechts im Widget]\n" + "\n".join(parts) +
            "\n\nDer Nutzer sieht diesen Canvas-Inhalt parallel zum Chat. "
            "Wenn er sich mit 'hier', 'das', 'die Aufgabe', 'der Text' o.ae. "
            "auf Canvas-Inhalte bezieht, antworte direkt darauf. Verweise auf "
            "einzelne Abschnitte/Aufgaben/Kacheln, wenn hilfreich."
        )
        messages.append({"role": "system", "content": canvas_ctx})

    for h in history[-10:]:
        messages.append(h)

    # ── Pre-fetch only "always" areas, on-demand areas via LLM tool call ──
    # "always" areas: pre-fetched and injected (guaranteed to be available)
    # "on-demand" areas: only queried when LLM explicitly calls query_knowledge
    knowledge_prefetched = False
    always_areas: list[str] = []  # tracked for redundant-call guard in tool loop
    # Retrieval-Defaults — ueberschreibbar via ENV oder rag-retrieval.yaml
    # (siehe boerdi.services.rag.retrieval.get_retrieval_settings). Aktuelle
    # Werte bleiben 15 / 0.30, damit bestehende Installationen unveraendert laufen.
    from boerdi.services.rag.retrieval import get_retrieval_settings as _get_rag_settings
    _rag_settings = _get_rag_settings()
    _RAG_TOP_K = _rag_settings["top_k"]
    _RAG_MIN_SCORE = _rag_settings["min_score"]
    _RAG_MAX_CHARS_PER_AREA = _rag_settings["max_chars_per_area"]
    # Pattern-Gate-Log + Prefetch-Trigger (siehe Berechnung oben).
    _logger.info(
        "rag-prefetch-gate: pattern=%s sources=%r → allowed=%s",
        pattern_output.get("pattern_id") or pattern_label,
        _pattern_sources_decl,
        _rag_allowed_for_pattern,
    )
    if available_rag_areas and rag_config and _rag_allowed_for_pattern:
        always_areas = [
            a for a in available_rag_areas
            if rag_config.get(a, {}).get("mode") == "always"
        ]

        if always_areas:
            from boerdi.services.rag.retrieval import get_rag_context as _get_rag_ctx
            # Side-channel out_sources: collect the filenames of the top
            # chunks the prefetch picked. Used downstream by
            # ``_attach_guide_qr`` (services/guide_markers.py) to surface
            # the EXACT source URL via ``rag_url_index``, instead of the
            # generic Domain-Hauptseite.
            _prefetch_sources: list[str] = []
            prefetch_ctx = await _get_rag_ctx(
                session, message, areas=always_areas, top_k=_RAG_TOP_K,
                min_score=_RAG_MIN_SCORE,
                max_chars_per_area=_RAG_MAX_CHARS_PER_AREA,
                out_sources=_prefetch_sources,
            )
            if _prefetch_sources:
                used_src = session_state.setdefault("_rag_top_sources", [])
                for s in _prefetch_sources:
                    if s not in used_src:
                        used_src.append(s)
            _logger.info(
                "RAG pre-fetch for areas %s: %d chars",
                always_areas, len(prefetch_ctx) if prefetch_ctx else 0,
            )
            if prefetch_ctx:
                knowledge_prefetched = True
                # Track prefetched areas in session_state so the Guide-QR
                # injector (services/guide_markers.py:_attach_guide_qr) sieht
                # sie als *Kandidaten*. Es ist nicht garantiert, dass der Bot
                # die Quelle wirklich nutzt — der Injektor prüft anschließend
                # via Brand-Regex am Bot-Response-Text, ob die Area
                # tatsächlich verwendet wurde.
                used = session_state.setdefault("_rag_areas_used", [])
                for _a in always_areas:
                    if _a and _a not in used:
                        used.append(_a)
                # Inject as a completed tool call — tell the LLM ALL always-areas were searched
                areas_label = ", ".join(always_areas)
                messages.append({"role": "user", "content": message})
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "prefetch_knowledge",
                        "type": "function",
                        "function": {
                            "name": "query_knowledge",
                            "arguments": json.dumps({
                                "area": always_areas[0],
                                "query": message,
                            }),
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": "prefetch_knowledge",
                    "content": (
                        f"[Bereits durchsuchte Bereiche: {areas_label}]\n\n"
                        + prefetch_ctx[:12000]
                    ),
                })

    if not knowledge_prefetched:
        messages.append({"role": "user", "content": message})

    # ── Speculative MCP prefetch injection ─────────────────────────
    # If the turn setup spawned a speculative MCP search in parallel with
    # safety and pattern selection, the result lands here as `prefetched_tool`.
    # We inject it as a completed assistant tool-call so the LLM sees the
    # data already available and (in most cases) skips its own tool round.
    mcp_prefetched = False
    mcp_prefetch_cards: list[dict] = []
    if (
        prefetched_tool
        and prefetched_tool.get("name")
        and prefetched_tool.get("result_text")
        and prefetched_tool["name"] not in (blocked_tools or [])
    ):
        _name = prefetched_tool["name"]
        _args = prefetched_tool.get("arguments") or {}
        _txt = prefetched_tool["result_text"]
        try:
            # Welle E v4+12 (Sprint K rev2, 2026-05-27): Topic-Pages-
            # Primary-Prefetch braucht ``parse_wlo_topic_page_cards``,
            # damit das ``topic_pages``-Variant-Array gefüllt wird — sonst
            # rendert das Frontend die Cards als „Sammlung" statt
            # „Themenseite". Bug-Befund: bei „Klimawandel"-Suche feuerte
            # der Primary-Tool ``search_wlo_topic_pages`` korrekt, aber
            # ``parse_wlo_cards`` verlor die Variant-Annotation → keine
            # Themenseiten-Box im Chat-Widget.
            if _name == "search_wlo_topic_pages":
                from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards as _ptp
                mcp_prefetch_cards = _ptp(_txt) or []
            else:
                mcp_prefetch_cards = parse_wlo_cards(_txt) or []
            if _name == "search_wlo_collections":
                for c in mcp_prefetch_cards:
                    c.setdefault("node_type", "collection")
        except Exception:
            mcp_prefetch_cards = []
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "prefetch_mcp",
                "type": "function",
                "function": {
                    "name": _name,
                    "arguments": json.dumps(_args),
                },
            }],
        })
        messages.append({
            "role": "tool",
            "tool_call_id": "prefetch_mcp",
            "content": frame_untrusted(_name, _redact_search_content_for_llm(
                _name, _txt, mcp_prefetch_cards, _inline_grouping_mode)),
        })
        mcp_prefetched = True

    # Extra-prefetches — Themenseiten + Einzelinhalte (oder die jeweils
    # andere Kombination) laufen im Turn-Setup parallel zum primary spec_task.
    # Wir injizieren JEDEN als simulated tool call, damit der LLM den
    # GESAMTEN Treffer-Pool (Themenseite + Sammlung + Einzelinhalt) im
    # current turn sieht. Effekt: er kann fundiert 5 IDs auswählen, kennt
    # die Titel/Beschreibungen für seine Intro-Prosa, UND kann in folge-
    # turns auf jeden einzelnen Treffer per node_id Bezug nehmen (z.B.
    # für Remix-Anfragen).
    prefetched_extras_cards: list[dict] = []
    if prefetched_extras:
        from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards as _ptp
        for _i, _ex in enumerate(prefetched_extras):
            _ex_name = _ex.get("name") or ""
            _ex_args = _ex.get("arguments") or {}
            _ex_text = _ex.get("result_text") or ""
            if not _ex_name or not _ex_text:
                continue
            if _ex_name in (blocked_tools or []):
                continue
            # Cards parsen mit dem richtigen Parser. topic_pages liefert
            # variant-Arrays, normale Such-Tools nicht.
            try:
                if _ex_name == "search_wlo_topic_pages":
                    _ex_cards = _ptp(_ex_text) or []
                else:
                    _ex_cards = parse_wlo_cards(_ex_text) or []
                if _ex_name == "search_wlo_collections":
                    for _c in _ex_cards:
                        _c.setdefault("node_type", "collection")
            except Exception:
                _ex_cards = []
            prefetched_extras_cards.extend(_ex_cards)
            # In messages als simulated tool call einbinden — eindeutige
            # tool_call_id pro extra, damit OpenAI's tool-result-pairing
            # nicht durcheinanderkommt.
            _tc_id = f"prefetch_extra_{_i}"
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": _tc_id,
                    "type": "function",
                    "function": {
                        "name": _ex_name,
                        "arguments": json.dumps(_ex_args),
                    },
                }],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": _tc_id,
                "content": frame_untrusted(_ex_name, _redact_search_content_for_llm(
                    _ex_name, _ex_text, _ex_cards, _inline_grouping_mode)),
            })

    # Tool calling loop
    # mcp_prefetch_cards = primary; prefetched_extras_cards = extras.
    # Beide dedupen per node_id, damit Mehrfach-Listing nicht passiert
    # (gleicher Treffer kann z.B. in collections- UND content-Suche
    # auftauchen).
    all_cards: list[dict] = []
    _seen_ids: dict[str, dict] = {}
    for _c in list(mcp_prefetch_cards) + list(prefetched_extras_cards):
        _nid = _c.get("node_id") if isinstance(_c, dict) else None
        if _nid and _nid in _seen_ids:
            _existing = _seen_ids[_nid]
            if not _existing.get("topic_pages") and _c.get("topic_pages"):
                _existing["topic_pages"] = _c["topic_pages"]
            if not _existing.get("topic_page_url") and _c.get("topic_page_url"):
                _existing["topic_page_url"] = _c["topic_page_url"]
            continue
        if _nid:
            _seen_ids[_nid] = _c
        all_cards.append(_c)
    # UI-Box-Status nach Prefetch-Phase: separate ``role: system``-Message,
    # damit die LLM gleich beim ersten Tool-Loop-Schritt weiß, was nach
    # Prefetch sichtbar wäre. Greift nur im inline_grouping_mode — sonst
    # wäre die Info redundant (Tile-Cards werden flach gerendert).
    _initial_footer = _ui_box_state_footer(all_cards, _inline_grouping_mode)
    if _initial_footer.strip():
        messages.append({
            "role": "system",
            "content": (
                "Status der UI-Boxen aus den Prefetch-Tool-Calls:"
                + _initial_footer
            ),
        })
    tools_called: list[str] = []
    outcomes: list = []  # ToolOutcome list (Triple-Schema T-23)
    if knowledge_prefetched:
        tools_called.append("query_knowledge (prefetch)")
    if mcp_prefetched:
        tools_called.append(f"{prefetched_tool['name']} (prefetch)")
        from boerdi.api.schemas import ToolOutcome
        outcomes.append(ToolOutcome(
            tool=prefetched_tool["name"],
            status="success" if mcp_prefetch_cards else "empty",
            item_count=len(mcp_prefetch_cards),
        ))
    if prefetched_extras:
        from boerdi.api.schemas import ToolOutcome
        for _ex in prefetched_extras:
            _ex_name = _ex.get("name") or "?"
            tools_called.append(f"{_ex_name} (prefetch-extra)")
            outcomes.append(ToolOutcome(
                tool=_ex_name,
                status="success",
                item_count=0,  # zähle hier nicht detailliert — primary deckt's ab
            ))
    return (
        messages, all_cards, tools_called, outcomes,
        knowledge_prefetched, always_areas, mcp_prefetched,
        _RAG_TOP_K, _RAG_MIN_SCORE, _RAG_MAX_CHARS_PER_AREA,
    )
