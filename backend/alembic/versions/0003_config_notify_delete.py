"""0003 — Config-NOTIFY auch beim Löschen (S1).

Der Trigger aus 0001 feuerte ``AFTER INSERT OR UPDATE``. Ein gelöschter
Konfigurations-Bereich blieb damit im Prozess-Cache **jeder anderen Replika**
stehen, bis sie neu startete: ``ConfigStore.delete()`` räumt nur den eigenen
(``self._cache.pop``), und die Benachrichtigung, die alle anderen aufweckt, kam
nie.

Aufgefallen beim Bau des Studio-Knopfes „Auslieferungsstand herstellen"
(``docs/plans/2026-08-17-werkszustand-im-studio.md``): dessen scharfe Betriebsart
löscht Bereiche, die nur in der Datenbank stehen. Ohne diese Migration hätte der
Knopf die Hälfte seiner Arbeit still nicht getan — auf einem Ein-Prozess-Server
unsichtbar, im Cluster ein Zustand, der je Replika verschieden ist.

Der bestehende ``DELETE /api/config/file`` hat denselben Fehler und wird hier
mitgeheilt; er wird nur seltener benutzt.

**``COALESCE(NEW, OLD)`` ist der Kern.** Beim ``DELETE`` ist ``NEW`` in einem
Zeilen-Trigger ``NULL`` — ``NEW.area`` allein hätte den Namen nicht gefunden und
die Funktion wäre still ohne Wirkung gelaufen.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-17
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_config_changed() RETURNS trigger AS $$
        BEGIN
          PERFORM pg_notify('config_changed', COALESCE(NEW.area, OLD.area));
          RETURN COALESCE(NEW, OLD);
        END $$ LANGUAGE plpgsql
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_config_notify ON config_areas")
    op.execute("""
        CREATE TRIGGER trg_config_notify
          AFTER INSERT OR UPDATE OR DELETE ON config_areas
          FOR EACH ROW EXECUTE FUNCTION notify_config_changed()
    """)


def downgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION notify_config_changed() RETURNS trigger AS $$
        BEGIN PERFORM pg_notify('config_changed', NEW.area); RETURN NEW; END $$ LANGUAGE plpgsql
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_config_notify ON config_areas")
    op.execute("""
        CREATE TRIGGER trg_config_notify AFTER INSERT OR UPDATE ON config_areas
          FOR EACH ROW EXECUTE FUNCTION notify_config_changed()
    """)
