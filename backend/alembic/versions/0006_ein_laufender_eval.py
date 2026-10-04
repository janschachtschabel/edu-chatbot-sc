"""0006 — Höchstens ein laufender Eval-Lauf (Paket 4, E2; externes Audit F22).

``_ensure_no_running_run`` prüfte, angelegt wurde danach — ohne Index und ohne
Sperre. Zwei Starts zur selben Zeit sahen beide keinen laufenden Lauf und legten
beide einen an. Ein eindeutiger Teil-Index über ``status = 'running'`` lässt die
Datenbank entscheiden: der zweite ``INSERT`` scheitert, und der Start antwortet
mit derselben 409 wie bisher (``run_store._lauf_anlegen``).

Vor dem Index: Stehen schon mehrere Zeilen auf ``running`` (Absturz-Reste),
ließe er sich nicht anlegen, und die Migration hielte den Start der Anlage auf.
Alle bis auf die jüngste gehen deshalb auf ``failed`` — dasselbe, was das
Aufräumen beim nächsten Start mit veralteten Läufen ohnehin tut.

``IF NOT EXISTS`` und ohne ``CONCURRENTLY`` wie 0005: der Migrations-Dienst
läuft vor den Backends.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-03
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE eval_runs SET status = 'failed', "
        "error_message = 'weiterer laufender Run bei Migration 0006 abgeräumt' "
        "WHERE status = 'running' AND id <> ("
        "SELECT id FROM eval_runs WHERE status = 'running' "
        "ORDER BY created_at DESC LIMIT 1)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_runs_ein_laufender "
        "ON eval_runs ((true)) WHERE status = 'running'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_eval_runs_ein_laufender")
