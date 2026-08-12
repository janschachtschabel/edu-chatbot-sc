"""A4c — der Route-Knoten im Agent-Modus (``graph/nodes/route.py``).

Der Agent-Modus hat keine Musterwahl: er ist die Maschine, die sich ihr Werkzeug
selbst sucht. Damit fallen zwei Dinge aus, die den Bestandsweg ausmachen — die
``select_pattern``-Wahl und die beiden Schnellwege (Lernpfad, Canvas). Diese
Datei hält beide Ausfälle fest UND, genauso wichtig, was NICHT ausfällt:
Persona-Merge, Policy samt Werkzeug-Sperren und die QR-Policy.

Der wichtigste Test ist wieder der letzte: die **Gegenrichtung**. Ohne
``engine``-Angabe läuft die Musterwahl wie bisher — die Zusage „der Chatbot
antwortet standardmäßig weiter wie zuvor" gehört in einen Test, nicht in einen
Vorsatz.

**Warum die Schnellwege je einen eigenen Wächter bekommen:** der Canvas-Weg
hängt an Intent ``I05``, und der Agent-Modus klassifiziert gar nicht — er käme
also *zufällig* schon nicht dran. Ein Verhalten, das nur durch eine Eigenschaft
eines ANDEREN Knotens zustande kommt, ist nicht zugesichert, sondern geliehen.
Deshalb prüft ``test_der_canvas_schnellweg_bleibt_im_agent_modus_aus``
ausdrücklich mit einer I05-Klassifikation.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.domain.pattern_engine import PatternDef
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import route as route_mod
from boerdi.graph.nodes.route import route
from boerdi.services.canvas_fast_path import CanvasFastPathResult
from boerdi.services.lp_fast_path import LpFastPathResult


def _ctx(*, message="frage", classification=None, safety=None):
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    ctx.session_state = {
        "persona_id": "", "signal_history": [], "entities": {}, "state_id": "",
    }
    ctx.classification = classification or ClassificationResult()
    ctx.safety = safety or SafetyDecision(risk_level="low")
    ctx.memories = []
    return ctx


def _patch(monkeypatch, seen, *, policy=None, agent_out=None):
    """Alle Nachbarn des Knotens abfangen und ihren Aufruf vermerken.

    ``seen`` ist die Beweislage der Tests: welcher Nachbar wurde gerufen, mit
    welchen Argumenten. Ein NICHT eingetragener Schlüssel heißt „nie gerufen".
    """
    win = PatternDef(id="M09", label="Suche")

    def _sel(**k):
        seen["select_pattern"] = k
        return (win, {"tools": [], "id": "M09"}, {"M09": 1.0}, [])

    def _agent(**k):
        seen["agent_pattern"] = k
        winner = PatternDef(id="AGENT", label="AGENT (Werkzeug-Agent)")
        out = agent_out if agent_out is not None else {"id": "AGENT", "max_items": 5}
        return (winner, out, {"AGENT": 1.0}, [])

    def _dli(**k):
        seen["detect_lp_intent"] = k
        return (True, "Photosynthese")

    async def _lp(**k):
        seen["run_lp_fast_path"] = k
        return LpFastPathResult(
            routed=False, response_text=None, wlo_cards_raw=None,
            tools_called=[], new_state=k["new_state"], qr_mode=None,
            qr_max=None, qr_spec_task=k["qr_spec_task"],
        )

    async def _cv(**k):
        seen["run_canvas_create_fast_path"] = k
        return CanvasFastPathResult(
            routed=False, payload_out=None, forced_quick_replies=[],
            response_text="", tools_called=k["tools_called"], wlo_cards_raw=[],
            new_state=k["new_state"],
        )

    def _qrp(pid):
        seen["qr_policy"] = pid
        return ("exact", 4)

    monkeypatch.setattr(route_mod, "select_pattern", _sel)
    monkeypatch.setattr(route_mod, "agent_pattern", _agent)
    monkeypatch.setattr(route_mod, "detect_lp_intent", _dli)
    monkeypatch.setattr(route_mod, "run_lp_fast_path", _lp)
    monkeypatch.setattr(route_mod, "run_canvas_create_fast_path", _cv)
    monkeypatch.setattr(route_mod, "_qr_policy", _qrp)
    monkeypatch.setattr(route_mod, "assess_policy",
                        lambda **k: policy or PolicyDecision())
    monkeypatch.setattr(route_mod, "validate_transition",
                        lambda **k: {"validated_state": k["next_"], "plausible": True,
                                     "reason": "", "prev_next_likely": []})
    monkeypatch.setattr(route_mod, "load_rag_config", dict)


# ── Die Musterwahl entfällt ────────────────────────────────────────
@pytest.mark.anyio
async def test_im_agent_modus_faellt_die_musterwahl_aus(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(), engine="agent")
    assert "select_pattern" not in seen
    assert seen["agent_pattern"]["persona_id"] == "P-AND"
    assert (ctx.winner_id, ctx.winner_label) == ("AGENT", "AGENT (Werkzeug-Agent)")


@pytest.mark.anyio
async def test_der_agent_modus_traegt_ein_verwertbares_pattern_output(monkeypatch):
    """Die nachgelagerten Knoten (Assembly, Persist) lesen ``pattern_output``
    weiter — es darf nicht leer bleiben, sonst misst der A/B-Vergleich einen
    Unterschied, den er selbst gebaut hat."""
    seen: dict = {}
    _patch(monkeypatch, seen, agent_out={"id": "AGENT", "max_items": 5,
                                         "format_follow_up": "quick_replies"})
    ctx = await route(_ctx(), engine="agent")
    assert ctx.pattern_output["id"] == "AGENT"
    assert ctx.pattern_output["max_items"] == 5
    assert ctx.scores == {"AGENT": 1.0}


# ── Die Schnellwege entfallen ──────────────────────────────────────
@pytest.mark.anyio
async def test_der_lernpfad_schnellweg_bleibt_im_agent_modus_aus(monkeypatch):
    """Das Lernpfad-Gate feuert schon bei EINEM Stichwort im Satz — es hinge
    also auch im Agent-Modus an der Nachricht, nicht am Agenten."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(message="Erstelle einen Lernpfad zu Photosynthese"),
                      engine="agent")
    assert "detect_lp_intent" not in seen
    assert seen["run_lp_fast_path"]["has_lp_intent"] is False
    assert ctx.lp_routed is False


@pytest.mark.anyio
async def test_der_canvas_schnellweg_bleibt_im_agent_modus_aus(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(
        _ctx(classification=ClassificationResult(intent_id="I05")), engine="agent")
    assert "run_canvas_create_fast_path" not in seen
    assert ctx.canvas_routed is False
    assert ctx.canvas_payload is None


@pytest.mark.anyio
async def test_effektives_muster_und_qr_policy_stehen_auf_agent(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(), engine="agent")
    assert ctx.effective_pattern_id == "AGENT"
    assert seen["qr_policy"] == "AGENT"
    assert (ctx.qr_mode, ctx.qr_max) == ("exact", 4)
    assert ctx.fp_response_text is None and ctx.fp_wlo_cards_raw is None


# ── Was NICHT entfällt ─────────────────────────────────────────────
@pytest.mark.anyio
async def test_policy_und_werkzeug_sperren_gelten_auch_im_agent_modus(monkeypatch):
    """Der Agent-Modus spart den Klassifikator, nicht die Sicherheit."""
    seen: dict = {}
    _patch(monkeypatch, seen,
           policy=PolicyDecision(blocked_tools=["wlo_delete_content"]))
    ctx = await route(_ctx(safety=SafetyDecision(risk_level="low")), engine="agent")
    assert "wlo_delete_content" in ctx.safety.blocked_tools
    assert ctx.policy is not None
    assert ctx.session_state["persona_id"] == "P-AND"   # Persona-Merge lief
    assert ctx.context_snapshot is not None             # Kontext-Schnappschuss auch


# ── Gegenrichtung ──────────────────────────────────────────────────
@pytest.mark.anyio
async def test_gegenrichtung_ohne_angabe_laeuft_die_musterengine(monkeypatch):
    """Der Wächter für die Zusage des Nutzers: ohne ``engine`` wird die
    Agent-Variante **nie** gewählt, und beide Schnellwege stehen bereit."""
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = await route(_ctx(message="Erstelle einen Lernpfad zu Photosynthese",
                           classification=ClassificationResult(intent_id="I04")))
    assert "agent_pattern" not in seen
    assert seen["select_pattern"]["intent_id"] == "I04"
    assert seen["detect_lp_intent"]["message"].startswith("Erstelle")
    assert seen["run_lp_fast_path"]["has_lp_intent"] is True
    assert "run_canvas_create_fast_path" in seen
    assert ctx.winner_id == "M09"
