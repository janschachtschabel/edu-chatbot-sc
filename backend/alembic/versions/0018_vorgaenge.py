"""0018 — Vorgänge: Arbeitsstand einer Person über Züge hinweg (Paket V1, Plan 2026-11-05 §2).

Ein Vorgang trägt die Daten eines Vorhabens als **benannte, typisierte Teile** in einer Akte
(``wlo.vorgang@1``: ``teile``, ``historie``, ``lauf``) — erfasste Ordner, gelesenes Dokument,
übernommener Entwurf, später Ergebnisse von Kestra-Aufträgen. Er entsteht auch ohne Ablauf.
Besitzerin ist die bestätigte WLO-Person (``aufrufer`` = ``aufrufer_kennung``), ohne Anmeldung
``sitzung:<id>``. Höchstens drei je Person (Nutzerentscheid E-16); ``verfaellt_am`` = letzte Nutzung
+ Studio ``vorgang_tage`` (Vorgabe 3). ``session_id`` ist nur die Herkunft (``ON DELETE SET NULL``);
anonyme Vorgänge löscht ``delete_session`` mit.

``vorgang_ablage`` hält große Teile und frühere Fassungen, damit die Akte klein bleibt.
Die Aufträge (B-API-Jobs) bekommen mit Paket K1 eine eigene Tabelle.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-05
"""

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS vorgaenge (
            id TEXT PRIMARY KEY,
            aufrufer TEXT NOT NULL,
            session_id TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
            titel TEXT NOT NULL,
            zweck TEXT NOT NULL,
            status TEXT NOT NULL,
            akte JSONB NOT NULL,
            akte_version INTEGER NOT NULL DEFAULT 0,
            erstellt TIMESTAMPTZ NOT NULL DEFAULT now(),
            geaendert TIMESTAMPTZ NOT NULL DEFAULT now(),
            verfaellt_am TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgaenge_aufrufer ON vorgaenge (aufrufer)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vorgaenge_verfaellt_am ON vorgaenge (verfaellt_am)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS vorgang_ablage (
            vorgang_id TEXT NOT NULL REFERENCES vorgaenge(id) ON DELETE CASCADE,
            schluessel TEXT NOT NULL,
            typ TEXT NOT NULL,
            inhalt JSONB NOT NULL,
            groesse INTEGER NOT NULL,
            erstellt TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (vorgang_id, schluessel)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vorgang_ablage")
    op.execute("DROP TABLE IF EXISTS vorgaenge")
