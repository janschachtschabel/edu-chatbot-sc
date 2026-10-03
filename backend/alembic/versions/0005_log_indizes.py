"""0005 — Indizes für die Log-Tabellen und die Konfig-Historie (Audit 2026-09-29 §6.4).

Gefragt wird nach Sitzung — ``/api/safety/logs?session_id=…`` und das Löschen
einer Sitzung (``services/db_sessions.delete_session``) — und nach Bereich samt
Version: die Historie im Studio (``WHERE area = … ORDER BY version DESC``). Ohne
Index liest Postgres dafür jeweils die ganze Tabelle, und die Logs wachsen mit
jedem Zug.

``IF NOT EXISTS``: eine Anlage, die einen dieser Indizes schon von Hand angelegt
hat, bricht die Migration nicht ab. Ohne ``CONCURRENTLY``: der Migrations-Dienst
läuft vor den Backends (``compose.prod.yml``), es schreibt also niemand mit.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-01
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_safety_session ON safety_logs(session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_quality_session ON quality_logs(session_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_config_history_area ON config_history(area, version)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_config_history_area")
    op.execute("DROP INDEX IF EXISTS idx_quality_session")
    op.execute("DROP INDEX IF EXISTS idx_safety_session")
