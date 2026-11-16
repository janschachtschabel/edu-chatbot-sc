"""0023 — mehrere Strukturdokumente je Sitzung (Plan 2026-11-16, TG-3e).

Bis hierher trug ``dokument_uploads.session_id`` eine Eindeutigkeit (0017: „ein Dokument je
Sitzung, ein neues ersetzt das alte“). Der Nutzer will Themenbäume „aus einem oder mehreren
Strukturdokumenten“: anonym bis zu fünf je Sitzung (``services/dokumente/ablage.MAX_JE_SITZUNG``).
Die Eindeutigkeit fällt, ein gewöhnlicher Index trägt das Lesen je Sitzung.

Der Name der Eindeutigkeit stammt von Postgres (``UNIQUE`` in ``CREATE TABLE``, 0017):
``dokument_uploads_session_id_key``. Der Rückweg behält je Sitzung nur das jüngste Dokument —
sonst ließe sich die Eindeutigkeit nicht wieder anlegen.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-16
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE dokument_uploads "
               "DROP CONSTRAINT IF EXISTS dokument_uploads_session_id_key")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dokument_uploads_session_id "
               "ON dokument_uploads (session_id)")


def downgrade() -> None:
    # Je Sitzung nur das jüngste — die alte Regel „ein Dokument je Sitzung“.
    op.execute("""
        DELETE FROM dokument_uploads d
        USING dokument_uploads j
        WHERE d.session_id = j.session_id
          AND (d.erstellt, d.id) < (j.erstellt, j.id)
    """)
    op.execute("DROP INDEX IF EXISTS ix_dokument_uploads_session_id")
    op.execute("ALTER TABLE dokument_uploads "
               "ADD CONSTRAINT dokument_uploads_session_id_key UNIQUE (session_id)")
