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

def test_stream_content_wird_rekonstruiert_aber_nicht_gesendet(monkeypatch):
    # Plan Token-Streaming, E-S1: freier Inhaltstext geht nicht an ``on_token`` —
    # eine Vorrede vor Werkzeugaufrufen blitzte sonst auf und verschwände wieder.
    # Gestreamt wird nur das ``text``-Feld von ``respond_to_user``.
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
    # Nichts live gesendet, die Message trotzdem vollständig rekonstruiert.
    assert out == []
    msg = resp.choices[0].message
    assert msg.content == "Hallo"
    assert msg.role == "assistant"
    assert msg.tool_calls is None
    assert resp.choices[0].finish_reason == "stop"
    assert resp.usage is u
    assert resp.model == "gpt-x"


def test_antwort_text_laeuft_durch_den_denkfilter(monkeypatch):
    # Plan Token-Streaming, T2: der Extraktor bekam das rohe ``on_token`` und
    # umging den Denkmarken-Filter. Die Argumente behalten den Block roh — den
    # fertigen Text räumt ``antwort_aus_argumenten`` ab.
    _fake, out, resp = _run_stream(monkeypatch, [
        _chunk(tool_calls=[_tc_delta(0, id="tc1", name="respond_to_user",
                                     arguments='{"text": "vor<think>')]),
        _chunk(tool_calls=[_tc_delta(0, arguments='geheim</think>nach", "quick_replies": []}')]),
        _chunk(finish="tool_calls"),
    ])
    assert "".join(out) == "vornach"
    assert "geheim" in resp.choices[0].message.tool_calls[0].function.arguments


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



def _als_escape(text: str) -> str:
    """So schreibt ein Modell, das jedes Nicht-ASCII-Zeichen escapt."""
    return json.dumps({"text": text}, ensure_ascii=True)


@pytest.mark.parametrize("text", [
    "Grüße", chr(0x1F600) + "!", 'a"b/c', chr(0xD83D) + "x",
])
def test_extraktor_dekodiert_escapes_an_jeder_chunk_grenze(text):
    """Audit 2026-09-29: Unicode-Escapes kamen ohne Dekodierung beim Client an
    (Plan Token-Streaming, T1). Geprüft wird jede Schnittstelle zwischen zwei
    Chunks, also auch mitten im Escape und mitten im Surrogatpaar. Ein einsames
    hohes Surrogat wird sichtbar ersetzt statt geraten."""
    roh = _als_escape(text)
    erwartet = text.replace(chr(0xD83D), chr(0xFFFD))
    for schnitt in range(1, len(roh)):
        out: list[str] = []
        ex = lls._RespondToUserExtractor(out.append)
        ex.feed(roh[:schnitt])
        ex.feed(roh[schnitt:])
        assert "".join(out) == erwartet, f"Schnitt bei {schnitt}: {roh[:schnitt]!r}"

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
    resp = asyncio.run(lls._stream_completion(
        out.append, messages=[{"role": "user", "content": "hi"}]))
    sent = fake.calls[0]
    assert sent["model"] == "openai/gpt-5.6-luna"
    assert sent["api_base"] == "https://api.openai.com/v1"
    assert sent["api_key"] == "sk-x"
    # Paket 4 B3: eine Wiederholungsschicht (SDK-Vorgabe), kein ``num_retries``.
    assert "num_retries" not in sent
    assert sent["timeout"] == 75.0
    assert sent["verbosity"] == "low"  # GPT-5 gating flowed through
    # Der Strom lief durch; freier Inhaltstext geht nicht an ``on_token`` (E-S1).
    assert resp.choices[0].message.content == "ok"
    assert out == []


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
