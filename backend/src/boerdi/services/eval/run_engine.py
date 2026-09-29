"""Which engine answered an eval run (ST-7a) — read in exactly one place.

Since ST-7 every run records at start where its turns go
(``config.engine_effective``, resolved like the chat does via
``choose_engine``). Older golden runs carry only the explicit choice in
``config.engine`` — including ``hybrid`` from the K0 measurement — and
"default" there does not say which engine it was. Older generative runs carry
nothing. Unknown stays empty instead of being guessed.

The SQL condition sits next to the Python reading on purpose: the list filter
and the engine shown in each row must never disagree about a run.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import ColumnElement, func

from boerdi.db.models import EvalRun

#: What a run can carry as its engine — ``hybrid`` only from runs before K1-1.
KNOWN_ENGINES = ("pattern", "agent", "hybrid")


def run_engine(config: dict[str, Any] | None) -> str:
    """The engine of a run, or ``""`` when it was never recorded."""
    cfg = config or {}
    for key in ("engine_effective", "engine"):
        value = str(cfg.get(key) or "")
        if value in KNOWN_ENGINES:
            return value
    return ""


def engine_matches(engine: str) -> ColumnElement[bool]:
    """SQL twin of :func:`run_engine` for one engine: resolved value first,
    then the explicit choice of an older run."""
    return func.coalesce(
        EvalRun.config["engine_effective"].astext,
        EvalRun.config["engine"].astext,
    ) == engine
