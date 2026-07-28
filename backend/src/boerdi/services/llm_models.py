"""Model/provider name resolution — port of ALT ``llm_provider.py`` naming
logic (P1-6). Only pure resolution lives here (needed by /api/health); the
LLM transport (LiteLLM, pools, retries, usage hook) arrives in P3-1 as
``services/llm.py`` and builds on these helpers.
"""

from boerdi.settings import get_settings

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "openai": {"chat": "gpt-5.4-mini", "embed": "text-embedding-3-small"},
    "b-api-openai": {"chat": "gpt-5.4-mini", "embed": "text-embedding-3-small"},
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


def is_gpt5_model(model: str | None = None) -> bool:
    """True if the model name belongs to OpenAI's reasoning-capable GPT-5
    family. Also covers o1/o3/o4 reasoning models which share the same
    ``reasoning_effort`` contract."""
    name = (model or get_chat_model() or "").strip().lower()
    if not name:
        return False
    return (
        name.startswith("gpt-5")
        or name.startswith("o1")
        or name.startswith("o3")
        or name.startswith("o4")
    )


def supports_gpt5_params(model: str | None = None) -> bool:
    """Whether to send GPT-5 params (verbosity/reasoning_effort). Free for
    both OpenAI backends; b-api-academiccloud stays excluded (Qwen/GLM/
    Mistral models without the GPT-5 contract) — ALT llm_provider.py:597-610."""
    return is_gpt5_model(model) and get_provider() in ("openai", "b-api-openai")


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
