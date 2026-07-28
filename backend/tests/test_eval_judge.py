"""Port of ALT's judge tests (tests/test_eval_service.py:520-621).

Everything the judge does with an LLM reply: coerce + clamp the five scores, cap
the free-text fields, normalise the hint-vs-engine verdict, filter the judge's
own hallucinated boilerplate, and degrade to zeros when the call or the JSON
fails. Offline — the LLM boundary is faked.
"""

from __future__ import annotations

import asyncio
import json

from boerdi.services.eval import judge as ej
from boerdi.services.eval import scenario_gen as sg
from tests.eval_fakes import FakeLLM

_J_DEBUG = {"pattern": "?", "persona": "?", "intent": "?",
            "safety": "ok", "tools_called": []}


def _judge(monkeypatch, reply=None, exc=None, debug=None):
    fake = FakeLLM(replies=[reply] if reply is not None else [], exc=exc)
    monkeypatch.setattr(ej, "chat_completion", fake)
    out = asyncio.run(ej.judge_turn(
        {}, {}, "Nutzerfrage", "Bot-Antwort",
        debug if debug is not None else dict(_J_DEBUG),
    ))
    return out, fake


def test_judge_turn_coerces_and_clamps_scores(monkeypatch):
    reply = json.dumps({
        "intent_fit": 2, "persona_tone": "3", "pattern_match": "abc",
        "safety": -5, "info_quality": 1.9, "notes": 123,
    })
    out, _ = _judge(monkeypatch, reply)
    # "3" → int 3 → clamped to 2; "abc" → 0; -5 → 0; 1.9 → int() → 1.
    assert out["intent_fit"] == 2
    assert out["persona_tone"] == 2
    assert out["pattern_match"] == 0
    assert out["safety"] == 0
    assert out["info_quality"] == 1
    assert out["notes"] == "123"
    assert out["total"] == round((2 + 2 + 0 + 0 + 1) / 10.0, 3)


def test_judge_turn_caps_notes_issues_missing_info(monkeypatch):
    reply = json.dumps({
        "notes": "n" * 400,
        "issues": ["i" * 300] * 12,
        "missing_info": ["m" * 300] * 12,
    })
    out, _ = _judge(monkeypatch, reply)
    assert len(out["notes"]) == 300
    assert len(out["issues"]) == 8 and all(len(x) == 200 for x in out["issues"])
    assert len(out["missing_info"]) == 8
    assert all(len(x) == 200 for x in out["missing_info"])


def test_judge_turn_verdict_valid_and_floskel_filtered(monkeypatch):
    reply = json.dumps({
        "pattern_hint_verdict": "Engine_Better",
        "pattern_hint_reasoning": "Engine und Hint sind identisch, kein Vergleich nötig.",
    })
    out, _ = _judge(monkeypatch, reply)
    assert out["pattern_hint_verdict"] == "engine_better"
    # The judge sometimes echoes the prompt's own verdict *definition* back as
    # its reasoning. That is not an assessment → emptied, studio falls back to
    # notes.
    assert out["pattern_hint_reasoning"] == ""


def test_judge_turn_invalid_verdict_with_hint_falls_back_to_no_disagreement(monkeypatch):
    # ALT fix 2026-07-10 (B2): an invalid verdict plus a present hint yields the
    # neutral ``no_disagreement`` instead of an empty string, which used to be
    # persisted as "" and carried no aggregate meaning.
    debug = dict(_J_DEBUG, pattern_id_hint="M05", pattern_reasoning="weil")
    reply = json.dumps({"pattern_hint_verdict": "banana",
                        "pattern_hint_reasoning": "x" * 400})
    out, fake = _judge(monkeypatch, reply, debug=debug)
    assert out["pattern_hint_verdict"] == "no_disagreement"
    assert len(out["pattern_hint_reasoning"]) == 300
    # The hint's own rationale is handed to the judge.
    assert "Hint-Begründung: weil" in fake.calls[0]["messages"][0]["content"]


def test_judge_turn_missing_verdict_without_hint_is_no_disagreement(monkeypatch):
    out, _ = _judge(monkeypatch, json.dumps({"intent_fit": 1}))
    assert out["pattern_hint_verdict"] == "no_disagreement"


def test_judge_turn_call_params(monkeypatch):
    _, fake = _judge(monkeypatch, json.dumps({"intent_fit": 2}))
    call = fake.calls[0]
    assert call["model"] == sg.judge_model()
    assert call["temperature"] == 0.0
    assert call["response_format"] == {"type": "json_object"}
    assert call["background"] is True
    prompt = call["messages"][0]["content"]
    # Without persona/intent IDs the fallback expectations apply (no config I/O).
    assert "(kein Pattern-Datensatz — Bewertung ohne Pattern-Erwartungen)" in prompt
    assert "(keine Persona-Erwartungen)" in prompt
    assert "(keine Intent-Erwartungen)" in prompt


def test_judge_turn_llm_failure_degrades_to_zeros(monkeypatch):
    # One dead judge call must not abort a run of hundreds of turns.
    out, _ = _judge(monkeypatch, exc=RuntimeError("judge down"))
    assert out["total"] == 0.0
    assert (out["intent_fit"], out["persona_tone"], out["pattern_match"],
            out["safety"], out["info_quality"]) == (0, 0, 0, 0, 0)
    assert out["notes"] == "" and out["issues"] == [] and out["missing_info"] == []
    assert out["pattern_hint_verdict"] == "no_disagreement"


def test_judge_turn_unparseable_json_degrades_to_zeros(monkeypatch):
    out, _ = _judge(monkeypatch, "kein json")
    assert out["total"] == 0.0 and out["intent_fit"] == 0


def test_judge_turn_uses_the_bare_pattern_id_for_expectations(monkeypatch):
    """A decorated pattern must not be looked up verbatim.

    ``debug.pattern`` is formatted ``"M15 (Orientierung)"``; looking that up in
    the pattern config never matches, and the judge would silently be told
    "pattern not found" for every turn.
    """
    debug = dict(_J_DEBUG, pattern="M15 (Orientierung)")
    monkeypatch.setattr(
        ej, "_build_pattern_expectations", lambda pid: f"<{pid}>",
    )
    _, fake = _judge(monkeypatch, json.dumps({}), debug=debug)
    prompt = fake.calls[0]["messages"][0]["content"]
    assert "<M15>" in prompt
    # The undecorated original still reaches the judge as the engine's choice.
    assert "M15 (Orientierung)" in prompt
