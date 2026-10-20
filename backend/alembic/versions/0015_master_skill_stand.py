"""0015 — der Master-Skill-Stand als gemeinsame Zeile (Paket 17, C3).

Bis hier hielt jede Kopie den Master-Skill allein im Speicher: N Kopien fragten im Takt N-mal
das Repositorium ab, „Neu laden“ wirkte nur auf einer, und zwei Kopien konnten verschiedene
Fassungen in den Prompt legen. Seither holt nur die Kopie mit der Sperre
``__lauf:master-skill``, schreibt den Stand hierher und meldet ihn über ``config_changed``;
die übrigen übernehmen die Zeile (``services/master_skill_stand``).

Laufzeit-Zustand, keine Konfiguration: nicht in ``config_areas`` (sonst Teil von Export,
Schnappschuss und Werksabgleich). ``geprueft_um`` ist der letzte Versuch, auch ein
gescheiterter — er entscheidet, ob der Takt wieder abfragt; ``abgerufen_um`` der letzte Erfolg.

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-20
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS master_skill_stand ("
        " node_id TEXT PRIMARY KEY,"
        " text TEXT,"
        " abgerufen_um TIMESTAMPTZ,"
        " letzter_fehler TEXT,"
        " geprueft_um TIMESTAMPTZ NOT NULL DEFAULT now())"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS master_skill_stand")
