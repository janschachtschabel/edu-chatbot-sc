"""Central settings (spec §5.4) — single source for every env variable.

Parity: env names and defaults match ALT (badboerdi, inventoried 2026-07-10).
Deliberate normalizations vs. ALT (improvement V11, decided in P0-3):
- pydantic bool parsing (1/0, true/false, yes/no, on/off; case-insensitive)
  instead of ALT's per-site inconsistent parsing.
- garbage numeric values fail fast at boot instead of silently falling back.
- empty env value == unset (``env_ignore_empty``) — replicates ALT's
  ``os.getenv(...) or default`` pattern and the Docker ``${VAR:-}`` trap.
- real secrets are ``SecretStr`` and never appear in repr/logs.

Removed (replaced by stack): DATABASE_PATH -> DATABASE_URL,
RERANK_INTRA_OP_THREADS / RERANK_MAX_CONCURRENCY -> TEI sidecar (RERANK_URL).

``None`` defaults mean "layer decides": RAG_* -> rag-config.yaml then
_RAG_DEFAULTS (P6), GUIDE_TRUSTED_DOMAINS -> guide-mode.yaml (P2),
EMBED_DIM -> derived from embed model (P3).
"""

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env(name: str) -> AliasChoices:
    return AliasChoices(name)


_LLM_PROVIDERS = {"openai", "b-api-openai", "b-api-academiccloud"}
_VERBOSITY = {"low", "medium", "high"}
_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    # ── Core ────────────────────────────────────────────────────────────
    log_level: str = Field("INFO", validation_alias=_env("LOG_LEVEL"))
    studio_api_key: SecretStr = Field(
        SecretStr(""), validation_alias=_env("STUDIO_API_KEY"),
        description="X-Studio-Key; empty => admin disabled unless allow_open_admin",
    )
    cors_origins: str = Field(
        "*", validation_alias=_env("CORS_ORIGINS"),
        description="comma-separated; '*' disables credentials (parse: cors_origin_list)",
    )
    trust_forwarded_for: bool = Field(False, validation_alias=_env("TRUST_FORWARDED_FOR"))
    allow_open_admin: bool = Field(
        False, validation_alias=_env("BOERDI_ALLOW_OPEN_ADMIN"),
        description="dev opt-in: admin without key when studio_api_key is empty",
    )

    # ── LLM provider / models (resolution chain lives in services/llm.py) ─
    llm_provider: str = Field("openai", validation_alias=_env("LLM_PROVIDER"))
    llm_chat_model: str = Field(
        "", validation_alias=_env("LLM_CHAT_MODEL"),
        description="primary override, wins for every provider when set",
    )
    openai_model: str = Field(
        "", validation_alias=_env("OPENAI_MODEL"),
        description="legacy fallback, consulted only for provider=openai",
    )
    llm_embed_model: str = Field("", validation_alias=_env("LLM_EMBED_MODEL"))
    embed_dim: int | None = Field(
        None, validation_alias=_env("EMBED_DIM"),
        description="escape hatch; None => derived from embed model",
    )
    llm_max_concurrency: int = Field(20, validation_alias=_env("LLM_MAX_CONCURRENCY"))
    llm_read_timeout: float = Field(75.0, validation_alias=_env("LLM_READ_TIMEOUT"))
    bg_llm_max_concurrency: int = Field(4, validation_alias=_env("BG_LLM_MAX_CONCURRENCY"))
    llm_verbosity: str = Field("medium", validation_alias=_env("LLM_VERBOSITY"))
    llm_reasoning_effort: str = Field("low", validation_alias=_env("LLM_REASONING_EFFORT"))
    openai_api_key: SecretStr = Field(SecretStr(""), validation_alias=_env("OPENAI_API_KEY"))
    openai_base_url: str = Field(
        "", validation_alias=_env("OPENAI_BASE_URL"),
        description="empty => https://api.openai.com/v1 (resolved in services/llm.py)",
    )
    b_api_base_url: str = Field(
        "https://b-api.prod.openeduhub.net/api/v1/llm",
        validation_alias=_env("B_API_BASE_URL"),
        description="/openai or /academiccloud appended per provider",
    )
    b_api_key: SecretStr = Field(
        SecretStr(""), validation_alias=_env("B_API_KEY"),
        description="sent as X-API-KEY header for b-api-* providers",
    )
    b_api_audio: bool = Field(
        False, validation_alias=_env("B_API_AUDIO"),
        description="opt-in: STT/TTS via B-API (needs b_api_key)",
    )

    # ── Speech ──────────────────────────────────────────────────────────
    speech_force_enable: bool = Field(False, validation_alias=_env("SPEECH_FORCE_ENABLE"))
    stt_model: str = Field("gpt-4o-mini-transcribe", validation_alias=_env("STT_MODEL"))
    tts_model: str = Field("tts-1", validation_alias=_env("TTS_MODEL"))

    # ── MCP / repo ──────────────────────────────────────────────────────
    mcp_server_url: str = Field(
        "https://wlo-mcp-server.vercel.app/mcp", validation_alias=_env("MCP_SERVER_URL")
    )
    mcp_max_connections: int = Field(50, validation_alias=_env("MCP_MAX_CONNECTIONS"))
    repo_base_url: str = Field(
        "https://redaktion.openeduhub.net", validation_alias=_env("REPO_BASE_URL"),
        description="must match the repo the MCP server queries; rewrites card links",
    )

    # ── RAG / ingest / rerank ───────────────────────────────────────────
    rag_reranker_enabled: bool = Field(True, validation_alias=_env("RAG_RERANKER_ENABLED"))
    max_ingest_mb: int = Field(
        25, validation_alias=_env("BOERDI_MAX_INGEST_MB"), description="0 = unlimited"
    )
    text_extraction_url: str = Field(
        "https://text-extraction.prod.openeduhub.net",
        validation_alias=_env("TEXT_EXTRACTION_URL"),
        description="base URL; /from-url appended internally",
    )
    rag_top_k: int | None = Field(None, validation_alias=_env("RAG_TOP_K"))
    rag_min_score: float | None = Field(None, validation_alias=_env("RAG_MIN_SCORE"))
    rag_max_chars_per_area: int | None = Field(
        None, validation_alias=_env("RAG_MAX_CHARS_PER_AREA")
    )

    # ── Card pipeline ───────────────────────────────────────────────────
    card_pipeline_v2: bool = Field(False, validation_alias=_env("CARD_PIPELINE_V2"))
    card_ce_top_n: int = Field(3, validation_alias=_env("CARD_CE_TOP_N"))
    card_ce_gate_collection: float = Field(0.0, validation_alias=_env("CARD_CE_GATE_COLLECTION"))
    card_ce_gate_content: float = Field(-1.5, validation_alias=_env("CARD_CE_GATE_CONTENT"))
    chat_disable_select_top_cards: bool = Field(
        False, validation_alias=_env("CHAT_DISABLE_SELECT_TOP_CARDS")
    )
    chat_inline_quick_replies: bool = Field(
        False, validation_alias=_env("CHAT_INLINE_QUICK_REPLIES")
    )

    # ── Guide mode ──────────────────────────────────────────────────────
    guide_trusted_domains: str | None = Field(
        None, validation_alias=_env("GUIDE_TRUSTED_DOMAINS"),
        description="comma/whitespace-separated; when set, REPLACES the yaml list",
    )

    # ── Eval / loadtest ─────────────────────────────────────────────────
    allow_loadtest: bool = Field(True, validation_alias=_env("BOERDI_ALLOW_LOADTEST"))
    eval_chat_url: str = Field(
        "http://localhost:8000/api/chat", validation_alias=_env("EVAL_CHAT_URL")
    )
    eval_simulator_model: str = Field("gpt-4o-mini", validation_alias=_env("EVAL_SIMULATOR_MODEL"))
    eval_judge_model: str = Field("gpt-4o-mini", validation_alias=_env("EVAL_JUDGE_MODEL"))

    # ── Studio (consumed by studio-bff, P9) ─────────────────────────────
    studio_password: SecretStr = Field(SecretStr(""), validation_alias=_env("STUDIO_PASSWORD"))
    studio_cookie_secure: bool = Field(
        True, validation_alias=_env("STUDIO_COOKIE_SECURE"),
        description="Secure flag on the studio auth cookie; 0 only for plain-http local dev",
    )
    studio_dist_dir: str = Field(
        "studio_dist", validation_alias=_env("STUDIO_DIST_DIR"),
        description="built Angular studio; missing => /studio is not mounted",
    )

    # ── New in boerdi-chat (spec §5.4 "NEU") ────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://boerdi:boerdi@localhost:5432/boerdi",
        validation_alias=_env("DATABASE_URL"),
        description="dev default matches deploy/compose.dev.yml",
    )
    rate_limit_storage_uri: str = Field(
        "memory://", validation_alias=_env("RATE_LIMIT_STORAGE_URI"),
        description="slowapi storage; valkey://... in cluster (P10-6)",
    )
    rate_limit_chat: str = Field(
        "20/minute", validation_alias=_env("RATE_LIMIT_CHAT"),
        description="default-on public chat limit (improvement V7)",
    )
    otel_exporter_otlp_endpoint: str = Field(
        "", validation_alias=_env("OTEL_EXPORTER_OTLP_ENDPOINT"),
        description="empty => OTLP export off",
    )
    rerank_url: str = Field(
        "", validation_alias=_env("RERANK_URL"),
        description="TEI sidecar base URL; empty => reranker off (embedding-only)",
    )
    config_seed_dir: str = Field(
        "", validation_alias=_env("CONFIG_SEED_DIR"),
        description="ALT config tree for first import (P2/P11)",
    )
    widget_dist_dir: str = Field("widget_dist", validation_alias=_env("WIDGET_DIST_DIR"))

    # ── Normalization (parity with ALT read sites) ──────────────────────
    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("llm_provider")
    @classmethod
    def _coerce_provider(cls, v: str) -> str:
        v = v.lower()
        return v if v in _LLM_PROVIDERS else "openai"

    @field_validator("llm_verbosity")
    @classmethod
    def _coerce_verbosity(cls, v: str) -> str:
        v = v.lower()
        return v if v in _VERBOSITY else "medium"

    @field_validator("llm_reasoning_effort")
    @classmethod
    def _coerce_reasoning(cls, v: str) -> str:
        v = v.lower()
        return v if v in _REASONING else "low"

    @field_validator("llm_max_concurrency")
    @classmethod
    def _floor_llm_conc(cls, v: int) -> int:
        return max(2, v)

    @field_validator("llm_read_timeout")
    @classmethod
    def _floor_timeout(cls, v: float) -> float:
        return max(15.0, v)

    @field_validator("bg_llm_max_concurrency")
    @classmethod
    def _floor_bg(cls, v: int) -> int:
        return max(1, v)

    @field_validator("mcp_max_connections")
    @classmethod
    def _floor_mcp(cls, v: int) -> int:
        return max(5, v)

    @field_validator(
        "mcp_server_url", "openai_base_url", "b_api_base_url", "repo_base_url",
        "rerank_url", "otel_exporter_otlp_endpoint",
    )
    @classmethod
    def _rstrip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @field_validator("text_extraction_url")
    @classmethod
    def _normalize_extraction_url(cls, v: str) -> str:
        v = v.rstrip("/")
        if v.endswith("/from-url"):
            v = v[: -len("/from-url")].rstrip("/")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        # parity: plain split(","), items deliberately NOT stripped (ALT main.py:188)
        return self.cors_origins.split(",")


@lru_cache
def get_settings() -> Settings:
    return Settings()
