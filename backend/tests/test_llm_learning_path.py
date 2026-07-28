"""P5-6a (slice): learning-path generator — port of ALT llm_learning_path.py
(the 5 direct-call LP tests from ALT test_llm_service_generators.py).

Boundary faked: ``llm._acompletion`` (transport; captures the messages).
Transport-adaptation vs ALT (which patched the module-level ``client``): the
prompt-building is verbatim, so the same assertions on the system/user message
hold. Precedent: test_quick_replies_llm.py.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import llm
from boerdi.services import llm_learning_path as lp
from boerdi.settings import get_settings


def _content_resp(text):
    return SimpleNamespace(
        model="gpt-5.4-mini",
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(
            prompt_tokens=50, completion_tokens=20,
            prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
    )


class _Capture:
    """Fake ``_acompletion``: records call kwargs, returns a fixed content
    response or raises."""

    def __init__(self, text=None, raises=None):
        self.text, self.raises = text, raises
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return _content_resp(self.text)


def _run(monkeypatch, cap, title="Bruchrechnung",
         contents="1. [Video A](https://x)", session_state=None):
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    return asyncio.run(lp.generate_learning_path_text(
        title, contents, {} if session_state is None else session_state,
    ))


def test_lp_prompt_with_fach_and_stufe(monkeypatch):
    cap = _Capture(text="Pfad")
    _run(monkeypatch, cap, session_state={
        "persona_id": "P-W-LK",
        "entities": {"fach": "Biologie", "stufe": "Sek I"},
    })
    system = cap.calls[0]["messages"][0]["content"]
    user = cap.calls[0]["messages"][1]["content"]
    assert "Persona: P-W-LK" in system
    assert "Kontext: Fach: Biologie | Bildungsstufe: Sek I" in system
    # Beide Slots gesetzt → KEIN Ableitungs-Hinweis.
    assert "WICHTIG — Fach/Stufe ableiten" not in system
    assert 'zum Thema "Bruchrechnung"' in user
    assert "1. [Video A](https://x)" in user


def test_lp_default_hint_when_fach_or_stufe_missing(monkeypatch):
    # Beide fehlen → allgemeiner Kontext + Ableitungs-Hinweis für beide Slots.
    cap1 = _Capture(text="Pfad")
    _run(monkeypatch, cap1, session_state={})
    s1 = cap1.calls[0]["messages"][0]["content"]
    assert "Persona: P-AND" in s1  # Persona-Default
    assert "Kontext: allgemeine Lernende" in s1
    assert ("- Fach (NICHT genannt — leite plausible Annahme aus dem Thema ab): "
            "— leite ab") in s1
    assert "- Stufe (NICHT genannt" in s1
    # Nur Stufe fehlt → Fach konkret, Ableitungs-Hinweis nur für Stufe.
    cap2 = _Capture(text="Pfad")
    _run(monkeypatch, cap2, session_state={"entities": {"fach": "Mathe"}})
    s2 = cap2.calls[0]["messages"][0]["content"]
    assert "Kontext: Fach: Mathe" in s2
    assert "- Fach: Mathe" in s2
    assert "- Stufe (NICHT genannt" in s2


def test_lp_empty_content_yields_fallback_message(monkeypatch):
    cap = _Capture(text=None)
    out = _run(monkeypatch, cap)
    assert out == "Lernpfad konnte nicht erstellt werden."


def test_lp_reasoning_markers_stripped(monkeypatch):
    cap = _Capture(text="<think>plan</think>Pfad fertig")
    assert _run(monkeypatch, cap) == "Pfad fertig"


def test_lp_exception_embedded_in_error_message(monkeypatch):
    cap = _Capture(raises=RuntimeError("boom"))
    assert _run(monkeypatch, cap) == "Fehler beim Erstellen des Lernpfads: boom"
