"""Agent-Schleife: Text + Werkzeugaufruf in EINER Antwort führt das Werkzeug aus.

Geschwister von ``test_tool_loop_zwei_choices.py``: die Responses-Brücke legt
eine Antwort mit Begleitsatz UND Aufruf auf zwei Choices, und die Agent-Schleife
las wie die Werkzeugschleife nur ``choices[0]`` — die Suche fiel still weg, und
der Begleitsatz („Ich suche …") wurde zur Antwort.

Gefälscht wird ``llm._acompletion``, damit der Zusammenschluss in
``llm.chat_completion`` mitläuft (wie ``echter_transport`` in
``test_agent_loop.py``).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from boerdi.domain.config_models.engine import AgentLimits
from boerdi.services import agent_loop, llm, outcome_service
from boerdi.settings import get_settings


def _wahl(*, text, aufrufe, grund):
    return SimpleNamespace(
        finish_reason=grund, index=0,
        message=SimpleNamespace(role="assistant", content=text, tool_calls=aufrufe))


class _Brueckenantworten:
    def __init__(self):
        aufruf = SimpleNamespace(id="call_1", type="function", function=SimpleNamespace(
            name="search_wlo_content", arguments=json.dumps({"query": "Photosynthese"})))
        self._folge = [
            [_wahl(text="Ich suche passende Materialien.", aufrufe=None, grund="stop"),
             _wahl(text=None, aufrufe=[aufruf], grund="tool_calls")],
            [_wahl(text="Hier sind passende Materialien.", aufrufe=None, grund="stop")],
        ]

    async def __call__(self, **_kwargs):
        return SimpleNamespace(model="gpt-6-luna", usage=None, choices=self._folge.pop(0))


class _Werkzeuge:
    def __init__(self):
        self.aufrufe: list[str] = []

    async def __call__(self, tool_name, tool_args):
        from boerdi.api.schemas import ToolOutcome
        self.aufrufe.append(tool_name)
        return "treffer", ToolOutcome(tool=tool_name, status="success", item_count=1)


def test_text_und_aufruf_auf_zwei_choices_fuehrt_das_werkzeug_aus(monkeypatch) -> None:
    get_settings.cache_clear()
    llm.reset()
    monkeypatch.setattr(llm, "_acompletion", _Brueckenantworten())
    werkzeuge = _Werkzeuge()
    monkeypatch.setattr(outcome_service, "call_with_outcome", werkzeuge)

    lauf = asyncio.run(agent_loop.run_agent_loop(
        messages=[{"role": "system", "content": "sys"}],
        tools=[{"type": "function", "function": {"name": "search_wlo_content"}}],
        limits=AgentLimits(),
        usage_acc=None,
    ))

    assert werkzeuge.aufrufe == ["search_wlo_content"]
    assert lauf.tools_called == ["search_wlo_content"]
    assert lauf.text == "Hier sind passende Materialien."
