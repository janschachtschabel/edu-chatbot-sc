"""0016 — die Trace-ID je Zug (Paket 18C/D, Phase 1).

Aus einer Logzeile und aus der Fehlernummer einer Fehlerblase führt die Trace-ID zum Zug im
Studio. Dafür tragen die Nachricht, das Qualitäts- und das Sicherheitsprotokoll die Trace-ID der
Anfrage, in der sie entstanden sind. ``NULL`` bleibt erlaubt: Hintergrundläufe haben keine
Anfrage, und der Altbestand hat keine.

Gesucht wird nach dem Präfix der Fehlernummer — ``text_pattern_ops``, damit ``LIKE 'abc%'`` den
Index auch unter einer Sortierfolge nutzt, die nicht ``C`` ist. Nur Zeilen mit Trace-ID.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-29
"""

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

_TABELLEN = ("messages", "quality_logs", "safety_logs")


def upgrade() -> None:
    for tabelle in _TABELLEN:
        op.execute(f"ALTER TABLE {tabelle} ADD COLUMN IF NOT EXISTS trace_id TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_trace_id "
        "ON messages (trace_id text_pattern_ops) WHERE trace_id IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_messages_trace_id")
    for tabelle in _TABELLEN:
        op.execute(f"ALTER TABLE {tabelle} DROP COLUMN IF EXISTS trace_id")
