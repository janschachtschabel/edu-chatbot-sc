"""Response system-prompt builder (P3-3a) — byte-parity port of ALT
``llm_prompt_builder.py:40-880`` (``_build_system_prompt``, phases P1-P9).

Orchestrates the 5-layer LPA prompt and the display/tools/recency blocks (the
verbatim text lives in the sibling ``response_prompt_pattern`` /
``response_prompt_display_blocks`` / ``response_prompt_tools_text`` modules). The
``if/append`` control flow stays here so the ``system_parts`` list structure —
and its load-bearing ``"\\n".join`` separators — is byte-identical to ALT.

Deliberate NEU-deviations (all documented):
- ``simplify:`` the P9 ``_log_system_prompt_size`` telemetry (no tiktoken infra in
  NEU, non-behavioural) is omitted; seam marked below. The P3 semantic page-context
  block IS wired (R6): ``page_context.get_cached`` + ``render_for_prompt``, off the
  ``_page_metadata`` cache the ``page_context_enrich`` node populates.
- three dead ALT locals (``_pattern_id_for_m11``, ``has_rag_tools``, and the
  per-area ``mode``) are not carried — assigned but never read (F841 in NEU).
- ``_select_active_tools`` (P10-P11) is NOT here: it is blocked on P5/P6
  (``TOOL_DEFINITIONS`` does not exist yet) — see
  ``docs/plans/p3-response-prompt-contract.md``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from boerdi.domain.skill_precedence import anleitungs_hinweis, laufende_anleitung
from boerdi.i18n import resolve_locale
from boerdi.services import page_context
from boerdi.services import response_prompt_display_blocks as _display
from boerdi.services import response_prompt_tools_text as _tools_text
from boerdi.services.config_loader import (
    get_state_directive,
    load_base_persona,
    load_domain_rules,
    load_guardrails,
    load_persona_prompt,
)
from boerdi.services.response_prompt_pattern import render_pattern_layer
from boerdi.services.response_tool_selection import curation_blocked_by_mode

_logger = logging.getLogger(__name__)


def _get_state_meta_safe(state_id: str) -> dict[str, Any]:
    """Safe state-directive lookup (ALT ``llm_service._get_state_meta_safe``):
    empty dict on an unknown state or a lookup error, so the builder degrades to
    the ``(?)`` / ``—`` / Pattern-default placeholders instead of raising."""
    try:
        return get_state_directive(state_id) or {}
    except Exception as exc:  # noqa: BLE001
        _logger.warning("state-directive lookup failed for %s: %s", state_id, exc)
        return {}


def _build_system_prompt(
    classification: dict[str, Any],
    pattern_output: dict[str, Any],
    pattern_label: str,
    session_state: dict,
    environment: dict,
    rag_context: str,
    available_rag_areas: list[str] | None,
    rag_config: dict[str, Any] | None,
) -> tuple[str, bool, bool, bool]:
    """Compose the response system prompt (P1-P9). Returns ``(system,
    _cards_inline_mode, _inline_grouping_mode, _degradation_no_tools)`` — the
    finished prompt plus the three flags later phases (tool selection,
    inline-grouping closures) read."""
    # C1-f1: Die Ausgabe-Sprache kommt aus ``environment.locale`` — dem Feld,
    # das der Vertrag seit je fuehrt und das bis hierher niemand ausgewertet hat.
    # ``resolve_locale`` ist derselbe Parser wie fuer ``Accept-Language`` (C1-e1):
    # ``en-GB`` ist Englisch, alles Nichtunterstuetzte faellt auf Deutsch.
    lang = resolve_locale(environment.get("locale"))

    # P1: config loads.
    persona_id = classification.get("persona_id", "P-AND")
    base_persona = load_base_persona()
    guardrails = load_guardrails()
    persona_prompt = load_persona_prompt(persona_id)
    domain_rules = load_domain_rules()

    # State als Verlaufs-Phase (Welle C Sprint 6): Pattern wählt WAS antworten +
    # welche Tools, State sagt WIE in der aktuellen Verlaufs-Phase einzuzahlen ist.
    _resp_state_id = classification.get('next_state', 'S1')
    _resp_state_meta = _get_state_meta_safe(_resp_state_id)
    _resp_state_directive = (
        _resp_state_meta.get('bot_directive')
        or '— keine spezifische Direktive für diese Phase, folge dem Pattern.'
    )

    # P2: 5-Layer LPA prompt. ``_entities`` is extracted only to keep the Layer-5
    # f-string within the line limit; the emitted JSON is identical to ALT.
    _entities = json.dumps({
        k: v for k, v in (classification.get('entities') or {}).items()
        if not k.startswith('_')
    })
    system_parts = [
        base_persona,  # Layer 1: Identity
        domain_rules,  # Layer 2: Domain rules
        persona_prompt,  # Layer 3: Persona
        render_pattern_layer(pattern_output, persona_id),  # Layer 4: Pattern + Anrede
        f"""## Kontext
Seite: {environment.get('page', '/')}
Entities: {_entities}
Signale: {', '.join(classification.get('signals', []))}
Gesprächs-Phase: {_resp_state_id} ({_resp_state_meta.get('label', '?')})
Rolle in dieser Phase: {_resp_state_meta.get('role', '—')}

## Phase-Direktive (befolge, ergänzend zum Pattern-Verhalten)
{_resp_state_directive}""",  # Layer 5: Context + State-Phase
    ]

    # P3: semantic page-context block (resolved theme-page metadata, cached on
    # session_state["entities"]["_page_metadata"] by the page_context_enrich node).
    # Goes after the generic context so the LLM treats it as prime information.
    #
    # ``_pm`` steht ausserhalb des ``try``, weil P3c es unten nochmal braucht:
    # ein zweiter ``get_cached``-Aufruf liefe ohne diese Absicherung, und ein
    # Ausfall des Zwischenspeichers darf den Prompt nicht kosten (gepinnt von
    # ``test_page_context_block_failure_is_swallowed``). Bleibt es bei ``None``,
    # fällt P3c auf die Gesprächs-Notiz zurück — der einzige Skill-Hinweis, der
    # dann noch zu haben ist.
    _pm: dict[str, Any] | None = None
    try:
        _pm = page_context.get_cached(session_state)
        _pb = page_context.render_for_prompt(_pm, environment.get("page_context"))
        if _pb:
            system_parts.append(_pb)
        else:
            # Fallback: the widget's DOM-detector saw visible page text but MCP
            # could not resolve platform metadata — use the heuristic block.
            _raw_pb = page_context.render_raw_for_prompt(environment.get("page_context"))
            if _raw_pb:
                system_parts.append(_raw_pb)
    except Exception:  # noqa: BLE001 — a page-block failure must never break the prompt
        _logger.debug("page-context prompt block failed", exc_info=True)

    # P3b: die Anleitung, die noch in Arbeit ist. Ein Skill, der eine Rückfrage
    # stellt, bekommt die Antwort erst im NÄCHSTEN Zug — und der entschied bis
    # 2026-08-16 neu: gemessen ging „45 min physik sek 1" beim Klassifikator in
    # ein fremdes Muster, worauf das Modell eine andere Anleitung holte und
    # einen Material-Fund statt des Verlaufsplans lieferte.
    #
    # Der Block INFORMIERT und zwingt nicht — die Nutzer-Regel „das Modell
    # entscheidet, was es nutzt" bleibt; es soll die laufende Anleitung nur
    # überhaupt kennen.
    _lauf = laufende_anleitung(
        session_state.get("entities"), session_state.get("turn_count"))
    if _lauf:
        system_parts.append(
            "## Laufender Skill\n"
            f"In diesem Gespräch ist der freigegebene Skill `{_lauf}` in "
            "Arbeit — er hat zuletzt geantwortet oder nachgefragt.\n"
            "Passt die neue Nachricht dazu, auch als knappe Antwort auf seine "
            f"Rückfrage, arbeite mit IHM weiter: `get_skill(\"{_lauf}\")`. Geht "
            "es erkennbar um etwas anderes, ist er erledigt und du wählst frei."
        )

    # P3c: Anleitungen, die nur aus dem GESPRÄCH bekannt sind. Der Seitenblock
    # oben trägt den Katalog nur, wenn Seiten-Metadaten da sind; wer über die
    # Suche kommt, hat keine. Der Entscheid darüber (auch: auf der Seite
    # schweigen) sitzt in ``domain/skill_precedence`` — dieselbe Regel, die das
    # Routing liest, hier für den zweiten Leser.
    _skills = anleitungs_hinweis(
        (_pm or {}).get("context_facts"), session_state.get("entities"))
    if _skills:
        system_parts.append(_skills)

    # P4: M11 Edit needs the pre-edit canvas content explicitly in the prompt.
    _m11 = _display.render_m11_rerender_block(pattern_output, session_state)
    if _m11:
        system_parts.append(_m11)

    # P5: display modes. Flags computed early — the search-prompt blocks and the
    # tool lock (P8) all depend on them.
    _card_mode = pattern_output.get("card_text_mode", "minimal")
    _cards_inline_mode = environment.get("cards_enabled") is False
    _inline_grouping_mode = (
        _cards_inline_mode
        and environment.get("inline_result_grouping") is not False
    )
    _pattern_id = ((pattern_label or "").strip().split(" ")[0] or "").upper()
    _is_search_pattern = _pattern_id in {"M05", "M06", "M07", "M08"}
    _degradation_no_tools = bool(
        pattern_output.get("degradation")
        and pattern_output.get("missing_slots")
    )

    _card_block = _display.render_card_text_mode_block(_card_mode)
    if _card_block:
        system_parts.append(_card_block)
    if not _cards_inline_mode:
        system_parts.append(_display.RERANK_HINT_BLOCK)
    _result_block = _display.render_result_mode_block(
        inline_grouping_mode=_inline_grouping_mode,
        is_search_pattern=_is_search_pattern,
        cards_inline_mode=_cards_inline_mode,
        degradation_no_tools=_degradation_no_tools,
    )
    if _result_block:
        system_parts.append(_result_block)

    # P6: signal-driven modulation rules.
    if pattern_output.get("skip_intro"):
        system_parts.append("\n## Regel: Keine Einleitung. Direkt zur Sache.")
    if pattern_output.get("one_option"):
        system_parts.append("\n## Regel: Nur 1 Option anbieten. Nicht überfordern.")
    if pattern_output.get("add_sources"):
        system_parts.append("\n## Regel: Quellen und Herkunft explizit nennen.")
    if pattern_output.get("degradation"):
        system_parts.append(_tools_text.render_degradation_rules(
            pattern_output.get("missing_slots", []),
            pattern_output.get("blocked_patterns", []),
        ))

    # P7: RAG context (memory only, no blind injection) + guardrails (always
    # last, not overridable).
    if rag_context:
        system_parts.append(f"\n{rag_context}")
    system_parts.append(guardrails)

    # P8: tools vs no-tools. Degradation or an explicitly empty (non-mcp) tool
    # set locks tools and forces a pure-text reply.
    has_explicit_empty_tools = ("tools" in pattern_output and not pattern_output["tools"])
    pattern_wants_no_tools = _degradation_no_tools or (
        has_explicit_empty_tools and not (
            pattern_output.get("sources") and "mcp" in pattern_output["sources"]
        )
    )
    if pattern_wants_no_tools:
        if _degradation_no_tools:
            system_parts.append(
                _tools_text.DEGRADATION_NO_TOOLS_RULES
                + _tools_text.render_output_language(lang)
            )
        else:
            system_parts.append(
                _tools_text.M15_NO_TOOLS_RULES + _tools_text.render_output_language(lang)
            )
    else:
        system_parts.append(_tools_text.render_tools_block(
            session_state, available_rag_areas, rag_config, lang,
        ))

    # E3 (2026-08-10): Hat das Muster kuratierende Werkzeuge verlangt, die es
    # mangels Zugangsblock nicht bekommt, weiss das Modell davon sonst nichts —
    # es sucht ein Werkzeug, das gar nicht im Angebot steht, und weicht aus.
    # NUR in diesem Fall angehaengt: der Prompt jedes anderen Zuges bleibt
    # bytegleich, und der Block kostet Platz nur dort, wo er etwas erklaert.
    if curation_blocked_by_mode(pattern_output):
        system_parts.append(_tools_text.render_curation_unavailable(lang))

    # P9: recency anchor. ALT's _log_system_prompt_size("response", …) telemetry
    # is simplify-deferred (no tiktoken infra in NEU).
    _recap = _tools_text.render_recency_anchor(
        pattern_label, pattern_output.get("body_md"),
    )
    if _recap:
        system_parts.append(_recap)

    system = "\n".join(system_parts)
    return system, _cards_inline_mode, _inline_grouping_mode, _degradation_no_tools
