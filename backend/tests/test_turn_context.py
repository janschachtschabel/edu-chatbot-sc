"""graph.state.TurnContext — das typisierte Turn-State-Objekt (LangGraph-Zustand).

4-1 definiert die Felder, die in der ALT-Pipeline zwischen den Phasen wandern
(``_setup_turn`` / ``_classify_and_merge`` / ``_route_pattern`` /
``_produce_answer`` / ``_assemble_cards_and_qrs``). Dieser Test pinnt den
Zustands-Vertrag: Konstruktion aus einem ``ChatRequest`` mit Defaults,
Mutierbarkeit (Nodes aktualisieren Felder in-place), Zuweisung echter
Assessment-/Answer-Modelle und das deklarierte Kern-Feldset.

Die Routing-/Prefetch-/Canvas-/QR-Policy-Interna (``winner``/``pattern_output``,
``rag_config``, ``spec_*``, ``canvas_*``, ``qr_*``) sind bewusst auf die Slices
4-4/4-5/P5 vertagt, die ihre Produzenten bauen (siehe Modul-Docstring), und
werden hier NICHT eingefordert.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from boerdi.api.schemas import (
    ChatRequest,
    ChatResponse,
    ClassificationResult,
    ContextSnapshot,
    DebugInfo,
    PolicyDecision,
    SafetyDecision,
    WloCard,
)
from boerdi.graph.state import TurnContext
from boerdi.obs.usage import add_usage, extract_usage, new_accumulator


def _req() -> ChatRequest:
    return ChatRequest(session_id="s1", message="wie erkläre ich bruchrechnung?")


def test_constructs_from_request_with_defaults():
    ctx = TurnContext(req=_req())
    # Input / session (setup — 4-2)
    assert ctx.req.session_id == "s1"
    assert ctx.env == {}
    assert ctx.client_ip == ""
    assert ctx.session_state == {}
    assert ctx.history == []
    assert ctx.early_response is None
    # Assessment (assess parallel group + merge — 4-3)
    assert ctx.safety is None
    assert ctx.classification is None
    assert ctx.memories == []
    assert ctx.signals == []
    assert ctx.signal_history == []
    assert ctx.state_id == "S1"
    assert ctx.context_snapshot is None
    assert ctx.policy is None
    # NICHT ``== {}``: der Zug bringt den Token-Merkposten mit (s.u.).
    assert ctx.usage == new_accumulator()
    # Answer (respond / assemble — 4-5)
    assert ctx.response_text == ""
    assert ctx.cards == []
    assert ctx.quick_replies == []
    assert ctx.page_action is None
    assert ctx.pagination is None
    assert ctx.web_links == []
    # Observability
    assert isinstance(ctx.debug, DebugInfo)


def test_req_is_required():
    # ``req`` has no default — a turn is meaningless without the request.
    with pytest.raises(ValidationError):
        TurnContext()


# ── Token-Merkposten: die Naht zwischen ``graph.state`` und ``obs.usage`` ──
# ALT legt ihn zu Turn-Beginn an (``chat_turn_setup.py:175``:
# ``usage_acc = usage_accumulator_new()``). NEU hatte KEINEN Erzeuger: das Feld
# stand auf ``{}``, und ``add_usage`` kehrt bei leerem Merkposten still zurück
# (``if not acc: return``). Damit war jede der fünf Durchreichungen
# (assess/route/respond/assemble/persist) ein No-Op und ``debug.token_usage``
# immer leer. Beide Seiten waren für sich korrekt und getestet — die Tests
# bauten den Merkposten jedes Mal von Hand. Diese zwei Pins prüfen deshalb die
# VERBINDUNG, nicht die Seiten.

def test_frischer_zug_bringt_den_token_merkposten_mit():
    assert TurnContext(req=_req()).usage == new_accumulator()


def test_buchung_auf_dem_frischen_zug_kommt_an():
    ctx = TurnContext(req=_req())
    resp = SimpleNamespace(model="gpt-x", usage=SimpleNamespace(
        prompt_tokens=100, completion_tokens=20,
        prompt_tokens_details=SimpleNamespace(cached_tokens=64)))

    add_usage(ctx.usage, extract_usage(resp), phase="classify")

    assert ctx.usage["calls"] == 1
    assert ctx.usage["prompt_tokens"] == 100
    assert ctx.usage["cached_tokens"] == 64
    assert ctx.usage["per_phase"]["classify"]["completion"] == 20


def test_fields_are_mutable_across_phases():
    ctx = TurnContext(req=_req())
    # setup node writes input/session
    ctx.env = {"repo": "https://x"}
    ctx.client_ip = "1.2.3.4"
    ctx.session_state["persona_id"] = "P-RED"
    ctx.history.append({"role": "user", "content": "hi"})
    # assess node writes assessment
    ctx.safety = SafetyDecision(risk_level="medium")
    ctx.classification = ClassificationResult(intent_id="I05")
    ctx.memories.append({"key": "k", "value": "v", "memory_type": "short"})
    ctx.signals = ["S-DEF"]
    ctx.state_id = "S2"
    ctx.context_snapshot = ContextSnapshot(page="/mathe")
    ctx.policy = PolicyDecision(allowed=False)
    # respond node writes the answer
    ctx.response_text = "So geht Bruchrechnung …"
    ctx.cards.append(WloCard(node_id="n1", title="Bruch"))
    ctx.quick_replies = ["Mehr Beispiele"]

    assert ctx.safety.risk_level == "medium"
    assert ctx.classification.intent_id == "I05"
    assert ctx.memories[0]["value"] == "v"
    assert ctx.session_state["persona_id"] == "P-RED"
    assert ctx.state_id == "S2"
    assert ctx.policy.allowed is False
    assert ctx.cards[0].title == "Bruch"
    assert ctx.response_text.startswith("So geht")


def test_early_response_carries_a_chatresponse():
    ctx = TurnContext(req=_req())
    ctx.early_response = ChatResponse(session_id="s1", content="Tour gestartet")
    assert ctx.early_response.content == "Tour gestartet"


def test_declared_core_field_contract():
    # Pin the inter-phase state contract: the core fields must be present.
    # Superset (not equality) so later slices (4-3/4-5) can ADD their fields
    # without breaking this pin.
    expected = {
        "req", "env", "client_ip", "session_state", "history", "early_response",
        "safety", "classification", "memories", "signals", "signal_history",
        "state_id", "context_snapshot", "policy", "usage",
        "response_text", "cards", "quick_replies", "page_action", "pagination",
        "web_links", "debug",
    }
    assert expected <= set(TurnContext.model_fields)
