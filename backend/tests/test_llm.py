"""P3-1 slice (b): LiteLLM transport wrapper (services/llm.py).

Port of the ALT transport contract (docs/plans/p3-llm-transport-contract.md):
- build_chat_kwargs GPT-5 gating (verbosity / reasoning_effort / temperature
  drop rules) — the load-bearing piece;
- provider routing (api_base + api_key + X-API-KEY header per provider);
- the chat_completion wrapper wires routed model + timeout + num_retries and
  folds usage into the accumulator.

The network boundary is the module attribute ``llm._acompletion`` — tests
replace it with a fake that records the kwargs, so nothing hits the network.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.services import llm
from boerdi.settings import get_settings

_ENV = ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "OPENAI_API_KEY",
        "OPENAI_BASE_URL", "B_API_KEY", "B_API_BASE_URL", "B_API_CLEAR_CACHE",
        "LLM_VERBOSITY",
        "LLM_REASONING_EFFORT", "LLM_EMBED_MODEL")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    llm.reset()
    return monkeypatch


# ── build_chat_kwargs: GPT-5 gating ────────────────────────────────────────
def test_gpt5_default_sends_verbosity_and_effort_no_tools() -> None:
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "hi"}])
    assert kw["model"] == "gpt-5.6-luna"
    assert kw["verbosity"] == "low"  # W12: Vorgabe auf Geschwindigkeit
    assert kw["reasoning_effort"] == "low"
    assert "max_tokens" not in kw and "temperature" not in kw


_TOOLS = [{"type": "function", "function": {"name": "f"}}]


def test_gpt54_group_still_drops_reasoning_effort_on_tool_calls(monkeypatch) -> None:
    """Die ALT-Regel bleibt fuer die Gruppe, fuer die sie gilt (llm_provider.py:702-827)."""
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-5.4-mini")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], tools=_TOOLS, tool_choice="required",
    )
    assert kw["verbosity"] == "low"
    assert "reasoning_effort" not in kw
    assert kw["tools"] and kw["tool_choice"] == "required"


def test_luna_group_MUST_send_reasoning_effort_on_tool_calls() -> None:
    """W12b — gemessen gegen die echte API, nicht abgeleitet.

    ``gpt-5.6-luna`` weist eine Anfrage mit Werkzeugen ab, wenn ``reasoning_effort``
    FEHLT: *„Function tools with reasoning_effort are not supported … in
    /v1/chat/completions."* Der Text liest sich wie „du hast zu viel geschickt",
    gemeint ist das Gegenteil — ohne Angabe gilt das Vorgabe-Reasoning des
    Anbieters, und DAS vertraegt sich nicht mit Function Tools. Mit einem
    ausdruecklichen Wert (``low`` wie ``none``) kommt sauber ein tool_call zurueck.
    """
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], tools=_TOOLS, tool_choice="required",
    )
    assert kw["model"] == "gpt-5.6-luna"
    assert kw["reasoning_effort"] == "low"
    assert kw["verbosity"] == "low"


def test_luna_sends_the_literal_none_instead_of_omitting_it(monkeypatch) -> None:
    """``none`` ist fuer uns bisher ein Merker fuer *weglassen* — fuer luna waere
    genau das der 400er. Bei dieser Gruppe ist ``none`` ein echter API-Wert."""
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], tools=_TOOLS)
    assert kw["reasoning_effort"] == "none"


def test_gpt5_temperature_only_when_effort_none_and_gpt54(monkeypatch) -> None:
    # W12: das Modell steht hier AUSDRUECKLICH, es ist der Gegenstand des Tests.
    # Die Temperatur-Ausnahme ist an die 5.4-Familie gepinnt (`startswith`), und
    # ein pauschales Umbenennen auf das neue Standardmodell hat sie gerade
    # deshalb zu Recht rot gemacht.
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-5.4-mini")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], temperature=0.5)
    assert kw["temperature"] == 0.5
    assert "reasoning_effort" not in kw  # effort none is not sent


def test_the_new_default_model_gets_no_temperature(monkeypatch) -> None:
    """W12: gpt-5.6-luna faellt NICHT unter die 5.4-Ausnahme — und das ist richtig.

    Ob das Modell `temperature` neben abgeschaltetem Reasoning annimmt, steht in
    der Modellkarte nicht. Die schmale Erlaubnis bleibt deshalb bei der Familie,
    fuer die sie belegt ist. Ein Wert, den der Anbieter zurueckweist, kostet
    einen 400er mitten im Zug.
    """
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], temperature=0.5)
    assert kw["model"] == "gpt-5.6-luna"
    assert "temperature" not in kw


def test_gpt5_temperature_dropped_when_effort_not_none() -> None:
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], temperature=0.7)
    assert "temperature" not in kw  # effort=low (default) drops temperature


def test_classic_branch_passes_temperature_and_max_tokens(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")  # mistral, non-gpt5
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], temperature=0.3, max_tokens=512)
    assert kw["model"] == "mistral-large-3-675b-instruct-2512"
    assert kw["temperature"] == 0.3 and kw["max_tokens"] == 512
    assert "verbosity" not in kw and "reasoning_effort" not in kw


def test_extra_forwarded_skipping_none() -> None:
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], seed=42, logit_bias=None)
    assert kw["seed"] == 42 and "logit_bias" not in kw


def test_response_format_passthrough() -> None:
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], response_format={"type": "json_object"})
    assert kw["response_format"] == {"type": "json_object"}


# ── b-api Antwort-Cache (Sommercamp-Entscheid 2026-08-21) ──────────────────
def test_wire_transport_academiccloud_sendet_clear_cache(monkeypatch) -> None:
    """Staging gemessen (21.08.): der /llm/-Pfad cached Antworten serverseitig
    (Temperatur 1, dreimal dieselbe „Zufallszahl", Treffer in ~0,2 s) — ein
    Generierungsfehler bliebe so über alle identischen Züge stehen. Mit
    ``clearCache: true`` generiert academiccloud jedes Mal frisch."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("m", kw)
    assert kw["extra_body"] == {"clearCache": True}


def test_wire_transport_b_api_openai_umgeht_cache_per_user_feld(monkeypatch) -> None:
    """Gemessen 21.08.: ``clearCache`` reicht der openai-Pfad ungefiltert an
    OpenAI durch (HTTP 400 „Unknown parameter") — der Cache-Schlüssel der
    b-api umfasst aber den Body samt ``user`` (offizielles OpenAI-Feld):
    identisches ``user`` → Treffer in 0,2 s, neues ``user`` → frische
    Generierung. Ein Zufallswert je Request schaltet den Cache also auch hier
    ab, ohne unbekanntes Feld."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    kw1, kw2 = {}, {}
    llm.wire_transport("m", kw1)
    llm.wire_transport("m", kw2)
    assert "clearCache" not in kw1["extra_body"]
    u1 = kw1["extra_body"]["user"]
    u2 = kw2["extra_body"]["user"]
    assert u1.startswith("boerdi-nc-") and u1 != u2  # je Request frisch


def test_wire_transport_openai_nativ_sendet_kein_clear_cache(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("m", kw)
    assert "extra_body" not in kw


def test_wire_transport_clear_cache_abschaltbar(monkeypatch) -> None:
    monkeypatch.setenv("B_API_KEY", "bkey")
    monkeypatch.setenv("B_API_CLEAR_CACHE", "false")
    for provider in ("b-api-academiccloud", "b-api-openai"):
        monkeypatch.setenv("LLM_PROVIDER", provider)
        get_settings.cache_clear()
        kw = {}
        llm.wire_transport("m", kw)
        assert "extra_body" not in kw, provider


# ── provider routing ───────────────────────────────────────────────────────
def test_route_openai_native(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-native")
    get_settings.cache_clear()
    model, api_base, api_key, headers = llm.route("gpt-5.6-luna")
    assert model == "openai/gpt-5.6-luna"  # LiteLLM OpenAI-compatible prefix
    assert api_base == "https://api.openai.com/v1"
    assert api_key == "sk-native"
    assert headers is None


def test_route_b_api_openai_dual_auth(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    model, api_base, api_key, headers = llm.route("gpt-5.6-luna")
    assert model == "openai/gpt-5.6-luna"
    assert api_base == "https://b-api.staging.openeduhub.net/api/v1/llm/openai"
    assert api_key == "bkey"  # Bearer
    assert headers == {"X-API-KEY": "bkey"}  # and X-API-KEY


def test_route_academiccloud_suffix(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    _model, api_base, _key, _headers = llm.route("mistral-large-3-675b-instruct-2512")
    assert api_base.endswith("/academiccloud")


def test_route_b_api_without_key_uses_unused_placeholder(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    _model, _base, api_key, headers = llm.route("gpt-5.6-luna")
    assert api_key == "unused"  # SDK requires a truthy key
    assert headers is None  # no X-API-KEY when no key


# ── chat_completion wrapper ────────────────────────────────────────────────
class _FakeCompletion:
    """Records the kwargs of the last call; returns a usage-bearing response."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="gpt-5.6-luna",
            usage=SimpleNamespace(
                prompt_tokens=120, completion_tokens=30,
                prompt_tokens_details=SimpleNamespace(cached_tokens=64)),
            choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))],
        )


def test_chat_completion_wires_routing_timeout_retries(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    fake = _FakeCompletion()
    monkeypatch.setattr(llm, "_acompletion", fake)

    resp = asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "hi"}]))
    assert resp.choices[0].message.content == "ok"
    sent = fake.calls[0]
    assert sent["model"] == "openai/gpt-5.6-luna"
    assert sent["api_base"] == "https://api.openai.com/v1"
    assert sent["api_key"] == "sk-x"
    assert sent["num_retries"] == 2
    assert sent["timeout"] == 75.0
    assert sent["verbosity"] == "low"  # gating flowed through


def test_chat_completion_folds_usage_into_accumulator(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_acompletion", _FakeCompletion())
    from boerdi.obs import usage

    acc = usage.new_accumulator()
    asyncio.run(llm.chat_completion(
        messages=[{"role": "user", "content": "hi"}], usage_acc=acc, phase="classify"))
    assert acc["prompt_tokens"] == 120 and acc["completion_tokens"] == 30
    assert acc["cached_tokens"] == 64 and acc["calls"] == 1
    assert acc["per_phase"]["classify"]["calls"] == 1


def test_chat_completion_b_api_sends_extra_headers(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    fake = _FakeCompletion()
    monkeypatch.setattr(llm, "_acompletion", fake)
    asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}]))
    assert fake.calls[0]["extra_headers"] == {"X-API-KEY": "bkey"}


def test_chat_completion_propagates_errors(monkeypatch) -> None:
    async def boom(**kwargs):
        raise RuntimeError("upstream 503")

    monkeypatch.setattr(llm, "_acompletion", boom)
    with pytest.raises(RuntimeError, match="upstream 503"):
        asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}]))


def test_semaphore_limits_concurrency(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    get_settings.cache_clear()
    llm.reset()
    peak = 0
    active = 0

    async def slow(**kwargs):
        nonlocal peak, active
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return SimpleNamespace(model="m", usage=None, choices=[])

    monkeypatch.setattr(llm, "_acompletion", slow)

    async def fire_ten():
        await asyncio.gather(*[
            llm.chat_completion(messages=[{"role": "user", "content": "x"}]) for _ in range(10)
        ])

    asyncio.run(fire_ten())
    assert peak <= 2  # the live semaphore capped concurrency


# ── embedding wrapper (P6-1 embedding boundary) ───────────────────────────
class _FakeEmbedding:
    """Records the kwargs of the last call; returns a LiteLLM-shaped
    EmbeddingResponse.

    ``data`` holds **dicts**, gemessen am 2026-07-27 gegen die echte API
    (openai/text-embedding-3-small): ``type(resp.data[0]) is dict`` mit den
    Schlüsseln ``embedding``/``index``/``object``. Die frühere Attrappe gab
    hier ``SimpleNamespace`` zurück und berief sich auf
    ``litellm.types.utils.Embedding`` — das ist ein **TypedDict**, also zur
    Laufzeit ein dict; aus der Feldliste wurde fälschlich ein Objekt gelesen.
    Deshalb war die Suite grün, während jeder echte Aufruf mit
    ``'dict' object has no attribute 'embedding'`` starb. ``EmbeddingResponse``
    annotiert ``data`` als blankes ``typing.List`` — der Typ sagt hier nichts
    zu, nur die Messung.
    """

    def __init__(self, vector: list[float] | None = None) -> None:
        self.calls: list[dict] = []
        self.vector = [0.1, 0.2, 0.3] if vector is None else vector

    async def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            model="text-embedding-3-small",
            data=[{"embedding": self.vector, "index": 0, "object": "embedding"}],
        )


def test_embedding_returns_vector_and_wires_routing(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    fake = _FakeEmbedding([0.5, 0.6])
    monkeypatch.setattr(llm, "_aembedding", fake)

    vec = asyncio.run(llm.embedding("hallo welt"))
    assert vec == [0.5, 0.6]
    sent = fake.calls[0]
    assert sent["model"] == "openai/text-embedding-3-small"  # embed model, not chat
    assert sent["api_base"] == "https://api.openai.com/v1"
    assert sent["api_key"] == "sk-x"
    assert sent["num_retries"] == 2
    assert sent["timeout"] == 75.0
    assert sent["input"] == "hallo welt"


def test_embedding_reads_the_dict_shape_litellm_actually_returns(monkeypatch) -> None:
    """Der Regressionstest zum Live-Fund vom 2026-07-27.

    Vorher las die Produktion ``data[0].embedding`` (ALT-verbatim, dort korrekt,
    weil ALT einen nativen OpenAI-Client hatte). LiteLLM liefert ein dict ⇒
    ``AttributeError`` bei jedem echten Aufruf. Ohne diesen Test bleibt der
    Zugriff eine Vermutung: die alte Attrappe hat die falsche Form nachgebaut
    und war deshalb dauerhaft grün.
    """
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()
    fake = _FakeEmbedding([0.7, 0.8])
    monkeypatch.setattr(llm, "_aembedding", fake)

    assert asyncio.run(llm.embedding("x")) == [0.7, 0.8]


def test_embedding_also_reads_an_object_shaped_item(monkeypatch) -> None:
    """``EmbeddingResponse.data`` ist blankes ``typing.List`` — der Typ sagt
    nichts zu. Ein Anbieter, der Objekte liefert, darf nicht wieder still jede
    RAG-Antwort entwerten, deshalb wird auch diese Form gelesen (und geprüft:
    sonst wäre der Zweig ungetesteter Vorratscode)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    get_settings.cache_clear()

    async def fake(**_kwargs):
        return SimpleNamespace(data=[SimpleNamespace(embedding=[1.5, 2.5], index=0)])

    monkeypatch.setattr(llm, "_aembedding", fake)
    assert asyncio.run(llm.embedding("x")) == [1.5, 2.5]


def test_embedding_truncates_input_at_8000_chars(monkeypatch) -> None:
    fake = _FakeEmbedding()
    monkeypatch.setattr(llm, "_aembedding", fake)
    asyncio.run(llm.embedding("x" * 9000))
    assert len(fake.calls[0]["input"]) == 8000  # ALT parity: input=text[:8000]


def test_embedding_honours_llm_embed_model_env(monkeypatch) -> None:
    monkeypatch.setenv("LLM_EMBED_MODEL", "bge-m3")
    get_settings.cache_clear()
    fake = _FakeEmbedding()
    monkeypatch.setattr(llm, "_aembedding", fake)
    asyncio.run(llm.embedding("x"))
    assert fake.calls[0]["model"] == "openai/bge-m3"


def test_embedding_explicit_model_wins(monkeypatch) -> None:
    fake = _FakeEmbedding()
    monkeypatch.setattr(llm, "_aembedding", fake)
    asyncio.run(llm.embedding("x", model="text-embedding-3-large"))
    assert fake.calls[0]["model"] == "openai/text-embedding-3-large"


def test_embedding_b_api_routes_and_sends_extra_headers(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    fake = _FakeEmbedding()
    monkeypatch.setattr(llm, "_aembedding", fake)
    asyncio.run(llm.embedding("x"))
    sent = fake.calls[0]
    assert sent["extra_headers"] == {"X-API-KEY": "bkey"}
    assert sent["model"] == "openai/e5-mistral-7b-instruct"  # academiccloud embed default
    assert sent["api_base"].endswith("/academiccloud")


def test_embedding_propagates_errors(monkeypatch) -> None:
    async def boom(**kwargs):
        raise RuntimeError("embed 503")

    monkeypatch.setattr(llm, "_aembedding", boom)
    with pytest.raises(RuntimeError, match="embed 503"):
        asyncio.run(llm.embedding("x"))


def test_embedding_runs_under_the_live_semaphore(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MAX_CONCURRENCY", "2")
    get_settings.cache_clear()
    llm.reset()
    peak = 0
    active = 0

    async def slow(**kwargs):
        nonlocal peak, active
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return SimpleNamespace(model="m", data=[SimpleNamespace(embedding=[0.1], index=0)])

    monkeypatch.setattr(llm, "_aembedding", slow)

    async def fire_ten():
        await asyncio.gather(*[llm.embedding("x") for _ in range(10)])

    asyncio.run(fire_ten())
    assert peak <= 2  # shares the same bulkhead as chat_completion


def test_semaphore_public_wrapper_returns_same_per_loop() -> None:
    async def go():
        a = llm.semaphore()
        b = llm.semaphore()
        assert a is b and isinstance(a, asyncio.Semaphore)
        bg = llm.semaphore(background=True)
        assert bg is not a  # distinct live/bg bulkheads

    asyncio.run(go())


def test_wire_transport_merged_vorhandenes_extra_body(monkeypatch) -> None:
    """Review-NIT: die Zuweisung überschrieb ein vom Aufrufer gesetztes
    ``extra_body`` still — heute liefert es niemand zu, der Merge kostet
    nichts und verhindert den künftigen stillen Verlust."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    kw = {"extra_body": {"x": 1}}
    llm.wire_transport("m", kw)
    assert kw["extra_body"] == {"x": 1, "clearCache": True}
