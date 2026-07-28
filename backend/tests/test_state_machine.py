"""Charakterisierungs-Pins für state_machine — Conversation-State-Übergangs-
Validator. ALT ``app/services/state_machine.py`` hatte KEINEN Test (nur einen
veralteten, widersprüchlichen Doctest im Modul-Docstring, dessen 2. Beispiel
gegen den Self-Loop-Zweig lief) → hier frisch aus der ALT-Logik gepinnt.

Modul zog nach ``boerdi.domain.state_machine``. Der einzige Config-Seam
``get_state_directive`` wird am Domänen-Modul gemockt (dort per Name
importiert), damit die Tests unabhängig von ``04-states/states.yaml`` sind.
"""

from __future__ import annotations

import pytest

from boerdi.domain import state_machine as sm


def _boom(_state_id):
    raise AssertionError("get_state_directive darf hier nicht aufgerufen werden")


# ── Kurzschluss-Zweige (kein Config-Read) ──────────────────────────
def test_first_turn_is_always_plausible(monkeypatch):
    monkeypatch.setattr(sm, "get_state_directive", _boom)  # darf nicht laufen
    r = sm.validate_transition(prev="", next_="S1", intent="I01")
    assert r == {"validated_state": "S1", "plausible": True,
                 "reason": "", "prev_next_likely": []}


def test_self_loop_is_plausible_without_config(monkeypatch):
    # Exakt der Input des kaputten ALT-Doctests (prev==next_, intent="I02"):
    # ALT-Doc behauptete plausible=False — der Self-Loop-Zweig liefert True.
    monkeypatch.setattr(sm, "get_state_directive", _boom)
    r = sm.validate_transition(prev="S3", next_="S3", intent="I02")
    assert r["plausible"] is True
    assert r["validated_state"] == "S3"
    assert r["reason"] == ""
    assert r["prev_next_likely"] == []


# ── Config-basierte Zweige (get_state_directive gemockt) ───────────
def _mock_directive(monkeypatch, next_likely):
    monkeypatch.setattr(sm, "get_state_directive",
                        lambda sid: {"next_likely": next_likely})


def test_no_next_likely_defaults_to_plausible(monkeypatch):
    monkeypatch.setattr(sm, "get_state_directive", lambda sid: {})  # kein Hint
    r = sm.validate_transition(prev="S1", next_="S3")
    assert r["plausible"] is True
    assert r["prev_next_likely"] == []


def test_next_in_next_likely_is_plausible(monkeypatch):
    _mock_directive(monkeypatch, ["S2", "S3"])
    r = sm.validate_transition(prev="S1", next_="S2")
    assert r["plausible"] is True
    assert r["reason"] == ""
    assert r["prev_next_likely"] == ["S2", "S3"]


@pytest.mark.parametrize("intent", ["I05", "I06"])
def test_canvas_intent_override_to_s3(monkeypatch, intent):
    _mock_directive(monkeypatch, ["S2"])  # S3 NICHT in next_likely
    r = sm.validate_transition(prev="S1", next_="S3", intent=intent)
    assert r["plausible"] is True
    assert r["reason"] == "canvas-intent override (intent in {I05, I06})"
    assert r["prev_next_likely"] == ["S2"]


def test_canvas_override_only_for_s3_target(monkeypatch):
    # intent I05, aber Ziel != S3 → kein Override → implausibel.
    _mock_directive(monkeypatch, ["S3"])
    r = sm.validate_transition(prev="S1", next_="S2", intent="I05")
    assert r["plausible"] is False


def test_implausible_warn_leaves_state_unchanged(monkeypatch):
    _mock_directive(monkeypatch, ["S2"])
    r = sm.validate_transition(prev="S1", next_="S3", intent="I02")
    assert r["plausible"] is False
    assert r["validated_state"] == "S3"          # unverändert (reine Telemetrie)
    assert r["reason"] == "S3 nicht in next_likely von S1 [S2]"
    assert r["prev_next_likely"] == ["S2"]


def test_implausible_auto_correct_uses_first_next_likely(monkeypatch):
    _mock_directive(monkeypatch, ["S2", "S4"])
    r = sm.validate_transition(prev="S1", next_="S3", intent="I02",
                               auto_correct=True)
    assert r["plausible"] is False
    assert r["validated_state"] == "S2"          # korrigiert auf next_likely[0]
    assert r["reason"] == ("S3 nicht in next_likely von S1 [S2, S4]"
                           " → korrigiert zu S2")
    assert r["prev_next_likely"] == ["S2", "S4"]
