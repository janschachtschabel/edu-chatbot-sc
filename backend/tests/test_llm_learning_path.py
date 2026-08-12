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

from boerdi.obs.usage import new_accumulator
from boerdi.services import llm
from boerdi.services import llm_learning_path as lp
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


# ── Ausgabe-Sprache (C1-f2a) ───────────────────────────────────────────────
# Der Lernpfad-Markdown steht als Inline-Dokument im Chat — Bot-Text, den der
# Nutzer liest. Die Sprachangabe steht hier im USER-Prompt (Format-Block).

_LP_DE = "**Format (Markdown, auf Deutsch):**"


def _lp_messages(monkeypatch, **kw):
    cap = _Capture(text="Pfad")
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    asyncio.run(lp.generate_learning_path_text(
        "Bruchrechnung", "1. [Video A](https://x)", {}, **kw))
    return cap.calls[0]["messages"]


def test_lp_deutsch_bleibt_wortgleich(monkeypatch):
    ohne = _lp_messages(monkeypatch)
    mit = _lp_messages(monkeypatch, lang="de")
    assert ohne == mit
    assert _LP_DE in mit[1]["content"]


def test_lp_englisch_tauscht_die_direktive_und_haengt_den_hinweis_an(monkeypatch):
    from boerdi.i18n import template_hint
    system, user = _lp_messages(monkeypatch, lang="en")
    assert _LP_DE not in user["content"]
    assert "**Format (Markdown, auf Englisch (British English)):**" in user["content"]
    assert system["content"].endswith(template_hint("en").strip())


# ── C1-f2b6b: die Rueckfall-Saetze folgen derselben Sprache ────────────────

def test_lp_fallback_message_english(monkeypatch):
    cap = _Capture(text=None)
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    out = asyncio.run(lp.generate_learning_path_text(
        "Fractions", "1. [Video A](https://x)", {}, lang="en"))
    assert out == "The learning path could not be created."


def test_lp_error_message_english(monkeypatch):
    cap = _Capture(raises=RuntimeError("boom"))
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    out = asyncio.run(lp.generate_learning_path_text(
        "Fractions", "1. [Video A](https://x)", {}, lang="en"))
    assert out == "Error while creating the learning path: boom"


# ── K1b: der Lernpfad bucht seine Token ───────────────────────────────────
# ``max_tokens=2000`` macht ihn zu einem der groessten Einzelaufrufe des
# Systems — und er tauchte in keiner Kostenzahl auf.

def test_lp_bucht_unter_eigener_phase(monkeypatch):
    cap = _Capture(text="Pfad")
    acc = new_accumulator()
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)

    asyncio.run(lp.generate_learning_path_text(
        "Bruchrechnung", "1. [Video A](https://x)", {}, usage_acc=acc))

    assert acc["calls"] == 1
    assert acc["per_phase"]["learning_path"] == {
        "prompt": 50, "completion": 20, "cached": 0, "reasoning": 0, "calls": 1}


def test_lp_ohne_merkposten_bleibt_lauffaehig(monkeypatch):
    # Der Parameter ist optional — die Bestandsaufrufer (Tests, Evals) rufen
    # ohne ihn auf und duerfen nicht scheitern.
    cap = _Capture(text="Pfad")
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", cap)
    assert asyncio.run(lp.generate_learning_path_text("T", "c", {})) == "Pfad"
