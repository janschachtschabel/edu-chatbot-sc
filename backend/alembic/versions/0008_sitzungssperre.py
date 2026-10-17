"""0008 — Sitzungssperre über alle Kopien (Paket 7, P1 — P5-1, Audit C-H1).

Bis hier serialisierte ein ``asyncio.Lock`` je Prozess die Züge einer Sitzung;
zwei Kopien (``BACKEND_REPLICAS`` > 1) liefen trotzdem parallel und
überschrieben sich ``session_state``. Eine Advisory-Sperre müsste über den
ganzen Zug eine Verbindung halten (der Zug committet mehrfach, eine xact-Sperre
fiele jedes Mal) — bei 20 parallelen Zügen je Kopie mehr, als der Pool hat.

Deshalb ein Eintrag mit Ablaufzeit: genommen mit einem ``INSERT … ON CONFLICT``,
verlängert im Takt, freigegeben am Ende. Stirbt eine Kopie mitten im Zug, läuft
er ab (``services/sitzungssperre``). Ohne Fremdschlüssel auf ``sessions``: beim
ersten Zug einer Sitzung gibt es deren Zeile noch nicht.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-09
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS session_locks (
          session_id text PRIMARY KEY,
          owner text NOT NULL,
          expires_at timestamptz NOT NULL)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS session_locks")
