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
# W12: `max` ergaenzt — die Chat-Completions-Referenz fuehrt es auf
# (none|minimal|low|medium|high|xhigh|max). Fehlte hier, ein gueltiger Wert
# waere also beim Start als Tippfehler abgewiesen worden.
_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}


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
    cors_allow_all: bool = Field(
        True, validation_alias=_env("CORS_ALLOW_ALL"),
        description="open CORS for every origin; false => cors_origins applies",
    )
    cors_allow_extensions: bool = Field(
        True, validation_alias=_env("CORS_ALLOW_EXTENSIONS"),
        description="allow safari-web-extension:// and chrome-extension:// origins "
                    "(regex, in ADDITION to cors_origins)",
    )
    trust_forwarded_for: bool = Field(False, validation_alias=_env("TRUST_FORWARDED_FOR"))
    allow_open_admin: bool = Field(
        False, validation_alias=_env("BOERDI_ALLOW_OPEN_ADMIN"),
        description="dev opt-in: admin without key when studio_api_key is empty",
    )
    agent_open: bool = Field(
        False, validation_alias=_env("AGENT_OPEN"),
        description="test opt-in: /api/agent without any login (rate limit still applies)",
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
    # W12 (Nutzer-Vorgabe „Ziel ist hohe Geschwindigkeit"): medium -> low.
    # Die API-Referenz: „Lower values will result in more concise responses" —
    # weniger Ausgabe-Token heisst direkt kuerzere Antwortzeit. `reasoning_effort`
    # steht schon auf `low`.
    llm_verbosity: str = Field("low", validation_alias=_env("LLM_VERBOSITY"))
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
        # W7b (Nutzer-Vorgabe 2026-07-31): der Vercel-Server ist veraltet — er
        # kennt ``get_wlo_content_text`` nicht, das TOOL_DEFINITIONS dem Modell
        # aber anbietet. M17 („Inhalt anzeigen") rief dort ins Leere. Der neue
        # Host liefert 23 Werkzeuge, eine echte Obermenge der alten 12.
        "https://wlo-mcp.87.106.195.152.nip.io/mcp",
        validation_alias=_env("MCP_SERVER_URL"),
    )
    mcp_max_connections: int = Field(50, validation_alias=_env("MCP_MAX_CONNECTIONS"))
    mcp_auth_token: SecretStr = Field(
        SecretStr(""),
        validation_alias=_env("MCP_AUTH_TOKEN"),
        description=(
            "C2: Zugangsblock des MCP-Servers (`wlo2.…`, via dessen /auth-Seite). "
            "Gesetzt ⇒ Dienst-Betriebsart, alle Aufrufe tragen "
            "`Authorization: Bearer …`. Leer ⇒ anonym lesend — der Server "
            "antwortet dann weiter mit 200 und der vollen Werkzeugliste."
        ),
    )
    repo_base_url: str = Field(
        "https://redaktion.openeduhub.net", validation_alias=_env("REPO_BASE_URL"),
        description="must match the repo the MCP server queries; rewrites card links",
    )

    # ── RAG / ingest / rerank ───────────────────────────────────────────
    # W11 (Nutzer-Korrektur 2026-08-09): AN — wie ALT. Die kurz zuvor gesetzte
    # Vorgabe AUS ist damit zurueckgenommen. Bezahlbar wird es durch die drei
    # Werte darunter: 10 Kandidaten (statt ALTs 25) und die Latenz-Verteilung
    # 1 Worker x 3 Threads. Gemessen kostet der RAG-Pfad damit ~703 ms statt
    # 3726 ms, das Karten-Gate ~90 ms.
    rag_reranker_enabled: bool = Field(True, validation_alias=_env("RAG_RERANKER_ENABLED"))
    # W7: das CPU-Budget der In-Prozess-ONNX-Inferenz. Die beiden Knöpfe spannen
    # dasselbe Budget aus zwei Richtungen auf:
    #     Worker × Threads-je-Inferenz = beanspruchte Kerne.
    # Vorgabe (Nutzer 2026-08-09): halbe System-CPU, verteilt auf Worker à einem
    # Thread — bester Durchsatz. Wer stattdessen kurze Einzel-Latenz will, dreht
    # es um (1 Worker × N Threads): dasselbe Budget, andere Verteilung.
    # W9: die beiden Rerank-Pfade sind GETRENNT schaltbar, weil sie um Faktor 8
    # verschieden kosten (gemessen 2026-08-09, 3 Threads): Karten-Gate 227 ms bei
    # 25 Karten, RAG-Rerank 1853 ms bei 25 Chunks. Ein gemeinsamer Schalter hiesse:
    # wer den teuren Pfad abschaltet, verliert still auch das Off-Topic-Gate der
    # Karten — genau den Teil, der sichtbar Qualitaet bringt.
    card_reranker_enabled: bool = Field(
        True, validation_alias=_env("CARD_RERANKER_ENABLED"),
        description=(
            "Off-Topic-Gate der WLO-Karten (billig); RAG_RERANKER_ENABLED "
            "bleibt der Hauptschalter"
        ),
    )
    rag_chunk_reranker_enabled: bool = Field(
        True, validation_alias=_env("RAG_CHUNK_RERANKER_ENABLED"),
        description=(
            "Cross-Encoder ueber die RAG-Chunks (teuer); Gegenstueck zu "
            "CARD_RERANKER_ENABLED, damit 'Karten an, RAG aus' ausdrueckbar ist"
        ),
    )
    rerank_candidates: int = Field(
        10, ge=1, validation_alias=_env("RERANK_CANDIDATES"),
        description=(
            "Chunks aus der Embedding-Suche in den RAG-Rerank; "
            "WIRKSAM ist max(dieser Wert, RAG_TOP_K)"
        ),
    )
    rerank_intra_op_threads: int | None = Field(
        None, ge=1, validation_alias=_env("RERANK_INTRA_OP_THREADS"),
        description="Kerne PRO Inferenz (ORT intra_op); None => min(3, halbe CPU)",
    )
    rerank_max_concurrency: int | None = Field(
        None, ge=1, validation_alias=_env("RERANK_MAX_CONCURRENCY"),
        description="gleichzeitige Inferenzen; None => 1 (Latenz vor Durchsatz)",
    )
    # W8: das Embedding-Backend. Vorgabe bleibt der Anbieter (Nutzer-Entscheid
    # 2026-08-09: der Chat ist zeitkritisch, ein API-Aufruf skaliert nebenlaeufig).
    # `local` ist die Ausweichmoeglichkeit, kein Umzug — siehe services/rag/embed.py.
    embed_backend: str = Field(
        "api", validation_alias=_env("EMBED_BACKEND"),
        description="api (Vorgabe, LiteLLM) | local (ONNX im Haus)",
    )
    embed_ingest_parallel: int = Field(
        4, ge=1, validation_alias=_env("EMBED_INGEST_PARALLEL"),
        description=(
            "gleichzeitige Embedding-Aufrufe beim Ingest; EIGENER Deckel, damit "
            "ein Import nicht LLM_MAX_CONCURRENCY des Chats belegt"
        ),
    )
    embed_local_model: str = Field(
        "multilingual-e5-small", validation_alias=_env("EMBED_LOCAL_MODEL"),
        description="Kandidat aus rag/embed_local.LOCAL_MODELS; alle 384-dimensional",
    )
    embed_local_model_dir: str = Field(
        "models", validation_alias=_env("EMBED_LOCAL_MODEL_DIR"),
        description="Verzeichnis mit dem Embedding-Export; fehlt es => lokaler Weg aus",
    )
    rerank_model_dir: str = Field(
        "models", validation_alias=_env("RERANK_MODEL_DIR"),
        description="Verzeichnis mit dem exportierten Cross-Encoder; fehlt es => Reranker aus",
    )
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
        "seeds", validation_alias=_env("CONFIG_SEED_DIR"),
        description=(
            "config tree for the first import (P2/P11). Ships with the repo as "
            "backend/seeds so a fresh install starts WITHOUT the ALT tree beside "
            "it; afterwards the DB is the source of truth and the studio the way "
            "to change things (`boerdi export-config` writes it back out)."
        ),
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
        """Was der Betreiber GESCHRIEBEN hat — getrimmt, ohne Leereinträge.

        **ALT-Treue hier bewusst gebrochen** (Nutzer-Entscheid 2026-08-18). ALT
        spaltete nur an ``,`` und trimmte nicht; gemessen am selben Tag traf
        ``"https://a.de, https://b.de"`` mit dem zweiten Eintrag **nie** einen
        Ursprung, weil das führende Leerzeichen mitlief — und niemand erfuhr es.
        Ein Origin enthält per Definition keine Leerzeichen, ein solcher Eintrag
        kann also nur ein Tippfehler sein. Die Treue bewahrte hier bloß eine
        stille Falle.
        """
        return [teil.strip() for teil in self.cors_origins.split(",") if teil.strip()]

    @property
    def cors_effective_origins(self) -> list[str]:
        """Was tatsächlich GILT — der Schalter über der Liste.

        Getrennt von :attr:`cors_origin_list`, damit keine der beiden lügt: die
        eine sagt, was konfiguriert wurde, die andere, was wirkt. Wer beides in
        eine Eigenschaft presste, könnte einem Betreiber nicht mehr zeigen, dass
        seine Liste übersteuert wird — und genau das muss sichtbar sein.

        **Vorgabe ist offen** (Nutzer-Entscheid 2026-08-18): eine Anlage soll
        ohne Zutun einbettbar sein. Zumachen ist eine ausdrückliche Handlung
        (``CORS_ALLOW_ALL=false``). ``main.py`` warnt beim Start, wenn dadurch
        eine gepflegte Liste übergangen wird.
        """
        return ["*"] if self.cors_allow_all else self.cors_origin_list

    @property
    def cors_origin_regex(self) -> str | None:
        """Ursprünge von Browser-Erweiterungen — oder ``None``.

        **Warum eine Regel und kein Listeneintrag.** Safari vergibt einer
        Erweiterung ihre UUID JE INSTALLATION
        (``safari-web-extension://72c621e2-…``); auf dem nächsten Gerät ist es
        eine andere, nach einer Neuinstallation wieder. Eine statische Liste
        kann diesen Fall grundsätzlich nicht abdecken. Chrome vergibt eine feste
        Kennung — deshalb ist es dort nie aufgefallen, und deshalb steht Chrome
        hier trotzdem mit drin: ein Gastgeber soll nicht zwei Wege lernen müssen.

        Gemeldet am 2026-08-18 von den Plugin-Entwicklern, Safari-Konsole:
        Preflight 400 auf ``/api/chat/stream`` (das ist wörtlich Starlettes
        „Disallowed CORS origin") und daneben blockierte 200er auf den einfachen
        GETs — ein Befund, zwei Gesichter.

        **Sie ERWEITERT die Liste, sie ersetzt sie nicht** (Starlette prüft
        beides mit ODER, ``cors.py:102``). Und sie gibt den KONKRETEN Ursprung
        zurück statt ``*`` — nur so bleiben Anmeldedaten überhaupt möglich.

        Was sie öffnet, ehrlich benannt: jede Browser-Erweiterung darf diese API
        rufen. Das ist weniger, als es klingt — CORS ist keine Authentifizierung,
        ein Aufruf ohne Browser ignoriert die Liste vollständig. Die Abwehr gegen
        Missbrauch ist das Rate-Limit, nicht die Herkunftsliste.
        """
        if not self.cors_allow_extensions:
            return None
        # ``fullmatch`` verwendet Starlette; die Anker sind trotzdem gesetzt,
        # damit die Regel auch beim Lesen keine Vorsilbe zulässt.
        return r"^(safari-web-extension|chrome-extension)://[A-Za-z0-9-]+$"


@lru_cache
def get_settings() -> Settings:
    return Settings()
