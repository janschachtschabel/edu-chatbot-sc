"""0017 — hochgeladene Dokumente im Chat (Paket U3-2a, Plan 2026-11-04 §16.6).

Ein Strukturdokument (z. B. ein Lehrplan), im Chat hochgeladen und mit markitdown umgewandelt. Die
Rohdatei wird nie gespeichert — nur das bereinigte Markdown, die Gliederung und der Befund. Ein
Dokument je Sitzung (ein neues ersetzt das alte), an der Sitzung mit ``ON DELETE CASCADE``.
``verfaellt_am`` = letzte Nutzung + 24 h (Studio ``aufbewahrung_h``); abgelaufene Zeilen sind sofort
unlesbar und verschwinden im Aufbewahrungslauf.

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-05
"""

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS dokument_uploads (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL UNIQUE REFERENCES sessions(session_id) ON DELETE CASCADE,
            block_id TEXT NOT NULL,
            aufrufer TEXT,
            name TEXT NOT NULL,
            format TEXT NOT NULL,
            groesse INTEGER NOT NULL,
            befund JSONB NOT NULL,
            gliederung JSONB NOT NULL,
            markdown TEXT NOT NULL,
            erstellt TIMESTAMPTZ NOT NULL DEFAULT now(),
            genutzt TIMESTAMPTZ NOT NULL DEFAULT now(),
            verfaellt_am TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dokument_uploads_verfaellt_am "
               "ON dokument_uploads (verfaellt_am)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dokument_uploads")
