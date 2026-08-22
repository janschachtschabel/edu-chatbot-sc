"""``queries.get_trends`` — die Serien-Bildung ohne Datenbank.

Die Router-Tests faken den ganzen Service, die pg-Tests laufen offline nicht —
die Lücke dazwischen war genau der Review-Befund 1 (2026-08-22): Golden-v2-Läufe
schoben 0.0-Punkte in die Persona-/Intent-Serien, weil nur die Match-Serie den
GV6-None-Filter hatte. Diese Tests pinnen die Skip-Regel für alle drei Serien.
"""

from __future__ import annotations

import pytest

from boerdi.db.models import EvalRun
from boerdi.services.eval.queries import get_trends


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows):
        self.rows = rows

    async def execute(self, _stmt):
        return _FakeResult(self.rows)


def _run(run_id: str, cm: dict) -> EvalRun:
    return EvalRun(
        id=run_id, status="done", mode="golden",
        config={}, totals={"total_turns": 3, "avg_score": 1.0},
        summary={"classification_metrics": cm},
    )


_GOLDEN_CM = {
    # Golden v2: persona_id "*" → nichts gemessen. Seit dem Fix liefert
    # ``_aggregate_classification_metrics`` hier None statt 0.0.
    "persona_correct_rate": None, "persona_total_judged": 0,
    "intent_correct_rate": None, "intent_total_judged": 0,
    "llm_engine_match_rate": None, "llm_hint_present_count": 0,
    "token_usage_aggregate": {"cache_hit_rate": 0.4, "prompt_tokens": 10,
                              "cached_tokens": 4},
    "tool_compliance_per_pattern": {},
}

_GENERATIVE_CM = {
    "persona_correct_rate": 0.75, "persona_total_judged": 4,
    "intent_correct_rate": 0.5, "intent_total_judged": 4,
    "llm_engine_match_rate": 0.9, "llm_hint_present_count": 10,
    "token_usage_aggregate": {"cache_hit_rate": 0.2, "prompt_tokens": 5,
                              "cached_tokens": 1},
    "tool_compliance_per_pattern": {},
}


@pytest.mark.asyncio
async def test_none_raten_erzeugen_keinen_trend_punkt():
    """Ein Golden-Lauf (nichts gemessen) darf in keiner der drei
    Klassifikations-Serien als 0.0-Punkt auftauchen — Lücke statt Absturz."""
    out = await get_trends(_FakeSession([_run("eval-gold", _GOLDEN_CM)]), 10)
    assert out["persona_correct_trend"] == []
    assert out["intent_correct_trend"] == []
    assert out["llm_engine_match_trend"] == []
    # Der Lauf selbst bleibt in der Zeitachse sichtbar.
    assert [m["id"] for m in out["runs"]] == ["eval-gold"]


@pytest.mark.asyncio
async def test_echte_raten_bleiben_in_den_serien():
    out = await get_trends(_FakeSession([_run("eval-gen", _GENERATIVE_CM)]), 10)
    assert [p["value"] for p in out["persona_correct_trend"]] == [0.75]
    assert [p["value"] for p in out["intent_correct_trend"]] == [0.5]
    assert [p["value"] for p in out["llm_engine_match_trend"]] == [0.9]


@pytest.mark.asyncio
async def test_gemischte_laeufe_ueberspringen_nur_die_unmessbaren():
    rows = [_run("eval-gen", _GENERATIVE_CM), _run("eval-gold", _GOLDEN_CM)]
    out = await get_trends(_FakeSession(rows), 10)
    assert [p["run_id"] for p in out["persona_correct_trend"]] == ["eval-gen"]
    assert [p["run_id"] for p in out["intent_correct_trend"]] == ["eval-gen"]
    # Beide Läufe stehen in der Meta-Zeitachse (reversed → älteste zuerst).
    assert [m["id"] for m in out["runs"]] == ["eval-gold", "eval-gen"]
