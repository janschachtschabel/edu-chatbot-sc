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

from boerdi.obs.usage import new_accumulator
from boerdi.services import llm
from boerdi.services import llm_curation as cur
from boerdi.settings import get_settings


def _content_resp(text):
    return SimpleNamespace(
        model="gpt-5.6-luna",
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


# ── Ausgabe-Sprache (C1-f2a) ───────────────────────────────────────────────
# Die Kuratier-Analyse ist Bot-Text, den der Nutzer liest — sie muss der
# Widget-Sprache folgen wie die Hauptantwort (C1-f1).

_CUR_DE = "Antworte auf Deutsch in sauberem Markdown ohne einleitende Meta-Sätze."


def _cur_system(monkeypatch, **kw):
    cap = _Capture(text="Analyse")
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    asyncio.run(cur.generate_curation_text(
        "Bruchrechnung", "Soll-Text", "- Video A", "Nenne die Lücken.", {}, **kw))
    return cap.calls[0]["messages"][0]["content"]


def test_cur_deutsch_bleibt_wortgleich(monkeypatch):
    ohne = _cur_system(monkeypatch)
    mit = _cur_system(monkeypatch, lang="de")
    assert ohne == mit
    assert mit.endswith(_CUR_DE)


def test_cur_englisch_tauscht_die_direktive_und_haengt_den_hinweis_an(monkeypatch):
    from boerdi.i18n import template_hint
    system = _cur_system(monkeypatch, lang="en")
    assert _CUR_DE not in system
    assert "Antworte auf Englisch (British English) in sauberem Markdown" in system
    assert system.endswith(template_hint("en").strip())


# ── C1-f2b6b: die Rueckfall-Saetze folgen derselben Sprache ────────────────

def test_cur_fallback_message_english(monkeypatch):
    cap = _Capture(text=None)
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    out = asyncio.run(cur.generate_curation_text(
        "Fractions", "target", "- Video A", "Name the gaps.", {}, lang="en"))
    assert out == "The curation analysis could not be created."


def test_cur_error_message_english(monkeypatch):
    cap = _Capture(raises=RuntimeError("boom"))
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    out = asyncio.run(cur.generate_curation_text(
        "Fractions", "target", "- Video A", "Name the gaps.", {}, lang="en"))
    assert out == "Error during the curation analysis: boom"


# ── K1c: die Kuration bucht ihre Token ────────────────────────────────────

def test_kuration_bucht_unter_eigener_phase(monkeypatch):
    cap = _Capture(text="Analyse")
    acc = new_accumulator()
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)

    asyncio.run(cur.generate_curation_text(
        "Bruchrechnung", "Soll", "- Video A", "Nenne die Luecken.", {},
        usage_acc=acc))

    assert acc["calls"] == 1
    assert acc["per_phase"]["curation"] == {
        "prompt": 50, "completion": 20, "cached": 0, "reasoning": 0, "calls": 1}
