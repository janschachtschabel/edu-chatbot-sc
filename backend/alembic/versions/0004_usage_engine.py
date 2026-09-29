"""0004 — Maschine je Verbrauchszeile (AG-1).

``usage_events`` bekommt die Spalte ``engine``: die Maschine, an die der Zug
ging (``pattern``, ``agent``, ``hybrid``). Bis hier ließen sich Kosten nicht
nach Maschine trennen — die Muster-Kennung im Debug-Block war die einzige
Spur, und ein Hybrid-Zug mit gewähltem Muster sah aus wie ein Muster-Zug
(``docs/plans/2026-09-26-betriebsmodi-und-studio.md`` §2.4 und §8 AG-1).

**Nullbar und ohne Rückfüllung.** Alte Zeilen kennen ihre Maschine nicht, und
Frühausstiege (Direktaktionen) antworten vor jeder Maschine — ein geratener
Wert wäre Geld unter falschem Namen. Kein Index: gefragt wird immer nach einem
Zeitraum, und dafür gibt es ``idx_usage_created``.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-26
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``ADD COLUMN`` ohne Vorgabewert ist in Postgres eine reine
    # Katalogänderung: kein Umschreiben der Tabelle, keine lange Sperre.
    op.execute("ALTER TABLE usage_events ADD COLUMN IF NOT EXISTS engine text")


def downgrade() -> None:
    op.execute("ALTER TABLE usage_events DROP COLUMN IF EXISTS engine")
