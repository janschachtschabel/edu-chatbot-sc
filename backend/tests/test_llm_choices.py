"""Text und Werkzeugaufrufe kommen als EINE Wahl zurück (services/llm_choices.py).

LiteLLMs Brücke auf die Responses-API (gpt-5.4 und neuer, ``gpt-6-luna``)
legt eine Antwort mit Text UND Werkzeugaufrufen auf zwei Choices:
``choices[0]`` trägt den Text mit ``finish_reason="stop"``, ``choices[1]``
die Aufrufe mit ``"tool_calls"``. Live gemessen am 2026-09-30. Jeder Aufrufer
liest ``choices[0]`` — die Werkzeugschleife verlor so ein ``zeige_dokument``
samt überarbeitetem Text („Formuliere es einfacher" ohne Box).

Die Netzgrenze ist ``llm._acompletion`` wie in ``test_llm.py``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from boerdi.services import llm


def _aufruf(name: str, argumente: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"call_{name}", type="function",
        function=SimpleNamespace(name=name, arguments=argumente))


def _wahl(*, text: str | None, aufrufe: list | None, grund: str) -> SimpleNamespace:
    return SimpleNamespace(
        finish_reason=grund, index=0,
        message=SimpleNamespace(role="assistant", content=text, tool_calls=aufrufe))


def _antwort(*wahlen: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(model="gpt-6-luna", usage=None, choices=list(wahlen))


def _mit(monkeypatch, antwort: SimpleNamespace) -> SimpleNamespace:
    async def fake(**_kwargs):
        return antwort

    monkeypatch.setattr(llm, "_acompletion", fake)
    return asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}]))


def test_text_und_aufruf_auf_zwei_choices_werden_eine_wahl(monkeypatch) -> None:
    argumente = '{"titel": "Vereinfacht", "markdown": "# A"}'
    dokument = _aufruf("zeige_dokument", argumente)
    resp = _mit(monkeypatch, _antwort(
        _wahl(text="Ich habe den Text vereinfacht.", aufrufe=None, grund="stop"),
        _wahl(text=None, aufrufe=[dokument], grund="tool_calls"),
    ))

    assert len(resp.choices) == 1
    wahl = resp.choices[0]
    assert wahl.finish_reason == "tool_calls"
    assert [a.function.name for a in wahl.message.tool_calls] == ["zeige_dokument"]
    assert wahl.message.tool_calls[0].function.arguments == argumente
    assert wahl.message.content == "Ich habe den Text vereinfacht."


def test_aufrufe_aus_mehreren_choices_bleiben_alle_erhalten(monkeypatch) -> None:
    resp = _mit(monkeypatch, _antwort(
        _wahl(text="Moment.", aufrufe=None, grund="stop"),
        _wahl(text=None, aufrufe=[_aufruf("search_wlo_all", "{}"),
                                 _aufruf("zeige_dokument", "{}")], grund="tool_calls"),
    ))

    assert [a.function.name for a in resp.choices[0].message.tool_calls] == [
        "search_wlo_all", "zeige_dokument"]


def test_eine_wahl_bleibt_unveraendert(monkeypatch) -> None:
    einzig = _wahl(text="Hallo.", aufrufe=None, grund="stop")
    resp = _mit(monkeypatch, _antwort(einzig))

    assert resp.choices == [einzig]
    assert resp.choices[0].finish_reason == "stop"


def test_mehrere_textwahlen_ohne_aufrufe_bleiben_unveraendert(monkeypatch) -> None:
    """Ohne Aufrufe geht nichts verloren, was eine Schleife bräuchte — kein Umbau."""
    erste = _wahl(text="Teil eins.", aufrufe=None, grund="stop")
    zweite = _wahl(text="Teil zwei.", aufrufe=None, grund="stop")
    resp = _mit(monkeypatch, _antwort(erste, zweite))

    assert resp.choices == [erste, zweite]
