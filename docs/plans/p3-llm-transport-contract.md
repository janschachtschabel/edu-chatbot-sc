# P3-1 LLM-Transport — Portierungs-Vertrag (ALT → LiteLLM)

> Erhoben 2026-07-11 gegen `badboerdi/backend/app/services/{llm_provider,llm_usage,
> llm_service,llm_tool_loop,llm_streaming}.py`. Grundlage für `services/llm.py` (Slice b von 3-1).
> Namensauflösung (`get_provider`/`get_chat_model`/`get_embed_model`/`is_gpt5_model`/
> `supports_gpt5_params`/`get_embed_dim`) liegt bereits in `services/llm_models.py` (P1-6).
> Usage-Extraktion + Akkumulator liegt bereits in `obs/usage.py` (P3-1 Slice a).

## Reale Lib-API (verifiziert)
- litellm **1.91.1**: `await litellm.acompletion(model, messages, api_key, api_base, timeout,
  temperature, tools, tool_choice, response_format, num_retries, reasoning_effort,
  max_completion_tokens, **kwargs)`; Response ist OpenAI-geformt → `resp.usage.prompt_tokens`,
  `.completion_tokens`, `.prompt_tokens_details.cached_tokens`, `resp.model`. Moderation:
  `await litellm.amoderation(model="omni-moderation-latest", input=...)`.
- instructor **1.15.4**: `instructor.from_litellm(litellm.acompletion, mode=instructor.Mode.TOOLS)`
  → AsyncInstructor (für 3-2 Classify).

## Zwei wichtige ALT-Abweichungen vom Spec-Wortlaut
1. **Keine `asyncio.Semaphore` in ALT** — Concurrency kommt aus dem httpx-Pool
   `max_connections`. „live vs background" = **zwei getrennte Clients mit zwei Pools**, nicht
   zwei Semaphoren. LiteLLM hat kein Pool-Bulkhead → **explizite `asyncio.Semaphore` ist der
   korrekte NEU-Ersatz** (Spec 3-1 „Semaphore LLM_MAX_CONCURRENCY + BG_LLM_MAX_CONCURRENCY").
2. **Kein expliziter Retry/Backoff im App-Code** — OpenAI-SDK-Default `max_retries=2`.
   NEU: `num_retries=2` an `acompletion`.

## Client/Provider-Routing (ALT llm_provider.py:282-353)
- **Timeout:** `read = max(15.0, float(LLM_READ_TIMEOUT or 75.0))`, connect 10. → LiteLLM `timeout=read`.
- **Live-Pool:** `max_conc = max(2, int(LLM_MAX_CONCURRENCY or 20))` (default 20). **BG-Pool:**
  `max(1, int(BG_LLM_MAX_CONCURRENCY or 4))` (default 4). → zwei `asyncio.Semaphore`.
- **Provider → api_base + Auth:**
  - `openai`: `api_base = OPENAI_BASE_URL or "https://api.openai.com/v1"`, Auth = `Bearer OPENAI_API_KEY`.
  - `b-api-openai`: `api_base = (B_API_BASE_URL|default).rstrip("/") + "/openai"`; **BEIDE Header**
    `X-API-KEY: <B_API_KEY>` (via `extra_headers`/`default_headers`) **und** `Authorization: Bearer <B_API_KEY>`
    (via `api_key`). `api_key` nie leer → Fallback `"unused"`.
  - `b-api-academiccloud`: wie b-api-openai, aber `+ "/academiccloud"`.
  - Default B-API-Base: `https://b-api.prod.openeduhub.net/api/v1/llm`.
  - LiteLLM-Mapping: `model="openai/<name>"`-Präfix + `api_base` + `api_key` + `extra_headers={"X-API-KEY":...}`
    für b-api (OpenAI-kompatibler Pfad). Für native openai `model=<name>`.

## `build_chat_kwargs(*, model, messages, tools, tool_choice, temperature, max_tokens, response_format, verbosity, reasoning_effort, **extra)` — LOAD-BEARING (llm_provider.py:702-827)
- Immer `{"model": model or get_chat_model(), "messages": messages}`.
- `tools` nur wenn truthy; `tool_choice`/`response_format` nur wenn nicht None.
- **GPT-5-Zweig** (gated `supports_gpt5_params(model)`):
  - `verbosity = verbosity or get_verbosity()` — nur senden wenn Lib es kennt (bei LiteLLM: durchreichen, `litellm.drop_params=True` lässt Unbekanntes fallen).
  - `reasoning_effort` — **nur auf tool-LOSEN Calls** und nur wenn effort != "none". Bei `tools` gedroppt.
  - `temperature` — **nur** wenn effektiver effort == "none" UND Modellname startet mit "gpt-5.4" (`_accepts_temperature`). Sonst still gedroppt.
  - **Nie `max_tokens`/`max_completion_tokens`** auf GPT-5.
- **Klassik-Zweig:** `temperature` durchreichen wenn nicht None; `max_tokens` via `_shape_max_tokens(model, max_tokens)` (Reasoning-Buffer + Floor aus `_MODEL_PROFILES`); ohne max_tokens → Profil-Floor.
- `**extra` verbatim, None-Werte übersprungen.
- **NEU-Vereinfachung erlaubt:** statt `_sdk_supports`-Introspektion auf `openai.AsyncCompletions`
  → `litellm.drop_params=True` setzen und Params durchreichen (LiteLLM droppt vom Ziel-Modell
  nicht unterstützte). GPT-5-Gating-LOGIK (welche Params WANN gesetzt werden) bleibt aber Pflicht-Port.

## Aufruf + Fehler
- `await litellm.acompletion(**build_chat_kwargs(...), api_base=..., api_key=..., extra_headers=...,
  timeout=..., num_retries=2)` unter `async with live_semaphore:` (bzw. bg).
- Tool-Loop-Fehler: breites `except Exception` → user-facing String, Turn-Abbruch (llm_tool_loop.py:681).
  `classify_input` **kein** try/except um den Call; nur Parsing guarded. Safety/QR/LP/Curation wrappen
  ihren Call in try/except → `{}`/leer.
- Streaming (`_stream_completion`): `stream=True` + `stream_options={"include_usage": True}`; Usage aus
  letztem Chunk. → in P4-5 (SSE) relevant, nicht 3-1.

## Öffentliche Fläche, die andere Module importieren (Port-Ziele für services/llm.py)
`get_client`/`get_background_client` (Pool-Wahl → Semaphore-Wahl), `get_moderation_client`,
`get_embedding_client` + `get_embedding_model_for_client` (→ P6 RAG), `build_chat_kwargs`,
`get_verbosity`/`get_reasoning_effort` (schon in llm_models), `speech_enabled`/`speech_disabled_reason`
(→ P7 Speech), `reset_client_cache` (Tests/Hot-Reload). Usage: `extract_usage`/`new_accumulator`/
`add_usage` (schon in `obs/usage.py`).

## Moderation-Client (llm_provider.py:406-463) → 3-4 Safety
- `openai`: nativer Client wenn `OPENAI_API_KEY`, sonst None.
- `b-api-openai`: B-API proxied `/moderations` wenn `B_API_KEY`; sonst nativer Side-Channel wenn `OPENAI_API_KEY`.
- `b-api-academiccloud`: nur nativer Side-Channel (AcademicCloud hat keine Moderation).
- None = „Moderation überspringen, nur Regex-Floor". Consumer: `_openai_moderate` →
  `{"flagged", "categories":{cat:bool}, "scores":{cat:float}}`, `{}` bei Fehler (nie fail-closed).
  LiteLLM: `litellm.amoderation`.

## Tests (ALT-Mock-Muster)
Kein respx/HTTP-Mock: ALT patcht das **modul-gebundene `client`**-Singleton mit einem Fake, der
`.chat.completions.create(**kwargs)` bietet (`monkeypatch.setattr(<modul>, "client", fake)`). NEU:
`services/llm.py` sollte `acompletion` als **injizierbares/patchbares Modul-Attribut** halten
(z. B. `llm._acompletion = litellm.acompletion`), damit Tests es durch einen Fake ersetzen, der
die kwargs mitschreibt (`_SeqCaptureClient`-Äquivalent) — dann sind `build_chat_kwargs`-Matrix
(GPT-5-Gating) + Provider-Routing + Semaphore + Usage-Hook ohne echten Netz-Call testbar.
UNGETESTET in ALT (höchstes Risiko, in NEU testen!): Client-kwargs pro Provider (base_url,
X-API-KEY vs Bearer), Timeout/Pool-Limits, Moderation-Client-Wahl.
