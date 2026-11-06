"""0020 — Indizes der Vorgänge (Querschnitts-Review 2026-11-06).

- ``ix_vorgaenge_session_id``: ``session_id … ON DELETE SET NULL`` prüfte sonst bei jedem gelöschten
  Sitzungs-Datensatz die ganze Tabelle (die Aufbewahrung löscht in Stapeln zu 5000).
- ``ix_vorgaenge_aufrufer_muster`` (``text_pattern_ops``): ``aufrufer LIKE 'sitzung:%'`` nutzt so
  den Index auch unter einer Sortierfolge, die nicht ``C`` ist.
- ``ix_vorgaenge_aufrufer`` (0018) fällt weg: der Muster-Index trägt auch ``aufrufer = :a``.
- ``ix_vorgang_auftraege_vorgang`` heißt wie im Modell ``ix_vorgang_auftraege_vorgang_id``.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-06
"""

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgaenge_session_id ON vorgaenge (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgaenge_aufrufer_muster "
               "ON vorgaenge (aufrufer text_pattern_ops)")
    op.execute("DROP INDEX IF EXISTS ix_vorgaenge_aufrufer")
    op.execute("ALTER INDEX IF EXISTS ix_vorgang_auftraege_vorgang "
               "RENAME TO ix_vorgang_auftraege_vorgang_id")


def downgrade() -> None:
    op.execute("ALTER INDEX IF EXISTS ix_vorgang_auftraege_vorgang_id "
               "RENAME TO ix_vorgang_auftraege_vorgang")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgaenge_aufrufer ON vorgaenge (aufrufer)")
    op.execute("DROP INDEX IF EXISTS ix_vorgaenge_aufrufer_muster")
    op.execute("DROP INDEX IF EXISTS ix_vorgaenge_session_id")
