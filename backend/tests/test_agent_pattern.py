"""A4c — ``domain/agent_pattern``: der Ersatz für die Musterwahl im Agent-Modus.

Der Route-Test (``test_route_engine_mode``) fängt diese Funktion am Knoten ab —
er prüft die Verzweigung, nicht den Baustein. Hier läuft sie echt, samt der
**echten** ``phase3_modulate``: das ist die eigentliche Zusage dieses Moduls.
Ein handgeschriebenes Dict hätte dieselben Werte ein zweites Mal festgelegt; die
Tests unten belegen, dass sie stattdessen aus derselben Quelle kommen wie beim
Bestandsweg (Geräte-Deckel, Persona-Tonalität).

Die Config-Nähte sind wie in ``test_pattern_engine`` gemockt — geprüft wird die
Modulation, nicht der Loader.
"""

from __future__ import annotations

from boerdi.domain import pattern_engine as pe
from boerdi.domain.agent_pattern import (
    AGENT_PATTERN_ID,
    AGENT_PATTERN_LABEL,
    agent_pattern,
)
from boerdi.services import config_loader


def _mock_config(monkeypatch, *, device_max=None, tone=None):
    monkeypatch.setattr(pe, "_load_config_tables", lambda: (
        {}, [], device_max or {"desktop": 6, "mobile": 3}, {"P-AND": "neutral"}))
    monkeypatch.setattr(config_loader, "get_tone_modifier_for_persona",
                        lambda pid: tone or {"tone": "sachlich", "length_bias": 0.0,
                                             "formality": "sie", "card_text_mode": "",
                                             "override": False})


def _call(monkeypatch, *, device="desktop", persona_id="P-AND", **kw):
    _mock_config(monkeypatch, **kw)
    return agent_pattern(signals=[], device=device, entities={}, persona_id=persona_id)


def test_die_rueckgabeform_ist_die_von_select_pattern(monkeypatch):
    """Gleiche Form, anderer Erzeuger — sonst müsste alles Nachgelagerte den
    Agent-Modus kennen."""
    winner, output, scores, eliminated = _call(monkeypatch)
    assert (winner.id, winner.label) == (AGENT_PATTERN_ID, AGENT_PATTERN_LABEL)
    assert scores == {"AGENT": 1.0}
    assert eliminated == []
    assert isinstance(output, dict)


def test_die_kennung_ist_kein_muster(monkeypatch):
    """``AGENT`` soll in Qualitätslogs auf den ersten Blick von einem
    ``M``-Muster unterscheidbar sein."""
    winner, _, _, _ = _call(monkeypatch)
    assert not winner.id.startswith("M")


def test_das_output_traegt_die_schluessel_die_nachgelagert_gelesen_werden(monkeypatch):
    """``turn_assembly`` liest ``max_items``/``format_follow_up``,
    ``turn_persist`` Ton/Länge/Detailgrad. Fehlt einer, misst der A/B-Vergleich
    einen Unterschied, den er selbst gebaut hat."""
    _, output, _, _ = _call(monkeypatch)
    for key in ("tone", "length", "detail_level", "max_items",
                "card_text_mode", "format_follow_up"):
        assert key in output, key


def test_der_geraete_deckel_gilt_wie_im_bestandsweg(monkeypatch):
    """Beleg, dass die ECHTE Modulation läuft: der Deckel kommt aus der Config,
    nicht aus einer zweiten, hier festgeschriebenen Zahl."""
    _, desktop, _, _ = _call(monkeypatch, device="desktop")
    _, mobile, _, _ = _call(monkeypatch, device="mobile")
    assert desktop["max_items"] == 6
    assert mobile["max_items"] == 3


def test_der_persona_ton_wirkt_auch_im_agent_modus(monkeypatch):
    """Das synthetische Muster steht auf den Vorgabewerten — damit gewinnt der
    Persona-Modifier, genau wie bei einem Muster ohne eigene Tonalität."""
    _, output, _, _ = _call(
        monkeypatch, persona_id="P-LEH",
        tone={"tone": "warm", "length_bias": 0.0, "formality": "du",
              "card_text_mode": "highlight", "override": False})
    assert output["tone"] == "warm"
    assert output["formality"] == "du"


def test_ohne_slot_vorbedingung_keine_degradation(monkeypatch):
    """Der Agent fragt selbst nach, wenn ihm etwas fehlt — eine
    Slot-Degradation wäre eine Anweisung der Muster-Engine an ein LLM, das hier
    gar nicht gefragt wird."""
    _, output, _, _ = _call(monkeypatch)
    assert not output.get("degradation")
    assert not output.get("missing_slots")
