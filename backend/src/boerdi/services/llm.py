"""LLM chat transport over LiteLLM (P3-1, port of ALT llm_provider.py
transport path — see docs/plans/p3-llm-transport-contract.md).

Builds on services/llm_models.py (name resolution) and obs/usage.py (token
accounting). Two deliberate ALT-deviations, both documented in the contract:
- ALT had NO app-level semaphore (httpx pool max_connections was the
  bulkhead); LiteLLM has no pool bulkhead, so an explicit asyncio.Semaphore
  per event loop is the correct NEU equivalent — per provider since Paket 7
  (``services/llm_parallel.py``).
- Retries: like ALT, the OpenAI SDK default ``max_retries=2`` — and NO
  ``num_retries``. Until Paket 4 (B3) this said ``num_retries=2``; LiteLLM
  1.91.5 turned that into two retry layers (SDK plus ``acompletion_with_retries``):
  5 attempts on chat completions, 6 on the Responses bridge (measured
  2026-10-03, ``tests/test_llm_wiederholungen.py``). Without it: 3 on chat,
  2 (connect) / 1 (read timeout) on the Responses bridge.

``embedding`` (P6-1) is the RAG embedding sibling of ``chat_completion``: same
routing/timeout/retry/semaphore wiring, over LiteLLM's ``aembedding``.

The network boundaries are the module attributes ``_acompletion`` (chat) and
``_aembedding`` (embeddings) so tests can replace them without hitting the network.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import uuid4

import litellm

from boerdi.obs import usage as _usage
from boerdi.obs.zeiten import seit_ms
from boerdi.services.betriebsschalter import service_tier
from boerdi.services.llm_choices import vereinige_choices
from boerdi.services.llm_models import (
    get_chat_model,
    get_embed_model,
    get_provider,
    get_reasoning_effort,
    get_verbosity,
    param_rules,
)
from boerdi.services.llm_nachrichten import nachrichten_fuer

# Re-Export: Aufrufer und Tests sprechen ``llm.semaphore()`` / ``llm.reset()``
# an; die Grenzen je Anbieter stehen seit Paket 7 (L3) in ``llm_parallel``.
from boerdi.services.llm_parallel import (  # noqa: F401
    _semaphore,
    ingest_semaphore,
    platz,
    reset,
    semaphore,
)
from boerdi.services.llm_responses import RESPONSES_PRAEFIX, denkparameter_verlegen

# Re-Export (Paket 17): Aufrufer sprechen ``llm.router_route`` / ``llm.antwort_modell`` an.
from boerdi.services.llm_router import antwort_modell, router_route  # noqa: F401
from boerdi.settings import get_settings

# Let LiteLLM drop params the concrete target model doesn't accept — replaces
# ALT's per-SDK signature introspection (contract §"NEU-Vereinfachung").
litellm.drop_params = True

# Patchable network boundaries (tests replace these with fakes).
_acompletion = litellm.acompletion
_aembedding = litellm.aembedding

#: So oft wird ein **Aussetzer des Anbieters** wiederholt: eine Antwort ohne
#: Werkzeugaufruf UND ohne Inhalt. Beide Antwort-Schleifen lesen die Zahl von
#: hier — ``services/agent_loop`` (Agent) und ``services/tool_loop``
#: (Muster). Sie wohnt am Transport, weil sie das Verhalten des ANBIETERS
#: beschreibt und nicht das einer Schleife; zwei Kopien liefen auseinander.
#:
#: **Warum 2 und nicht 1.** Live gemessen am 21.08.2026 über 20 Agent-Züge
#: derselben Volltext-Frage: 7 Aussetzer, gut ein Drittel, und sie treten
#: unabhängig voneinander auf (dieselbe Eingabe, mal leer, mal vollständig).
#: Ein einziger zweiter Anlauf ließe rechnerisch ~12 % stumme Züge übrig — für
#: die Person weiterhin „antwortet manchmal nicht". Mit zwei sind es ~4 %.
#: Bezahlt wird das NUR im Ausfall; ein gelungener Zug ruft unverändert einmal.
LEERLAUF_VERSUCHE = 2

_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"

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
    load-bearing contract (ALT llm_provider.py:702-827). WELCHE Ausnahmen ein
    Modell braucht, steht seit W12b in ``llm_models._GROUPS``; hier wird nur noch
    ausgewertet:
    - verbosity: sent on GPT-5 (LiteLLM drops it if the model rejects it);
    - reasoning_effort: ``effort_with_tools`` sendet ihn IMMER woertlich (auch
      ``"none"``); sonst die ALT-Regel — nur bei tool-LOSEN Aufrufen und nur
      wenn != ``"none"``;
    - temperature: on GPT-5 only when effort == "none" AND the group allows it;
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
    rules = param_rules(resolved)
    if rules.gpt5_params:
        kwargs["verbosity"] = verbosity or get_verbosity()
        effort = reasoning_effort or get_reasoning_effort()
        if rules.effort_with_tools or (not has_tools and effort != "none"):
            kwargs["reasoning_effort"] = effort
        if effort == "none" and rules.temperature_on_none and temperature is not None:
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
    custom model name still routes correctly through a custom api_base.
    Models flagged ``responses_api`` go to OpenAI's /v1/responses via LiteLLM's
    ``responses/`` bridge — OpenAI direct and behind the b-api; the AcademicCloud
    gets the classic rules and stays on chat/completions (why: ``llm_models._GROUPS``)."""
    s = get_settings()
    provider = get_provider()
    # Paket 17 (A2): eine Route ersetzt nur den Namen des eingestellten Chat-Modells
    # (``llm_router``); die Regeln bleiben die des Modells.
    route_name = router_route(model)
    wire_name = route_name or model
    litellm_model = f"openai/{wire_name}"
    if param_rules(model).responses_api:
        litellm_model = f"{RESPONSES_PRAEFIX}{wire_name}"
    if provider == "openai":
        api_base = s.openai_base_url or _DEFAULT_OPENAI_BASE
        return litellm_model, api_base, s.openai_api_key.get_secret_value(), None
    # b-api-openai / b-api-academiccloud: OpenAI-compatible proxy, dual auth. Paket 8 (L8):
    # OpenAI embeddings take the OpenAI path even on the AcademicCloud — it has no embedding
    # model, and the knowledge base lives in the text-embedding-3-small space (ALT: side channel).
    academiccloud = provider == "b-api-academiccloud" and not model.startswith("text-embedding-")
    suffix = "/router" if route_name else "/academiccloud" if academiccloud else "/openai"
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
    s = get_settings()
    kwargs["model"] = litellm_model
    kwargs["api_base"] = api_base
    kwargs["api_key"] = api_key
    kwargs["timeout"] = s.llm_read_timeout
    # Keine ``num_retries``: siehe Modulkopf (Paket 4, B3).
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers
    # b-api-Antwort-Cache umgehen (Sommercamp-Entscheid 2026-08-21, GENERELL —
    # beide b-api-Pfade; Messwerte am Setting ``b_api_clear_cache``). Nur der
    # Transport aendert sich — Prompt-Aufbau und Embeddings bleiben unberuehrt.
    if s.b_api_clear_cache:
        provider = get_provider()
        if provider == "b-api-academiccloud":
            # Semantisches Feld, vom Gateway konsumiert (gemessen: jede
            # Antwort frisch generiert).
            kwargs.setdefault("extra_body", {})["clearCache"] = True
        elif provider == "b-api-openai":
            # ``clearCache`` wuerde hier an OpenAI durchgereicht (HTTP 400,
            # gemessen). Der Cache-Schluessel der b-api umfasst aber den Body
            # samt ``user`` (offizielles OpenAI-Feld): identisches ``user`` →
            # Treffer in 0,2 s, neues ``user`` → frische Generierung
            # (gemessen 21.08.). Ein Zufallswert je Request schaltet den
            # Cache also auch hier ab.
            kwargs.setdefault("extra_body", {})["user"] = f"boerdi-nc-{uuid4().hex}"
    # Paket 7, L2: Denktiefe und Ausführlichkeit kommen sonst nicht an (gpt-6).
    rules = param_rules(resolved)
    denkparameter_verlegen(kwargs, gpt5_familie=rules.gpt5_familie)
    # Tarif (Umgebung oder Studio-Fast-Modus, Paket 7 S1): nur OpenAI direkt, gpt-5/6 (L1).
    if get_provider() == "openai" and rules.gpt5_familie and (tarif := service_tier()):
        kwargs["service_tier"] = tarif
    # Die Form der Folge je Anbieter (Responses-Plan E-A1, E-AC): ``llm_nachrichten``.
    if "messages" in kwargs:
        kwargs["messages"] = nachrichten_fuer(get_provider(), kwargs["messages"])


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

    t0 = time.perf_counter()  # Wanduhr samt Warteschlange — so wartet der Zug
    async with platz("bg" if background else "live"):
        resp = await _acompletion(**kwargs)
    ms = seit_ms(t0)
    # Responses-Brücke: Text und Aufrufe können auf zwei Choices liegen — jeder
    # Aufrufer liest choices[0] (siehe services/llm_choices).
    resp = vereinige_choices(resp)
    resp.model = antwort_modell(getattr(resp, "model", "") or "", resolved)

    if usage_acc is not None:
        _usage.add_usage(usage_acc, _usage.extract_usage(resp), phase, ms=ms)
    return resp


async def embedding(
    text: str, *, model: str | None = None, kanal: str = "live",
) -> list[float]:
    """One embedding vector for ``text`` — the RAG embedding boundary (P6-1),
    sibling of ``chat_completion``: same provider routing, timeout, retries and
    concurrency semaphore. Errors propagate — the caller owns the policy.

    ``kanal`` (Paket 4, C4) picks the semaphore: ``live`` for the query
    embedding of a chat turn, ``ingest`` for imports and the backfill — their
    own process-wide channel (``EMBED_INGEST_PARALLEL``), so an import never
    takes the chat's slots.

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
        # Keine ``num_retries``: siehe Modulkopf (Paket 4, B3).
    }
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers

    async with platz(kanal):
        resp = await _aembedding(**kwargs)
    item = resp.data[0]
    return item["embedding"] if isinstance(item, dict) else item.embedding
