"""P0-3: settings parity with ALT (spec §5.4).

Defaults and env names must match the ALT inventory (badboerdi, 2026-07-10).
Deliberate normalizations (documented in boerdi/settings.py): pydantic bool
parsing, fail-fast on garbage numerics, empty env value == unset.
"""

import pytest
from pydantic import AliasChoices

from boerdi.settings import Settings

# §5.4 completeness checklist — every name must be a bound env alias.
SPEC_ENV_VARS = [
    # Core
    "LOG_LEVEL", "STUDIO_API_KEY", "CORS_ORIGINS", "TRUST_FORWARDED_FOR",
    "BOERDI_ALLOW_OPEN_ADMIN",
    # LLM
    "LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "LLM_EMBED_MODEL", "EMBED_DIM",
    "LLM_MAX_CONCURRENCY", "LLM_READ_TIMEOUT", "BG_LLM_MAX_CONCURRENCY",
    "LLM_VERBOSITY", "LLM_REASONING_EFFORT",
    "OPENAI_API_KEY", "OPENAI_BASE_URL", "B_API_BASE_URL", "B_API_KEY", "B_API_AUDIO",
    # Speech
    "SPEECH_FORCE_ENABLE", "STT_MODEL", "TTS_MODEL",
    # MCP
    "MCP_SERVER_URL", "MCP_MAX_CONNECTIONS", "REPO_BASE_URL",
    # RAG / Rerank
    "RAG_RERANKER_ENABLED", "BOERDI_MAX_INGEST_MB", "TEXT_EXTRACTION_URL",
    "RAG_TOP_K", "RAG_MIN_SCORE", "RAG_MAX_CHARS_PER_AREA",
    # Cards
    "CARD_PIPELINE_V2", "CARD_CE_TOP_N", "CARD_CE_GATE_COLLECTION",
    "CARD_CE_GATE_CONTENT", "CHAT_DISABLE_SELECT_TOP_CARDS", "CHAT_INLINE_QUICK_REPLIES",
    # Guide
    "GUIDE_TRUSTED_DOMAINS",
    # Eval / Loadtest
    "BOERDI_ALLOW_LOADTEST", "EVAL_CHAT_URL", "EVAL_SIMULATOR_MODEL", "EVAL_JUDGE_MODEL",
    # Studio (consumed by studio-bff, P9)
    "STUDIO_PASSWORD", "STUDIO_COOKIE_SECURE", "STUDIO_DIST_DIR",
    # NEW in boerdi-chat
    "DATABASE_URL", "RATE_LIMIT_STORAGE_URI", "RATE_LIMIT_CHAT",
    "OTEL_EXPORTER_OTLP_ENDPOINT", "RERANK_URL", "CONFIG_SEED_DIR", "WIDGET_DIST_DIR",
]


def bound_env_names() -> set[str]:
    names: set[str] = set()
    for field in Settings.model_fields.values():
        alias = field.validation_alias
        assert isinstance(alias, AliasChoices), "every field must declare its env names"
        names.update(str(choice) for choice in alias.choices)
    return names


@pytest.fixture()
def clean_env(monkeypatch: pytest.MonkeyPatch):
    for name in SPEC_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def fresh(**env: str) -> Settings:
    import os

    old = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    try:
        return Settings(_env_file=None)
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_spec_env_list_is_complete(clean_env) -> None:
    bound = bound_env_names()
    missing = [name for name in SPEC_ENV_VARS if name not in bound]
    assert missing == [], f"unbound spec vars: {missing}"


def test_defaults_match_alt(clean_env) -> None:
    s = Settings(_env_file=None)
    # Core
    assert s.log_level == "INFO"
    assert s.studio_api_key.get_secret_value() == ""  # SecretStr: never logged
    assert s.cors_origins == "*"
    assert s.trust_forwarded_for is False
    assert s.allow_open_admin is False
    # LLM (ALT llm_provider.py)
    assert s.llm_provider == "openai"
    assert s.llm_chat_model == ""
    assert s.openai_model == ""
    assert s.llm_embed_model == ""
    assert s.embed_dim is None  # None => derived from embed model (P3)
    assert s.llm_max_concurrency == 20
    assert s.llm_read_timeout == 75.0
    assert s.bg_llm_max_concurrency == 4
    assert s.llm_verbosity == "low"  # W12: Nutzer-Vorgabe „hohe Geschwindigkeit"
    assert s.llm_reasoning_effort == "low"
    assert s.openai_base_url == ""
    assert s.b_api_base_url == "https://b-api.prod.openeduhub.net/api/v1/llm"
    assert s.b_api_audio is False
    # Speech
    assert s.speech_force_enable is False
    assert s.stt_model == "gpt-4o-mini-transcribe"
    assert s.tts_model == "tts-1"
    # MCP
    # W7b (2026-07-31): der Vercel-Server ist veraltet (kennt
    # ``get_wlo_content_text`` nicht) — Default ist der neue Host. Der Zwilling
    # ``transport._DEFAULT_MCP_URL`` muss denselben Wert tragen; das pinnt
    # ``test_die_beiden_mcp_defaults_zeigen_auf_denselben_server``.
    assert s.mcp_server_url == "https://wlo-mcp.87.106.195.152.nip.io/mcp"
    assert s.mcp_max_connections == 50
    assert s.repo_base_url == "https://redaktion.openeduhub.net"
    # RAG (None => yaml layer decides, ALT _RAG_DEFAULTS live in the rag service)
    # W11 (Nutzer-Korrektur): wieder AN, wie ALT. Bezahlbar durch 10 Kandidaten
    # und die Latenz-Verteilung 1 Worker x 3 Threads.
    assert s.rag_reranker_enabled is True
    assert s.max_ingest_mb == 25
    assert s.text_extraction_url == "https://text-extraction.prod.openeduhub.net"
    assert s.rag_top_k is None
    assert s.rag_min_score is None
    assert s.rag_max_chars_per_area is None
    # Cards
    assert s.card_pipeline_v2 is False
    assert s.card_ce_top_n == 3
    assert s.card_ce_gate_collection == 0.0
    assert s.card_ce_gate_content == -1.5
    assert s.chat_disable_select_top_cards is False
    assert s.chat_inline_quick_replies is False
    # Guide (None => guide-mode.yaml wins, env replaces yaml entirely)
    assert s.guide_trusted_domains is None
    # Eval / Loadtest
    assert s.allow_loadtest is True
    assert s.eval_chat_url == "http://localhost:8000/api/chat"
    assert s.eval_simulator_model == "gpt-4o-mini"
    assert s.eval_judge_model == "gpt-4o-mini"
    # NEW
    assert s.database_url == "postgresql+asyncpg://boerdi:boerdi@localhost:5432/boerdi"
    assert s.rate_limit_storage_uri == "memory://"
    assert s.rate_limit_chat == "20/minute"
    assert s.otel_exporter_otlp_endpoint == ""
    assert s.rerank_url == ""
    assert s.widget_dist_dir == "widget_dist"


def test_alt_env_names_bind_fields(clean_env) -> None:
    s = fresh(
        BOERDI_ALLOW_OPEN_ADMIN="1",
        BOERDI_MAX_INGEST_MB="50",
        BOERDI_ALLOW_LOADTEST="false",
        LLM_READ_TIMEOUT="120",
        MCP_SERVER_URL="https://example.org/mcp/",
    )
    assert s.allow_open_admin is True
    assert s.max_ingest_mb == 50
    assert s.allow_loadtest is False
    assert s.llm_read_timeout == 120.0
    assert s.mcp_server_url == "https://example.org/mcp"  # trailing slash stripped (ALT)


def test_empty_env_value_means_unset(clean_env) -> None:
    s = fresh(EMBED_DIM="", LLM_MAX_CONCURRENCY="", RAG_TOP_K="")
    assert s.embed_dim is None
    assert s.llm_max_concurrency == 20
    assert s.rag_top_k is None


def test_numeric_floors_like_alt(clean_env) -> None:
    s = fresh(
        LLM_MAX_CONCURRENCY="1",
        LLM_READ_TIMEOUT="5",
        BG_LLM_MAX_CONCURRENCY="0",
        MCP_MAX_CONNECTIONS="2",
    )
    assert s.llm_max_concurrency == 2
    assert s.llm_read_timeout == 15.0
    assert s.bg_llm_max_concurrency == 1
    assert s.mcp_max_connections == 5


def test_enum_coercion_like_alt(clean_env) -> None:
    assert fresh(LLM_PROVIDER="banana").llm_provider == "openai"
    assert fresh(LLM_PROVIDER="B-API-OpenAI").llm_provider == "b-api-openai"
    assert fresh(LLM_VERBOSITY="extreme").llm_verbosity == "medium"
    assert fresh(LLM_REASONING_EFFORT="ultra").llm_reasoning_effort == "low"


def test_inverted_bool_defaults(clean_env) -> None:
    assert fresh(RAG_RERANKER_ENABLED="off").rag_reranker_enabled is False
    assert fresh(BOERDI_ALLOW_LOADTEST="0").allow_loadtest is False


def test_cors_origin_list_parity(clean_env) -> None:
    assert Settings(_env_file=None).cors_origin_list == ["*"]
    # ALT parity: plain split(","), items are NOT stripped
    assert fresh(CORS_ORIGINS="https://a.de, https://b.de").cors_origin_list == [
        "https://a.de",
        " https://b.de",
    ]


def test_url_normalization_parity(clean_env) -> None:
    s = fresh(
        OPENAI_BASE_URL="https://api.example.com/v1/",
        B_API_BASE_URL="https://b.example.com/api/v1/llm/",
        TEXT_EXTRACTION_URL="https://tx.example.com/from-url",
        REPO_BASE_URL="https://repo.example.com/",
    )
    assert s.openai_base_url == "https://api.example.com/v1"
    assert s.b_api_base_url == "https://b.example.com/api/v1/llm"
    assert s.text_extraction_url == "https://tx.example.com"  # /from-url appended internally
    assert s.repo_base_url == "https://repo.example.com"


def test_die_beiden_mcp_defaults_zeigen_auf_denselben_server():
    """``settings.mcp_server_url`` und ``transport._DEFAULT_MCP_URL`` sind Zwillinge.

    Der zweite greift genau dann, wenn der erste leer ist — die Compose-Falle
    ``${MCP_SERVER_URL:-}``. Driften sie auseinander, landet ausgerechnet der
    Notfall-Pfad auf einem anderen Server als der Normalfall, und zwar lautlos.
    Beim Server-Wechsel 2026-07-31 (W7b) wäre genau das passiert: der Zwilling
    stand noch auf dem alten Host ohne ``get_wlo_content_text``.
    """
    from boerdi.services.mcp.transport import _DEFAULT_MCP_URL
    from boerdi.settings import Settings

    assert _DEFAULT_MCP_URL == Settings().mcp_server_url
