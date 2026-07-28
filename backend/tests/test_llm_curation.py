"""P5-6a (slice): curation generator — port of ALT llm_curation.py
(``generate_curation_text``). ALT has NO direct unit test for this newer
(Seitenkontext-Feature) generator — it was only mocked as a boundary in
test_chat_direct_actions.py. These are characterization tests pinning ALT's
real behavior (prompt structure + fallback chain), mirroring the LP tests.

Boundary faked: ``llm._acompletion`` (transport; captures the messages).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import llm
from boerdi.services import llm_curation as cur
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
    def __init__(self, text=None, raises=None):
        self.text, self.raises = text, raises
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises is not None:
            raise self.raises
        return _content_resp(self.text)


def _run(monkeypatch, cap, title="Bruchrechnung", compendium="Soll-Text",
         contents="- Video A", instruction="Nenne die Lücken.",
         session_state=None):
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    return asyncio.run(cur.generate_curation_text(
        title, compendium, contents, instruction,
        {} if session_state is None else session_state,
    ))


def test_cur_prompt_soll_ist_structure_and_persona(monkeypatch):
    cap = _Capture(text="Analyse")
    _run(monkeypatch, cap, session_state={"persona_id": "P-RED"})
    system = cap.calls[0]["messages"][0]["content"]
    user = cap.calls[0]["messages"][1]["content"]
    assert "Persona: P-RED" in system
    assert "STRIKTE ERDUNG" in system
    assert 'Sammlung: "Bruchrechnung"' in user
    assert "## SOLL" in user
    assert "Soll-Text" in user
    assert "## IST" in user
    assert "- Video A" in user
    # Die Studio-Instruction (curate_prompt) steht am Ende des User-Prompts.
    assert user.rstrip().endswith("Nenne die Lücken.")


def test_cur_persona_defaults_to_p_and(monkeypatch):
    cap = _Capture(text="Analyse")
    _run(monkeypatch, cap, session_state={})
    assert "Persona: P-AND" in cap.calls[0]["messages"][0]["content"]


def test_cur_empty_content_yields_fallback_message(monkeypatch):
    cap = _Capture(text=None)
    out = _run(monkeypatch, cap)
    assert out == "Die Kuratier-Analyse konnte nicht erstellt werden."


def test_cur_reasoning_markers_stripped(monkeypatch):
    cap = _Capture(text="<think>plan</think>Analyse fertig")
    assert _run(monkeypatch, cap) == "Analyse fertig"


def test_cur_exception_embedded_in_error_message(monkeypatch):
    cap = _Capture(raises=RuntimeError("boom"))
    assert _run(monkeypatch, cap) == "Fehler bei der Kuratier-Analyse: boom"
