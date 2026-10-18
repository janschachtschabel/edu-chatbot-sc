"""0012 — Ablage der festen Prompt-Bausteine (Paket 13, A4).

``prompt_versions`` hält jede Fassung eines festen Systemteils (Agent-Kopf, Master-Skill,
Seitenregeln, Muster-Antwortschichten, Klassifikator-Festteil) genau einmal, Schlüssel ist die
Prüfsumme. Läufe und Züge tragen nur Prüfsummen; ein Vergleich zweier Läufe holt hier die Texte.
Nur feste Teile, keine Nutzer- oder Seitendaten — deshalb ohne Aufbewahrungsfrist.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-17
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS prompt_versions (
            hash text PRIMARY KEY,
            art text NOT NULL,
            text text NOT NULL,
            erstmals timestamptz NOT NULL DEFAULT now(),
            zuletzt timestamptz NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS prompt_versions")
