"""Ende zu Ende im Backend (Plan ``2026-10-01-token-streaming``, T13).

Echt laufen die Sperre und Umformung des Muster-Zugs (``respond_strom``), der
Tool-Loop, ``_stream_completion`` samt Extraktor und Denkfilter und der
``TokenStrom``. Gefälscht ist nur der Transport (``llm._acompletion``) — in
Häppchen von drei Zeichen, wie der Spike vom 2026-10-01 sie zeigte, mit
Unicode-Escapes und einem Link im Text.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from boerdi.api.schemas import ChatRequest, Environment, SafetyDecision
from boerdi.domain.antwort_werkzeug import antwort_werkzeug
from boerdi.domain.url_helpers import _extract_web_links_from_text
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond_strom as rs_mod
from boerdi.graph.nodes.respond_strom import strom_fuer_muster_zug
from boerdi.obs.progress import TurnProgress
from boerdi.services import llm, tool_loop
from boerdi.services.token_stream import TokenStrom
from boerdi.settings import get_settings

_SESSION = object()
_ANTWORT = ("Photosynthese wandelt Licht in chemische Energie um. "
            "Mehr dazu bei [WLO](https://wlo.de) — Grüße " + chr(0x1F600))


@pytest.fixture(autouse=True)
def _strom_an(monkeypatch):
    monkeypatch.setenv("CHAT_TOKEN_STREAMING", "1")
    get_settings.cache_clear()
    monkeypatch.setattr(rs_mod, "inline_anzahl", lambda _po: 3)
    yield
    get_settings.cache_clear()


def _stuecke(args_json: str):
    """Der Antwort-Aufruf als Strom: Name, dann die Argumente in Häppchen."""
    def _tc(**kw):
        fn = SimpleNamespace(name=kw.get("name"), arguments=kw.get("arguments"))
        return SimpleNamespace(index=1, id=kw.get("id"), function=fn)

    def _chunk(tool_calls=None, finish=None):
        delta = SimpleNamespace(role="assistant", content=None, tool_calls=tool_calls)
        return SimpleNamespace(usage=None, model="m",
                               choices=[SimpleNamespace(delta=delta, finish_reason=finish)])

    yield _chunk([_tc(id="tc1", name="respond_to_user")])
    for i in range(0, len(args_json), 3):
        yield _chunk([_tc(arguments=args_json[i:i + 3])])
    yield _chunk(finish="tool_calls")


def _transport(monkeypatch, args_json: str):
    async def _acompletion(**_kw):
        async def _gen():
            for c in _stuecke(args_json):
                yield c
        return _gen()

    monkeypatch.setattr(llm, "_acompletion", _acompletion)


def _ctx(winner_id: str) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message="Was ist Photosynthese?",
                        environment=Environment()))
    ctx.winner_id = winner_id
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.session_state = {"entities": {}, "turn_count": 1}
    return ctx


def _loop(on_token):
    state = dict(
        message="Was ist Photosynthese?", classification={}, pattern_output={},
        pattern_label="M04", session_state={}, rag_context="", blocked_tools=[],
        active_tools=[antwort_werkzeug(3, 60)], _inline_qr_enabled=True,
        _inline_grouping_mode=False, messages=[{"role": "system", "content": "sys"}],
        all_cards=[], tools_called=[], outcomes=[], knowledge_prefetched=False,
        mcp_prefetched=False, always_areas=[], _RAG_TOP_K=3, _RAG_MIN_SCORE=0.25,
        _RAG_MAX_CHARS_PER_AREA=4000, usage_acc=None, on_token=on_token,
    )
    return asyncio.run(tool_loop._run_tool_loop(_SESSION, **state))


class _Uhr:
    """Jeder Blick auf die Uhr ist einen Takt später — jedes Stück ein Rahmen."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        self.t += 0.06
        return self.t


def test_die_verketteten_stuecke_ergeben_den_umgeformten_antworttext(monkeypatch):
    _transport(monkeypatch, json.dumps(
        {"text": _ANTWORT, "quick_replies": ["Mehr dazu"]}, ensure_ascii=True))
    ereignisse: list[dict] = []
    strom = TokenStrom(TurnProgress(ereignisse.append), uhr=_Uhr())
    offen = strom_fuer_muster_zug(strom, _ctx("M04"), {})

    text, _cards, _tools, _outs = _loop(offen)
    offen.schliessen()

    stuecke = [e["data"] for e in ereignisse if e["kind"] == "text"]
    assert len(stuecke) > 5, "es kam nicht stückweise"
    gesendet = ""
    for stueck in stuecke:
        assert stueck["pos"] == len(gesendet), "Lücke in der Rahmenfolge"
        gesendet += stueck["text"]
    assert text == _ANTWORT
    assert gesendet == _extract_web_links_from_text(_ANTWORT, cards=None)[0]
    assert "](" not in gesendet
    assert strom.abschluss(gesendet)["drift"] is False


def test_ein_suchzug_sendet_keinen_text(monkeypatch):
    """M05 ist gesperrt: der Tool-Loop bekommt kein ``on_token``, die Runde läuft
    ungestreamt über ``chat_completion``, und kein Stück geht hinaus."""
    gestreamt: list[dict] = []

    async def _strom_spion(on_token, **kw):
        gestreamt.append(kw)
        raise RuntimeError("gesperrt")

    async def _antwort(**_kw):
        tc = SimpleNamespace(id="tc1", type="function", function=SimpleNamespace(
            name="respond_to_user",
            arguments=json.dumps({"text": "Hier sind Treffer.", "quick_replies": []})))
        msg = SimpleNamespace(role="assistant", content=None, tool_calls=[tc])
        return SimpleNamespace(usage=None, model="m",
                               choices=[SimpleNamespace(message=msg, finish_reason="tool_calls")])

    monkeypatch.setattr(tool_loop, "_stream_completion", _strom_spion)
    monkeypatch.setattr(llm, "chat_completion", _antwort)
    ereignisse: list[dict] = []
    strom = TokenStrom(TurnProgress(ereignisse.append))

    text, _cards, _tools, _outs = _loop(strom_fuer_muster_zug(strom, _ctx("M05"), {}))

    assert text == "Hier sind Treffer."
    assert gestreamt == []
    assert ereignisse == []
