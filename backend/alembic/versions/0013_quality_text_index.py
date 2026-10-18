"""0013 — Teilindex für Qualitäts-Zeilen, deren Text noch nicht geleert ist (Review PR #18, B2).

Der Text-Schritt des Aufbewahrungslaufs (``services/aufbewahrung``, Bereich ``quality_text``)
sucht Zeilen ohne Marke ``text_geleert``, die älter als die Gesprächsfrist sind. Geleerte Zeilen
bleiben bis zur Frist des Protokolls liegen; ohne Index las jeder Lauf ihr ganzes ``data`` (samt
Debug) erneut. Im Teilindex stehen nur ungeleerte Zeilen — eine geleerte fällt beim Leeren heraus.

``CONCURRENTLY``: die Tabelle wächst mit jedem Zug, ein gewöhnlicher Index sperrte das Schreiben
während des Deploys. Das geht nur außerhalb einer Transaktion (``autocommit_block``).

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-18
"""

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_quality_logs_text_offen
            ON quality_logs (created_at, id)
            WHERE (data ->> 'text_geleert') IS NULL
        """)


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_quality_logs_text_offen")
