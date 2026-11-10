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

Plan 2026-11-10, TB-E2 (user decision N3): the studio preview's chats and trial runs (widget
attributes ``vorschau``/``probe``) keep the widget prefix ``bb-``; their mark is the column
``sessions.vorschau`` (migration 0022 — not ``entities``, which retention empties). ``production``
therefore also leaves out every such session, and the scope ``probe`` shows only them. The filter
is an uncorrelated ``NOT IN (SELECT …)`` on a partial index — still static SQL.

Both helpers emit STATIC SQL: the only inputs are the scope keyword (matched
against fixed literals) and, for the Core variant, a column object from code.
"""

from typing import Final, Literal

from sqlalchemy import ColumnElement, and_, literal_column, or_, select, text

EVAL_PREFIX: Final = "eval-"
LOADTEST_PREFIX: Final = "loadtest-"
STUDIO_PREFIX: Final = "studio-"
#: Paket 19 (Audit M-5): diese Präfixe darf nur die Anlage selbst wählen — am öffentlichen
#: Eingang weist ``api/turn_auth.pruefe_oeffentliche_kennung`` sie ab. Groß/klein wie
#: :func:`scope_sql` (``LIKE`` unterscheidet): ``Eval-x`` zählt als Betrieb und bleibt offen.
RESERVIERTE_PRAEFIXE: Final = (EVAL_PREFIX, LOADTEST_PREFIX, STUDIO_PREFIX)
#: Paket 19 (N-9): die Kennung ist der einzige Schlüssel eines Verlaufs — öffentlich (Chat und
#: Lese-Endpunkt) mindestens so lang. Das Widget erzeugt ``bb-<uuid>`` (39 Zeichen).
MIN_OEFFENTLICHE_KENNUNG: Final = 16
#: Quelle der Aufträge, die der Auftragstester des Studios über ``/studio/api/agent``
#: auslöst (Paket 9, Review Paket 7 MINOR 31) — Probeläufe ohne Sitzung, kein Betrieb.
STUDIO_QUELLE: Final = "studio-probe"
#: Paket 15 (A6): Judge, Simulator und Szenarien eines Eval-Laufs buchen ohne Sitzung unter
#: ``eval-judge`` / ``eval-simulator`` / ``eval-szenario`` — Auswertung, kein Betrieb.
EVAL_QUELLE_PREFIX: Final = "eval-"

#: TB-E2: the sessions of the studio preview (column ``sessions.vorschau``, migration 0022). Static
#: SQL — no input reaches it. ``session_id`` is the primary key, so ``NOT IN`` meets no NULL.
PROBE_SITZUNGEN_SQL: Final = (
    "SELECT probe_s.session_id FROM sessions AS probe_s WHERE probe_s.vorschau")

#: The vocabulary of every ``scope`` parameter (quality, usage, sessions).
Scope = Literal["all", "production", "eval", "probe"]


def _probe_sitzungen():  # noqa: ANN202 — ein SQLAlchemy-Ausdruck (Unterabfrage)
    return select(literal_column("probe_s.session_id")).select_from(
        text("sessions AS probe_s")).where(
        text("probe_s.vorschau"))


def scope_sql(scope: str) -> str:
    """WHERE fragment on ``session_id`` for raw-SQL queries; ``''`` = no restriction.

    Unknown values restrict nothing, as the quality routes always did (their
    ``scope`` is a plain string).
    """
    s = (scope or "all").strip().lower()
    if s == "production":
        return (f"session_id NOT LIKE '{EVAL_PREFIX}%' "
                f"AND session_id NOT LIKE '{LOADTEST_PREFIX}%' "
                f"AND session_id NOT LIKE '{STUDIO_PREFIX}%' "
                f"AND session_id NOT IN ({PROBE_SITZUNGEN_SQL})")
    if s == "eval":
        return f"session_id LIKE '{EVAL_PREFIX}%'"
    if s == "probe":
        return f"session_id IN ({PROBE_SITZUNGEN_SQL})"
    return ""


def scope_clause(
    scope: str, column: ColumnElement[str], quelle: ColumnElement[str] | None = None,
) -> ColumnElement[bool] | None:
    """The same filter for SQLAlchemy Core queries; ``None`` = no restriction.

    ``quelle`` (``usage_events.quelle``, Paket 9): rows without a session count as
    production unless the studio's task tester booked them (:data:`STUDIO_QUELLE`) or an
    eval run did (``eval-…``, Paket 15) — those count as eval.
    """
    s = (scope or "all").strip().lower()
    if s == "production":
        # Paket 7 (P3): eine Zeile ohne Sitzung (Auftrag der Agent-API) ist
        # Betrieb. Ohne ``IS NULL`` fiele sie heraus — ``NULL NOT LIKE`` ist NULL.
        ohne_sitzung = column.is_(None)
        if quelle is not None:
            ohne_sitzung = and_(ohne_sitzung, or_(
                quelle.is_(None),
                and_(quelle != STUDIO_QUELLE, quelle.not_like(f"{EVAL_QUELLE_PREFIX}%"))))
        return or_(ohne_sitzung,
                   and_(column.not_like(f"{EVAL_PREFIX}%"),
                        column.not_like(f"{LOADTEST_PREFIX}%"),
                        column.not_like(f"{STUDIO_PREFIX}%"),
                        column.not_in(_probe_sitzungen())))
    if s == "probe":
        return column.in_(_probe_sitzungen())
    if s == "eval":
        if quelle is None:
            return column.like(f"{EVAL_PREFIX}%")
        return or_(column.like(f"{EVAL_PREFIX}%"),
                   and_(column.is_(None), quelle.like(f"{EVAL_QUELLE_PREFIX}%")))
    return None
