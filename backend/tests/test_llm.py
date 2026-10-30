"""P3-1 slice (b): LiteLLM transport wrapper (services/llm.py).

Port of the ALT transport contract (docs/plans/p3-llm-transport-contract.md):
- build_chat_kwargs GPT-5 gating (verbosity / reasoning_effort / temperature
  drop rules) — the load-bearing piece;
- provider routing (api_base + api_key per provider; one Bearer header, Paket 17);
- the chat_completion wrapper wires routed model + timeout (no num_retries) and
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
    assert kw["model"] == "gpt-6-luna"  # Paket 8: die Vorgabe
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


def test_luna_group_MUST_send_reasoning_effort_on_tool_calls(monkeypatch) -> None:
    """W12b — gemessen gegen die echte API, nicht abgeleitet.

    ``gpt-5.6-luna`` weist eine Anfrage mit Werkzeugen ab, wenn ``reasoning_effort``
    FEHLT: *„Function tools with reasoning_effort are not supported … in
    /v1/chat/completions."* Der Text liest sich wie „du hast zu viel geschickt",
    gemeint ist das Gegenteil — ohne Angabe gilt das Vorgabe-Reasoning des
    Anbieters, und DAS vertraegt sich nicht mit Function Tools. Mit einem
    ausdruecklichen Wert (``low`` wie ``none``) kommt sauber ein tool_call zurueck.

    Seit Paket 8 ist gpt-6-luna die Vorgabe; das Modell steht hier deshalb
    ausdrücklich, damit der Test weiter die 5.6-Gruppe prüft.
    """
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-5.6-luna")
    get_settings.cache_clear()
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
    """W12: das Standardmodell (seit Paket 8 gpt-6-luna, vorher gpt-5.6-luna) faellt
    NICHT unter die 5.4-Ausnahme — und das ist richtig.

    Ob das Modell `temperature` neben abgeschaltetem Reasoning annimmt, steht in
    der Modellkarte nicht. Die schmale Erlaubnis bleibt deshalb bei der Familie,
    fuer die sie belegt ist. Ein Wert, den der Anbieter zurueckweist, kostet
    einen 400er mitten im Zug.
    """
    monkeypatch.setenv("LLM_REASONING_EFFORT", "none")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], temperature=0.5)
    assert kw["model"] == "gpt-6-luna"
    assert "temperature" not in kw


def test_gpt6_bekommt_den_gpt5_vertrag_samt_effort_bei_werkzeugen(monkeypatch) -> None:
    """Gemessen 2026-09-26 gegen OpenAI direkt: gpt-6-luna weist ``max_tokens``
    und ``temperature`` != 1 ab wie gpt-5.6-luna, und Werkzeuge ohne
    ``reasoning_effort`` ebenso. Ohne eigene Regelgruppe fiel es auf die
    klassischen Regeln — jeder Werkzeug-Zug ein 400er."""
    monkeypatch.setenv("LLM_CHAT_MODEL", "gpt-6-luna")
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], tools=_TOOLS,
        temperature=0.4, max_tokens=512)
    assert kw["model"] == "gpt-6-luna"
    assert (kw["reasoning_effort"], kw["verbosity"]) == ("low", "low")
    assert "temperature" not in kw and "max_tokens" not in kw


def test_gpt5_temperature_dropped_when_effort_not_none() -> None:
    kw = llm.build_chat_kwargs(messages=[{"role": "user", "content": "x"}], temperature=0.7)
    assert "temperature" not in kw  # effort=low (default) drops temperature


def test_classic_branch_passes_temperature_and_max_tokens(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")  # qwen, non-gpt5
    get_settings.cache_clear()
    kw = llm.build_chat_kwargs(
        messages=[{"role": "user", "content": "x"}], temperature=0.3, max_tokens=512)
    assert kw["model"] == "qwen3-30b-a3b-instruct-2507"
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


# ── OpenAI-Fast-Modus (Nutzer 2026-10-01) ──────────────────────────────────
def test_wire_transport_setzt_den_tarif_nur_bei_openai(monkeypatch) -> None:
    """Gemessen 2026-10-01 direkt bei OpenAI: gpt-6-luna nimmt
    ``service_tier: "fast"`` an (die Antwort meldet ``fast``), eine Antwort mit
    ~250 Token kam im Median in 3,1 statt 4,3 s — zum 4- bis 5-fachen Preis.
    Über die b-api ist das ungemessen; ihre Pfade bleiben unberührt."""
    monkeypatch.setenv("LLM_SERVICE_TIER", "fast")
    monkeypatch.setenv("B_API_KEY", "bkey")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("gpt-6-luna", kw)
    assert kw["service_tier"] == "fast"
    # Paket 7, L1: nur die gpt-5-/gpt-6-Familie — Judge-Modelle nicht.
    kw = {}
    llm.wire_transport("gpt-4o-mini", kw)
    assert "service_tier" not in kw
    for provider in ("b-api-openai", "b-api-academiccloud"):
        monkeypatch.setenv("LLM_PROVIDER", provider)
        get_settings.cache_clear()
        kw = {}
        llm.wire_transport("gpt-6-luna", kw)
        assert "service_tier" not in kw, provider


def test_wire_transport_ohne_tarif_sendet_keinen(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("m", kw)
    assert "service_tier" not in kw


def test_der_studio_schalter_fast_modus_setzt_den_tarif(monkeypatch) -> None:
    """Paket 7 (S1): ohne ``LLM_SERVICE_TIER`` entscheidet das Studio
    (``01-base/engine`` → ``betrieb.fast_modus``) — weiter nur OpenAI direkt."""
    from boerdi.domain.config_models.engine import EngineArea
    from boerdi.services import betriebsschalter

    monkeypatch.delenv("LLM_SERVICE_TIER", raising=False)
    monkeypatch.setattr(betriebsschalter, "load_engine",
                        lambda: EngineArea.model_validate({"betrieb": {"fast_modus": True}}))
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("gpt-6-luna", kw)
    assert kw["service_tier"] == "fast"
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    kw = {}
    llm.wire_transport("gpt-6-luna", kw)
    assert "service_tier" not in kw


def test_ein_unbekannter_tarif_faellt_auf_den_standard_zurueck(monkeypatch) -> None:
    # Wie Verbosity/Reasoning: ein Tippfehler darf nicht jeden Aufruf mit 400
    # scheitern lassen — er fällt auf den Standard (nichts senden) zurück.
    monkeypatch.setenv("LLM_SERVICE_TIER", "schnell")
    get_settings.cache_clear()
    assert get_settings().llm_service_tier == ""


# ── provider routing ───────────────────────────────────────────────────────
def test_route_openai_native(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-native")
    get_settings.cache_clear()
    model, api_base, api_key, headers = llm.route("gpt-4.1-mini")
    assert model == "openai/gpt-4.1-mini"  # LiteLLM OpenAI-compatible prefix
    # Paket 7, L2: gpt-5.6 geht bei OpenAI direkt wie gpt-6 ausdrücklich über
    # Responses — nur dort kommen Denktiefe und Ausführlichkeit verlässlich an.
    assert llm.route("gpt-5.6-luna")[0] == "openai/responses/gpt-5.6-luna"
    assert api_base == "https://api.openai.com/v1"
    assert api_key == "sk-native"
    assert headers is None


def test_route_openai_nativ_fuehrt_gpt6_ueber_den_responses_weg(monkeypatch) -> None:
    """``/v1/chat/completions`` nimmt bei gpt-6-luna Werkzeuge nur mit
    ``reasoning_effort=none`` an und verweist selbst auf ``/v1/responses`` (400,
    gemessen 2026-09-26). ``openai/responses/<modell>`` ist LiteLLMs Brücke
    dorthin; die Antwort kommt in der gewohnten Chat-Form zurück."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-native")
    get_settings.cache_clear()
    model, api_base, _key, headers = llm.route("gpt-6-luna")
    assert model == "openai/responses/gpt-6-luna"
    assert api_base == "https://api.openai.com/v1"
    assert headers is None


def test_route_b_api_openai_fuehrt_gpt6_ueber_den_responses_weg(monkeypatch) -> None:
    """Paket 9 (Review, CRITICAL): Hinter der b-api steht dasselbe OpenAI. Auf
    ``/openai/chat/completions`` weist gpt-6-luna Werkzeuge ab („use /v1/responses
    or set reasoning_effort to 'none'“, Probe 2026-10-09), ``/openai/responses``
    antwortet 200 (Paket 7, §1). Ohne den Responses-Weg scheiterte mit der
    Vorgabe aus Paket 8 jeder Werkzeugaufruf."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    get_settings.cache_clear()
    assert llm.route("gpt-6-luna")[0] == "openai/responses/gpt-6-luna"
    assert llm.route("gpt-5.6-luna")[0] == "openai/responses/gpt-5.6-luna"
    assert llm.route("gpt-4.1-mini")[0] == "openai/gpt-4.1-mini"


def test_route_academiccloud_bleibt_auf_chat_completions(monkeypatch) -> None:
    """Die AcademicCloud bleibt auf ``/chat/completions`` (Nutzer-Vorgabe
    2026-09-26); dort gelten ohnehin die klassischen Regeln (``param_rules``)."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    assert llm.route("gpt-6-luna")[0] == "openai/gpt-6-luna"


def test_route_b_api_openai_genau_ein_kopf(monkeypatch) -> None:
    """Paket 17 (B3): nur ``Authorization: Bearer`` (aus ``api_key``) — die b-api
    weist einen Schlüssel ab, wenn daneben ein ungültiger ``X-API-KEY`` steht."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    model, api_base, api_key, headers = llm.route("gpt-5.6-luna")
    assert model == "openai/responses/gpt-5.6-luna"
    assert api_base == "https://b-api.staging.openeduhub.net/api/v1/llm/openai"
    assert api_key == "bkey"  # Bearer
    assert headers is None  # kein X-API-KEY daneben


def test_route_academiccloud_suffix(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    _model, api_base, _key, _headers = llm.route("qwen3-30b-a3b-instruct-2507")
    assert api_base.endswith("/academiccloud")


def test_auf_der_academiccloud_bettet_der_openai_pfad_ein(monkeypatch) -> None:
    """Paket 8 (M1): die AcademicCloud führt kein Einbettungsmodell (Probe
    2026-10-09), und die Wissensbasis liegt im Raum von text-embedding-3-small.
    Ein Einbettungsmodell von OpenAI geht deshalb auf den OpenAI-Pfad der b-api —
    derselbe Schlüssel, gemessen 200 mit 1 536 Dimensionen."""
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    model, api_base, api_key, headers = llm.route("text-embedding-3-small")
    assert model == "openai/text-embedding-3-small"
    assert api_base == "https://b-api.staging.openeduhub.net/api/v1/llm/openai"
    assert (api_key, headers) == ("bkey", None)


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
    assert sent["model"] == "openai/responses/gpt-6-luna"
    assert sent["api_base"] == "https://api.openai.com/v1"
    assert sent["api_key"] == "sk-x"
    # Paket 4 B3: eine Wiederholungsschicht (SDK-Vorgabe), kein ``num_retries``.
    assert "num_retries" not in sent
    assert sent["timeout"] == 75.0
    # gating flowed through — seit Paket 7 (L2) als ``text.verbosity``
    assert sent["extra_body"]["text"] == {"verbosity": "low"}


def test_chat_completion_folds_usage_into_accumulator(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_acompletion", _FakeCompletion())
    from boerdi.obs import usage

    acc = usage.new_accumulator()
    asyncio.run(llm.chat_completion(
        messages=[{"role": "user", "content": "hi"}], usage_acc=acc, phase="classify"))
    assert acc["prompt_tokens"] == 120 and acc["completion_tokens"] == 30
    assert acc["cached_tokens"] == 64 and acc["calls"] == 1
    assert acc["per_phase"]["classify"]["calls"] == 1
    # Plan 2026-09-30 (T7): die Wanduhr-Dauer des Aufrufs, einschliesslich
    # Warteschlange, landet bei der Phase.
    assert isinstance(acc["per_phase"]["classify"]["ms"], int)
    assert acc["per_phase"]["classify"]["ms"] >= 0


def test_chat_completion_b_api_sendet_keinen_zweiten_kopf(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-openai")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    fake = _FakeCompletion()
    monkeypatch.setattr(llm, "_acompletion", fake)
    asyncio.run(llm.chat_completion(messages=[{"role": "user", "content": "x"}]))
    assert fake.calls[0]["api_key"] == "bkey"
    assert "extra_headers" not in fake.calls[0]


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
    # Paket 4 B3: eine Wiederholungsschicht (SDK-Vorgabe), kein ``num_retries``.
    assert "num_retries" not in sent
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


def test_embedding_b_api_routet_mit_einem_kopf(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    monkeypatch.setenv("B_API_KEY", "bkey")
    get_settings.cache_clear()
    fake = _FakeEmbedding()
    monkeypatch.setattr(llm, "_aembedding", fake)
    asyncio.run(llm.embedding("x"))
    sent = fake.calls[0]
    assert sent["api_key"] == "bkey"
    assert "extra_headers" not in sent  # Paket 17: genau ein Kopf
    # Paket 8 (L8): die AcademicCloud führt kein Einbettungsmodell.
    assert sent["model"] == "openai/text-embedding-3-small"
    assert sent["api_base"].endswith("/openai")


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
    """Paket 18F: ``semaphore()`` ist ein Platz über ``platz`` (Frist, Schlüssel-Meldung) — er
    nimmt den EINEN Anbieter-Deckel der Schleife; Hintergrund hat seinen eigenen."""
    async def go():
        live = llm._semaphore("live")
        assert live is llm._semaphore("live") and isinstance(live, asyncio.Semaphore)
        basis = live._value
        async with llm.semaphore():
            assert live._value == basis - 1
        async with llm.semaphore(background=True):
            assert llm._semaphore("bg") is not live  # distinct live/bg bulkheads
            assert llm._semaphore("bg")._value == get_settings().bg_llm_max_concurrency - 1
        assert live._value == basis

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
