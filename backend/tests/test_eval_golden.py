"""C3: the golden run's soft layer (``services/eval/golden.py``).

Port of the judge + aggregation block of ALT ``eval_golden.execute_golden_run``
(assertions from ALT tests/test_eval_service.py:1148-1235). Two rules carry the
whole module:

* the headline ``avg_score`` stays the DETERMINISTIC hard pass rate — the judge
  average is reported beside it (``judge_avg``), never mixed into it, or the run
  list and the scorecard would show different numbers for the same run;
* a judge that fails costs its turn a score, not the run.

Offline: ``judge_turn`` is faked, and the IDs are synthetic (``P-SYN``…) so no
assertion depends on the real persona/intent config — the same reason
test_eval_metrics.py uses them.
"""

from __future__ import annotations

import asyncio

from boerdi.services.eval import golden as eg

_DBG = {"pattern": "M-SYN (z)", "persona": "P-SYN (x)",
        "intent": "I-SYN (y)", "tools_called": []}

# What ``aggregate_golden`` (evals/run_golden.py, tested there) returns for two
# all-passing turns. Passed in rather than recomputed: this module composes the
# summary, it does not own the deterministic scorecard.
_GM = {"overall_pass_rate": 1.0, "turns": 2, "flows": 1,
       "hard_passed": 10, "hard_total": 10, "rates": {}, "per_turn": [],
       "per_flow": {}, "passed": {}, "totals": {}}


def _convs(*, error_turn: bool = False, persona: str = "P-SYN") -> list[dict]:
    turns: list[dict] = [
        {"user": "text eins", "bot": "b1", "debug": dict(_DBG),
         "expected_persona": persona, "expected_intent": "I-SYN"},
        {"user": "text zwei", "bot": "b2", "debug": dict(_DBG),
         "expected_persona": None, "expected_intent": None},
    ]
    if error_turn:
        turns.append({"user": "text drei", "bot": "(chat error: down)", "debug": {},
                      "error": "down", "expected_persona": persona,
                      "expected_intent": "I-SYN"})
    return [{"kind": "golden", "flow_id": "F1", "title": "Flow Eins",
             "persona_id": persona, "intent_id": "I-SYN", "turns": turns}]


def _patch_defs(monkeypatch) -> None:
    monkeypatch.setattr(eg, "load_persona_definitions", lambda: [
        {"id": "P-SYN", "label": "Synth-Persona", "description": "erfunden"},
    ])
    monkeypatch.setattr(eg, "load_intents", lambda: [
        {"id": "I-SYN", "label": "Synth-Intent", "description": "erfunden"},
    ])


def _judge_spy(monkeypatch, *, result=None, exc=None) -> list[tuple]:
    calls: list[tuple] = []

    async def fake_judge(persona, intent, user, bot, dbg):
        calls.append((persona, intent, user, bot, dbg))
        if exc is not None:
            raise exc
        return dict(result or {"total": 0.5, "notes": ""})

    monkeypatch.setattr(eg, "judge_turn", fake_judge)
    return calls


# ── judge_conversations ──────────────────────────────────────────────────
def test_judges_every_answered_turn_and_skips_error_turns(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)
    convs = _convs(error_turn=True)

    judged = asyncio.run(eg.judge_conversations(convs))

    assert judged == 2 and len(calls) == 2
    t1, t2, t3 = convs[0]["turns"]
    assert t1["judge"]["total"] == 0.5 and t2["judge"]["total"] == 0.5
    # A turn the chat never answered has nothing to score.
    assert "judge" not in t3


def test_resolves_persona_and_intent_from_config(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)

    asyncio.run(eg.judge_conversations(_convs()))

    assert calls[0][0]["label"] == "Synth-Persona"
    assert calls[0][1]["label"] == "Synth-Intent"
    assert calls[0][2] == "text eins" and calls[0][3] == "b1"
    assert calls[0][4]["pattern"] == "M-SYN (z)"


def test_unknown_persona_becomes_a_labelled_stub(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)

    asyncio.run(eg.judge_conversations(_convs(persona="P-XX")))

    assert calls[0][0] == {"id": "P-XX", "label": "P-XX", "description": ""}


def test_turn_without_expected_intent_gets_an_empty_stub(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    calls = _judge_spy(monkeypatch)

    asyncio.run(eg.judge_conversations(_convs()))

    # Turn 2 asserts no intent, so the judge is told there is no target rather
    # than being handed the flow's first one. (The run metrics DO fall back to
    # the conversation-level intent — a different question, see below.)
    assert calls[1][1] == {"id": "", "label": "", "description": ""}


def test_config_is_read_once_per_run_not_per_turn(monkeypatch) -> None:
    reads: list[str] = []
    monkeypatch.setattr(eg, "load_persona_definitions",
                        lambda: (reads.append("p"), [])[1])
    monkeypatch.setattr(eg, "load_intents", lambda: (reads.append("i"), [])[1])
    _judge_spy(monkeypatch)

    asyncio.run(eg.judge_conversations(_convs()))

    assert reads == ["p", "i"]


def test_a_failing_judge_costs_its_turn_not_the_run(monkeypatch) -> None:
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch, exc=RuntimeError("judge provider 500"))
    convs = _convs()

    judged = asyncio.run(eg.judge_conversations(convs))

    # Still counted as judged: ALT records a zero-score verdict, and dropping
    # the turn instead would quietly raise the average of the survivors.
    assert judged == 2
    turn = convs[0]["turns"][0]
    assert turn["judge"]["total"] == 0.0
    assert "judge provider 500" in turn["judge"]["notes"]


# ── summarize_golden_run ─────────────────────────────────────────────────
def test_headline_stays_deterministic_and_judge_is_reported_beside_it(
    monkeypatch,
) -> None:
    _patch_defs(monkeypatch)
    _judge_spy(monkeypatch)
    convs = _convs()
    asyncio.run(eg.judge_conversations(convs))
    gm = dict(_GM)

    summary = eg.summarize_golden_run(convs, target_turns=2, golden_metrics=gm)

    assert summary["avg_score"] == 1.0 == gm["overall_pass_rate"]
    assert summary["judge_avg"] == 0.5
    assert gm["judge_avg"] == 0.5 and gm["judged_turns"] == 2
    assert summary["golden_metrics"] is gm
    assert summary["target_turns"] == 2 and summary["current_activity"] == "Fertig"


def test_unjudged_run_carries_no_judge_average() -> None:
    gm = dict(_GM)

    summary = eg.summarize_golden_run(_convs(), target_turns=2, golden_metrics=gm)

    assert summary["avg_score"] == 1.0  # deterministic rate, unchanged
    assert "judge_avg" not in summary and "judge_avg" not in gm
    assert summary["total_judged_turns"] == 0


def test_summary_fills_the_source_of_the_five_trend_series() -> None:
    summary = eg.summarize_golden_run(
        _convs(), target_turns=2, golden_metrics=dict(_GM),
    )

    # GET /eval/trends reads nothing but summary.classification_metrics; a gold
    # run that omits it leaves all five series permanently empty.
    cm = summary["classification_metrics"]
    assert cm["persona_total_judged"] == 2 and cm["persona_correct_rate"] == 1.0
    # Turn 2 asserts nothing, so the conversation-level intent stands in.
    assert cm["intent_total_judged"] == 2 and cm["intent_correct_rate"] == 1.0
    assert cm["llm_hint_present_count"] == 0  # no hint in the faked debug
    assert "matrix" in summary and "pattern_usage" in summary


def test_failed_run_still_summarizes_what_was_collected() -> None:
    summary = eg.summarize_golden_run(
        _convs(), target_turns=9, golden_metrics=dict(_GM),
        current_activity="Fehler: down",
    )

    assert summary["current_activity"] == "Fehler: down"
    assert summary["target_turns"] == 9
    assert summary["golden_metrics"]["turns"] == 2
