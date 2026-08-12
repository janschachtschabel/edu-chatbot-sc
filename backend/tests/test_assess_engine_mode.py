"""A4b — ``assess`` im Agent-Modus: kein Klassifikator, Safety bleibt.

Der Nutzer-Entscheid dazu ist zweiteilig, und beide Hälften stehen hier:

* Der **Klassifikationsprompt entfällt** — das ist der Sinn des Agent-Modus
  („eine einfachere und schnellere Variante ohne Klassifikationsprompt").
* Das **Sicherheits-Gate bleibt an**. Gemessen: ``assess_safety`` nimmt nur
  Nachricht und Signale, hängt also nicht am Klassifikator — es im Agent-Modus
  zu behalten kostet nichts, was der Modus einspart.

Die nachgelagerten Knoten bekommen trotzdem eine gültige ``ClassificationResult``:
gebaut wird sie mit ``_fallback_classification``, der Funktion, die es dafür
schon gibt (Krisen-Kurzschluss und Classify-Fehler nutzen sie ebenfalls).
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes.assess import assess


def _ctx(message: str = "Finde Material zu Bruchrechnen"):
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    ctx.session_state = {"persona_id": "P02", "state_id": "S2"}
    return ctx


async def _memory_ok(session_id: str) -> list[dict]:
    return [{"key": "fach", "value": "Mathe", "memory_type": "short"}]


def _spies(monkeypatch):
    gezaehlt = {"safety": 0, "classify": 0}

    async def _safety(*a, **k):
        gezaehlt["safety"] += 1
        return SafetyDecision(risk_level="low")

    async def _classify(*a, **k):
        gezaehlt["classify"] += 1
        return ClassificationResult(intent_id="I02")

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)
    return gezaehlt


def test_agent_modus_ruft_den_klassifikator_nicht(monkeypatch):
    gezaehlt = _spies(monkeypatch)
    ctx = asyncio.run(assess(_ctx(), _memory_ok, engine="agent"))
    assert gezaehlt["classify"] == 0
    assert ctx.classification is not None


def test_agent_modus_behaelt_das_sicherheits_gate(monkeypatch):
    gezaehlt = _spies(monkeypatch)
    asyncio.run(assess(_ctx(), _memory_ok, engine="agent"))
    assert gezaehlt["safety"] == 1


def test_agent_modus_holt_die_erinnerungen_weiter(monkeypatch):
    _spies(monkeypatch)
    ctx = asyncio.run(assess(_ctx(), _memory_ok, engine="agent"))
    assert ctx.memories == [{"key": "fach", "value": "Mathe", "memory_type": "short"}]


def test_die_ersatz_klassifikation_traegt_persona_und_zustand(monkeypatch):
    """Sonst verlöre der Agent-Modus die Sitzungs-Fortschreibung — die
    nachgelagerten Knoten lesen beides."""
    _spies(monkeypatch)
    ctx = asyncio.run(assess(_ctx(), _memory_ok, engine="agent"))
    assert ctx.classification.persona_id == "P02"
    assert ctx.classification.next_state == "S2"


def test_gegenrichtung_die_musterengine_klassifiziert_weiter(monkeypatch):
    """Der Wächter für die Zusage: ohne ``engine`` und mit ``pattern`` läuft der
    Bestand unverändert."""
    gezaehlt = _spies(monkeypatch)
    ctx = asyncio.run(assess(_ctx(), _memory_ok))
    assert gezaehlt["classify"] == 1
    assert ctx.classification.intent_id == "I02"

    gezaehlt2 = _spies(monkeypatch)
    asyncio.run(assess(_ctx(), _memory_ok, engine="pattern"))
    assert gezaehlt2["classify"] == 1


def test_die_krise_schlaegt_auch_im_agent_modus_durch(monkeypatch):
    """Das Regex-Gate läuft vor allem anderen — der Modus darf daran nichts
    ändern."""
    gezaehlt = _spies(monkeypatch)
    ctx = asyncio.run(assess(_ctx("ich will mich umbringen"), _memory_ok,
                             engine="agent"))
    assert ctx.safety.risk_level == "high"
    assert gezaehlt["safety"] == 0        # Kurzschluss: gar kein LLM
    assert gezaehlt["classify"] == 0
