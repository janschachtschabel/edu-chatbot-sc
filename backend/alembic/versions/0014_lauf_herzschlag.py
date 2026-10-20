"""0014 — Herzschlag der Läufe, höchstens ein laufender Lasttest (Paket 17, C1/C2).

Bei mehreren Repliken stimmte die Annahme „eine ``running``-Zeile nach einem Prozessstart ist
verwaist“ nicht mehr: ein neuer Pod brach den laufenden Lasttest eines anderen ab, und ein
beendeter Pod hinterließ einen Eval-Lauf, der neue Läufe bis zu 2 h blockierte. Seither
schreibt jeder Lauf alle 15 s ``heartbeat_at`` (``obs/herzschlag``); verwaist ist nur, wessen
Herzschlag ausbleibt.

Der Unique-Teilindex macht für Lasttests, was 0006 für Eval-Läufe tat: Prüfen-dann-Einfügen
ließ zwei gleichzeitige Starts durch. Vorher gehen alle laufenden Lasttest-Zeilen bis auf die
jüngste auf ``failed`` — sonst ließe sich der Index nicht anlegen.

``IF NOT EXISTS`` und ohne ``CONCURRENTLY`` wie 0006: der Migrations-Dienst läuft vor den
Backends.

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-20
"""

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE loadtest_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ")
    op.execute("ALTER TABLE eval_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ")
    op.execute(
        "UPDATE loadtest_runs SET status = 'failed', "
        "result = COALESCE(result, '{}'::jsonb) || jsonb_build_object('error', "
        "'beim Update auf 0014 abgeräumt: es lief ein jüngerer Lasttest') "
        "WHERE status = 'running' AND id <> ("
        "SELECT id FROM loadtest_runs WHERE status = 'running' "
        "ORDER BY created_at DESC LIMIT 1)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_loadtest_runs_ein_laufender "
        "ON loadtest_runs ((true)) WHERE status = 'running'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_loadtest_runs_ein_laufender")
    op.execute("ALTER TABLE eval_runs DROP COLUMN IF EXISTS heartbeat_at")
    op.execute("ALTER TABLE loadtest_runs DROP COLUMN IF EXISTS heartbeat_at")
