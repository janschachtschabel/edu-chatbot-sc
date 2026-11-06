"""0019 — Aufträge eines Vorgangs (b-api-Jobs, Paket K1a, Plan 2026-11-05 §5/§9).

Ein ``auftrag``-Schritt startet einen Kestra-Flow über die b-api; die Job-ID hält diese Tabelle (der
Schlüssel, mit dem er gestartet wurde, wird NIE gespeichert — abgefragt wird im Zug der Person).
Geht der Vorgang (Frist, Sitzung, Löschen), gehen seine Aufträge mit (``ON DELETE CASCADE``).
``status``: ``laeuft`` | ``fertig`` | ``fehler`` | ``abgebrochen``.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-06
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vorgang_auftraege (
            id TEXT PRIMARY KEY,
            vorgang_id TEXT NOT NULL REFERENCES vorgaenge(id) ON DELETE CASCADE,
            job_id TEXT NOT NULL,
            flow TEXT NOT NULL,
            schritt TEXT NOT NULL,
            status TEXT NOT NULL,
            erstellt TIMESTAMPTZ NOT NULL DEFAULT now(),
            geaendert TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgang_auftraege_vorgang "
               "ON vorgang_auftraege (vorgang_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vorgang_auftraege")
