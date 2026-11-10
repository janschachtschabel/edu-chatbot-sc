"""0022 — Sitzungen der Studio-Vorschau tragen eine eigene Spalte (Plan 2026-11-10, TB-E2).

``sessions.vorschau`` (``boolean``, Vorgabe ``false``): die Sitzung stammt aus der Widget-Vorschau
des Studios (Gespräch oder Ablauf-Probe) und zählt nicht als Betrieb
(``services/session_origin``). Bis hierher stand die Marke nur in ``entities`` (``_probe``,
``_vorschau``) — die Aufbewahrung leert ``entities`` nach der Frist der Gesprächsverläufe
(``aufbewahrung._stand_leeren``), danach zählte jede Vorschau-Sitzung wieder als Betrieb
(Review TB-E2, Befund 1). Die Spalte bleibt.

Vorhandene Marken werden übernommen. Der Teilindex ``ix_sessions_vorschau`` trägt den
Herkunftsfilter (Review TB-E2, Befund 4): er liest nur die wenigen Vorschau-Zeilen.

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-10
"""

from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS vorschau boolean NOT NULL "
               "DEFAULT false")
    op.execute("UPDATE sessions SET vorschau = true "
               "WHERE entities @> '{\"_probe\": true}'::jsonb "
               "OR entities @> '{\"_vorschau\": true}'::jsonb")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sessions_vorschau ON sessions (session_id) "
               "WHERE vorschau")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_sessions_vorschau")
    op.execute("ALTER TABLE sessions DROP COLUMN IF EXISTS vorschau")
