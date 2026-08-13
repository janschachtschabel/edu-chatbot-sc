"""Response orchestrator (``generate_response``) — port of ALT
``llm_service.py:160-312``.

This is the top-level entry the chat turn calls to produce the final answer. It
wires the five response phases in order and returns the finished
``(response_text, wlo_cards, tools_called, outcomes)`` tuple:

    P1-P9   ``_build_system_prompt``      (services/response_prompt_builder.py)
    P10-P11 ``_select_active_tools``      (services/response_tool_selection.py)
    P12/P14 ``_assemble_messages``        (services/tool_loop_messages.py)
    P15     ``_run_tool_loop``            (services/tool_loop.py)
    P16     ``_max_iterations_fallback``  (services/tool_loop_fallback.py)

Home: its own module. ALT co-located it with ``classify_input`` and a large
re-export facade in ``llm_service.py``; NEU already split classify to
``services/classify.py`` and the phases to their own modules, so the orchestrator
that sits *above* them belongs in neither a phase module nor the (complete,
1020-line) ``tool_loop.py`` — it is the thin glue that composes them.

NEU-deviation vs ALT (the only one): ``session`` is prepended as the first
parameter and threaded as the first argument into ``_assemble_messages`` and
``_run_tool_loop`` — pg-DI for the RAG retrieval reached through the tool loop
(ALT read a module-global engine). Every other statement is ALT-verbatim; the
call sites remain bare-name positional calls, so the body is AST-identical to
ALT modulo that seam. Precedent: the same seam in R1a/R1b (tool_loop.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from boerdi.services.response_prompt_builder import _build_system_prompt
from boerdi.services.response_tool_selection import _select_active_tools
from boerdi.services.tool_loop import _run_tool_loop
from boerdi.services.tool_loop_fallback import _max_iterations_fallback
from boerdi.services.tool_loop_messages import _assemble_messages

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


async def generate_response(
    session: AsyncSession,
    message: str,
    history: list[dict],
    classification: dict[str, Any],
    pattern_output: dict[str, Any],
    pattern_label: str,
    session_state: dict,
    environment: dict,
    rag_context: str = "",
    available_rag_areas: list[str] | None = None,
    rag_config: dict[str, Any] | None = None,
    blocked_tools: list[str] | None = None,
    prefetched_tool: dict[str, Any] | None = None,
    prefetched_extras: list[dict[str, Any]] | None = None,
    canvas_state: dict | None = None,
    usage_acc: dict[str, Any] | None = None,
    on_token: Any = None,
) -> tuple[str, list[dict], list[str], list]:
    """Generate the final response using the selected pattern and MCP tools.

    Returns (response_text, wlo_cards, tools_called, outcomes).
    Outcomes is a list of ToolOutcome objects (Triple-Schema T-23).

    ``on_token`` is the Phase-2 streaming hook (POST /api/chat/stream). When
    provided, the LLM call inside the tool-loop runs with ``stream=True``
    and forwards each text-delta to the callback — both for plain content
    responses AND for ``respond_to_user`` tool args (where the ``text``
    field is extracted progressively from the JSON arg-stream). Default
    ``None`` keeps the regular non-streaming POST /api/chat unchanged.

    ``session`` is the request-scoped AsyncSession (NEU pg-DI); it is only
    forwarded to the phases that reach the database (RAG retrieval inside the
    tool loop) — ALT read a module-global engine instead.
    """
    blocked_tools = blocked_tools or []
    # Phasen-Split Teil 1: System-Prompt-Komposition (P1-P9) als eigene
    # Modul-Funktion; liefert den Prompt plus die von spaeteren Phasen
    # weitergelesenen Anzeige-/Degradations-Flags.
    (
        system,
        _cards_inline_mode,
        _inline_grouping_mode,
        _degradation_no_tools,
    ) = _build_system_prompt(
        classification,
        pattern_output,
        pattern_label,
        session_state,
        environment,
        rag_context,
        available_rag_areas,
        rag_config,
    )

    # Phasen-Split Teil 1: Tool-Auswahl (P10-P11) als eigene Modul-Funktion;
    # liefert die aktive Tool-Liste plus RAG-Gate-/Inline-QR-Werte fuer die
    # nachgelagerten Phasen (RAG-Prefetch, Tool-Loop).
    (
        active_tools,
        _pattern_sources_decl,
        _rag_allowed_for_pattern,
        _inline_qr_enabled,
    ) = _select_active_tools(
        classification,
        pattern_output,
        available_rag_areas,
        rag_config,
        _cards_inline_mode,
        _degradation_no_tools,
        # Nur fürs Protokoll: ``pattern_output`` trägt keine Kennung, die
        # E3-Warnung stand deshalb im Betrieb als „Muster ?" da (F-neu).
        pattern_label=pattern_label,
    )

    # Phasen-Split Teil 2: Messages-Aufbau + Prefetch-Injektion (P12+P14)
    # als eigene Modul-Funktion; liefert den Messages-Stack, die Card-/
    # Tool-Akkumulatoren und die vom Tool-Loop weitergelesenen
    # Prefetch-Flags + Retrieval-Settings.
    (
        messages,
        all_cards,
        tools_called,
        outcomes,
        knowledge_prefetched,
        always_areas,
        mcp_prefetched,
        _RAG_TOP_K,
        _RAG_MIN_SCORE,
        _RAG_MAX_CHARS_PER_AREA,
    ) = await _assemble_messages(
        session,
        message,
        history,
        pattern_output,
        pattern_label,
        session_state,
        available_rag_areas,
        rag_config,
        blocked_tools,
        prefetched_tool,
        prefetched_extras,
        canvas_state,
        system,
        _inline_grouping_mode,
        _pattern_sources_decl,
        _rag_allowed_for_pattern,
    )
    # Phasen-Split Teil 2: Tool-Loop (P15) als eigene Modul-Funktion.
    # Liefert entweder das finale 4-Tupel (Final-Answer- oder
    # API-Fehlerpfad) ODER None, wenn max_iterations ohne finale Antwort
    # erreicht wurde — dann greift unten der P16-Fallback.
    result = await _run_tool_loop(
        session,
        message,
        classification,
        pattern_output,
        pattern_label,
        session_state,
        rag_context,
        blocked_tools,
        active_tools,
        _inline_qr_enabled,
        _inline_grouping_mode,
        messages,
        all_cards,
        tools_called,
        outcomes,
        knowledge_prefetched,
        mcp_prefetched,
        always_areas,
        _RAG_TOP_K,
        _RAG_MIN_SCORE,
        _RAG_MAX_CHARS_PER_AREA,
        usage_acc,
        on_token,
    )
    if result is not None:
        return result

    # Phasen-Split Teil 1: Max-Iterations-Fallback (P16) als eigene Modul-
    # Funktion — jeder Pfad darin returnt das finale 4-Tupel, daher direktes
    # ``return await``.
    return await _max_iterations_fallback(
        messages, all_cards, tools_called, outcomes, usage_acc)
