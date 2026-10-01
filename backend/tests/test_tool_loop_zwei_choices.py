"""Werkzeugschleife: Text + ``zeige_dokument`` in EINER Antwort liefert die Box.

Nachgestellt ist der Zug vom 2026-09-30 („Formuliere es einfacher"): das Modell
schrieb den Begleitsatz UND rief ``zeige_dokument`` mit dem überarbeiteten Text.
Die Responses-Brücke legte beides auf zwei Choices, die Schleife las nur
``choices[0]`` — der Begleitsatz wurde zur Antwort, die Box fiel still weg.

Gefälscht wird eine Ebene tiefer als in ``test_tool_loop.py`` (dort
``llm.chat_completion``): hier ``llm._acompletion``, damit der Zusammenschluss in
``llm.chat_completion`` mitläuft — genau der Weg, den der Zug im Betrieb nimmt.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from boerdi.services import card_collect, llm, tool_loop

_DOKUMENT = {"titel": "Vereinfachte Fassung", "art": "dokument",
             "markdown": "# Umwelt\n\nKurz und einfach erklärt."}


def _wahl(*, text, aufrufe, grund):
    return SimpleNamespace(
        finish_reason=grund, index=0,
        message=SimpleNamespace(role="assistant", content=text, tool_calls=aufrufe))


class _Brueckenantworten:
    """``_acompletion`` wie die Responses-Brücke: erst Text + Aufruf auf zwei
    Choices, dann der Begleitsatz als gewöhnliche Antwort."""

    def __init__(self):
        aufruf = SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(
            name="zeige_dokument", arguments=json.dumps(_DOKUMENT)))
        self._folge = [
            [_wahl(text="Ich habe den Text vereinfacht.", aufrufe=None, grund="stop"),
             _wahl(text=None, aufrufe=[aufruf], grund="tool_calls")],
            [_wahl(text="Hier ist die vereinfachte Fassung.", aufrufe=None, grund="stop")],
        ]

    async def __call__(self, **_kwargs):
        return SimpleNamespace(model="gpt-6-luna", usage=None, choices=self._folge.pop(0))


def test_text_und_zeige_dokument_auf_zwei_choices_liefert_die_box(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_acompletion", _Brueckenantworten())
    monkeypatch.setattr(card_collect, "parse_wlo_cards", lambda text: [])
    sitzung: dict = {}

    ergebnis = asyncio.run(tool_loop._run_tool_loop(
        object(),
        message="Formuliere es einfacher", classification={}, pattern_output={},
        pattern_label="Iterative Nachbearbeitung", session_state=sitzung,
        rag_context="", blocked_tools=[], active_tools=[],
        _inline_qr_enabled=False, _inline_grouping_mode=False,
        messages=[{"role": "system", "content": "sys"}], all_cards=[],
        tools_called=[], outcomes=[], knowledge_prefetched=False,
        mcp_prefetched=False, always_areas=[], _RAG_TOP_K=3, _RAG_MIN_SCORE=0.25,
        _RAG_MAX_CHARS_PER_AREA=4000, usage_acc=None, on_token=None,
    ))

    geliefert = sitzung.get(tool_loop.GELIEFERTE_DOKUMENTE_KEY) or []
    assert [d["title"] for d in geliefert] == ["Vereinfachte Fassung"]
    assert "Kurz und einfach erklärt." in geliefert[0]["content"]
    assert ergebnis[0] == "Hier ist die vereinfachte Fassung."
