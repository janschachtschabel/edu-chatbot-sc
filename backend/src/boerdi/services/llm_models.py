"""Model/provider name resolution — port of ALT ``llm_provider.py`` naming
logic (P1-6). Only pure resolution lives here (needed by /api/health); the
LLM transport (LiteLLM, pools, retries, usage hook) arrives in P3-1 as
``services/llm.py`` and builds on these helpers.
"""

from typing import NamedTuple

from boerdi.settings import get_settings

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    # W12 (Nutzer-Vorgabe 2026-08-09): gpt-5.6-luna. Aus der Modellkarte
    # geprueft: 1.050.000 Token Kontext, Reasoning-Token, Streaming,
    # function_calling und Structured Outputs — alles, was der Zug braucht.
    # `is_gpt5_model` greift ueber den Praefix "gpt-5" automatisch, die
    # GPT-5-Parameter gehen also ohne Zusatzcode mit.
    "openai": {"chat": "gpt-5.6-luna", "embed": "text-embedding-3-small"},
    "b-api-openai": {"chat": "gpt-5.6-luna", "embed": "text-embedding-3-small"},
    "b-api-academiccloud": {
        "chat": "mistral-large-3-675b-instruct-2512",
        "embed": "e5-mistral-7b-instruct",
    },
}

_EMBED_MODEL_DIMS: dict[str, int] = {
    # OpenAI
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    # AcademicCloud / other B-API upstream models
    "e5-mistral-7b-instruct": 4096,
    "bge-m3": 1024,
    "bge-large-en-v1.5": 1024,
    "jina-embeddings-v2-base-de": 768,
    "jina-embeddings-v2-base-en": 768,
}

_EMBED_DIM_DEFAULT = 1536  # safe fallback (OpenAI 3-small / ada-002)


def get_provider() -> str:
    """Provider id; invalid values are already coerced to "openai" in settings."""
    return get_settings().llm_provider


def get_chat_model() -> str:
    """Chain (ALT llm_provider.py:172-180): LLM_CHAT_MODEL wins for every
    provider; OPENAI_MODEL is a legacy fallback consulted only for provider
    ``openai``; otherwise the provider default."""
    s = get_settings()
    if s.llm_chat_model:
        return s.llm_chat_model
    provider = get_provider()
    if provider == "openai" and s.openai_model:
        return s.openai_model
    return _PROVIDER_DEFAULTS[provider]["chat"]


def get_embed_model() -> str:
    s = get_settings()
    return s.llm_embed_model or _PROVIDER_DEFAULTS[get_provider()]["embed"]


class ParamRules(NamedTuple):
    """Welche Parameter eine Modellgruppe vertraegt.

    Vorher standen diese Ausnahmen als ``startswith``-Pruefungen mitten in
    ``build_chat_kwargs``. Das ist der falsche Ort: dort entscheidet sich, WIE
    eine Anfrage gebaut wird, nicht WAS ein bestimmtes Modell akzeptiert. Ein
    neues Modell braucht jetzt eine Zeile in ``_GROUPS`` statt eine weitere
    Verzweigung im Bauplan.
    """

    #: verbosity / reasoning_effort ueberhaupt senden
    gpt5_params: bool
    #: ``reasoning_effort`` AUCH bei Werkzeug-Aufrufen — und dann woertlich,
    #: einschliesslich ``"none"``.
    effort_with_tools: bool
    #: ``temperature`` erlaubt, wenn das Reasoning abgeschaltet ist
    temperature_on_none: bool


_CLASSIC = ParamRules(gpt5_params=False, effort_with_tools=False, temperature_on_none=False)

#: Praefix -> Regeln; der LAENGSTE passende Praefix gewinnt (``gpt-5.6`` vor ``gpt-5``).
_GROUPS: dict[str, ParamRules] = {
    # W12b, gegen die echte API gemessen (2026-08-09): luna weist eine Anfrage
    # MIT Werkzeugen ab, wenn `reasoning_effort` FEHLT — dann gilt das
    # Vorgabe-Reasoning des Anbieters, und das vertraegt sich nicht mit Function
    # Tools auf /v1/chat/completions. Mit ausdruecklichem Wert (`low` wie `none`)
    # kommt sauber ein tool_call zurueck.
    "gpt-5.6": ParamRules(gpt5_params=True, effort_with_tools=True, temperature_on_none=False),
    # ALT-verbatim (llm_provider.py:702-827): kein Reasoning bei Werkzeugen,
    # dafuer `temperature` neben abgeschaltetem Reasoning.
    "gpt-5.4": ParamRules(gpt5_params=True, effort_with_tools=False, temperature_on_none=True),
    # Uebrige Reasoning-Modelle. Gemessen ist, dass gpt-5.4 UND gpt-5.6 einen
    # ausdruecklichen Wert auch mit Werkzeugen annehmen; fuer o1/o3/o4 liegt keine
    # Messung vor, deshalb bleibt hier die vorsichtigere ALT-Regel stehen.
    "gpt-5": ParamRules(gpt5_params=True, effort_with_tools=False, temperature_on_none=False),
    "o1": ParamRules(gpt5_params=True, effort_with_tools=False, temperature_on_none=False),
    "o3": ParamRules(gpt5_params=True, effort_with_tools=False, temperature_on_none=False),
    "o4": ParamRules(gpt5_params=True, effort_with_tools=False, temperature_on_none=False),
}


def param_rules(model: str | None = None) -> ParamRules:
    """Die Parameter-Regeln fuer ``model`` (oder das aktive Chat-Modell).

    ``b-api-academiccloud`` faellt immer auf ``_CLASSIC``: dort liegen Qwen/GLM/
    Mistral ohne den GPT-5-Vertrag — ALT llm_provider.py:597-610.
    """
    name = (model or get_chat_model() or "").strip().lower()
    if not name or get_provider() not in ("openai", "b-api-openai"):
        return _CLASSIC
    for prefix in sorted(_GROUPS, key=len, reverse=True):
        if name.startswith(prefix):
            return _GROUPS[prefix]
    return _CLASSIC


def is_gpt5_model(model: str | None = None) -> bool:
    """True if the model name belongs to OpenAI's reasoning-capable GPT-5
    family. Also covers o1/o3/o4 reasoning models which share the same
    ``reasoning_effort`` contract. Provider-blind by design — the
    provider gate lives in ``param_rules``."""
    name = (model or get_chat_model() or "").strip().lower()
    return bool(name) and any(name.startswith(p) for p in _GROUPS)


def supports_gpt5_params(model: str | None = None) -> bool:
    """Whether to send GPT-5 params (verbosity/reasoning_effort). Free for
    both OpenAI backends; b-api-academiccloud stays excluded (Qwen/GLM/
    Mistral models without the GPT-5 contract) — ALT llm_provider.py:597-610."""
    return param_rules(model).gpt5_params


def get_verbosity() -> str:
    return get_settings().llm_verbosity


def get_reasoning_effort() -> str:
    return get_settings().llm_reasoning_effort


def get_embed_dim(model: str | None = None) -> int:
    """Vector dimension of an embedding model (ALT llm_provider.py:219-238).

    Lookup order: EMBED_DIM escape hatch -> model-name table -> 1536.
    Accepts bare or namespaced names ("openai/text-embedding-3-large").
    """
    s = get_settings()
    if s.embed_dim is not None:
        return s.embed_dim
    name = (model or get_embed_model() or "").lower().strip()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return _EMBED_MODEL_DIMS.get(name, _EMBED_DIM_DEFAULT)
