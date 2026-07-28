"""Charakterisierungs-Pins für domain.context.build_context — baut eine
``ContextSnapshot`` aus (env, session_state, classification, memories). ALT
``app/services/context_service.py`` hatte KEINEN Unit-Test (nur Integration in
``test_chat_impl_net``) → hier frisch aus der ALT-Logik gepinnt. Reine Funktion,
kein I/O; Modul zog nach ``boerdi.domain.context``.
"""

from __future__ import annotations

from boerdi.api.schemas import ClassificationResult
from boerdi.domain.context import build_context


def test_defaults_when_inputs_empty():
    snap = build_context({}, {})
    assert snap.page == "/"
    assert snap.device == "desktop"
    assert snap.locale == "de-DE"
    assert snap.session_duration == 0
    assert snap.turn_count == 0
    assert snap.entities == {}
    assert snap.recent_signals == []
    assert snap.memory_keys == []
    assert snap.last_intent == ""
    assert snap.last_state == ""


def test_env_values_used():
    env = {"page": "/suche", "device": "mobile", "locale": "en-US",
           "session_duration": "12"}
    snap = build_context(env, {})
    assert snap.page == "/suche"
    assert snap.device == "mobile"
    assert snap.locale == "en-US"
    assert snap.session_duration == 12   # str → int-Koerzierung


def test_session_duration_none_coerces_to_zero():
    snap = build_context({"session_duration": None}, {})
    assert snap.session_duration == 0


def test_turn_count_from_session_state():
    snap = build_context({}, {"turn_count": 3})
    assert snap.turn_count == 3


def test_entities_hide_internal_scratchpad_keys():
    ss = {"entities": {"thema": "Photosynthese", "fach": "Bio",
                       "_last_contents": "[...]", "_canvas_topic": "x"}}
    snap = build_context({}, ss)
    assert snap.entities == {"thema": "Photosynthese", "fach": "Bio"}


def test_recent_signals_last_ten():
    ss = {"signal_history": [f"s{i}" for i in range(12)]}
    snap = build_context({}, ss)
    assert snap.recent_signals == [f"s{i}" for i in range(2, 12)]   # letzte 10


def test_memory_keys_from_memories_capped():
    mems = [{"key": f"k{i}", "value": f"v{i}"} for i in range(12)]
    snap = build_context({}, {}, memories=mems)
    assert snap.memory_keys == [f"k{i}" for i in range(10)]   # cap 10


def test_classification_sets_last_intent_and_state():
    cls = ClassificationResult(intent_id="I05", next_state="S3")
    snap = build_context({}, {}, classification=cls)
    assert snap.last_intent == "I05"
    assert snap.last_state == "S3"
