"""graph.nodes.route — Routing-Entscheidungs-Kern (P4-4).

Port des ENTSCHEIDUNGS-KERNS aus ALT ``chat_turn_setup`` (Persona/Signal/State-
Merge + ``validate_transition`` + ``assess_policy`` + Policy→Safety-Tool-Merge)
und dem Kopf von ``chat_turn_routing._route_pattern`` (``select_pattern`` +
Blocked-Tools-Strip + RAG-Whitelist + Memory-Render). Die P5-verflochtenen Teile
(Spec-Prefetch, LP-/Canvas-Fast-Path, Effective-Pattern-Reconciliation,
QR-Policy, ``build_context``) sind bewusst vertagt (``simplify:``-Marker im Node).

Die drei Domänen-Funktionen + ``load_rag_config`` werden am Node-Modul gemockt →
der Node ist ohne LLM/DB voll fake-testbar. Die reinen Helfer
``_resolve_rag_areas`` / ``_render_memory_context`` werden direkt getestet.
"""

from __future__ import annotations

import asyncio

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
from boerdi.graph.nodes.route import _render_memory_context, _resolve_rag_areas, route
from boerdi.obs.progress import TurnProgress
from boerdi.services.canvas_fast_path import CanvasFastPathResult
from boerdi.services.lp_fast_path import LpFastPathResult


def _ctx(*, message="frage", session_state=None, classification=None, safety=None,
         memories=None):
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    ctx.session_state = session_state if session_state is not None else {
        "persona_id": "", "signal_history": [], "entities": {}, "state_id": "",
    }
    ctx.classification = classification or ClassificationResult()
    ctx.safety = safety or SafetyDecision(risk_level="low")
    ctx.memories = memories if memories is not None else []
    return ctx


def _patch(monkeypatch, captured, *, winner=None, pattern_output=None, policy=None,
           trans=None, rag_config=None, vt_raises=False,
           canvas_result=None, qr_ret=("exact", 4),
           lp_intent_ret=(False, ""), lp_result=None):
    win = winner or PatternDef(id="M09", label="Suche")
    out = pattern_output if pattern_output is not None else {"tools": []}

    def _sel(**k):
        captured["select"] = k
        return (win, out, {win.id: 1.0}, [])

    def _vt(**k):
        captured["validate"] = k
        if vt_raises:
            raise RuntimeError("validator exploded")
        return trans or {"validated_state": k["next_"], "plausible": True,
                         "reason": "", "prev_next_likely": []}

    def _dli(**k):
        captured["lp_intent"] = k
        return lp_intent_ret

    async def _lp(**k):
        captured["lp"] = k
        if lp_result is not None:
            return lp_result
        return LpFastPathResult(
            routed=False, response_text=None, wlo_cards_raw=None,
            tools_called=[], new_state=k["new_state"], qr_mode=None,
            qr_max=None, qr_spec_task=k["qr_spec_task"],
        )

    async def _cv(**k):
        captured["canvas"] = k
        if canvas_result is not None:
            return canvas_result
        return CanvasFastPathResult(
            routed=False, payload_out=None, forced_quick_replies=[],
            response_text="", tools_called=k["tools_called"], wlo_cards_raw=[],
            new_state=k["new_state"],
        )

    def _qrp(pid):
        captured["qr_policy"] = pid
        return qr_ret

    monkeypatch.setattr(route_mod, "select_pattern", _sel)
    monkeypatch.setattr(route_mod, "assess_policy", lambda **k: policy or PolicyDecision())
    monkeypatch.setattr(route_mod, "validate_transition", _vt)
    monkeypatch.setattr(route_mod, "load_rag_config",
                        lambda: rag_config if rag_config is not None else {})
    monkeypatch.setattr(route_mod, "detect_lp_intent", _dli)
    monkeypatch.setattr(route_mod, "run_lp_fast_path", _lp)
    monkeypatch.setattr(route_mod, "run_canvas_create_fast_path", _cv)
    monkeypatch.setattr(route_mod, "_qr_policy", _qrp)
    return win, out


# ── Persona-Update (R-06) ──────────────────────────────────────────
@pytest.mark.parametrize("existing,detected,turn_type,expected", [
    ("", "P-LEH", "initial", "P-LEH"),          # leer → detektiert übernehmen
    ("P-AND", "P-LEH", "correction", "P-LEH"),  # Korrektur → überschreiben
    ("P-LEH", "P-ENT", "initial", "P-ENT"),     # spezifisch ≠ bestehend → update
    ("P-LEH", "P-AND", "initial", "P-LEH"),     # Fallback-Detektion → behalten
])
def test_persona_update(monkeypatch, existing, detected, turn_type, expected):
    captured = {}
    _patch(monkeypatch, captured)
    ctx = _ctx(
        session_state={"persona_id": existing, "signal_history": [], "entities": {},
                       "state_id": ""},
        classification=ClassificationResult(persona_id=detected, turn_type=turn_type),
    )
    out = asyncio.run(route(ctx))
    assert out.session_state["persona_id"] == expected
    assert captured["select"]["persona_id"] == expected   # select sieht den Update


# ── Signal/State-Merge + validate_transition-Verdrahtung ───────────
def test_signals_state_merge_and_validate_wired(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured)
    ctx = _ctx(
        session_state={"persona_id": "P-LEH", "signal_history": ["alt"], "entities": {},
                       "state_id": "S2"},
        classification=ClassificationResult(signals=["knapp"], next_state="S3",
                                            intent_id="I05"),
    )
    out = asyncio.run(route(ctx))
    assert out.signals == ["knapp"]
    assert set(out.signal_history) == {"alt", "knapp"}
    assert out.state_id == "S3"
    # validate_transition mit prev aus session_state, next_ = neuer State, intent
    assert captured["validate"] == {"prev": "S2", "next_": "S3", "intent": "I05",
                                    "auto_correct": False}
    assert out.trans_check["plausible"] is True


def test_validate_transition_exception_never_fails_turn(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured, vt_raises=True)
    ctx = _ctx(classification=ClassificationResult(next_state="S3"))
    out = asyncio.run(route(ctx))
    # Fallback statt Crash: state übernommen, plausibel, Fehler in reason.
    assert out.trans_check["validated_state"] == "S3"
    assert out.trans_check["plausible"] is True
    assert "validator" in out.trans_check["reason"].lower()


# ── Policy → Safety-Tool-Merge + Blocked-Tools-Strip ───────────────
def test_policy_blocked_tools_merged_into_safety(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured,
           policy=PolicyDecision(matched_rules=["r1"], blocked_tools=["t_a", "t_b"]))
    ctx = _ctx(safety=SafetyDecision(risk_level="low", blocked_tools=["t_b"]))
    out = asyncio.run(route(ctx))
    # dedupe, Reihenfolge stabil: bestehendes t_b bleibt, t_a angehängt.
    assert out.safety.blocked_tools == ["t_b", "t_a"]
    assert out.policy.matched_rules == ["r1"]


def test_blocked_tools_stripped_from_pattern_output(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured,
           pattern_output={"tools": ["search_wlo_content", "t_a"]},
           policy=PolicyDecision(blocked_tools=["t_a"]))
    ctx = _ctx(safety=SafetyDecision(risk_level="low"))
    out = asyncio.run(route(ctx))
    assert out.pattern_output["tools"] == ["search_wlo_content"]


# ── select_pattern-Verdrahtung (Enforce/Hint) + Ausgabe-Felder ─────
def test_select_receives_enforced_and_hint(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured)
    ctx = _ctx(
        safety=SafetyDecision(risk_level="high", enforced_pattern="M01"),
        classification=ClassificationResult(pattern_id_hint="M09", intent_confidence=0.7),
    )
    asyncio.run(route(ctx))
    assert captured["select"]["enforced_pattern_id"] == "M01"
    assert captured["select"]["pattern_id_hint"] == "M09"
    assert captured["select"]["intent_confidence"] == 0.7


def test_empty_enforced_pattern_becomes_none(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured)
    ctx = _ctx(safety=SafetyDecision(risk_level="low", enforced_pattern=""))
    asyncio.run(route(ctx))
    assert captured["select"]["enforced_pattern_id"] is None


def test_routing_output_fields_written(monkeypatch):
    captured = {}
    win = PatternDef(id="M11", label="Nachbearbeitung")
    _patch(monkeypatch, captured, winner=win, pattern_output={"tools": [], "tone": "warm"})
    out = asyncio.run(route(_ctx()))
    assert out.winner_id == "M11"
    assert out.winner_label == "Nachbearbeitung"
    assert out.pattern_output["tone"] == "warm"
    assert out.scores == {"M11": 1.0}
    assert out.eliminated == []


def test_context_snapshot_built(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured)
    ctx = _ctx(
        session_state={"persona_id": "P-LEH", "signal_history": ["knapp"],
                       "entities": {"thema": "Bio", "_scratch": "x"}, "state_id": "S1",
                       "turn_count": 2},
        classification=ClassificationResult(intent_id="I05", next_state="S3"),
    )
    ctx.env = {"page": "/suche", "device": "mobile"}
    ctx.memories = [{"key": "fach", "value": "Bio"}]  # bewusst NICHT an build_context
    out = asyncio.run(route(ctx))
    snap = out.context_snapshot
    assert snap is not None
    assert (snap.page, snap.device, snap.turn_count) == ("/suche", "mobile", 2)
    assert snap.entities == {"thema": "Bio"}            # interner _scratch verborgen
    assert (snap.last_intent, snap.last_state) == ("I05", "S3")
    # ALT-Parität: build_context wird ohne memories aufgerufen → memory_keys leer,
    # obwohl ctx.memories gesetzt ist.
    assert snap.memory_keys == []


# ── Fast-Path-Tail: Canvas-Fast-Path + Reconcile + QR-Policy + fp-markers ──
# ALT ``_route_pattern`` Z. 610-674. LP-Fast-Path noch nicht verdrahtet →
# ``lp_routed`` bleibt False (Canvas-Guard prüft intent==I05, LP intent I04/
# Keywords → kein Fehl-Routing). ``run_canvas_create_fast_path`` + ``_qr_policy``
# sind am Node gemockt; ``reconcile_effective_pattern`` läuft echt.
def test_fp_tail_no_fast_path_effective_is_winner(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured, winner=PatternDef(id="M03", label="Klärung"),
           qr_ret=("speculative", 3))
    ctx = _ctx(classification=ClassificationResult(intent_id="I03"))
    out = asyncio.run(route(ctx))
    assert out.lp_routed is False and out.canvas_routed is False
    # Kein Fast-Path → effektives Pattern = Engine-Sieger.
    assert out.effective_pattern_id == "M03"
    assert out.effective_pattern_label == "Klärung"
    # QR-Policy am effektiven Pattern aufgelöst.
    assert captured["qr_policy"] == "M03"
    assert (out.qr_mode, out.qr_max) == ("speculative", 3)
    # Kein Fast-Path → keine fp-Marker (Respond nutzt den Standardpfad).
    assert out.fp_response_text is None and out.fp_wlo_cards_raw is None
    assert out.tools_called == []
    assert out.qr_spec_task is None


def test_fp_tail_canvas_create_effective_m10(monkeypatch):
    captured = {}
    cv = CanvasFastPathResult(
        routed=True, payload_out=None, forced_quick_replies=[],
        response_text="# Arbeitsblatt: Brüche\n\n…",
        tools_called=["canvas_service.generate_canvas_content"],
        wlo_cards_raw=[], new_state="S3",
    )
    _patch(monkeypatch, captured, winner=PatternDef(id="M03", label="Klärung"),
           canvas_result=cv, qr_ret=("exact", 4))
    ctx = _ctx(classification=ClassificationResult(intent_id="I05"))
    out = asyncio.run(route(ctx))
    assert out.canvas_routed is True
    # Echtes Material (tools_called enthält den Generator) → effective M10.
    assert out.effective_pattern_id == "M10"
    assert out.effective_pattern_label == "KI-Inhalt-Generierung"
    assert out.fp_response_text == "# Arbeitsblatt: Brüche\n\n…"
    assert out.fp_wlo_cards_raw == []
    assert out.tools_called == ["canvas_service.generate_canvas_content"]
    assert out.state_id == "S3"                         # new_state-Rebind
    assert captured["qr_policy"] == "M10"               # QR am effektiven Pattern
    # Canvas-Fast-Path bekam den Route-Kontext (lp_routed=False, echte Objekte).
    assert captured["canvas"]["lp_routed"] is False
    assert captured["canvas"]["classification"] is ctx.classification
    assert captured["canvas"]["pattern_output"] is out.pattern_output


def test_fp_tail_canvas_slot_clarification_effective_m03(monkeypatch):
    captured = {}
    cv = CanvasFastPathResult(
        routed=True, payload_out=None,
        forced_quick_replies=["📝 Arbeitsblatt", "❓ Quiz"],
        response_text="Welches Material soll ich erstellen?",
        tools_called=[], wlo_cards_raw=[], new_state="S1",
    )
    _patch(monkeypatch, captured, winner=PatternDef(id="M07", label="Sonstiges"),
           canvas_result=cv)
    ctx = _ctx(classification=ClassificationResult(intent_id="I05"))
    out = asyncio.run(route(ctx))
    assert out.canvas_routed is True
    # Leerer tools_called → Slot-Klärung, effective MUSS auf M03 (nicht in Box rahmen).
    assert out.effective_pattern_id == "M03"
    assert out.effective_pattern_label == "Slot-Klärung"
    assert out.canvas_forced_quick_replies == ["📝 Arbeitsblatt", "❓ Quiz"]
    assert out.fp_response_text == "Welches Material soll ich erstellen?"


# ── Fast-Path-Tail Teil 2: LP-Head-Wiring (detect_lp_intent + run_lp_fast_path) ──
# ALT ``_route_pattern`` Z. 196-597 (Head-Gate + LP-Body) VOR dem Canvas-Call.
# Beide sind am Node gemockt; ``reconcile_effective_pattern`` läuft echt.
def test_fp_tail_lp_routed_effective_m09(monkeypatch):
    captured = {}
    lp = LpFastPathResult(
        routed=True, response_text="> **Lernpfad: Eiszeit**\n\n…",
        wlo_cards_raw=[{"node_id": "n1"}],
        tools_called=["search_wlo_collections (Eiszeit)", "generate_learning_path"],
        new_state="S3", qr_mode="speculative", qr_max=3, qr_spec_task="TASK",
    )
    _patch(monkeypatch, captured, winner=PatternDef(id="M03", label="Klärung"),
           lp_intent_ret=(True, "Eiszeit"), lp_result=lp)
    ctx = _ctx(classification=ClassificationResult(intent_id="I04"))
    out = asyncio.run(route(ctx))
    assert out.lp_routed is True and out.canvas_routed is False
    # LP-Fast-Path überschreibt den Engine-Sieger M03 → effektiv M09.
    assert out.effective_pattern_id == "M09"
    assert out.effective_pattern_label == "Lernpfad-Erstellung"
    # fp-Marker + tools_called + State kommen aus dem LP-Ergebnis.
    assert out.fp_response_text == "> **Lernpfad: Eiszeit**\n\n…"
    assert out.fp_wlo_cards_raw == [{"node_id": "n1"}]
    assert out.tools_called == ["search_wlo_collections (Eiszeit)", "generate_learning_path"]
    assert out.state_id == "S3"                          # new_state-Rebind aus LP
    # QR-Policy stammt aus dem LP-Block (M09-Policy) — _qr_policy wird NICHT aufgerufen.
    assert (out.qr_mode, out.qr_max) == ("speculative", 3)
    assert "qr_policy" not in captured
    assert out.qr_spec_task == "TASK"
    # Canvas bekam lp_routed=True (Passthrough) + die LP-tools_called als Input.
    assert captured["canvas"]["lp_routed"] is True
    assert captured["canvas"]["tools_called"] == [
        "search_wlo_collections (Eiszeit)", "generate_learning_path"]


def test_fp_tail_lp_gate_and_body_receive_route_context(monkeypatch):
    captured = {}
    _patch(monkeypatch, captured, lp_intent_ret=(True, "Photosynthese"))
    ctx = _ctx(message="Erstelle einen Lernpfad zur Photosynthese",
               classification=ClassificationResult(intent_id="I04", next_state="S2"))
    ctx.usage = {"tokens": 0}
    out = asyncio.run(route(ctx))
    # Head-Gate bekam die Nachricht + die echten Route-Objekte.
    assert captured["lp_intent"]["message"] == "Erstelle einen Lernpfad zur Photosynthese"
    assert captured["lp_intent"]["classification"] is ctx.classification
    assert captured["lp_intent"]["session_state"] is ctx.session_state
    assert captured["lp_intent"]["pattern_output"] is out.pattern_output
    # LP-Body bekam das Gate-Ergebnis + usage-Accumulator + new_state durchgereicht.
    assert captured["lp"]["has_lp_intent"] is True
    assert captured["lp"]["thema"] == "Photosynthese"
    assert captured["lp"]["usage_acc"] is ctx.usage
    assert captured["lp"]["new_state"] == "S2"
    assert captured["lp"]["qr_spec_task"] is None
    # Gate feuerte, Body (default) nicht geroutet → kein Fehl-Override.
    assert out.lp_routed is False


# ── Reiner Helfer: RAG-Whitelist ───────────────────────────────────
def test_resolve_rag_areas_explicit_whitelist_filtered():
    cfg = {"a": {"mode": "always"}, "b": {"mode": "on-demand"}}
    # explizite rag_areas werden gegen die Config gefiltert (x existiert nicht)
    assert _resolve_rag_areas({"rag_areas": ["a", "x"]}, cfg) == ["a"]
    # explizit leere Liste bleibt leer (= „kein RAG")
    assert _resolve_rag_areas({"rag_areas": []}, cfg) == []


def test_resolve_rag_areas_sources_without_rag_kills_it():
    cfg = {"a": {"mode": "always"}}
    assert _resolve_rag_areas({"sources": ["web"]}, cfg) == []


def test_resolve_rag_areas_default_always_plus_on_demand():
    cfg = {"a": {"mode": "always"}, "b": {"mode": "on-demand"}, "c": {"mode": "always"}}
    # Default (weder rag_areas noch sources) → nur always-on
    assert _resolve_rag_areas({}, cfg) == ["a", "c"]
    # sources enthält "rag" → always + on-demand ergänzt
    assert _resolve_rag_areas({"sources": ["rag"]}, cfg) == ["a", "c", "b"]


# ── Reiner Helfer: Memory-Render ───────────────────────────────────
def test_render_memory_context_empty():
    assert _render_memory_context([]) == ""


def test_render_memory_context_formats_and_caps():
    mems = [{"key": f"k{i}", "value": f"v{i}"} for i in range(12)]
    rendered = _render_memory_context(mems)
    assert rendered.startswith("\nErinnerungen:\n- k0: v0\n- k1: v1")
    # Cap bei 10 Einträgen
    assert "k9: v9" in rendered
    assert "k10" not in rendered


# ── C9: Fortschritts-Meldung ────────────────────────────────────────

def test_route_reports_context_policy_and_pattern_in_order(monkeypatch):
    """Drei ALT-Schritte liegen in NEU dicht beieinander in diesem Knoten
    (ALT: ``context``/``policy`` im Setup, ``pattern`` im Routing). Die
    Reihenfolge ist das, was das Widget als Label-Abfolge zeigt."""
    _patch(monkeypatch, {})
    seen: list[dict] = []
    asyncio.run(route(_ctx(), progress=TurnProgress(seen.append)))
    assert [e["step"] for e in seen] == ["context", "policy", "pattern"]
    assert [e["kind"] for e in seen] == ["record", "start", "start"]
