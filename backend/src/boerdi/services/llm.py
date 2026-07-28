"""LLM chat transport over LiteLLM (P3-1, port of ALT llm_provider.py
transport path — see docs/plans/p3-llm-transport-contract.md).

Builds on services/llm_models.py (name resolution) and obs/usage.py (token
accounting). Two deliberate ALT-deviations, both documented in the contract:
- ALT had NO app-level semaphore (httpx pool max_connections was the
  bulkhead); LiteLLM has no pool bulkhead, so an explicit asyncio.Semaphore
  per event loop is the correct NEU equivalent (LLM_MAX_CONCURRENCY live /
  BG_LLM_MAX_CONCURRENCY background).
- ALT relied on the OpenAI SDK default max_retries=2; here num_retries=2.

``embedding`` (P6-1) is the RAG embedding sibling of ``chat_completion``: same
routing/timeout/retry/semaphore wiring, over LiteLLM's ``aembedding``.

The network boundaries are the module attributes ``_acompletion`` (chat) and
``_aembedding`` (embeddings) so tests can replace them without hitting the network.
"""

from __future__ import annotations

import asyncio
from typing import Any

import litellm

from boerdi.obs import usage as _usage
from boerdi.services.llm_models import (
    get_chat_model,
    get_embed_model,
    get_provider,
    get_reasoning_effort,
    get_verbosity,
    supports_gpt5_params,
)
from boerdi.settings import get_settings

# Let LiteLLM drop params the concrete target model doesn't accept — replaces
# ALT's per-SDK signature introspection (contract §"NEU-Vereinfachung").
litellm.drop_params = True

# Patchable network boundaries (tests replace these with fakes).
_acompletion = litellm.acompletion
_aembedding = litellm.aembedding

_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"

# Per-event-loop semaphores: (loop_id, "live"|"bg") -> Semaphore. A single
# module-level Semaphore would bind to the first loop and break under
# asyncio.run in tests; production has one loop so this is one entry.
_semaphores: dict[tuple[int, str], asyncio.Semaphore] = {}


def reset() -> None:
    """Drop cached semaphores (hot-reload / test isolation)."""
    _semaphores.clear()


def _semaphore(kind: str) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    key = (id(loop), kind)
    sem = _semaphores.get(key)
    if sem is None:
        s = get_settings()
        size = s.bg_llm_max_concurrency if kind == "bg" else s.llm_max_concurrency
        sem = asyncio.Semaphore(size)
        _semaphores[key] = sem
    return sem


def semaphore(*, background: bool = False) -> asyncio.Semaphore:
    """Public accessor for the per-loop concurrency bulkhead. Every LLM entry
    point (chat_completion here, the instructor classify path in
    services/classify.py) acquires this so they share one limit."""
    return _semaphore("bg" if background else "live")


def build_chat_kwargs(
    *,
    model: str | None = None,
    messages: list[dict[str, Any]],
    tools: list | None = None,
    tool_choice: Any = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: Any = None,
    verbosity: str | None = None,
    reasoning_effort: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Assemble the completion kwargs (bare model). GPT-5 gating is the
    load-bearing contract (ALT llm_provider.py:702-827):
    - verbosity: sent on GPT-5 (LiteLLM drops it if the model rejects it);
    - reasoning_effort: only on tool-LESS calls and only when != "none";
    - temperature: on GPT-5 only when effort == "none" AND model is gpt-5.4;
      on classic models passed through as given;
    - max_tokens: never on GPT-5; classic passes it through (simplify: no
      reasoning-buffer shaping — ALT _shape_max_tokens; LiteLLM caps per model).
    """
    resolved = model or get_chat_model()
    kwargs: dict[str, Any] = {"model": resolved, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    if tool_choice is not None:
        kwargs["tool_choice"] = tool_choice
    if response_format is not None:
        kwargs["response_format"] = response_format

    has_tools = bool(tools)
    if supports_gpt5_params(resolved):
        kwargs["verbosity"] = verbosity or get_verbosity()
        effort = reasoning_effort or get_reasoning_effort()
        if not has_tools and effort != "none":
            kwargs["reasoning_effort"] = effort
        if effort == "none" and resolved.lower().startswith("gpt-5.4") and temperature is not None:
            kwargs["temperature"] = temperature
    else:
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

    for k, v in extra.items():
        if v is not None:
            kwargs[k] = v
    return kwargs


def route(model: str) -> tuple[str, str, str, dict[str, str] | None]:
    """(litellm_model, api_base, api_key, extra_headers) for the current
    provider. All endpoints are OpenAI-compatible -> "openai/" prefix so a
    custom model name still routes correctly through a custom api_base."""
    s = get_settings()
    provider = get_provider()
    litellm_model = f"openai/{model}"
    if provider == "openai":
        api_base = s.openai_base_url or _DEFAULT_OPENAI_BASE
        return litellm_model, api_base, s.openai_api_key.get_secret_value(), None
    # b-api-openai / b-api-academiccloud: OpenAI-compatible proxy, dual auth
    suffix = "/academiccloud" if provider == "b-api-academiccloud" else "/openai"
    api_base = s.b_api_base_url.rstrip("/") + suffix
    b_key = s.b_api_key.get_secret_value().strip()
    api_key = b_key or "unused"  # SDK requires a truthy key
    extra_headers = {"X-API-KEY": b_key} if b_key else None
    return litellm_model, api_base, api_key, extra_headers


def wire_transport(resolved: str, kwargs: dict[str, Any]) -> None:
    """Stamp the transport params for ``resolved`` (bare model name) onto
    ``kwargs`` in place: routed litellm model, api_base/api_key, timeout,
    retries, optional X-API-KEY header. Shared by ``chat_completion`` and its
    streaming twin (services/llm_streaming.py)."""
    litellm_model, api_base, api_key, extra_headers = route(resolved)
    kwargs["model"] = litellm_model
    kwargs["api_base"] = api_base
    kwargs["api_key"] = api_key
    kwargs["timeout"] = get_settings().llm_read_timeout
    kwargs["num_retries"] = 2
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers


async def chat_completion(
    *,
    messages: list[dict[str, Any]],
    model: str | None = None,
    tools: list | None = None,
    tool_choice: Any = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: Any = None,
    background: bool = False,
    usage_acc: dict[str, Any] | None = None,
    phase: str | None = None,
    **extra: Any,
) -> Any:
    """One non-streaming chat completion. Wires provider routing, timeout and
    retries, runs under the live (or background) concurrency semaphore, and
    folds token usage into ``usage_acc`` when given. Errors propagate — the
    caller owns the error policy (tool loop / safety / QR wrap as needed)."""
    resolved = model or get_chat_model()
    kwargs = build_chat_kwargs(
        model=resolved, messages=messages, tools=tools, tool_choice=tool_choice,
        temperature=temperature, max_tokens=max_tokens, response_format=response_format,
        **extra,
    )
    wire_transport(resolved, kwargs)

    async with _semaphore("bg" if background else "live"):
        resp = await _acompletion(**kwargs)

    if usage_acc is not None:
        _usage.add_usage(usage_acc, _usage.extract_usage(resp), phase)
    return resp


async def embedding(text: str, *, model: str | None = None) -> list[float]:
    """One embedding vector for ``text`` — the RAG embedding boundary (P6-1),
    sibling of ``chat_completion``: same provider routing, timeout, retries and
    live concurrency semaphore. Errors propagate — the caller owns the policy.

    NEU-deviation vs ALT ``rag_service.get_embedding``: ALT hand-picked a native
    OpenAI side-channel client (``llm_provider.get_embedding_client``) so its
    1536-dim RAG DB kept working on academiccloud. LiteLLM routes providers
    itself, so the side-channel is gone — model and dimension come from Env
    (``LLM_EMBED_MODEL`` / ``EMBED_DIM`` via ``llm_models.get_embed_model`` /
    ``get_embed_dim``) and MUST match the pgvector column's dimension. The input
    truncation (``text[:8000]``) is ALT-verbatim.

    **Der Antwort-Zugriff ist es NICHT — und das war ein Fehler (behoben
    2026-07-27).** ALT las ``resp.data[0].embedding`` und lag richtig: sein
    nativer OpenAI-Client liefert Pydantic-Objekte. LiteLLM liefert an dieser
    Stelle **dicts**; live gemessen gegen openai/text-embedding-3-small ist
    ``type(resp.data[0]) is dict`` mit ``embedding``/``index``/``object``. Der
    wörtlich übernommene Attribut-Zugriff starb deshalb bei JEDEM echten Aufruf
    mit ``'dict' object has no attribute 'embedding'`` — und weil der
    respond-Node LLM-Fehler bewusst abfängt, wurde daraus keine 500, sondern
    still der Ersatztext: jede RAG-gestützte Antwort war entwertet, ohne dass
    etwas rot wurde. Die Attrappe im Test hatte den Attribut-Zugriff mit
    ``SimpleNamespace`` nachgebaut und sich dabei auf
    ``litellm.types.utils.Embedding`` berufen — ein **TypedDict**, also zur
    Laufzeit ein dict.

    Beide Formen werden bedient, weil der Typ nichts zusagt:
    ``EmbeddingResponse.data`` ist als blankes ``typing.List`` annotiert. Ein
    Anbieter oder eine Version, die Objekte liefert, darf hier nicht wieder
    einen stillen Totalausfall auslösen.
    """
    resolved = model or get_embed_model()
    litellm_model, api_base, api_key, extra_headers = route(resolved)
    kwargs: dict[str, Any] = {
        "model": litellm_model,
        "input": text[:8000],
        "api_base": api_base,
        "api_key": api_key,
        "timeout": get_settings().llm_read_timeout,
        "num_retries": 2,
    }
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers

    async with _semaphore("live"):
        resp = await _aembedding(**kwargs)
    item = resp.data[0]
    return item["embedding"] if isinstance(item, dict) else item.embedding
