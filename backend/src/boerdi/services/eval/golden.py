"""Soft quality layer for a golden run (port of ALT ``eval_golden.py``'s
judge + aggregation block, C3).

The deterministic half of a golden run lives in ``evals/run_golden.py``: it
fires the flows, applies the hard Soll-Ist checks and computes the scorecard.
That file must stay importable without the backend package (framework-free CLI
for reference/A-B runs, see its README), so the LLM judge cannot live there.
This module is the framework-side other half:

* ``judge_conversations`` scores every answered turn via ``eval/judge.py``;
* ``summarize_golden_run`` composes the run summary from the three aggregators.

The headline stays deterministic. ``avg_score`` is the hard pass rate — the
same number the scorecard shows — and the judge average is reported next to it
as ``judge_avg``. Mixing the judge into the headline would make the run list
and the scorecard disagree about the same run, and would make a rerun with a
warmer judge look like a quality improvement.

Persistence is deliberately absent: ``eval_service`` owns every DB write.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services.config_loader import load_intents, load_persona_definitions
from boerdi.services.eval.judge import judge_turn
from boerdi.services.eval.metrics import (
    _aggregate,
    _aggregate_classification_metrics,
    count_chat_error_turns,
    count_judge_failed_turns,
)

logger = logging.getLogger(__name__)


def _stub(entity_id: str) -> dict[str, str]:
    """Placeholder definition for an id the config does not know.

    The judge prompt renders ``label`` and ``description``; handing it ``None``
    would put "None" into the rubric.
    """
    return {"id": entity_id, "label": entity_id, "description": ""}


async def judge_conversations(conversations: list[dict[str, Any]]) -> int:
    """Attach an LLM-judge verdict to every answered turn, in place.

    Returns the number of turns successfully judged. Turns carrying an
    ``error`` are skipped: the chat never answered, so there is nothing to
    score and a zero would punish the run for an outage.

    GV4: v2 records carry the Zielgruppe separately (``persona_id`` is "*" so
    the classification metrics see no target) — the judge rubric prefers it.
    The turn's ``must_offer`` travels to the judge as ``soll_angebot`` and
    becomes the ``auftrag_erfuellt`` axis. A failing judge call marks the turn
    ``judge_failed`` (no ``judge`` key), which keeps it out of ``judge_avg``
    instead of dragging it down with a silent zero.

    One judge call per turn — a 12-flow gold run is roughly 40 calls, which is
    why ``judge`` is opt-in on the endpoint.
    """
    persona_defs = {p.get("id"): p for p in load_persona_definitions()}
    intent_defs = {i.get("id"): i for i in load_intents()}
    judged = 0

    for conv in conversations:
        flow_persona = str(conv.get("zielgruppe") or conv.get("persona_id") or "*")
        persona = persona_defs.get(flow_persona) or _stub(flow_persona)
        for turn in conv.get("turns", []):
            if turn.get("error"):
                continue
            # Per-turn expectation, NOT the flow's primary intent: a multi-turn
            # flow shifts intent, and judging turn 3 against turn 1's target
            # would score a correct answer as wrong. An unset expectation
            # becomes an empty stub — "no target" rather than a guessed one.
            # (v2 records carry no intent expectations at all.)
            intent_id = str(turn.get("expected_intent") or "")
            intent = intent_defs.get(intent_id) or _stub(intent_id)
            soll = str(
                ((turn.get("golden") or {}).get("expected") or {})
                .get("must_offer") or ""
            )
            try:
                turn["judge"] = await judge_turn(
                    persona, intent, turn.get("user") or "",
                    turn.get("bot") or "", turn.get("debug") or {},
                    soll_angebot=soll or None,
                )
            except Exception as e:
                logger.warning("[golden] judge failed for a turn: %s", e)
                turn["judge_failed"] = str(e)[:200]
                continue
            judged += 1

    return judged


def summarize_golden_run(
    conversations: list[dict[str, Any]],
    *,
    target_turns: int,
    golden_metrics: dict[str, Any],
    current_activity: str = "Fertig",
) -> dict[str, Any]:
    """Build the ``eval_runs.summary`` payload for a golden run.

    ``golden_metrics`` comes from the deterministic runner (``aggregate_golden``)
    and is enriched in place with the judge cut, so the scorecard and the
    summary cannot drift apart.
    """
    summary = _aggregate(conversations)
    summary["target_turns"] = target_turns
    summary["current_activity"] = current_activity
    # The only source GET /eval/trends reads for its five series. A golden run
    # that omits it leaves those series empty no matter how many runs exist.
    summary["classification_metrics"] = _aggregate_classification_metrics(conversations)
    summary["golden_metrics"] = golden_metrics
    if summary.get("total_judged_turns"):
        judge_avg = summary.get("avg_score")
        summary["judge_avg"] = judge_avg
        golden_metrics["judge_avg"] = judge_avg
        golden_metrics["judged_turns"] = summary["total_judged_turns"]
    # GV4: ausgefallene Judge-Aufrufe werden GEZÄHLT statt als 0 gemittelt —
    # sonst sähe ein Gutachter-Ausfall wie ein Bot-Versagen aus. (Seit Review
    # Runde 2 derselbe Zähler wie im generativen Summary — eine Definition.)
    judge_failed = count_judge_failed_turns(conversations)
    summary["judge_failed_turns"] = judge_failed
    if judge_failed:
        golden_metrics["judge_failed_turns"] = judge_failed
    # Review-Befund 4 (2026-08-22): Chat-Fehler-Züge zählen wie Judge-Ausfälle.
    # Die CLI meldet sie über Exit 1 + stderr; der GESPEICHERTE Lauf stand
    # ohne Zähler grün da, obwohl N Züge nie stattfanden.
    chat_errors = count_chat_error_turns(conversations)
    summary["chat_error_turns"] = chat_errors
    if chat_errors:
        golden_metrics["chat_error_turns"] = chat_errors
    summary["avg_score"] = golden_metrics["overall_pass_rate"]
    return summary
