"""Port of ALT tests/test_eval_prompts.py — the three eval prompt templates.

The templates are static ``.format()`` strings. ALT pinned their exact byte
length and placeholder set so that a verbatim move stays verifiably intact; the
same assertions here make the ALT→NEU port byte-exact rather than "looks right".

The lengths (3994 / 1566 / 12164) are ALT's, unchanged. If a template is ever
edited on purpose, the number in this test is what has to move with it.
"""

from __future__ import annotations

import string

from boerdi.services.eval.prompts import (
    _JUDGE_PROMPT,
    _SCENARIO_PROMPT,
    _SIMULATOR_SYSTEM,
)


def _placeholders(s: str) -> list[str]:
    return sorted({f for _, f, _, _ in string.Formatter().parse(s) if f})


def test_scenario_prompt_contract():
    assert isinstance(_SCENARIO_PROMPT, str) and len(_SCENARIO_PROMPT) == 3994
    assert _placeholders(_SCENARIO_PROMPT) == [
        "count", "intent_desc", "intent_label", "intent_triggers",
        "persona_desc", "persona_label", "persona_markers_block",
    ]


def test_simulator_system_contract():
    assert isinstance(_SIMULATOR_SYSTEM, str) and len(_SIMULATOR_SYSTEM) == 1566
    assert _placeholders(_SIMULATOR_SYSTEM) == [
        "intent_desc", "intent_label", "persona_desc",
        "persona_label", "persona_markers_block",
    ]


def test_judge_prompt_contract():
    assert isinstance(_JUDGE_PROMPT, str) and len(_JUDGE_PROMPT) == 12164
    assert _placeholders(_JUDGE_PROMPT) == [
        "bot_response", "debug_intent", "debug_pattern", "debug_pattern_hint",
        "debug_pattern_hint_reasoning", "debug_persona", "debug_safety",
        "debug_tools", "intent_desc", "intent_expectations", "intent_label",
        "pattern_expectations", "persona_desc", "persona_expectations",
        "persona_label", "user_msg",
    ]
