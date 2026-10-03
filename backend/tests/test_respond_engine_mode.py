"""SF-1 — die Weiche in ``respond`` bei erzwungenem Muster (``graph/nodes/respond.py``).

Im Agent-Modus reicht ``respond`` den Zug an ``respond_agent``
weiter (die Weiche selbst prüft ``test_respond_agent``, Abschnitt „Die Weiche in
``respond``"). Hat das Sicherheits-Gate ein Muster erzwungen (M01 Krise, M02
Drohung), bleibt der Zug dagegen im Muster-Weg, gleich welche Maschine gewählt
ist. Bis 2026-09-26 lief die Krise durch die Schleife: von M01 kamen dort nur die
gesperrten Such-Werkzeuge an, die Hilfsnummern und die Ablehnung aus M02 nie.

``route`` stellt dafür das Schutzmuster bereit (``test_route_engine_mode``); hier
steht der Zug so, wie ``route`` ihn hinterlässt. ``generate_response`` und
``respond_agent`` sind die Grenzen und werden AN DIESEM Modul abgefangen.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond as respond_mod
from boerdi.graph.nodes.respond import respond


def _ctx(safety: SafetyDecision, message: str = "Ich will nicht mehr leben"):
    """Der Zug nach ``route``: mit Erzwingung steht das Schutzmuster darin,
    ohne sie das synthetische Muster der Schleife."""
    muster = safety.enforced_pattern or "AGENT"
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id="bb-1", message=message, environment=Environment()))
    ctx.env = ctx.req.environment.model_dump()
    ctx.session_state = {"persona_id": "P-AND", "entities": {}}
    ctx.safety = safety
    ctx.policy = PolicyDecision()
    ctx.classification = ClassificationResult(intent_id="I07")
    ctx.winner_id = ctx.winner_label = ctx.effective_pattern_id = muster
    ctx.pattern_output = {"id": muster, "tools": [], "sources": ["llm"]}
    ctx.qr_mode = "exact"
    return ctx


def _patch(monkeypatch, seen):
    """Beide Wege abfangen; ``seen`` vermerkt, welcher lief und womit."""
    async def _agent(ctx, progress=None, session=None, on_token=None):
        seen["respond_agent"] = True
        seen["on_token"] = on_token
        ctx.response_text = "vom Agenten"
        return ctx

    async def _generate(session, **k):
        seen["generate_response"] = k
        return ("Telefonseelsorge: 0800 111 0 111", [], [], [])

    monkeypatch.setattr(respond_mod, "respond_agent", _agent)
    monkeypatch.setattr(respond_mod, "generate_response", _generate)


@pytest.mark.anyio
@pytest.mark.parametrize("muster", ["M01", "M02"])
async def test_ein_erzwungenes_muster_antwortet_ueber_den_muster_weg(
        monkeypatch, muster):
    seen: dict = {}
    _patch(monkeypatch, seen)
    safety = SafetyDecision(risk_level="high", enforced_pattern=muster)
    ctx = await respond(_ctx(safety), session=object(), engine="agent")
    assert "respond_agent" not in seen
    assert seen["generate_response"]["pattern_output"]["id"] == muster
    assert seen["generate_response"]["pattern_label"] == muster
    assert ctx.response_text.startswith("Telefonseelsorge")


@pytest.mark.anyio
async def test_ohne_erzwingung_antwortet_weiter_die_schleife(monkeypatch):
    """Die Gegenrichtung: hohes Risiko ohne erzwungenes Muster (hier ein
    Gefahr-Signal) lässt die gewählte Maschine antworten."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    safety = SafetyDecision(risk_level="high", reasons=["danger_signal"])
    ctx = await respond(_ctx(safety, message="frage"), session=object(),
                        engine="agent")
    assert seen["respond_agent"] is True
    assert "generate_response" not in seen
    assert ctx.response_text == "vom Agenten"


@pytest.mark.anyio
async def test_der_strom_reist_mit_in_den_agent_zug(monkeypatch):
    """Token-Streaming (Plan 2026-10-01, T20): die Naht endet nicht im
    Muster-Weg — ``respond_agent`` entscheidet selbst, ob es streamt."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    strom = object()
    await respond(_ctx(SafetyDecision(risk_level="low"), message="frage"),
                  session=object(), engine="agent", on_token=strom)
    assert seen["on_token"] is strom
