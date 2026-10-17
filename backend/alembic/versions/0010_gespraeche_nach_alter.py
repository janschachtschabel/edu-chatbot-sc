"""0010 — Index auf ``created_at`` für Nachrichten und Merkposten (Paket 9).

Die Aufbewahrung (Paket 8, ``services/aufbewahrung``) fragt je Protokoll
``created_at < Grenze`` — im Überblick des Studios und in jedem Löschstapel. Die
Log-Tabellen haben den Index seit 0001 (``idx_safety_created``,
``idx_quality_created``), ``messages`` und ``memory`` nicht: Postgres las dafür
die ganze Tabelle (Review Paket 7, MINOR 19).

``IF NOT EXISTS`` und ohne ``CONCURRENTLY`` wie in 0005: der Migrations-Dienst
läuft vor den Backends, es schreibt niemand mit.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-09
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_memory_created ON memory(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_memory_created")
    op.execute("DROP INDEX IF EXISTS idx_messages_created")
