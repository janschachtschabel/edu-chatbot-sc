"""Tool-calling loop for the chat turn (P5-3, port of ALT llm_tool_loop.py).

This is the orchestration core of ``generate_response``: assemble the messages
(P12/P14), run the tool-calling loop (P15), and close with a fallback when the
loop exhausts its iterations without a final answer (P16). It is deliberately
independent of the downstream SSE layer — the loop *returns* the finished
``(response_text, cards, tools_called, outcomes)`` tuple; streaming to the
widget is the caller's concern (the optional ``on_token`` seam is the only
streaming touchpoint, and it injects the *upstream* LLM-token stream, not SSE).

Home: ``services/tool_loop.py`` drops ALT's ``llm_`` module prefix, mirroring
how ALT ``chat_prefetch`` → NEU ``services/prefetch.py`` — this sits with the
other turn-orchestration services (``prefetch``, ``turn_assembly``,
``card_pipeline``, ``outcome_service``), not the ``llm_*`` generators.

The pure inline-grouping helpers ALT co-located here (``_strip_trailing_option_
lines``, the card predicates, ``_ui_box_state_footer``, ``_redact_search_
content_for_llm``) already live framework-free in ``domain/inline_grouping.py``.

Transport seam (NEU-deviation, same rewrite as every ported LLM consumer):
ALT held module-level ``client``/``MODEL`` singletons and called
``client.chat.completions.create(**build_chat_kwargs(...))``. Eiserne Regel 3
forbids module-global connection state, so the call goes through
``llm.chat_completion`` (which wires model/routing/timeout/retry/semaphore
internally). Prompt text and control flow are ALT-verbatim. Precedent:
llm_curation.py / llm_learning_path.py.

Slice status: all three phases are ported — ``_max_iterations_fallback``
(P16), ``_assemble_messages`` (P12/P14) and ``_run_tool_loop`` (P15).
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any

from boerdi.domain.inline_grouping import (
    _redact_search_content_for_llm,
    _strip_trailing_option_lines,
    _ui_box_state_footer,
)
from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.domain.untrusted_text import frame_untrusted
from boerdi.domain.write_confirm import (
    extract_confirm_token,
    is_confirmable,
    is_expired,
    redact_confirm_token,
    remember_pending,
    strip_confirm_token,
    token_for,
)
from boerdi.obs.usage import add_usage, extract_usage
from boerdi.services import llm
from boerdi.services.card_collect import CARD_YIELDING_TOOLS as _CARD_YIELDING_TOOLS
from boerdi.services.card_collect import collect_cards
from boerdi.services.llm_streaming import _stream_completion
from boerdi.services.mcp.parsers import parse_wlo_cards

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_logger = logging.getLogger(__name__)


# Die Menge wohnt seit A4c-2a bei der Logik, die sie auswertet
# (``services/card_collect``, mit ihrer Begründung); hier bleibt der Name
# gebunden, weil dieses Modul der angestammte Fundort ist und Tests ihn so lesen.
CARD_YIELDING_TOOLS = _CARD_YIELDING_TOOLS


async def _max_iterations_fallback(
    messages: list[dict],
    all_cards: list[dict],
    tools_called: list[str],
    outcomes: list,
    usage_acc: dict[str, Any] | None = None,
) -> tuple[str, list[dict], list[str], list]:
    """Abschluss-Fallback (P16) fuer ``generate_response``: der Tool-Loop hat
    max_iterations erreicht, ohne finalen Text zu liefern. Jeder Pfad liefert
    das finale ``(response_text, wlo_cards, tools_called, outcomes)``-Tupel.

    ``usage_acc`` bucht den Zusammenfassungs-Aufruf unter der eigenen Phase
    ``fallback_summary`` (K1f). Eigene Phase statt ``response``, weil ihr
    Auftauchen zugleich meldet, dass dieser Zug die Iterationsgrenze gerissen
    hat — das ist ein Qualitaetssignal, das in der Kostenschau nicht in der
    normalen Antwort untergehen soll. Der Aufruf ist trotz kurzer Ausgabe
    nicht klein: er haengt die GANZE bisherige Nachrichtenkette an.
    """
    # Fallback: if max_iterations reached without final text, generate a
    # short closing summary based on whatever we found.
    if all_cards:
        try:
            summary_resp = await llm.chat_completion(
                messages=messages + [{
                    "role": "user",
                    "content": (
                        "Bitte fasse jetzt KURZ (1–2 Sätze) zusammen, was du gefunden "
                        "hast — ohne weitere Tool-Aufrufe. Sprich den Nutzer direkt an."
                    ),
                }],
                temperature=0.4,
                usage_acc=usage_acc,
                phase="fallback_summary",
            )
            text = strip_reasoning_markers((summary_resp.choices[0].message.content or "").strip())
            if text:
                return text, all_cards, tools_called, outcomes
        except Exception as e:
            _logger.warning("Fallback summary failed: %s", e)
        return (
            f"Ich habe {len(all_cards)} passende Materialien für dich gefunden — "
            "schau sie dir gerne an:",
            all_cards, tools_called, outcomes,
        )
    return "Ich konnte leider keine Antwort generieren.", all_cards, tools_called, outcomes


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


async def _run_tool_loop(
    session: AsyncSession,
    message: str,
    classification: dict[str, Any],
    pattern_output: dict[str, Any],
    pattern_label: str,
    session_state: dict,
    rag_context: str,
    blocked_tools: list[str],
    active_tools: list[dict],
    _inline_qr_enabled: bool,
    _inline_grouping_mode: bool,
    messages: list[dict],
    all_cards: list[dict],
    tools_called: list[str],
    outcomes: list,
    knowledge_prefetched: bool,
    mcp_prefetched: bool,
    always_areas: list[str],
    _RAG_TOP_K: int,
    _RAG_MIN_SCORE: float,
    _RAG_MAX_CHARS_PER_AREA: int,
    usage_acc: dict[str, Any] | None,
    on_token: Any,
) -> tuple[str, list[dict], list[str], list] | None:
    """Tool-Calling-Loop (Phase P15) fuer ``generate_response`` — verbatim port
    of ALT llm_tool_loop.py:565-1158: tool_choice-Gates, Stream-vs-Create,
    Usage-Phase-Label, Tool-Dispatch (select_top_cards / respond_to_user /
    query_knowledge / blocked / Filter-Injektion / call_with_outcome /
    Card-Parse-Merge) und Reflection-Retry (Phase A1).

    NEU-deviations (sanctioned, see the AST fidelity gate): ``session`` is
    prepended for the pg-DI ``get_rag_context`` seam; the LLM round goes
    through ``llm.chat_completion`` / ``_stream_completion`` on SEMANTIC
    kwargs instead of ALT's ``build_chat_kwargs(model=MODEL, ...)`` +
    ``client`` singleton; usage folding uses the ``obs.usage`` names
    (``add_usage``/``extract_usage``); the ALT no-op
    ``resolve_discipline_labels`` call is dropped (lp_fast_path precedent).

    Returns: das finale ``(response_text, wlo_cards, tools_called,
    outcomes)``-Tupel (Final-Answer- oder API-Fehlerpfad) ODER ``None``
    als Fortsetzungs-Marker, wenn max_iterations ohne finale Antwort
    erreicht wurde — der Call-Site faellt dann auf
    ``_max_iterations_fallback`` (P16) durch. ``messages``/``all_cards``/
    ``tools_called``/``outcomes`` werden in-place weitergefuehrt, der
    Fallback sieht also den vollen Loop-Stand.
    """
    max_iterations = 5
    first_iteration = True
    # Phase A1 — Reflection-Loop-Flag: nur EINMAL retryen, sonst Endlosschleife
    _reflection_done = False
    # E1 (2026-08-10): der offene Bestätigungsvorgang, wie er beim EINTRITT in
    # diesen Zug aussah. Genau das macht ihn zur Zeitgrenze: eine Vorschau, die
    # weiter unten in diesem Zug entsteht, landet in ``session_state`` — aber
    # nicht mehr hier. Sie ist damit erst im nächsten Zug bestätigbar, und
    # zwischen zwei Zügen steht der Mensch. ``_run_tool_loop`` wird genau
    # einmal pro Zug betreten (``services/generate.py:153``, einzige
    # Aufrufstelle) — daran hängt diese Eigenschaft.
    # Der Schnappschuss vom Zug-Eintritt. Er wohnt in ``entities``, weil NUR
    # die fünf Spalten aus ``update_session`` einen Zug überdauern; ein
    # Schlüssel auf oberster Ebene von ``session_state`` stirbt mit der
    # Anfrage (``graph/nodes/setup.py`` baut den Zustand jeden Zug neu).
    # Bis 2026-08-11 stand er dort — dadurch war dies immer ``None`` und
    # keine Bestätigung je einlösbar.
    _pending_at_turn_start = (session_state.get("entities") or {}).get("_pending_write")

    for iteration in range(max_iterations):  # noqa: B007 — verbatim ALT (unused index)
        tool_choice: Any = None
        if active_tools:
            # Force tool call on first iteration — but NOT if context is already available
            # (pre-fetched knowledge or prior content cards already provide context)
            has_prior_content = bool(session_state.get("entities", {}).get("_last_contents"))
            # Pattern-Override: Discovery/Listing-Patterns brauchen IMMER den
            # echten Tool-Output (Karten), auch wenn RAG-Kontext da ist —
            # sonst antwortet der LLM mit einer Aufzählung in Text statt mit
            # klickbaren Karten. WLO-MCP-Calls sind günstig, also kann der
            # Extra-Round-Trip sein.
            pattern_forces_tool = bool(pattern_output.get("force_tool_use"))
            # `tools_called` enthält ggf. bereits "query_knowledge (prefetch)"
            # vom RAG-Vorabfetch — das soll force_tool_use NICHT blockieren.
            # Nur ECHTE MCP-Tool-Calls (kein "(prefetch)"-Suffix) zählen als
            # "Tool wurde schon aufgerufen, Force erfüllt".
            real_tools_called = [
                t for t in tools_called
                if not (isinstance(t, str) and "(prefetch)" in t)
            ]
            if pattern_forces_tool and first_iteration and not real_tools_called:
                tool_choice = "required"
                _logger.info(
                    "force_tool_use=true → tool_choice=required (active_tools=%d)",
                    len(active_tools),
                )
            elif (
                first_iteration
                and not tools_called
                and not knowledge_prefetched
                and not mcp_prefetched
                and not has_prior_content
            ):
                tool_choice = "required"
            first_iteration = False

        # Map pattern.length → GPT-5 verbosity. RAG/knowledge-heavy turns get
        # an extra bump so the model actually USES the prefetched context
        # rather than condensing it into a one-liner.
        _length = (pattern_output.get("length") or "mittel").lower()
        _verbosity_map = {"kurz": "low", "mittel": "medium", "lang": "high"}
        _verbosity = _verbosity_map.get(_length, "medium")
        if knowledge_prefetched or (rag_context and len(rag_context) > 500):
            # RAG context present → lift at least one notch (medium → high).
            if _verbosity == "low":
                _verbosity = "medium"
            elif _verbosity == "medium":
                _verbosity = "high"

        kwargs = dict(
            messages=messages,
            tools=active_tools or None,
            tool_choice=tool_choice,
            temperature=0.4,
            verbosity=_verbosity,
        )

        try:
            if on_token is not None:
                # Phase-2 Streaming — same kwargs but tokens arrive progressively
                # via on_token. The reconstructed _StreamedResponse exposes the
                # same attributes so the tool-loop body below is unchanged.
                resp = await _stream_completion(on_token, **kwargs)
            else:
                resp = await llm.chat_completion(**kwargs)
        except Exception as e:
            _logger.error("LLM API error: %s", e)
            return f"Fehler bei der Verarbeitung: {e}", all_cards, tools_called, outcomes

        choice = resp.choices[0]
        if usage_acc is not None:
            # A2.1 — Phase-Label je Iteration: tool-Iteration vs final response.
            # Hilft bei der Cache-Hit-Rate-Diagnose: "response"-Calls haben oft
            # keinen Cache-Hit, weil Tool-Output-Messages den Prompt variieren.
            _phase = (
                "tool_loop"
                if (choice.finish_reason == "tool_calls" and choice.message.tool_calls)
                else "response"
            )
            add_usage(usage_acc, extract_usage(resp), phase=_phase)

        # Track whether the model used the optional respond_to_user tool —
        # if so, the for-loop's tool-handling falls through and we treat it
        # as the final response instead of a continued tool round-trip.
        _inline_response_text: str | None = None
        _inline_quick_replies: list[str] = []

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            # Diagnose (2026-07-04): zählt netz-gebundene MCP-Tool-Calls PRO
            # LLM-Runde. Nur bei ≥2 in EINER Runde würde eine Parallelisierung
            # (asyncio.gather statt seriellem await) überhaupt Wall-Clock
            # sparen — diese Zeile liefert die Häufigkeitsdaten für diese
            # Entscheidung. Lokale/virtuelle Tools (Auswahl, Inline-Antwort,
            # RAG) sind kein MCP-Netz-Call und zählen nicht mit. Rein
            # beobachtend, kein Verhaltenseffekt.
            _LOCAL_TOOLS = {"select_top_cards", "respond_to_user", "query_knowledge"}
            _mcp_calls_this_round = sum(
                1 for _tc in choice.message.tool_calls
                if _tc.function.name not in _LOCAL_TOOLS
            )
            if _mcp_calls_this_round >= 2:
                _logger.info(
                    "parallel-mcp-round: %d netz-gebundene MCP-Tool-Calls in einer "
                    "Runde (%s) — Kandidat für gather-Parallelisierung",
                    _mcp_calls_this_round,
                    [tc.function.name for tc in choice.message.tool_calls],
                )
            # Convert message to a dict shape OpenAI accepts on the next call.
            # Non-streaming responses ship a Pydantic ChatCompletionMessage that
            # the SDK can re-serialize; the streaming path produces our own
            # ``_StreamedMessage`` shim, which has the same attributes but
            # isn't auto-serialized — hand it through as a plain dict so both
            # paths work uniformly.
            messages.append({
                "role": getattr(choice.message, "role", "assistant"),
                "content": getattr(choice.message, "content", None),
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    } for tc in choice.message.tool_calls
                ],
            })
            for tc in choice.message.tool_calls:
                tool_name = tc.function.name
                # B8 (2026-06-10): malformed Tool-Args (Token-Limit-Abbruch,
                # Streaming-Reassembly) warfen vorher den GANZEN Turn auf den
                # generischen Fehlerpfad. Stattdessen: als Tool-Fehler zurück-
                # melden und weiterlaufen — das LLM wiederholt den Call dann
                # mit korrektem JSON oder antwortet ohne Tool.
                try:
                    tool_args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError) as _ja_err:
                    _logger.warning("tool-call %s: malformed arguments (%s)",
                                    tool_name, _ja_err)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": ("Fehler: Die Tool-Argumente waren kein "
                                    "gültiges JSON. Bitte denselben Aufruf "
                                    "mit korrektem JSON wiederholen."),
                    })
                    continue
                tools_called.append(tool_name)

                # ── Inline-Mode-Curation: select_top_cards ────────────
                # LLM-Auswahl der finalen Treffer-Anzeige (siehe Tool-
                # Definition oben). IDs in session_state stashen — wird im
                # Postprocess (_apply_widget_modes_postprocess) genutzt, um
                # die Cards auf genau diese IDs zu filtern in dieser
                # Reihenfolge.
                if tool_name == "select_top_cards":
                    ids = tool_args.get("card_ids") or []
                    reasoning = (tool_args.get("reasoning") or "").strip()
                    # Sanitize: nur Strings, dedupe, max 5
                    clean_ids: list[str] = []
                    seen: set[str] = set()
                    for x in ids:
                        # Trim FIRST, then judge: comparing the raw value against
                        # a set of trimmed ones let " abc " slip past "abc".
                        xs = x.strip() if isinstance(x, str) else ""
                        if xs and xs not in seen:
                            clean_ids.append(xs)
                            seen.add(xs)
                        if len(clean_ids) >= 5:
                            break
                    session_state["_selected_card_ids"] = clean_ids
                    session_state["_selected_card_reasoning"] = reasoning
                    _logger.info(
                        "select_top_cards: %d IDs picked — %s",
                        len(clean_ids), reasoning[:120],
                    )
                    # Welle E (2026-05-23) — Konsistenz Prompt ↔ Anzeige:
                    # nach der Auswahl bekommt der LLM einen verschärften
                    # Reminder, dass er NUR über diese IDs sprechen darf.
                    # Backend-seitiges Trunken der älteren Tool-Results
                    # wäre noch sauberer (siehe TODO), würde aber den
                    # OpenAI-Tool-Call-Chain brechen.
                    _consistency_tail = ""
                    try:
                        from boerdi.services.config_loader import (
                            load_display_rules_config as _ldrc,
                        )
                        _dr_pak = (_ldrc().get("prompt_anzeige_konsistenz") or {})
                        _pak_excl = set(_dr_pak.get("exclude_patterns") or [])
                        if (
                            _dr_pak.get("enabled", True)
                            and (pattern_output.get("id") or "") not in _pak_excl
                            and clean_ids
                        ):
                            _consistency_tail = (
                                "\n\nWICHTIG: Im nächsten ``respond_to_user``-"
                                "Aufruf darfst du NUR über genau diese "
                                f"{len(clean_ids)} ausgewählten IDs sprechen. "
                                "Material, Sammlungen oder Themenseiten, die "
                                "in vorigen Tool-Results stehen aber NICHT in "
                                "dieser Auswahl, NICHT erwähnen — der User "
                                "sieht im Frontend nur diese gewählten Treffer. "
                                "Wenn du im Text auf Treffer Bezug nimmst: "
                                "ausschließlich auf die gewählten."
                            )
                    except Exception:  # pragma: no cover — defensive
                        _consistency_tail = ""

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": (
                            (
                                f"OK — Auswahl gespeichert ({len(clean_ids)} IDs). "
                                "Rufe jetzt respond_to_user mit der Prosa-Antwort auf."
                                if _inline_qr_enabled
                                else f"OK — Auswahl gespeichert ({len(clean_ids)} IDs)."
                            ) + _consistency_tail
                        ),
                    })
                    continue

                # ── Combined-output: model emitted FINAL answer + quick_replies ─
                # See env CHAT_INLINE_QUICK_REPLIES + the respond_to_user tool
                # definition above. Treat this as the equivalent of a
                # finish_reason == "stop" with the extracted text.
                if tool_name == "respond_to_user":
                    _inline_response_text = strip_reasoning_markers((tool_args.get("text") or "").strip())  # noqa: E501
                    qr = tool_args.get("quick_replies") or []
                    _inline_quick_replies = [
                        str(r).strip() for r in qr if isinstance(r, str) and str(r).strip()
                    ][:4]
                    # Safety net: the model occasionally ALSO writes the quick-
                    # replies / "Bring mich hin"-link as bold lines at the END of
                    # the answer text. They belong only in quick_replies (rendered
                    # as pills/buttons), not as text in the bubble — strip them.
                    _inline_response_text = _strip_trailing_option_lines(
                        _inline_response_text, _inline_quick_replies
                    )
                    # OpenAI requires every tool call to be followed by a
                    # role=tool message in the chain. Acknowledge briefly.
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "OK",
                    })
                    # The break below skips every SIBLING call of this same
                    # parallel batch, leaving them without a role=tool answer.
                    # Normally harmless (the chain is discarded), but the
                    # reflection retry further down re-sends exactly this chain
                    # — and OpenAI rejects one in which a tool_call has no tool
                    # message, so the turn degraded to an error bubble although
                    # the model's answer was already in hand (audit 2026-08-12,
                    # F-5). The answer is deliberately NOT "OK": in that retry
                    # it would tell the model a search had run when it had not.
                    _answered = {
                        m.get("tool_call_id") for m in messages
                        if isinstance(m, dict) and m.get("role") == "tool"
                    }
                    for _sibling in choice.message.tool_calls:
                        if _sibling.id in _answered:
                            continue
                        messages.append({
                            "role": "tool",
                            "tool_call_id": _sibling.id,
                            "content": ("Nicht ausgeführt: Die Antwort wurde "
                                        "bereits mit respond_to_user gegeben."),
                        })
                    # Don't process more tool calls — respond_to_user means
                    # we're done.
                    break

                # ── Handle virtual knowledge tool ──────────────
                if tool_name == "query_knowledge":
                    from boerdi.services.rag.retrieval import get_rag_context
                    area = tool_args.get("area", "general")
                    query = tool_args.get("query", message)

                    # Track explicitly-queried RAG areas in session_state so the
                    # downstream Guide-QR-injector (chat.py:_attach_guide_qr) can
                    # offer a "Bring mich hin"-link to the area's source URL
                    # (z.B. WissenLebtOnline → https://wissenlebtonline.de/).
                    # Bewusst NUR explizite Calls — die mode:always-Prefetch
                    # läuft immer, das wäre als Guide-Trigger zu breit.
                    used = session_state.setdefault("_rag_areas_used", [])
                    if area and area not in used:
                        used.append(area)

                    # Guard: if this area was already covered by the pre-fetch
                    # and the query is the same, return a short hint instead of
                    # re-querying the database (saves an embedding API call).
                    if knowledge_prefetched and area in always_areas and query == message:
                        _logger.info("query_knowledge(%s): skipped — already pre-fetched", area)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": (
                                f"Bereich '{area}' wurde bereits vorab durchsucht. "
                                "Die Ergebnisse findest du in der vorherigen query_knowledge-Antwort."  # noqa: E501
                            ),
                        })
                        continue

                    _explicit_sources: list[str] = []
                    result_text = await get_rag_context(
                        session, query, areas=[area], top_k=_RAG_TOP_K,
                        min_score=_RAG_MIN_SCORE,
                        max_chars_per_area=_RAG_MAX_CHARS_PER_AREA,
                        out_sources=_explicit_sources,
                    )
                    if _explicit_sources:
                        used_src = session_state.setdefault("_rag_top_sources", [])
                        for s in _explicit_sources:
                            if s not in used_src:
                                used_src.append(s)
                    if not result_text:
                        result_text = f"Keine relevanten Informationen im Bereich '{area}' gefunden."  # noqa: E501
                    _logger.info("query_knowledge(%s): %d chars", area, len(result_text))

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_text[:6000],
                    })
                    continue

                # ── Handle MCP tools ──────────────────────────
                # Safety: refuse blocked tools (Triple-Schema T-19)
                if tool_name in blocked_tools:
                    from boerdi.api.schemas import ToolOutcome
                    outcomes.append(ToolOutcome(
                        tool=tool_name, status="error",
                        error="blocked by safety layer",
                    ))
                    messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": "Tool wurde aus Sicherheitsgruenden blockiert.",
                    })
                    continue

                # Enforce maxResults limit on search/collection tools.
                # (maxItems is a legacy alias accepted by our Pydantic validator.)
                MAX_RESULTS = 5
                if tool_name in ("search_wlo_collections", "search_wlo_content", "get_collection_contents"):  # noqa: E501
                    # Migrate legacy key if the LLM passed the old name.
                    if "maxItems" in tool_args and "maxResults" not in tool_args:
                        tool_args["maxResults"] = tool_args.pop("maxItems")
                    tool_args.setdefault("maxResults", MAX_RESULTS)
                    if tool_args["maxResults"] > MAX_RESULTS:
                        tool_args["maxResults"] = MAX_RESULTS

                # ── Safety net: forward entity-level filters the LLM forgot ──
                # The classifier extracts medientyp / fach / stufe up-front; the
                # LLM is instructed to pass them as learningResourceType /
                # discipline / educationalContext on content searches, but it's
                # not 100% reliable (especially when it chains
                # search_wlo_collections first and then does a "fallback"
                # search_wlo_content). We inject missing filters here so user
                # intent isn't lost. mcp_client's fuzzy label→URI resolver
                # tolerates paraphrased entity values.
                if tool_name == "search_wlo_content":
                    _classif_entities = classification.get("entities", {}) or {}
                    # Migrate any legacy keys the LLM might still send
                    if "resourceType" in tool_args and "learningResourceType" not in tool_args:
                        tool_args["learningResourceType"] = tool_args.pop("resourceType")
                    if "educationalLevel" in tool_args and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = tool_args.pop("educationalLevel")
                    _medientyp = _classif_entities.get("medientyp")
                    if _medientyp and "learningResourceType" not in tool_args:
                        _logger.info(
                            "injecting learningResourceType=%r from entities.medientyp (LLM omitted it)",  # noqa: E501
                            _medientyp,
                        )
                        tool_args["learningResourceType"] = _medientyp
                    _fach = _classif_entities.get("fach")
                    if _fach and "discipline" not in tool_args:
                        tool_args["discipline"] = _fach
                    _stufe = _classif_entities.get("stufe")
                    if _stufe and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = _stufe
                # Same for search_wlo_collections — collections can't be
                # filtered by learningResourceType, but fach/stufe are valid
                # and worth propagating.
                elif tool_name == "search_wlo_collections":
                    _classif_entities = classification.get("entities", {}) or {}
                    if "educationalLevel" in tool_args and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = tool_args.pop("educationalLevel")
                    _fach = _classif_entities.get("fach")
                    if _fach and "discipline" not in tool_args:
                        tool_args["discipline"] = _fach
                    _stufe = _classif_entities.get("stufe")
                    if _stufe and "educationalContext" not in tool_args:
                        tool_args["educationalContext"] = _stufe

                # ── E1 (2026-08-10): Bestätigungs-Wall ────────────────
                # Die kuratierenden Werkzeuge sind zweistufig: ohne
                # ``confirmToken`` nur Vorschau, erst der zweite Aufruf mit
                # dem Schlüssel führt aus. Der Server bindet den Schlüssel an
                # die Änderung — aber er kann nicht sehen, ob zwischen beiden
                # Schritten ein MENSCH stand. Bei fünf Iterationen pro Zug
                # stünde dort sonst niemand.
                #
                # Deshalb: das Modell darf keinen Schlüssel setzen, und
                # einsetzen dürfen wir ihn nur für einen Vorgang aus einem
                # FRÜHEREN Zug — ``_pending_at_turn_start`` ist der
                # Schnappschuss vom Zug-Eintritt. Was in diesem Zug entsteht,
                # steht nicht darin und ist in diesem Zug nicht bestätigbar.
                # Der Zugwechsel ist der Mensch.
                if is_confirmable(tool_name):
                    tool_args = strip_confirm_token(tool_name, tool_args)
                    # Die Uhr steht hier und nicht in der Domäne: dort wohnt
                    # die Identität eines Vorhabens, hier die Zeit (E4).
                    _jetzt = time.time()
                    _confirm = token_for(
                        _pending_at_turn_start, tool_name, tool_args, now=_jetzt)
                    if _confirm:
                        tool_args = {**tool_args, "confirmToken": _confirm}
                        _pending_at_turn_start = None
                        session_state.setdefault("entities", {}).pop("_pending_write", None)
                    elif ((_pending_at_turn_start or {}).get("tool") == tool_name
                          and is_expired(_pending_at_turn_start, now=_jetzt)):
                        # E4: derselbe Vorgang, nur zu spät. Ohne diesen Zweig
                        # meldete die Zeile darunter „Argumente weichen ab" —
                        # ein Grund, den es hier nicht gibt. Der Merkposten
                        # bleibt liegen; die gleich folgende neue Vorschau
                        # überschreibt ihn mit einem frischen Zeitpunkt.
                        _logger.info(
                            "offener Vorgang für %s ist abgelaufen — es folgt eine "
                            "neue Vorschau", tool_name)
                    elif (_pending_at_turn_start or {}).get("tool") == tool_name:
                        # Offener Vorgang DESSELBEN Werkzeugs, aber andere
                        # Argumente: es wird nicht bestätigt, sondern neu
                        # vorgeschaut. Von hier aus sind zwei Fälle nicht zu
                        # unterscheiden — der Nutzer hat angepasst (Normalfall),
                        # oder das Modell hat im Bestätigungszug ein Feld mehr
                        # oder weniger genannt (dann sagt der Nutzer „ja" und
                        # wird erneut gefragt). Deshalb INFO statt WARNING:
                        # aufgezeichnet, ohne einen Fehler zu behaupten.
                        # Ohne diese Zeile ist der Rückfall spurlos.
                        #
                        # Nur der Werkzeugname, wie beim Nachbarn unten: weder
                        # Schlüssel noch Argumente gehören ins Protokoll.
                        _logger.info(
                            "offener Vorgang für %s nicht bestätigt — Argumente weichen "
                            "von der Vorschau ab; es folgt eine neue Vorschau",
                            tool_name)

                # Triple-Schema T-23: call with structured outcome
                from boerdi.services.outcome_service import call_with_outcome
                result_text, outcome = await call_with_outcome(tool_name, tool_args)
                outcomes.append(outcome)

                # Rückweg des Walls: den frisch geprägten Schlüssel merken und
                # aus dem Text nehmen, BEVOR er irgendwohin weiterfließt
                # (Nachrichtenkette, Karten, Protokoll). Sähe das Modell ihn,
                # könnte es im selben Zug bestätigen.
                if is_confirmable(tool_name):
                    _minted = extract_confirm_token(result_text)
                    # Redigiert wird ZUERST — danach kann kein Pfad mehr den
                    # rohen Text weiterreichen. Seit S1 gibt es einen zweiten
                    # Empfänger (den offenen Vorgang, aus dem die sichtbare
                    # Vorschau-Box gespeist wird); die Reihenfolge macht die
                    # Zusicherung an der Stelle ablesbar, an der sie gilt.
                    # Die Absagen-Unterscheidung unten bleibt unberührt: die
                    # Redaktion ersetzt nur den Schlüssel, ``confirmToken:``
                    # selbst überlebt sie.
                    result_text = redact_confirm_token(result_text)
                    if _minted:
                        # In ``entities``, weil der Merkposten den Zug
                        # überdauern MUSS — siehe Zug-Eintritt oben.
                        session_state.setdefault("entities", {})["_pending_write"] = (
                            remember_pending(tool_name, tool_args, _minted, now=time.time()))
                        # S1: derselbe Text ein zweites Mal — diesmal für den
                        # Menschen. Der Server formuliert die Abnahme bereits
                        # vollständig und auf Deutsch; bisher endete sie in der
                        # Nachrichtenkette des Modells, und der Nutzer las nur
                        # die Nacherzählung.
                        #
                        # Auf oberster Ebene, und das ist genau umgekehrt zum
                        # Merkposten daneben: die Vorschau DARF den Zug nicht
                        # überdauern. Dass dort nichts gespeichert wird, ist
                        # hier die gewünschte Eigenschaft.
                        session_state["_write_preview"] = result_text
                    elif "confirmToken:" in result_text:
                        # Der Server kündigt einen Schlüssel an, wir lesen aber
                        # keinen heraus: dann hat sich sein Vorschautext
                        # geändert. Sichtbar machen statt still hinnehmen —
                        # die Folge wäre, dass sich nichts mehr bestätigen
                        # lässt. Der Wall selbst hält auch dann, denn er trägt
                        # auf dem HINWEG (``strip_confirm_token``): ein
                        # Schlüssel, den das Modell sieht, kann es trotzdem
                        # nicht absetzen.
                        #
                        # Der Doppelpunkt ist der Unterschied und kein Zufall:
                        # die Vorschau sagt „mit confirmToken: <schlüssel>
                        # wiederholen", die drei Absagen (abgelaufen, andere
                        # Änderung, unbekannt) sagen „ohne confirmToken
                        # wiederholen". Ohne ihn schlüge diese Warnung bei
                        # jedem abgelaufenen Schlüssel falsch an.
                        _logger.warning(
                            "Vorschautext von %s nennt confirmToken, enthält aber "
                            "keinen lesbaren Schlüssel — Bestätigung nicht möglich",
                            tool_name)
                # A4c-2a: Parser-Auswahl, Sammlungs-Markierung, Themenseiten-
                # Mischung und Entdopplung wohnen in ``services/card_collect``,
                # seit die Agent-Schleife dieselbe Ernte braucht.
                cards = collect_cards(all_cards, tool_name, result_text)

                # ── Inline-Result-Grouping: search_wlo_content-Redaction ──
                # Im Box-Anzeige-Modus zeigt die UI Einzelinhalte NICHT direkt
                # an — sie tauchen nur indirekt über die "Alle Treffer zur
                # Suche"-CTA auf. Wenn die LLM den vollen Tool-Result-Text mit
                # Titeln/Beschreibungen sieht, paraphrasiert sie diese unter-
                # mauernd ("ein Arbeitsblatt und ein Video für Fläche, Umfang
                # und Konstruktion") — der User sieht aber gar keine
                # Materialien in der UI und ist verwirrt (User-Feedback
                # 2026-05-21). Helper-Funktion ``_redact_search_content_for_llm``
                # ersetzt den Text durch eine kompakte Summary (Anzahl + grobe
                # Typ-Verteilung). Cards selbst bleiben in ``all_cards``, sodass
                # Lernpfad-Generator (separater Flow) und Such-CTA-Count weiter
                # arbeiten.
                # Tool-Result + UI-Box-Status-Footer (Anti-Hallucination):
                # die Footer-Zeile sagt der LLM, was nach diesem Call WIRKLICH
                # in den sichtbaren Boxen landet — sodass sie im Antwort-Text
                # keine Sammlungen/Themenseiten erfinden kann.
                # D4 (2026-08-10): ``frame_untrusted`` kennzeichnet Werkzeuge,
                # deren Nutzlast Langform-Prosa von Dritten ist (Volltext,
                # Kompendium), als Daten statt Anweisung — indirekte
                # Prompt-Einschleusung. Der UI-Box-Status ist UNSERE Anweisung
                # und bleibt deshalb AUSSERHALB des Rahmens; innerhalb wuerde
                # der Rahmen sie mit entwerten.
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": (
                        frame_untrusted(
                            tool_name,
                            _redact_search_content_for_llm(tool_name, result_text, cards, _inline_grouping_mode),  # noqa: E501
                        )
                        + _ui_box_state_footer(all_cards, _inline_grouping_mode)
                    ),
                })

            # If respond_to_user was called among the tool calls, treat THIS
            # iteration as the finish point. Otherwise continue the outer
            # for-loop into the next LLM round-trip.
            if _inline_response_text is None:
                continue
            # Inline final response — set response_text + stash quick_replies
            # and fall through to the Reflection/return path below (which
            # used to be the ``else`` branch only).
            response_text = _inline_response_text
            session_state["_inline_quick_replies"] = _inline_quick_replies
        else:
            response_text = strip_reasoning_markers(choice.message.content or "")

        # ── Final-answer path — runs for BOTH content-only and inline
        #    respond_to_user tool calls. Phase A1 Reflection check gates the
        #    return so a missing-tool retry can still trigger.
        if True:
            # Phase A1 — Reflection-Loop für Tool-Compliance:
            # Wenn das Pattern Tools verlangt (force_tool_use=true) UND keines
            # davon im Tool-Loop tatsächlich gerufen wurde, einmal mit harter
            # Korrektur-Anweisung neu versuchen. Schützt vor LLMs, die einen
            # netten Text-Antwort-Shortcut nehmen, obwohl ihre Pattern-Definition
            # eindeutig MCP-/Service-Calls verlangt.
            #
            # Sicherheits-Conditions (vermeidet Endlos-Loops):
            #   - läuft nur 1× pro Turn (Flag _reflection_done)
            #   - greift nur wenn pattern_output.force_tool_use == True
            #   - greift nur wenn pattern_output.tools eine echte Liste ist
            #   - greift nur wenn keines der erwarteten Tools im tools_called auftaucht
            requires_tools = bool(pattern_output.get("force_tool_use"))
            required_tools = list(pattern_output.get("tools") or [])
            requires_all = bool(pattern_output.get("requires_all_tools"))
            actual_bare = {(t or "").split(" ", 1)[0].strip() for t in tools_called}
            # B1: requires_all_tools=true → vollständige Coverage; sonst Schnittmenge
            if requires_all:
                missing_tools = [t for t in required_tools if t not in actual_bare]
                tool_satisfied = not missing_tools
            else:
                missing_tools = list(required_tools) if not (set(required_tools) & actual_bare) else []  # noqa: E501
                tool_satisfied = bool(set(required_tools) & actual_bare)

            if (not _reflection_done) and requires_tools and required_tools and not tool_satisfied:
                _logger.info(
                    "Reflection-Loop: Pattern %s verlangt Tools %s (mode=%s), aufgerufen %s, fehlend %s — Retry",  # noqa: E501
                    pattern_label, required_tools,
                    "ALL" if requires_all else "ANY",
                    sorted(actual_bare), missing_tools,
                )
                _reflection_done = True
                # Korrektur-Nachricht in den Loop-Messages-Stack einfügen
                if requires_all:
                    msg = (
                        f"⚠ KORREKTUR: Du hast PAT-{pattern_label} gewählt; dieses Pattern "
                        f"verlangt ALLE diese Tools nacheinander: {', '.join(required_tools)}. "
                        f"Du hast {sorted(actual_bare) or 'keinen davon'} bisher gerufen. "
                        f"Rufe JETZT die fehlenden Tools ({', '.join(missing_tools)}) auf, "
                        f"BEVOR du final antwortest."
                    )
                else:
                    msg = (
                        f"⚠ KORREKTUR: Du hast PAT-{pattern_label} gewählt, aber KEINEN der "
                        f"verlangten Tools genutzt: {', '.join(required_tools)}. "
                        f"Rufe JETZT mindestens EINEN dieser Tools auf, BEVOR du final "
                        f"antwortest. Ohne Tool-Aufruf hast du keine echten Daten zur Verfügung — "
                        f"deine Antwort wäre erfunden."
                    )
                messages.append({"role": "user", "content": msg})
                # Continue zur nächsten Iteration: Loop wird Tools forcieren
                # weil active_tools immer noch gesetzt ist und der LLM jetzt
                # den expliziten Hinweis hat.
                continue

            return response_text, all_cards, tools_called, outcomes
    # Loop erschoepft ohne finale Antwort → Fortsetzungs-Marker fuer den
    # P16-Fallback am Call-Site.
    return None
