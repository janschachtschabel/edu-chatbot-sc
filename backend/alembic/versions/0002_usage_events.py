"""0002 — usage_events (Kostenüberwachung K2a).

Eigene Tabelle für den Token-Verbrauch je Zug und Modell. Warum nicht die
vorhandene JSONB-Spalte ``messages.debug`` auswerten (Nutzer-Entscheid, siehe
``docs/plans/2026-08-11-kostenueberwachung.md`` §3): abrechnungsfest,
indizierbar, mit eigener Aufbewahrungsfrist und unabhängig vom Debug-Format.

**Ohne Rückfüllung.** Die Vergangenheit trägt die Erfassungslücken, die K1
geschlossen hat (der Merkposten hatte bis 2026-08-11 gar keinen Erzeuger);
alte Züge zu importieren hieße, falsche Zahlen abrechnungsfest zu machen.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ``cached_tokens`` ist in ``prompt_tokens`` ENTHALTEN, ``reasoning_tokens``
    # in ``completion_tokens`` — so zählt es der Anbieter. Wer sie addiert,
    # rechnet doppelt. Absichtlich KEINE CHECK-Bedingung darauf: eine Zeile
    # verlieren, weil ein Anbieter einmal seltsam zählt, wäre schlechter als
    # eine seltsame Zeile zu haben — und der Schreibpfad darf einen Zug nie
    # scheitern lassen.
    op.execute("""
        CREATE TABLE usage_events (
          id bigserial PRIMARY KEY,
          session_id text NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
          model text NOT NULL,
          prompt_tokens     int NOT NULL DEFAULT 0,
          cached_tokens     int NOT NULL DEFAULT 0,
          completion_tokens int NOT NULL DEFAULT 0,
          reasoning_tokens  int NOT NULL DEFAULT 0,
          calls             int NOT NULL DEFAULT 0,
          created_at timestamptz NOT NULL DEFAULT now())
    """)
    # Zwei Abfragewege, zwei Indizes: „je Sitzung" (Abrechnungseinheit) und
    # „je Zeitraum". Der zweite ist Pflicht, nicht Kür — die Tabelle wächst
    # etwa wie ``messages``, und ohne ihn wird die Monatsabfrage langsam.
    op.execute("CREATE INDEX idx_usage_session ON usage_events(session_id)")
    op.execute("CREATE INDEX idx_usage_created ON usage_events(created_at)")


def downgrade() -> None:
    # Die beiden Indizes fallen mit der Tabelle.
    op.execute("DROP TABLE IF EXISTS usage_events")
