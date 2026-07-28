"""Port of ALT tests/test_eval_metrics.py — the three eval aggregators.

Pure computation over finished conversations. ALT's file also covered
``estimate_cost`` and ``_aggregate_golden``; both are already ported and tested
elsewhere in NEU (test_eval_router.py "service: estimate math" and
test_golden_runner.py), so re-asserting them here would be duplication. What is
left is exactly the three functions this slice ports:

* ``_aggregate`` — persona×intent score matrix + pattern usage
* ``_aggregate_per_phase`` — token usage per LLM phase incl. cache hit rate
* ``_aggregate_classification_metrics`` — the run-global classification report
  that feeds ``summary.classification_metrics`` and therefore ``/eval/trends``
"""

from __future__ import annotations

from boerdi.services import config_loader
from boerdi.services.eval.metrics import (
    _aggregate,
    _aggregate_classification_metrics,
    _aggregate_per_phase,
)

# ── _aggregate ──────────────────────────────────────────────────────


def test_aggregate_empty_shape():
    r = _aggregate([])
    assert set(r.keys()) == {
        "avg_score", "matrix", "pattern_usage", "total_judged_turns",
    }
    assert r["total_judged_turns"] == 0


def test_aggregate_matrix_scores_and_patterns():
    conv = {"persona_id": "P1", "intent_id": "I1", "turns": [
        {"judge": {"total": 8.0}, "debug": {"pattern": "M1"}},
        {"judge": {"total": 6.0}, "debug": {"pattern": "M1"}},
        # No judge → not scored, but the pattern still counts as used.
        {"judge": {}, "debug": {"pattern": "M2"}},
    ]}
    out = _aggregate([conv])
    assert out["matrix"]["P1"]["I1"] == 7.0
    assert out["avg_score"] == 7.0
    assert out["total_judged_turns"] == 2
    assert out["pattern_usage"] == {"M1": 2, "M2": 1}


# ── _aggregate_per_phase ────────────────────────────────────────────


def test_aggregate_per_phase_empty_is_empty_dict():
    assert _aggregate_per_phase([]) == {}


def test_aggregate_per_phase_sums_and_hit_rate():
    conv = {"turns": [
        {"debug": {"token_usage": {"per_phase": {
            "classify": {"prompt": 60, "completion": 10, "cached": 15, "calls": 1},
        }}}},
        {"debug": {"token_usage": {"per_phase": {
            "classify": {"prompt": 40, "completion": 5, "cached": 5, "calls": 1},
            "response": {"prompt": 100, "completion": 50, "cached": 0, "calls": 1},
        }}}},
    ]}
    out = _aggregate_per_phase([conv])
    assert out["classify"]["prompt"] == 100
    assert out["classify"]["cached"] == 20
    assert out["classify"]["calls"] == 2
    assert out["classify"]["hit_rate"] == 0.2   # 20/100
    assert out["response"]["hit_rate"] == 0.0   # cached 0


# ── _aggregate_classification_metrics ───────────────────────────────


def _clf_conv():
    """Two turns: the first classified correctly throughout, the second wrong.

    Synthetic IDs (P-SYN…) so the assertions never depend on the real config.
    """
    return {"persona_id": "P-SYN", "intent_id": "I-SYN", "turns": [
        {
            "user": "text eins",
            "debug": {
                "persona": "P-SYN (x)", "intent": "I-SYN (y)", "pattern": "M-SYN (z)",
                "pattern_id_hint": "M-SYN",
                "state_id": "S2", "prev_state_id": "S1", "transition_plausible": True,
                "token_usage": {
                    "prompt_tokens": 100, "completion_tokens": 40,
                    "cached_tokens": 25, "calls": 2,
                    "models": {"gpt-4o-mini": {
                        "prompt": 100, "completion": 40, "cached": 25, "calls": 2,
                    }},
                    "per_phase": {"classify": {
                        "prompt": 60, "completion": 10, "cached": 15, "calls": 1,
                    }},
                },
            },
            "judge": {"total": 8.0, "pattern_match": 2},
        },
        {
            "user": "text zwei",
            "debug": {
                "persona": "P-OTHER (x)", "intent": "I-OTHER (y)", "pattern": "M99 (z)",
                "pattern_id_hint": "M-SYN",
                "state_id": "S3", "prev_state_id": "S2", "transition_plausible": False,
            },
            "judge": {
                "total": 3.0, "pattern_match": 0,
                "pattern_hint_verdict": "hint_better",
            },
        },
    ]}


def test_aggregate_classification_metrics_empty_shape():
    r = _aggregate_classification_metrics([])
    assert isinstance(r, dict)
    assert r["judged_turns"] == 0
    for k in ("intent_correct_rate", "persona_correct_rate",
              "tool_compliance_rate", "state_distribution"):
        assert k in r


def test_classification_persona_intent_accuracy_and_confusion():
    out = _aggregate_classification_metrics([_clf_conv()])
    assert out["persona_correct_rate"] == 0.5
    assert out["persona_total_judged"] == 2
    assert out["persona_confusion"] == {"P-SYN": {"P-SYN": 1, "P-OTHER": 1}}
    # P-SYN is not a configured persona → the marker check is permissive, so
    # every turn counts as "achievable".
    assert out["persona_correct_rate_fair"] == 0.5
    assert out["persona_achievable_total"] == 2
    assert out["intent_correct_rate"] == 0.5
    assert out["intent_confusion"] == {"I-SYN": {"I-SYN": 1, "I-OTHER": 1}}


def test_classification_hint_engine_and_judge():
    out = _aggregate_classification_metrics([_clf_conv()])
    assert out["llm_hint_present_count"] == 2
    assert out["llm_engine_match_rate"] == 0.5
    assert out["pattern_confusion_llm_vs_engine"] == {"M-SYN": {"M-SYN": 1, "M99": 1}}
    assert out["judged_turns"] == 2
    assert out["pattern_match_score_distribution"] == {"0": 1, "1": 0, "2": 1}
    assert out["engine_pattern_judge_ok_rate"] == 0.5
    assert out["llm_pattern_judge_ok_lower_bound"] == 0.5


def test_classification_hint_verdict_and_state_flow():
    out = _aggregate_classification_metrics([_clf_conv()])
    assert out["pattern_hint_verdict_counts"]["no_disagreement"] == 1
    assert out["pattern_hint_verdict_counts"]["hint_better"] == 1
    assert out["pattern_disagreement_pairs"] == {"M99 → M-SYN": {"hint_better": 1}}
    assert out["pattern_hint_better_rate"] == 1.0
    assert out["state_distribution"] == {"S2": 1, "S3": 1}
    assert out["state_transitions"] == {"S1": {"S2": 1}, "S2": {"S3": 1}}
    assert out["transitions_total"] == 2
    assert out["transition_plausibility_rate"] == 0.5


def test_classification_token_usage_aggregate():
    tua = _aggregate_classification_metrics([_clf_conv()])["token_usage_aggregate"]
    assert tua["prompt_tokens"] == 100
    assert tua["completion_tokens"] == 40
    assert tua["cached_tokens"] == 25
    assert tua["turns_with_usage"] == 1
    assert tua["cache_hit_rate"] == 0.25
    assert tua["per_model"]["gpt-4o-mini"]["hit_rate"] == 0.25
    assert tua["per_phase"]["classify"]["hit_rate"] == 0.25


def test_classification_tool_compliance(monkeypatch):
    # The pattern's declared tools come from config; patched on the module so
    # the aggregator's call-time lookup sees it (ALT does the same).
    monkeypatch.setattr(
        config_loader, "load_pattern_definitions",
        lambda: [{"id": "M-SYN",
                  "tools": ["search_wlo_collections", "get_node_details"]}],
    )
    conv = {"persona_id": "", "intent_id": "", "turns": [
        {"user": "x", "debug": {
            "pattern": "M-SYN (z)",
            "tools_called": ["search_wlo_collections (prefetch)"],
        }, "judge": {}},
        {"user": "y", "debug": {
            "pattern": "M-SYN (z)", "tools_called": ["irgendein_anderes_tool"],
        }, "judge": {}},
    ]}
    out = _aggregate_classification_metrics([conv])
    assert out["tool_compliance_total"] == 2
    assert out["tool_compliance_rate"] == 0.5
    assert out["tool_compliance_per_pattern"]["M-SYN"] == {"ok": 1, "total": 2}


def test_trends_keys_are_present_so_the_studio_series_can_fill():
    """The six keys GET /eval/trends reads must exist on a real aggregate.

    Without them the five classification series stay permanently empty — the
    defect this slice exists to remove.
    """
    out = _aggregate_classification_metrics([_clf_conv()])
    for key in ("tool_compliance_per_pattern", "token_usage_aggregate",
                "llm_engine_match_rate", "llm_hint_present_count",
                "persona_correct_rate", "persona_total_judged",
                "intent_correct_rate", "intent_total_judged"):
        assert key in out, key
    assert set(out["token_usage_aggregate"]) >= {
        "cache_hit_rate", "prompt_tokens", "cached_tokens",
    }
