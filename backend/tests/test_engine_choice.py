"""A4a — welche Maschine diesen Zug beantwortet (``services/engine_choice.py``).

Der Umschalter liegt zweifach, und beide Ebenen werden hier festgehalten: der
Studio-Bereich ``01-base/engine`` ist die **Vorgabe**, die Kopfzeile
``X-Boerdi-Engine`` die **Übersteuerung je Anfrage** (ohne sie ließe sich kein
A/B in *einem* Golden-Lauf fahren).

Der wichtigste Test dieser Datei ist der letzte: die Gegenrichtung. Mit der
ausgelieferten Vorgabe und ohne Kopfzeile muss ``pattern`` herauskommen — das ist
die Zusage „der Chatbot läuft standardmäßig weiter wie bisher", und sie gehört
in einen Test statt in einen Vorsatz.
"""

from __future__ import annotations

from boerdi.domain.config_models.engine import EngineArea
from boerdi.services import engine_choice


def _waehle(monkeypatch, header=None, engine=None):
    # Die Attrappe hat die ECHTE Signatur: ``load_engine`` ist synchron. Eine
    # async-Attrappe hier hat den Fehler ``await load_engine()`` im Produktiv-
    # code eine Scheibe lang verdeckt — er flog erst auf, als der Chat-Zug ihn
    # rief (A4b, 2026-08-12).
    monkeypatch.setattr(engine_choice, "load_engine", lambda: engine or EngineArea())
    return engine_choice.choose_engine(header)


def test_ohne_kopfzeile_gilt_die_vorgabe(monkeypatch):
    assert _waehle(monkeypatch) == "pattern"


def test_die_vorgabe_kann_auf_agent_stehen(monkeypatch):
    assert _waehle(monkeypatch, engine=EngineArea(mode="agent")) == "agent"


def test_die_kopfzeile_uebersteuert_nach_agent(monkeypatch):
    assert _waehle(monkeypatch, header="agent") == "agent"


def test_die_kopfzeile_uebersteuert_auch_zurueck(monkeypatch):
    """Die Übersteuerung muss in BEIDE Richtungen gehen: sonst ließe sich eine
    auf ``agent`` gestellte Anlage nicht stichprobenweise gegen den Bestand
    messen."""
    engine = EngineArea(mode="agent")
    assert _waehle(monkeypatch, header="pattern", engine=engine) == "pattern"


def test_die_vorgabe_kann_auf_hybrid_stehen(monkeypatch):
    assert _waehle(monkeypatch, engine=EngineArea(mode="hybrid")) == "hybrid"


def test_die_kopfzeile_uebersteuert_nach_hybrid(monkeypatch):
    assert _waehle(monkeypatch, header="hybrid") == "hybrid"


def test_die_kopfzeile_uebersteuert_aus_dem_hybrid_heraus(monkeypatch):
    """Auch die dritte Maschine muss sich stichprobenweise gegen die beiden
    anderen messen lassen — sonst ließe sich eine auf ``hybrid`` gestellte
    Anlage nicht mit EINER Golden-Suite gegen den Bestand fahren."""
    hybrid = EngineArea(mode="hybrid")
    assert _waehle(monkeypatch, header="pattern", engine=hybrid) == "pattern"
    assert _waehle(monkeypatch, header="agent", engine=hybrid) == "agent"


def test_die_drei_maschinen_sind_verschieden():
    """Wächter gegen einen Tippfehler in den Konstanten: drei Namen, drei Werte.
    Fielen zwei zusammen, liefe eine Maschine still als die andere — und der
    A/B-Vergleich verglich einen Lauf mit sich selbst, ohne rot zu werden."""
    drei = {engine_choice.PATTERN, engine_choice.AGENT, engine_choice.HYBRID}
    assert len(drei) == 3
    assert drei == set(engine_choice._ERLAUBT)


def test_unbekannte_kopfzeile_wird_ignoriert(monkeypatch):
    """Ein Tippfehler darf nicht auf einen anderen Weg schalten — und erst
    recht nicht still den Bestand verlassen."""
    for unsinn in ("Agent!", "", "   ", "pattern-engine", "gpt", "hybrid-engine"):
        assert _waehle(monkeypatch, header=unsinn) == "pattern"


def test_die_kopfzeile_ist_unempfindlich_gegen_schreibweise(monkeypatch):
    assert _waehle(monkeypatch, header="  Agent  ") == "agent"


def test_ein_unlesbarer_bereich_bleibt_bei_pattern(monkeypatch):
    """``load_engine`` fängt seine Fehler selbst ab und liefert die Vorgabe;
    hier wird der Fall gepinnt, dass er trotzdem einmal wirft."""
    def _boom():
        raise RuntimeError("Datenbank weg")
    monkeypatch.setattr(engine_choice, "load_engine", _boom)
    assert engine_choice.choose_engine(None) == "pattern"


def test_gegenrichtung_der_ausgelieferte_stand_bleibt_die_musterengine(monkeypatch):
    """Der Wächter für die Zusage des Nutzers: mit dem ausgelieferten Bereich
    und ohne Kopfzeile wird die Agent-Schleife **nie** gewählt."""
    from boerdi.services.config_loader.engine import load_engine as echt  # noqa: F401
    assert EngineArea().mode == "pattern"
    assert _waehle(monkeypatch, header=None, engine=EngineArea()) == "pattern"
