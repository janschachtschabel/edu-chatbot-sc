"""R1b-1: streaming twin of chat_completion (services/llm_streaming.py).

Ported 1:1 from ALT tests/test_llm_service_generators.py (the direct
``_stream_completion`` + ``_RespondToUserExtractor`` blocks) with the transport
fake swapped: ALT patched the ``client`` singleton on the streaming module,
NEU patches the standard network boundary ``llm._acompletion`` (which, awaited
with ``stream=True``, hands back an async iterator of OpenAI-shaped chunks).

Three NEU-only pins cover the declared transport deviation: semantic kwargs are
built+routed inside ``_stream_completion`` (mirror of chat_completion's wiring
test), the live semaphore is held for the WHOLE stream consumption (ALT's
bulkhead was the httpx pool, which a stream also occupied end-to-end), and
errors propagate to the caller (the tool loop owns the error policy).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace as _NS

import pytest

from boerdi.services import llm
from boerdi.services import llm_streaming as lls
from boerdi.settings import get_settings

_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY",
        "OPENAI_BASE_URL", "B_API_KEY", "B_API_BASE_URL", "LLM_VERBOSITY",
        "LLM_REASONING_EFFORT", "LLM_MAX_CONCURRENCY")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    llm.reset()
    return monkeypatch


class _StreamFake:
    """Fake ``llm._acompletion``: records kwargs, returns an async generator
    over the preset chunks (the shape LiteLLM's awaited ``acompletion(stream=
    True)`` hands back)."""

    def __init__(self, chunks):
        self.calls: list[dict] = []
        self._chunks = chunks

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)

        async def _gen():
            for c in self._chunks:
                yield c
        return _gen()


def _chunk(*, content=None, role=None, tool_calls=None, finish=None,
           usage=None, model=None, no_choices=False):
    if no_choices:
        return _NS(usage=usage, model=model, choices=[])
    delta = _NS(role=role, content=content, tool_calls=tool_calls)
    return _NS(usage=usage, model=model,
               choices=[_NS(delta=delta, finish_reason=finish)])


def _tc_delta(index=0, id=None, name=None, arguments=None):  # noqa: A002 — OpenAI-Feldname
    fn = _NS(name=name, arguments=arguments)
    return _NS(index=index, id=id, function=fn)


def _usage_obj(prompt, completion):
    return _NS(prompt_tokens=prompt, completion_tokens=completion,
               prompt_tokens_details=None)


def _run_stream(monkeypatch, chunks, **kwargs):
    fake = _StreamFake(chunks)
    monkeypatch.setattr(llm, "_acompletion", fake)
    out: list[str] = []
    resp = asyncio.run(lls._stream_completion(out.append, model="m", messages=[], **kwargs))
    return fake, out, resp


# ════════════════════════════════════════════════════════════════════════
# _stream_completion — ported ALT pins
# ════════════════════════════════════════════════════════════════════════

def test_stream_content_tokens_and_reconstruction(monkeypatch):
    u = _usage_obj(10, 5)
    fake, out, resp = _run_stream(monkeypatch, [
        _chunk(role="assistant", content="Hal", model="gpt-x"),
        _chunk(content="lo"),
        _chunk(finish="stop"),
        _chunk(usage=u, no_choices=True),  # Usage-only-Final-Chunk (leere choices)
    ])
    # kwargs werden auf Streaming gezwungen (stream + include_usage).
    assert fake.calls[0]["stream"] is True
    assert fake.calls[0]["stream_options"] == {"include_usage": True}
    # Tokens live durchgereicht + Message rekonstruiert.
    assert "".join(out) == "Hallo"
    msg = resp.choices[0].message
    assert msg.content == "Hallo"
    assert msg.role == "assistant"
    assert msg.tool_calls is None
    assert resp.choices[0].finish_reason == "stop"
    assert resp.usage is u
    assert resp.model == "gpt-x"


def test_stream_think_block_filtered_live_but_kept_in_content(monkeypatch):
    # NOTE: pinnt IST-Verhalten — der ThinkSafe-Streamer filtert nur die
    # LIVE-Emission; der aggregierte msg.content behält den <think>-Block roh
    # (der finale Strip passiert erst downstream in generate_response).
    _fake, out, resp = _run_stream(monkeypatch, [
        _chunk(content="vor"), _chunk(content="<think>"),
        _chunk(content="geheim"), _chunk(content="</think>"),
        _chunk(content="nach"), _chunk(finish="stop"),
    ])
    assert "".join(out) == "vornach"
    assert resp.choices[0].message.content == "vor<think>geheim</think>nach"


def test_stream_respond_to_user_streams_text_field(monkeypatch):
    _fake, out, resp = _run_stream(monkeypatch, [
        _chunk(tool_calls=[_tc_delta(0, id="tc1", name="respond_to_user",
                                     arguments='{"text": "Hal')]),
        _chunk(tool_calls=[_tc_delta(0, arguments='lo", "quick_replies": []}')]),
        _chunk(finish="tool_calls"),
    ])
    # Der text-Feld-Inhalt wird progressiv aus den JSON-Args extrahiert.
    assert "".join(out) == "Hallo"
    tcs = resp.choices[0].message.tool_calls
    assert len(tcs) == 1
    assert tcs[0].id == "tc1"
    assert tcs[0].function.name == "respond_to_user"
    assert json.loads(tcs[0].function.arguments) == {
        "text": "Hallo", "quick_replies": [],
    }
    assert resp.choices[0].message.content is None


def test_stream_args_before_name_are_replayed(monkeypatch):
    # Kommen Args-Chunks VOR dem Tool-Namen, werden sie beim Namens-Eintreffen
    # in den Extractor nachgespielt — kein Text geht verloren.
    _fake, out, resp = _run_stream(monkeypatch, [
        _chunk(tool_calls=[_tc_delta(0, id="tc1", arguments='{"text": "Hi"')]),
        _chunk(tool_calls=[_tc_delta(0, name="respond_to_user", arguments='}')]),
    ])
    assert "".join(out) == "Hi"
    assert resp.choices[0].message.tool_calls[0].function.arguments == '{"text": "Hi"}'


def test_stream_other_tools_accumulate_silently(monkeypatch):
    _fake, out, resp = _run_stream(monkeypatch, [
        _chunk(tool_calls=[_tc_delta(0, id="tc1", name="search_wlo_content",
                                     arguments='{"query": "mathe"}')]),
        _chunk(finish="tool_calls"),
    ])
    assert out == []  # kein user-sichtbarer Text
    tc = resp.choices[0].message.tool_calls[0]
    assert tc.function.name == "search_wlo_content"
    assert tc.function.arguments == '{"query": "mathe"}'


def test_stream_multiple_tool_calls_ordered_by_index(monkeypatch):
    # Deltas treffen für Index 1 VOR Index 0 ein → Rekonstruktion sortiert.
    _fake, _out, resp = _run_stream(monkeypatch, [
        _chunk(tool_calls=[_tc_delta(1, id="b", name="search_wlo_collections",
                                     arguments="{}")]),
        _chunk(tool_calls=[_tc_delta(0, id="a", name="search_wlo_content",
                                     arguments="{}")]),
    ])
    tcs = resp.choices[0].message.tool_calls
    assert [t.id for t in tcs] == ["a", "b"]
    assert [t.function.name for t in tcs] == [
        "search_wlo_content", "search_wlo_collections",
    ]


# ── _RespondToUserExtractor direkt (Kern-Parser des Streamings) ──────────

def test_extractor_translates_json_escapes():
    out: list[str] = []
    ex = lls._RespondToUserExtractor(out.append)
    ex.feed(json.dumps({"text": 'a\nb "q"'}))
    assert "".join(out) == 'a\nb "q"'


def test_extractor_null_text_gives_up_silently():
    out: list[str] = []
    ex = lls._RespondToUserExtractor(out.append)
    ex.feed('{"text": null}')
    assert out == []
    assert ex.buffer == '{"text": null}'  # Buffer sammelt trotzdem alles


def test_extractor_key_straddling_chunk_boundary():
    out: list[str] = []
    ex = lls._RespondToUserExtractor(out.append)
    ex.feed('{"te')          # "text"-Key über Chunk-Grenze gesplittet
    assert out == []
    ex.feed('xt": "ok"}')
    assert "".join(out) == "ok"


def test_extractor_on_token_exception_swallowed():
    def _boom(piece):
        raise ValueError("callback kaputt")

    ex = lls._RespondToUserExtractor(_boom)
    ex.feed('{"text": "abc"}')  # darf NICHT hochkommen
    assert ex.buffer == '{"text": "abc"}'


# ════════════════════════════════════════════════════════════════════════
# NEU transport pins — the declared deviation vs ALT
# ════════════════════════════════════════════════════════════════════════

def test_stream_wires_routing_timeout_retries(monkeypatch):
    # Mirror of test_llm.py::test_chat_completion_wires_routing_timeout_retries:
    # _stream_completion takes the SAME semantic kwargs and does the full
    # build_chat_kwargs + route wiring itself (no pre-built kwargs, no client).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    fake = _StreamFake([_chunk(content="ok", finish="stop")])
    monkeypatch.setattr(llm, "_acompletion", fake)

    out: list[str] = []
    asyncio.run(lls._stream_completion(
        out.append, messages=[{"role": "user", "content": "hi"}]))
    sent = fake.calls[0]
    assert sent["model"] == "openai/gpt-5.4-mini"
    assert sent["api_base"] == "https://api.openai.com/v1"
    assert sent["api_key"] == "sk-x"
    assert sent["num_retries"] == 2
    assert sent["timeout"] == 75.0
    assert sent["verbosity"] == "medium"  # GPT-5 gating flowed through
    assert "".join(out) == "ok"


def test_stream_holds_live_semaphore_for_whole_consumption(monkeypatch):
    # The bulkhead must span the stream CONSUMPTION, not just the connect —
    # otherwise N streams could run beyond LLM_MAX_CONCURRENCY. (Settings floor
    # LLM_MAX_CONCURRENCY at 2, so the base size is read from the semaphore.)
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    get_settings.cache_clear()
    llm.reset()
    during: list[int] = []

    async def fake(**kwargs):
        async def _gen():
            during.append(llm.semaphore()._value)  # base-1 == held
            yield _chunk(content="x")
            during.append(llm.semaphore()._value)
        return _gen()

    monkeypatch.setattr(llm, "_acompletion", fake)

    async def main():
        sem = llm.semaphore()
        base = sem._value
        resp = await lls._stream_completion(lambda s: None, model="m", messages=[])
        return base, sem._value, resp

    base, after, resp = asyncio.run(main())
    assert during == [base - 1, base - 1]  # held while every chunk is consumed
    assert after == base                   # released at stream end
    assert resp.choices[0].message.content == "x"


def test_stream_propagates_errors(monkeypatch):
    async def boom(**kwargs):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(llm, "_acompletion", boom)
    with pytest.raises(RuntimeError, match="upstream 503"):
        asyncio.run(lls._stream_completion(lambda s: None, model="m", messages=[]))
