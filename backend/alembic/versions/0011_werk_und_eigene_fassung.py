"""0011 — Werksfassung und eigene Fassung je Konfigurationsbereich (Paket 12).

``config_areas`` bleibt die gelebte Konfiguration. Neu je Bereich:

* ``werk_hash`` — Prüfsumme der Werksfassung (Seed im Image), auf der der Bereich zuletzt stand.
  Gleicht der Inhalt ihr noch, ist er unberührt, und der Werksabgleich hebt ihn auf eine neue
  Werksfassung. ``NULL``: kein Werksbereich oder (Bestand vor 0011) noch nicht zugeordnet.
* ``eigene_fassung`` — die eigene Fassung, solange im Studio die Werksfassung gewählt ist;
  ``eigene_basis`` — deren Werks-Prüfsumme (sie reist mit, Review Paket 12 #8).

``config_werk_entfernt`` merkt sich Werksbereiche, die im Studio gelöscht wurden — sonst legte der
nächste Werksabgleich sie wieder an. ``config_snapshots.art`` unterscheidet von Hand angelegte und
automatische Schnappschüsse (``hand`` / ``auto``); der Bestand gilt als ``hand``.

Keine Datenmigration: die Zuordnung des Bestands macht der Werksabgleich, der die Seeds kennt.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE config_areas ADD COLUMN IF NOT EXISTS werk_hash text")
    op.execute("ALTER TABLE config_areas ADD COLUMN IF NOT EXISTS eigene_fassung jsonb")
    op.execute("ALTER TABLE config_areas ADD COLUMN IF NOT EXISTS eigene_basis text")
    op.execute("""
        CREATE TABLE IF NOT EXISTS config_werk_entfernt (
            area text PRIMARY KEY,
            entfernt_am timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "ALTER TABLE config_snapshots ADD COLUMN IF NOT EXISTS art text NOT NULL DEFAULT 'hand'")


def downgrade() -> None:
    op.execute("ALTER TABLE config_snapshots DROP COLUMN IF EXISTS art")
    op.execute("DROP TABLE IF EXISTS config_werk_entfernt")
    op.execute("ALTER TABLE config_areas DROP COLUMN IF EXISTS eigene_basis")
    op.execute("ALTER TABLE config_areas DROP COLUMN IF EXISTS eigene_fassung")
    op.execute("ALTER TABLE config_areas DROP COLUMN IF EXISTS werk_hash")
