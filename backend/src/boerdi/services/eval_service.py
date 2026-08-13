"""Eval service (P7) — facade over ``services/eval/`` for ``api/eval.py``.

The router stays thin; everything DB- or config-touching lives behind this
import point (spec rule 4). The implementation is split by responsibility:

* ``eval/cost`` — config snapshot + cost estimate (pure, no DB)
* ``eval/queries`` — ``eval_runs`` reads + pattern analytics over quality_logs
* ``eval/mutations`` — the delete paths
* ``eval/run_store`` — what both run families share: chat URL, parallel-guard,
  terminal write
* ``eval/generative_run`` — validation, run row and background job of the
  **generative** family, which drives the engine in ``services/eval/``
  (scenario generator, user simulator, LLM judge, metrics)
* ``eval/golden_run`` — the same for the **golden** family, which reuses the
  ported, framework-free runner ``evals/run_golden.py`` (deterministic per-turn
  checks + scorecard) and adds the optional judge layer on top

Both write ``summary.classification_metrics``, which is what ``GET /eval/trends``
reads for its five series.

Persistence maps ALT's flat ``eval_runs`` columns onto NEU's JSONB layout
(``config``/``totals``/``summary``/``conversations``); read endpoints reproduce
ALT's response shapes from that layout.
"""

from boerdi.services.eval.cost import (
    _compute_target_turns,
    estimate,
    estimate_cost,
    list_gold_flows,
    list_personas_and_intents,
)
from boerdi.services.eval.generative_run import (
    _execute_generative_run,
    _progress_writer,
    start_generative_run,
)
from boerdi.services.eval.golden_run import (
    _execute_golden_run,
    _load_golden_runner,
    start_golden_eval_run,
)
from boerdi.services.eval.mutations import (
    clear_eval_quality_logs,
    delete_run,
    delete_runs,
)
from boerdi.services.eval.queries import (
    get_run,
    get_trends,
    list_runs,
    pattern_usage_stats,
)
from boerdi.services.eval.run_store import _ensure_no_running_run, _finalize_run

__all__ = [
    "_compute_target_turns",
    "_ensure_no_running_run",
    "_execute_generative_run",
    "_execute_golden_run",
    "_finalize_run",
    "_load_golden_runner",
    "_progress_writer",
    "clear_eval_quality_logs",
    "delete_run",
    "delete_runs",
    "estimate",
    "estimate_cost",
    "get_run",
    "get_trends",
    "list_gold_flows",
    "list_personas_and_intents",
    "list_runs",
    "pattern_usage_stats",
    "start_generative_run",
    "start_golden_eval_run",
]
