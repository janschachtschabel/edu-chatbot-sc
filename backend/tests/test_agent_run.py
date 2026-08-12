"""A3a — ein Agent-Lauf ohne HTTP (``services/agent_run.py``).

Geprüft wird das, was der Endpunkt später nur noch durchreicht: welche Limits
gelten, was vorab aufgelöst wird, und ob ``execute`` an einer persönlichen
Anmeldung hängt statt an der Behauptung des Aufrufers.

Gefälscht: ``agent_loop.run_agent_loop`` (die Scheibe darunter, in A2 belegt),
``outcome_service.call_with_outcome`` (MCP-Netzaufruf) und ``load_engine``
(Datenbank).
"""

from __future__ import annotations

import asyncio
import json

import pytest
from pydantic import ValidationError

from boerdi.api.schemas_agent import AgentRequest
from boerdi.domain.config_models.engine import AgentLimits, EngineArea
from boerdi.services import agent_loop, agent_run, agent_write, outcome_service
from boerdi.services.agent_loop import AgentRun
from boerdi.services.mcp import auth


class _LoopFake:
    """``run_agent_loop`` — hält fest, womit die Schleife gerufen wurde."""

    def __init__(self, run=None):
        self.kwargs: dict | None = None
        self._run = run or AgentRun(
            text="fertig", result={"note": 4}, stop_reason="submit", iterations=2,
            tools_called=["search_wlo_content"])

    async def __call__(self, **kwargs):
        self.kwargs = kwargs
        return self._run


class _OutcomeFake:
    def __init__(self, result_map=None):
        self.calls: list[tuple[str, dict]] = []
        self._map = result_map or {}

    async def __call__(self, tool_name, tool_args):
        from boerdi.api.schemas import ToolOutcome
        self.calls.append((tool_name, dict(tool_args)))
        return self._map.get(tool_name, f"result:{tool_name}"), ToolOutcome(
            tool=tool_name, status="success", item_count=1)


def _lauf(monkeypatch, req, *, engine=None, loop=None, outcome=None, personal=False):
    loop = loop or _LoopFake()
    out = outcome or _OutcomeFake()
    monkeypatch.setattr(agent_loop, "run_agent_loop", loop)
    monkeypatch.setattr(agent_run, "run_agent_loop", loop)
    monkeypatch.setattr(outcome_service, "call_with_outcome", out)

    # Synchron wie das Original — siehe die Lehre in test_engine_choice.
    monkeypatch.setattr(agent_run, "load_engine", lambda: engine or EngineArea())
    monkeypatch.setattr(auth, "has_personal_auth", lambda: personal)
    # Die Schreib-Regel wohnt seit A4c-2b in ``agent_write`` (zweiter Aufrufer:
    # der Agent-Modus im Chat). Nur der ORT des Patches ist gewandert — die
    # Zusicherungen darunter sind unverändert.
    monkeypatch.setattr(agent_write, "has_personal_auth", lambda: personal)
    antwort = asyncio.run(agent_run.run_agent(req))
    return loop, out, antwort


# ── Antwortform ──────────────────────────────────────────────────────────


def test_lauf_wird_zur_antwort_durchgereicht(monkeypatch):
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="Prüfe X."))
    assert antwort.text == "fertig"
    assert antwort.result == {"note": 4}
    assert antwort.stop_reason == "submit"
    assert antwort.iterations == 2
    assert antwort.tools_called == ["search_wlo_content"]


def test_anweisung_wird_zur_nutzernachricht(monkeypatch):
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(instruction="Bewerte die Sachrichtigkeit."))
    messages = loop.kwargs["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "Bewerte die Sachrichtigkeit."}


def test_result_schema_erreicht_die_werkzeugliste(monkeypatch):
    schema = {"type": "object", "properties": {"sachrichtigkeit": {"type": "integer"}}}
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Bewerte.", result_schema=schema))
    submit = [t for t in loop.kwargs["tools"]
              if t["function"]["name"] == "submit_result"][0]
    assert submit["function"]["parameters"]["properties"]["result"] == schema
    assert "result" in submit["function"]["parameters"]["required"]


# ── Vorabauflösung ───────────────────────────────────────────────────────


def test_node_ids_werden_vorab_aufgeloest(monkeypatch):
    out = _OutcomeFake({"get_nodes_details": "Titel: Bruchrechnen"})
    loop, out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Prüfe diese Inhalte.", node_ids=["n1", "n2"]), outcome=out)
    assert out.calls == [("get_nodes_details", {"nodeIds": ["n1", "n2"]})]
    messages = loop.kwargs["messages"]
    tool_msgs = [m for m in messages if m.get("role") == "tool"]
    assert len(tool_msgs) == 1
    assert "Titel: Bruchrechnen" in tool_msgs[0]["content"]
    # Ein Werkzeug-Ergebnis braucht seinen Aufruf davor, sonst lehnt der
    # Anbieter die Kette ab.
    assert any(m.get("tool_calls") for m in messages)


def test_sammlung_holt_die_anleitungen_vorab(monkeypatch):
    out = _OutcomeFake({"get_skill_registry": "Skill: Qualitätsprüfung"})
    loop, out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Kuratiere.", collection_id="c1"), outcome=out)
    assert out.calls == [("get_skill_registry", {"collectionId": "c1"})]
    inhalt = [m for m in loop.kwargs["messages"] if m.get("role") == "tool"][0]["content"]
    # H9: die Freigabeliste ist Fremdtext und muss gerahmt sein.
    assert "FREMDINHALT" in inhalt
    assert "Skill: Qualitätsprüfung" in inhalt


def test_ohne_angaben_kein_vorab_aufruf(monkeypatch):
    _loop, out, _a = _lauf(monkeypatch, AgentRequest(instruction="Nur Text."))
    assert out.calls == []


def test_ein_fehlschlag_beim_vorablauf_beendet_den_lauf_nicht(monkeypatch):
    """Ein gelöschter Knoten darf keinen 500 erzeugen — der Agent arbeitet
    weiter und sagt selbst, was er nicht prüfen konnte."""
    class _Boom:
        calls: list = []

        async def __call__(self, tool_name, tool_args):
            raise RuntimeError("MCP weg")

    loop, _out, antwort = _lauf(monkeypatch, AgentRequest(
        instruction="Prüfe.", node_ids=["n1"]), outcome=_Boom())
    assert antwort.stop_reason == "submit"
    inhalt = [m for m in loop.kwargs["messages"] if m.get("role") == "tool"][0]["content"]
    assert "nicht abrufen" in inhalt


# ── Limits und Schreibrecht ──────────────────────────────────────────────


def test_limits_kommen_aus_der_konfiguration(monkeypatch):
    engine = EngineArea(agent=AgentLimits(max_iterations=7, deadline_s=30))
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(instruction="X."), engine=engine)
    assert loop.kwargs["limits"].max_iterations == 7
    assert loop.kwargs["limits"].deadline_s == 30


def test_execute_ohne_persoenliche_anmeldung_faellt_auf_propose(monkeypatch):
    """Das Schreibrecht hängt an einer angemeldeten Person, nicht an der
    Behauptung des Aufrufers. Das Dienstkonto der Anlage ist keine Person."""
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Lege an.", write_mode="execute"), personal=False)
    assert loop.kwargs["limits"].write_mode == "propose"


def test_execute_mit_persoenlicher_anmeldung_gilt(monkeypatch):
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Lege an.", write_mode="execute"), personal=True)
    assert loop.kwargs["limits"].write_mode == "execute"


def test_auch_die_konfigurierte_vorgabe_verlangt_eine_person(monkeypatch):
    """Die Prüfung sitzt am Ergebnis, nicht an der Übersteuerung — sonst wäre
    ein redaktionell gesetztes ``execute`` ein Loch."""
    engine = EngineArea(agent=AgentLimits(write_mode="execute"))
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(instruction="Lege an."),
                           engine=engine, personal=False)
    assert loop.kwargs["limits"].write_mode == "propose"


def test_propose_darf_immer_herunterstufen(monkeypatch):
    engine = EngineArea(agent=AgentLimits(write_mode="execute"))
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Nur vorschlagen.", write_mode="propose"),
        engine=engine, personal=True)
    assert loop.kwargs["limits"].write_mode == "propose"


def test_kuration_kann_abgewaehlt_werden(monkeypatch):
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(
        instruction="Nur lesen.", allow_curation=False), personal=True)
    namen = {t["function"]["name"] for t in loop.kwargs["tools"]}
    assert "wlo_create_collection" not in namen
    assert "search_wlo_content" in namen


# ── Systemprompt ─────────────────────────────────────────────────────────


def test_systemprompt_nennt_die_ausgabesprache(monkeypatch):
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(instruction="X.", locale="en"))
    system = loop.kwargs["messages"][0]["content"]
    assert "Englisch" in system


def test_systemprompt_traegt_keinen_chatbot_rahmen(monkeypatch):
    """Der Nutzer-Entscheid: kein Begrüßungstext, keine Muster, kein
    Klassifikator. Der Prompt darf davon nichts mitschleppen."""
    loop, _out, _a = _lauf(monkeypatch, AgentRequest(instruction="X."))
    system = loop.kwargs["messages"][0]["content"].lower()
    for wort in ("begrüßung", "quick-repl", "pattern", "pat-"):
        assert wort not in system


def test_node_ids_sind_auf_fuenfzig_gedeckelt():
    """Der Deckel steht am Rand, weil ``get_nodes_details`` bei 50 endet — eine
    Liste mit 500 IDs wäre ein stiller Teilabruf."""
    with pytest.raises(ValidationError):
        AgentRequest(instruction="X.", node_ids=[f"n{i}" for i in range(51)])


def test_die_anweisung_darf_nicht_leer_sein():
    with pytest.raises(ValidationError):
        AgentRequest(instruction="   ")


def test_antwort_ist_serialisierbar(monkeypatch):
    """Der Endpunkt (A3b) gibt sie als JSON heraus; ein freies ``result`` darf
    das nicht sprengen."""
    _loop, _out, antwort = _lauf(monkeypatch, AgentRequest(instruction="X."))
    assert json.loads(antwort.model_dump_json())["result"] == {"note": 4}
