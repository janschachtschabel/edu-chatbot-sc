"""0009 — Verbrauch ohne Sitzung: Aufträge der Agent-API (Paket 7, P3 — P5-3).

Aufträge über ``/api/agent`` verbrauchen Token, gehören aber keiner Chat-Sitzung
— und erschienen deshalb nirgends in der Kostenübersicht. ``session_id`` wird
nullbar (der Fremdschlüssel bleibt für alle Zeilen MIT Sitzung), und ``quelle``
sagt, woher eine Zeile ohne Sitzung kommt (``agent-api``). Chat-Zeilen lassen
die Spalte leer.

Beides reine Katalogänderungen (``DROP NOT NULL``, ``ADD COLUMN`` ohne
Vorgabewert): kein Umschreiben der Tabelle.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-09
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE usage_events ALTER COLUMN session_id DROP NOT NULL")
    op.execute("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS quelle text")


def downgrade() -> None:
    # Zeilen ohne Sitzung passen nicht mehr ins alte Schema — sie gehen mit.
    op.execute("DELETE FROM usage_events WHERE session_id IS NULL")
    op.execute("ALTER TABLE usage_events DROP COLUMN IF EXISTS quelle")
    op.execute("ALTER TABLE usage_events ALTER COLUMN session_id SET NOT NULL")
