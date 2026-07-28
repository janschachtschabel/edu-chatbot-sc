"""P3-3 (slice): quick-reply generator — port of ALT llm_quick_replies.py
(direct-call tests from ALT test_llm_service_generators.py).

Boundaries faked: ``llm._acompletion`` (transport; captures the system prompt),
``qr.get_state_directive`` and ``qr._analytical_personas`` (config). The
page-context line is deferred (its own later package), so its ALT test is not
ported here.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.services import llm
from boerdi.services import quick_replies_llm as qr
from boerdi.settings import get_settings


def _content_resp(text: str):
    return SimpleNamespace(
        model="gpt-5.4-mini",
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=50, completion_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
    )


class _Capture:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return _content_resp(self.text)


_QR_CLS = {"persona_id": "P-AND", "intent_id": "I01", "next_state": "S2"}


@pytest.fixture()
def _qr_env(monkeypatch):
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(qr, "get_state_directive", lambda sid: {
        "id": sid, "label": "Ergebnis-Kuratierung", "role": "",
        "bot_directive": "Biete Refinement-Optionen an.", "next_likely": [],
    })
    monkeypatch.setattr(qr, "_analytical_personas", lambda: frozenset({"P-X-ANA"}))
    return monkeypatch


def _run(monkeypatch, text, *, message="Zeig mir Mathe",
         response_text="Hier ist Material.", classification=None,
         session_state=None, usage_acc=None, count=4):
    cap = _Capture(text)
    monkeypatch.setattr(llm, "_acompletion", cap)
    out = asyncio.run(qr.generate_quick_replies(
        message, response_text,
        dict(_QR_CLS) if classification is None else classification,
        {} if session_state is None else session_state,
        usage_acc=usage_acc, count=count,
    ))
    return out, cap


def _system_of(cap: _Capture) -> str:
    return cap.calls[0]["messages"][0]["content"]


# ── parsing / dedup / cap ──────────────────────────────────────────────────
def test_qr_parses_dedupes_and_caps(_qr_env) -> None:
    out, _ = _run(
        _qr_env,
        "1. Zeig mir mehr\n- zeig mir mehr\n• Anderes Thema\nNoch was bitte\nFuenfte Zeile",
        count=3)
    assert out == ["Zeig mir mehr", "Anderes Thema", "Noch was bitte"]


def test_qr_reasoning_markers_stripped_before_parsing(_qr_env) -> None:
    out, _ = _run(_qr_env, "<think>plan</think>Zeig mir mehr\nAnderes Thema")
    assert out == ["Zeig mir mehr", "Anderes Thema"]


def test_qr_count_clamped_into_1_to_6(_qr_env) -> None:
    _, c1 = _run(_qr_env, "A", count=0)
    assert "Du generierst genau 4 kurze" in _system_of(c1)
    _, c2 = _run(_qr_env, "A", count=99)
    assert "Du generierst genau 6 kurze" in _system_of(c2)


def test_qr_prompt_context_entities_and_filled_hints(_qr_env) -> None:
    _, cap = _run(_qr_env, "A", classification={
        "persona_id": "P-AND", "intent_id": "I05", "next_state": "S2",
        "entities": {"thema": "Photosynthese", "_intern": "geheim"},
    })
    system = _system_of(cap)
    assert "Persona: P-AND (Anrede: du)" in system
    assert "Intent: I05" in system
    assert "Gesprächs-Phase: S2 (Ergebnis-Kuratierung)" in system
    assert "Biete Refinement-Optionen an." in system
    assert '{"thema": "Photosynthese"}' in system  # internal _-keys filtered
    assert "_intern" not in system
    assert "Zeig mir mehr Material zu Photosynthese" in system  # {thema} filled
    assert "{thema}" not in system


def test_qr_fach_only_fills_thema_placeholder_generically(_qr_env) -> None:
    _, cap = _run(_qr_env, "A", classification={
        "persona_id": "P-AND", "next_state": "S2", "entities": {"fach": "Mathe"},
    })
    system = _system_of(cap)
    assert "Was gibt es noch zu Mathe?" in system
    assert "Zeig mir mehr Material zu dem Thema" in system


def test_qr_state_fallback_and_canvas_marker(_qr_env) -> None:
    _qr_env.setattr(qr, "get_state_directive", lambda sid: {})
    _, cap = _run(_qr_env, "A",
                  classification={"persona_id": "P-AND", "intent_id": "I01"},
                  session_state={"state_id": "S3"})
    system = _system_of(cap)
    assert "Gesprächs-Phase: S3 () — Canvas-Arbeit aktiv" in system
    assert "— keine spezifische Direktive für diese Phase" in system


def test_qr_user_message_truncates_response_text_at_500(_qr_env) -> None:
    _, cap = _run(_qr_env, "A", response_text="X" * 600)
    user = cap.calls[0]["messages"][1]["content"]
    assert "Bot-Antwort: " + "X" * 500 in user
    assert "X" * 501 not in user


def test_qr_usage_folded_under_quick_replies_phase(_qr_env) -> None:
    from boerdi.obs import usage

    acc = usage.new_accumulator()
    _run(_qr_env, "Zeig mir mehr", usage_acc=acc)
    assert acc["per_phase"]["quick_replies"]["calls"] == 1
    assert acc["prompt_tokens"] == 50 and acc["completion_tokens"] == 20


def test_qr_returns_empty_on_transport_error(_qr_env) -> None:
    async def boom(**kwargs):
        raise RuntimeError("llm down")

    _qr_env.setattr(llm, "_acompletion", boom)
    out = asyncio.run(qr.generate_quick_replies("m", "r", dict(_QR_CLS), {}))
    assert out == []  # best-effort enhancement: failure yields no QRs, not a crash


# ── _capability_hints_for_persona (pure) ───────────────────────────────────
def test_hints_analytical_vs_didactic_selection(_qr_env) -> None:
    ana = qr._capability_hints_for_persona("P-X-ANA", in_canvas=False, has_topic=True)
    did = qr._capability_hints_for_persona("P-AND", in_canvas=False, has_topic=True)
    assert any("Statistiken gibt es zu WLO" in h for h in ana)
    assert any("Zeig mir mehr Material zu" in h for h in did)
    assert not any("Statistiken gibt es zu WLO" in h for h in did)


def test_hints_drop_topic_placeholders_when_no_topic(_qr_env) -> None:
    hints = qr._capability_hints_for_persona("P-AND", in_canvas=False, has_topic=False)
    assert not any("{thema}" in h or "{fach}" in h for h in hints)


def test_hints_drop_edit_hints_when_not_in_canvas(_qr_env) -> None:
    no_canvas = qr._capability_hints_for_persona("P-AND", in_canvas=False, has_topic=True)
    in_canvas = qr._capability_hints_for_persona("P-AND", in_canvas=True, has_topic=True)
    assert not any("einfacher" in h.lower() for h in no_canvas)
    assert any("einfacher" in h.lower() for h in in_canvas)


def test_analytical_personas_default_when_config_empty(monkeypatch) -> None:
    monkeypatch.setattr(qr, "load_canvas_persona_priorities", lambda: {"analytical_personas": []})
    assert qr._analytical_personas() == frozenset({"P-ENT", "P-RED"})
    monkeypatch.setattr(qr, "load_canvas_persona_priorities",
                        lambda: {"analytical_personas": ["P-Z"]})
    assert qr._analytical_personas() == frozenset({"P-Z"})
