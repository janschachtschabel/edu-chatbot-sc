"""Where a session came from — read from its id, the only place that says so (ST-9).

No column and no header records the origin. The widget names its sessions
``bb-<uuid>`` (the studio preview embeds the same widget, so its sessions count
as real ones), the evaluation runs ``eval-<hex>`` (``services/eval/runner.py``,
and ``evals/run_golden.py`` on its own, it imports nothing from here), the load
test ``loadtest-<run>-s<stage>-<n>`` (``services/loadtest.py``), the chat probe on
the studio's agent page ``studio-<uuid>`` (ST-8e; the id is made in the browser,
``views/agent-probe.component.ts``).

``production`` = neither an eval, a load-test nor a studio-probe session. Until
ST-9 the quality filter only excluded ``eval-`` and counted load-test traffic as
real conversations — the studio labels that choice "real conversations only".

Both helpers emit STATIC SQL: the only inputs are the scope keyword (matched
against three literals) and, for the Core variant, a column object from code.
"""

from typing import Final, Literal

from sqlalchemy import ColumnElement, and_

EVAL_PREFIX: Final = "eval-"
LOADTEST_PREFIX: Final = "loadtest-"
STUDIO_PREFIX: Final = "studio-"

#: The vocabulary of every ``scope`` parameter (quality, usage, sessions).
Scope = Literal["all", "production", "eval"]


def scope_sql(scope: str) -> str:
    """WHERE fragment on ``session_id`` for raw-SQL queries; ``''`` = no restriction.

    Unknown values restrict nothing, as the quality routes always did (their
    ``scope`` is a plain string).
    """
    s = (scope or "all").strip().lower()
    if s == "production":
        return (f"session_id NOT LIKE '{EVAL_PREFIX}%' "
                f"AND session_id NOT LIKE '{LOADTEST_PREFIX}%' "
                f"AND session_id NOT LIKE '{STUDIO_PREFIX}%'")
    if s == "eval":
        return f"session_id LIKE '{EVAL_PREFIX}%'"
    return ""


def scope_clause(scope: str, column: ColumnElement[str]) -> ColumnElement[bool] | None:
    """The same filter for SQLAlchemy Core queries; ``None`` = no restriction."""
    s = (scope or "all").strip().lower()
    if s == "production":
        return and_(column.not_like(f"{EVAL_PREFIX}%"),
                    column.not_like(f"{LOADTEST_PREFIX}%"),
                    column.not_like(f"{STUDIO_PREFIX}%"))
    if s == "eval":
        return column.like(f"{EVAL_PREFIX}%")
    return None
