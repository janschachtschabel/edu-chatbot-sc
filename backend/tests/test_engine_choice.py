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

import pytest

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


def test_die_kopfzeile_hybrid_gilt_als_agent(monkeypatch, caplog):
    """K1-1 (2026-09-27): der Hybrid ist entfernt. Laufende Einbettungen, die
    ihn noch anfordern, dürfen nicht brechen und auch nicht still auf die
    Vorgabe fallen — sie bekommen die Schleife, mit einer Warnung im Log."""
    engine_choice._warne_einmal.cache_clear()
    with caplog.at_level("WARNING"):
        assert _waehle(monkeypatch, header="hybrid") == "agent"
        assert _waehle(monkeypatch, header="Hybrid") == "agent"
    warnungen = [r for r in caplog.records if "hybrid" in r.getMessage().lower()]
    assert len(warnungen) == 1  # einmal je Prozess, nicht je Zug


def test_eine_gespeicherte_hybrid_vorgabe_gilt_als_agent(monkeypatch):
    engine = EngineArea.model_validate({"mode": "hybrid"})
    assert _waehle(monkeypatch, engine=engine) == "agent"


def test_die_zwei_maschinen_sind_verschieden():
    """Wächter gegen einen Tippfehler in den Konstanten: zwei Namen, zwei Werte.
    Fielen sie zusammen, liefe eine Maschine still als die andere — und der
    A/B-Vergleich verglich einen Lauf mit sich selbst, ohne rot zu werden."""
    zwei = {engine_choice.PATTERN, engine_choice.AGENT}
    assert len(zwei) == 2
    assert zwei == set(engine_choice._ERLAUBT)
    assert not hasattr(engine_choice, "HYBRID")


@pytest.mark.parametrize(("engine", "erzwungen", "schleife"), [
    ("agent", "", True),
    ("agent", None, True),
    ("pattern", "", False),
    ("agent", "M01", False),
    ("agent", "M02", False),
    ("pattern", "M01", False),
])
def test_ein_erzwungenes_muster_holt_den_zug_aus_der_schleife(
        engine, erzwungen, schleife):
    """SF-1: Die Sicherheit geht der Maschine vor. ``route`` und ``respond``
    fragen beide hier — dieselbe Tabelle für beide Knoten."""
    assert engine_choice.zug_laeuft_ueber_die_schleife(engine, erzwungen) is schleife


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
