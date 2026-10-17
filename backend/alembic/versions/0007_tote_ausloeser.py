"""0007 — Tote Auslöser aus der Konfiguration räumen (Paket 7, K4).

``05-canvas/create-triggers`` und ``05-canvas/edit-triggers`` hatten keinen Leser
im Produktionscode und sind mit Modell, Seed und Studio-Abschnitt gestrichen
(Nutzer-Entscheid 2026-10-09). Ohne diese Migration blieben ihre Zeilen in jeder
bestehenden Datenbank stehen: in „Alle Bereiche“ als Rohdokument, das nichts
bewirkt, und im Abgleich mit dem Auslieferungsstand als ewige Abweichung.

Die Versionsgeschichte (``config_history``) bleibt unberührt. Der NOTIFY-Trigger
aus 0003 meldet das Löschen jeder Replika. ``downgrade`` stellt nichts wieder her:
der Inhalt hatte keine Wirkung, und die Seeds stehen in der Git-Geschichte.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-09
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "DELETE FROM config_areas "
        "WHERE area IN ('05-canvas/create-triggers', '05-canvas/edit-triggers')"
    )


def downgrade() -> None:
    pass
