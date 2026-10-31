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

from limits import parse_many
from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env(name: str) -> AliasChoices:
    return AliasChoices(name)


#: Umbenannte Variablen, alt → neu (2026-10-28: alle Namen englisch). Der alte Name wirkt
#: übergangsweise weiter; der Start warnt (``main._warn_insecure_config``).
UMBENANNTE_VARIABLEN: dict[str, str] = {
    "RAG_UMWANDLUNG_FRIST_S": "RAG_CONVERSION_TIMEOUT_S",
    "RAG_UMWANDLUNG_MAX_MB": "RAG_CONVERSION_MAX_MB",
}


def _env_umbenannt(name: str) -> AliasChoices:
    """Der neue Name zuerst, dahinter der alte aus :data:`UMBENANNTE_VARIABLEN`."""
    return AliasChoices(name, *(alt for alt, neu in UMBENANNTE_VARIABLEN.items() if neu == name))


_LLM_PROVIDERS = {"openai", "b-api-openai", "b-api-academiccloud"}
_B_API_KEY_MODES = {"auto", "static", "forward"}
#: Diese Werte von ``RATE_LIMIT_CHAT`` schalten das äußere Limit ab (``api/ratelimit``).
RATE_LIMIT_AUS = ("off", "0", "none", "false", "disabled")
_MODERATION_FAILURE_MODES = {"open", "closed"}
_VERBOSITY = {"low", "medium", "high"}
# W12: `max` ergaenzt — die Chat-Completions-Referenz fuehrt es auf
# (none|minimal|low|medium|high|xhigh|max). Fehlte hier, ein gueltiger Wert
# waere also beim Start als Tippfehler abgewiesen worden.
_REASONING = {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
# OpenAI ``service_tier`` (Fast-Mode-Leitfaden 2026-10: ``priority`` ist der
# ältere Name für ``fast``).
_SERVICE_TIERS = {"auto", "default", "flex", "priority", "fast"}
# Paket 8 (P2): CSP der Studio-Seite. Ein unbekannter Wert fällt auf ``enforce`` —
# ein Tippfehler darf den Schutz nicht still abschalten.
_STUDIO_CSP = {"enforce", "report", "off"}


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
    # Paket 17 (D4): ``json`` für den Betrieb (eine JSON-Zeile je Eintrag), ``text`` lokal.
    log_format: str = Field("text", validation_alias=_env("LOG_FORMAT"))
    # Paket 18C/D: Inhalte (Nachrichten, Prompts, Werkzeugargumente) stehen im Log nur mit
    # diesem Schalter — für eine akute Analyse, danach wieder aus. Eigene Zeilen mit Inhalt
    # stehen auf DEBUG; die Fremd-Logger (``obs/drittlogger``) öffnet er aber ganz, auch
    # unter ``LOG_LEVEL=INFO``: dann kommen etwa die ERROR-Zeilen von instructor und
    # Warnungen von LiteLLM mit Anbietertext (Review 2026-10-30).
    log_content: bool = Field(False, validation_alias=_env("LOG_CONTENT"))
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
    # ── Master-Skill (N3, 2026-08-18) ───────────────────────────────
    # Eine redaktionelle Gesamtanleitung aus dem Repositorium, die im
    # Agent-Modus als stabiler Prompt-Kopf laeuft. Vorgabe AUS: sie
    # kostet einen MCP-Abruf und aendert das Verhalten, das gehoert zu einer
    # bewussten Handlung. Die Kennung ist vorbelegt, damit Anschalten ein
    # Schalter ist und keine Suche. Je Einbettung uebersteuert
    # ``environment.master_skill`` (Rangfolge in ``services/master_skill``).
    master_skill_enabled: bool = Field(
        False, validation_alias=_env("MASTER_SKILL_ENABLED"),
        description="load the master skill as the first system block (agent)",
    )
    master_skill_node_id: str = Field(
        "535cabca-47e4-4cbf-9cab-ca47e40cbf4e",
        validation_alias=_env("MASTER_SKILL_NODE_ID"),
        description="WLO nodeId of the master skill (get_skill)",
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
    # Paket 7 (L3): ungesetzt gilt die Vorgabe je Anbieter (``services/llm_parallel``):
    # OpenAI 20 für den Chat, hinter der b-api ein gemeinsamer Deckel von 2.
    llm_max_concurrency: int | None = Field(None, validation_alias=_env("LLM_MAX_CONCURRENCY"))
    llm_read_timeout: float = Field(75.0, validation_alias=_env("LLM_READ_TIMEOUT"))
    # Paket 18F (Nutzer-Entscheid F2): so lange wartet ein Chat-Aufruf höchstens auf einen
    # LLM-Platz; danach gilt der Zug als ausgelastet (``services/llm_parallel``). 0 = ohne Frist.
    llm_slot_wait_s: float = Field(30.0, ge=0, validation_alias=_env("LLM_SLOT_WAIT_S"))
    # Paket 10 (Audit 2026-10-10, M-5): die eigene Frist der Klassifikation — sie
    # blockiert jeden Muster-Zug. Gemessen (84 Dev-Züge, 2026-10-14): Median 2,9 s,
    # p99 6,5 s, höchstens 7,4 s. Danach die Vorgabe-Klassifikation (``assess``).
    classify_timeout_s: float = Field(20.0, validation_alias=_env("CLASSIFY_TIMEOUT_S"))
    bg_llm_max_concurrency: int = Field(4, validation_alias=_env("BG_LLM_MAX_CONCURRENCY"))
    # W12 (Nutzer-Vorgabe „Ziel ist hohe Geschwindigkeit"): medium -> low.
    # Die API-Referenz: „Lower values will result in more concise responses" —
    # weniger Ausgabe-Token heisst direkt kuerzere Antwortzeit. `reasoning_effort`
    # steht schon auf `low`.
    llm_verbosity: str = Field("low", validation_alias=_env("LLM_VERBOSITY"))
    llm_reasoning_effort: str = Field("low", validation_alias=_env("LLM_REASONING_EFFORT"))
    # OpenAI-Tarif (``service_tier``), leer = nicht gesetzt: dann entscheidet der
    # Studio-Schalter Fast-Modus (Paket 7, S1, ``services/betriebsschalter``).
    # ``fast`` gemessen 2026-10-01 mit gpt-6-luna: eine Antwort mit ~250 Token im
    # Median 3,1 statt 4,3 s, zum 4- bis 5-fachen Preis; nicht mit EU-Datenresidenz.
    # Wirkt nur bei ``LLM_PROVIDER=openai`` und der gpt-5/6-Familie (services/llm.py).
    llm_service_tier: str = Field("", validation_alias=_env("LLM_SERVICE_TIER"))
    openai_api_key: SecretStr = Field(SecretStr(""), validation_alias=_env("OPENAI_API_KEY"))
    openai_base_url: str = Field(
        "", validation_alias=_env("OPENAI_BASE_URL"),
        description="empty => https://api.openai.com/v1 (resolved in services/llm.py)",
    )
    # 2026-08-19 auf Staging gezogen (Nutzer: nur Staging). ACHTUNG, die eine
    # Falle: Adresse und Schluessel gehoeren zusammen. ``b_api_key`` kommt aus
    # EINER Variablen ``B_API_KEY`` — wer dort einen Produktions-Schluessel
    # hinterlegt, bekommt gegen diese Adresse 401. Beide Deployments
    # existieren (je 401 ohne Schluessel, gemessen 2026-08-19).
    b_api_base_url: str = Field(
        "https://b-api.staging.openeduhub.net/api/v1/llm",
        validation_alias=_env("B_API_BASE_URL"),
        description=(
            "/openai or /academiccloud appended per provider. Default staging — "
            "B_API_KEY must be the key for THIS deployment."
        ),
    )
    b_api_key: SecretStr = Field(
        SecretStr(""), validation_alias=_env("B_API_KEY"),
        description="b-api key (Bearer); a key forwarded by the b-api proxy wins (Paket 17)",
    )
    # Paket 17 (A1, Nutzer 2026-10-20): eine Route des b-api-Routers
    # (``/api/v1/llm/router``) statt des Modellnamens. Leer = aus (Vorgabe, weil die
    # Routen noch nicht angelegt sind). Die Route ersetzt nur den Namen, unter dem das
    # Chat-Modell hinausgeht; die Parameterregeln bleiben die von ``LLM_CHAT_MODEL`` —
    # eine Route bündelt nur Modelle EINER Familie (b-api-Doku, gemessen 2026-10-20).
    b_api_route: str = Field(
        "", validation_alias=_env("B_API_ROUTE"),
        description="b-api router route name for the chat model (b-api-openai only)",
    )
    # Paket 17 (AB2, Nutzer 2026-10-20): woher der b-api-Schlüssel eines Zuges kommt.
    # ``auto`` (Vorgabe, auch leer/unbekannt): ``Authorization: Bearer`` vom b-api-Proxy, sonst
    # ``B_API_KEY``. ``static``: immer ``B_API_KEY``, der Kopf zählt nicht (wie vor Paket 17).
    # ``forward``: jeder Zug braucht den durchgereichten Schlüssel, sonst 401 — für eine
    # Anlage, die nur hinter dem Proxy steht. Hintergrundläufe nehmen in jedem Modus B_API_KEY.
    b_api_key_mode: str = Field(
        "auto", validation_alias=_env("B_API_KEY_MODE"),
        description="auto | static | forward — source of the b-api key per turn",
    )
    # Paket 18A (Nutzer-Entscheid E1, 2026-10-28): was ein Zug tut, dessen Moderation
    # lief, aber nichts lieferte (Ausfall, Überlast, fehlende Zugangsdaten).
    # ``open`` (Vorgabe, auch leer/unbekannt): antworten, der Ausfall steht in der
    # Entscheidung und im Zähler. ``closed``: freundliche Absage statt Antwort —
    # setzt einen erreichbaren Moderationszugang voraus.
    moderation_failure_mode: str = Field(
        "open", validation_alias=_env("MODERATION_FAILURE_MODE"),
        description="open | closed — turn behaviour when moderation is unavailable",
    )
    b_api_audio: bool = Field(
        False, validation_alias=_env("B_API_AUDIO"),
        description="opt-in: STT/TTS via B-API (needs b_api_key)",
    )
    # Sommercamp-Entscheid 2026-08-21: der /llm/-Pfad der b-api cached
    # Antworten serverseitig (Staging gemessen: Temperatur 1, dreimal dieselbe
    # „Zufallszahl", Treffer in ~0,2 s) — ein Generierungsfehler bliebe damit
    # über alle identischen Züge stehen. Wirkt NUR bei b-api-academiccloud:
    # der openai-Pfad reicht das Feld ungefiltert an OpenAI durch → HTTP 400
    # bei jedem Zug (gemessen; Verdrahtung in services/llm.wire_transport).
    b_api_clear_cache: bool = Field(
        True, validation_alias=_env("B_API_CLEAR_CACHE"),
        description=(
            "bypass the b-api response cache per request "
            "(clearCache: true; academiccloud only)"
        ),
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
    # Paket 4 B2 (externes Audit F04): Gesamtfrist EINES Werkzeugaufrufs samt
    # Verbindung und Handshake. Vorher galten nur die SDK-Vorgaben (30 s
    # Verbindung, 300 s je Lesevorgang, keine Gesamtgrenze) plus ein Retry.
    mcp_call_timeout_s: float = Field(60.0, validation_alias=_env("MCP_CALL_TIMEOUT_S"))
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
    # Befund 2026-08-19 (Nutzer: "es darf nur auf staging zeigen"): die Vorgabe
    # stand auf Produktion, waehrend der MCP-Server nachweislich Staging
    # befragt (gemessen mit ``wlo_health_check``). Weil ``rewrite_repo_host_v2``
    # JEDEN Treffer auf diesen Wert umschreibt, trugen Staging-Knoten
    # Produktions-Adressen — Links ins Leere oder auf einen fremden Knoten
    # gleicher ID. Vorgabe ist deshalb Staging: eine vergessene Angabe zeigt
    # aufs Uebungssystem, nie auf den Wirkbetrieb.
    repo_base_url: str = Field(
        "https://repository.staging.openeduhub.net",
        validation_alias=_env("REPO_BASE_URL"),
        description=(
            "must match the repo the MCP server queries; rewrites card links. "
            "Default is staging — a forgotten value must not hit production."
        ),
    )

    # ── RAG / ingest / rerank ───────────────────────────────────────────
    # W11 (Nutzer-Korrektur 2026-08-09): AN — wie ALT. Die kurz zuvor gesetzte
    # Vorgabe AUS ist damit zurueckgenommen. Bezahlbar wird es durch die drei
    # Werte darunter: 10 Kandidaten (statt ALTs 25) und die Latenz-Verteilung
    # 1 Worker x 3 Threads. Gemessen kostet der RAG-Pfad damit ~703 ms statt
    # 3726 ms, das Karten-Gate ~90 ms.
    # Nutzer-Entscheid 2026-10-15: Vorgabe wieder AUS. Das Modell liegt weder im Repo noch
    # im Image; eingeschaltet bezieht das Backend es selbst (``RERANK_AUTO_DOWNLOAD``,
    # ``services/rag/reranker_bezug``). Ohne Modell rechnet nichts damit.
    rag_reranker_enabled: bool = Field(False, validation_alias=_env("RAG_RERANKER_ENABLED"))
    rerank_auto_download: bool = Field(
        True, validation_alias=_env("RERANK_AUTO_DOWNLOAD"),
        description=(
            "eingeschaltet und Modell fehlt => beim Start selbst beziehen (Hugging Face, "
            "gepinnt); false fuer Server ohne Internet (dann Handinstallation)"
        ),
    )
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
    # Paket 9 (Review Paket 7, MAJOR 6): die Umwandlung im Kindprozess
    # (``services/rag/umwandeln_kind``) — Frist in Sekunden und Speichergrenze in MB
    # (Linux ``RLIMIT_DATA``; 0 = aus).
    rag_conversion_timeout_s: float = Field(
        120.0, gt=0, validation_alias=_env_umbenannt("RAG_CONVERSION_TIMEOUT_S"))
    rag_conversion_max_mb: int = Field(
        1024, ge=0, validation_alias=_env_umbenannt("RAG_CONVERSION_MAX_MB"))
    # 2026-08-19: Vorgabe auf Staging gezogen (Nutzer: nur Staging). Zwei
    # Dinge dazu, damit niemand mehr davon erwartet, als der Wert leistet:
    # (1) In DIESEM Backend liest ihn nichts — die Textextraktion macht der
    #     MCP-Server mit seiner eigenen ``WLO_TEXT_EXTRACTION_URL``. Die
    #     Angabe ist eine Naht ohne Verbraucher, kein Schalter.
    # (2) Der zuvor eingetragene Prod-Host beantwortet keinen Aufruf: seine
    #     Zertifikatskette ist nicht vertrauenswuerdig (gemessen 2026-08-19).
    text_extraction_url: str = Field(
        "https://text-extraction.staging.openeduhub.net",
        validation_alias=_env("TEXT_EXTRACTION_URL"),
        description="base URL; /from-url appended internally (no consumer here)",
    )
    rag_top_k: int | None = Field(None, validation_alias=_env("RAG_TOP_K"))
    rag_min_score: float | None = Field(None, validation_alias=_env("RAG_MIN_SCORE"))
    rag_max_chars_per_area: int | None = Field(
        None, validation_alias=_env("RAG_MAX_CHARS_PER_AREA")
    )

    # ── Card pipeline ───────────────────────────────────────────────────
    card_pipeline_v2: bool = Field(False, validation_alias=_env("CARD_PIPELINE_V2"))
    card_ce_top_n: int = Field(3, validation_alias=_env("CARD_CE_TOP_N"))
    # Spiegel der Vorgabe in ``services/card_reranker.threshold_for_tool`` (liest die Umgebung
    # selbst): dort seit 2026-08-16 −1.0. Stand hier bis 2026-10-15 noch auf 0.0 — irreführend.
    card_ce_gate_collection: float = Field(
        -1.0, validation_alias=_env("CARD_CE_GATE_COLLECTION"))
    card_ce_gate_content: float = Field(-1.5, validation_alias=_env("CARD_CE_GATE_CONTENT"))
    chat_disable_select_top_cards: bool = Field(
        False, validation_alias=_env("CHAT_DISABLE_SELECT_TOP_CARDS")
    )
    # Schnellantworten im Antwort-Aufruf (``respond_to_user``) — Vorgabe seit
    # 2026-09-30: gemessen 15,9 → 9,3 s je Zug und passende Vorschläge
    # (Plan ``docs/plans/2026-09-30-muster-kette-zeit.md``).
    chat_inline_quick_replies: bool = Field(
        True, validation_alias=_env("CHAT_INLINE_QUICK_REPLIES")
    )
    # Derselbe Weg im Agent-Modus. Seit Paket 7 (S3) ein Studio-Schalter
    # (``01-base/engine`` → ``betrieb.agent_schnellantworten``, Vorgabe an seit Paket 15);
    # gesetzt geht die Umgebung vor, ungesetzt (``None``) entscheidet das Studio
    # (``services/betriebsschalter``). ``CHAT_INLINE_QUICK_REPLIES=0`` gilt auch hier.
    agent_inline_quick_replies: bool | None = Field(
        None, validation_alias=_env("AGENT_INLINE_QUICK_REPLIES")
    )
    # Token-Streaming der Antwort ins Widget (``text_delta``). Seit Paket 7 (S2)
    # ein Studio-Schalter mit Vorgabe an; gesetzt geht die Umgebung vor.
    # Gestreamt wird nur der Text von ``respond_to_user``: der Muster-Weg braucht
    # ``CHAT_INLINE_QUICK_REPLIES``, der Agent zusätzlich die Agent-Schnellantworten.
    chat_token_streaming: bool | None = Field(
        None, validation_alias=_env("CHAT_TOKEN_STREAMING")
    )

    # ── Guide mode ──────────────────────────────────────────────────────
    guide_trusted_domains: str | None = Field(
        None, validation_alias=_env("GUIDE_TRUSTED_DOMAINS"),
        description="comma/whitespace-separated; when set, REPLACES the yaml list",
    )

    # ── Eval / loadtest ─────────────────────────────────────────────────
    allow_loadtest: bool = Field(True, validation_alias=_env("BOERDI_ALLOW_LOADTEST"))
    eval_chat_url: str = Field(
        "http://127.0.0.1:8100/api/chat", validation_alias=_env("EVAL_CHAT_URL")
    )
    # Paket 7 (L4, Nutzer 2026-10-09): leer heißt das Chat-Modell — Evaluationen
    # laufen mit dem Modell, das für den Chat eingestellt ist.
    eval_simulator_model: str = Field("", validation_alias=_env("EVAL_SIMULATOR_MODEL"))
    eval_judge_model: str = Field("", validation_alias=_env("EVAL_JUDGE_MODEL"))
    # Paket 13 (A2/A7): Stand des Abbilds, als Build-Argumente gesetzt; lokal leer.
    boerdi_version: str = Field("", validation_alias=_env("BOERDI_VERSION"))
    git_sha: str = Field("", validation_alias=_env("GIT_SHA"))
    # Paket 17 (D1): Port für /health, /ready, /metrics — nur im Cluster erreichbar
    # (Leitfaden „Übergabe an Team 6“). Der öffentliche Port bleibt 8100.
    internal_port: int = Field(8101, ge=1, le=65535, validation_alias=_env("INTERNAL_PORT"))
    # Gesamt-Review Paket 17 (D1): wessen X-Forwarded-For/-Proto Uvicorn glaubt — daraus wird
    # die Client-Adresse (Drosselung je IP) und das Schema der Weiterleitungen. ``*`` passt zu
    # Compose (kein App-Port veröffentlicht, nur traefik spricht mit 8100); in Kubernetes die
    # Pod-CIDR des Ingress, sonst fälscht jeder, der 8100 erreicht, seine Adresse.
    forwarded_allow_ips: str = Field("*", validation_alias=_env("FORWARDED_ALLOW_IPS"))

    @field_validator("internal_port")
    @classmethod
    def _nicht_der_oeffentliche_port(cls, v: int) -> int:
        # Review Phase D (C12): auf 8100 lauscht der Hauptserver (``serve.OEFFENTLICHER_PORT``)
        # — beide auf einem Port endeten im Bind-Fehler beim Start.
        if v == 8100:
            raise ValueError("INTERNAL_PORT darf nicht 8100 sein (öffentlicher Port)")
        return v

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
    studio_csp: str = Field(
        "enforce", validation_alias=_env("STUDIO_CSP"),
        description="CSP on the studio page: enforce | report (Report-Only) | off",
    )
    hsts_max_age: int = Field(
        86400, validation_alias=_env("HSTS_MAX_AGE"),
        description="Strict-Transport-Security max-age in seconds on every response; 0 = off",
    )

    # ── New in boerdi-chat (spec §5.4 "NEU") ────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://boerdi:boerdi@localhost:5432/boerdi",
        validation_alias=_env("DATABASE_URL"),
        description="dev default matches deploy/compose.dev.yml",
    )
    # Paket 10 (Audit 2026-10-10, M-8): der Verbindungs-Pool je Replik; die Vorgaben sind
    # die von SQLAlchemy (5 + 10). Seit Paket 19 (H-5) hält ein Zug seine Verbindung nur
    # noch während der Abfragen, nicht über LLM und MCP — 15 Verbindungen tragen damit
    # weit mehr als 15 gleichzeitige Züge.
    db_pool_size: int = Field(5, ge=1, validation_alias=_env("DB_POOL_SIZE"))
    db_max_overflow: int = Field(10, ge=0, validation_alias=_env("DB_MAX_OVERFLOW"))
    # Paket 19 (Audit 2026-10-31, M-10): Fristen je Verbindung, in Sekunden; 0 = aus.
    # ``statement_timeout``/``idle_in_transaction_session_timeout``/``lock_timeout`` setzt
    # der Server, ``command_timeout`` der Client (asyncpg) — er fängt auch eine
    # Netzpartition ohne RST. Lange Läufe (VACUUM) heben die Frist für sich auf; die
    # Kommandozeile (``boerdi …``) baut ihre Engine ohne Fristen.
    db_statement_timeout_s: float = Field(
        60.0, ge=0, validation_alias=_env("DB_STATEMENT_TIMEOUT_S"))
    db_command_timeout_s: float = Field(
        90.0, ge=0, validation_alias=_env("DB_COMMAND_TIMEOUT_S"))
    db_idle_in_transaction_timeout_s: float = Field(
        300.0, ge=0, validation_alias=_env("DB_IDLE_IN_TRANSACTION_TIMEOUT_S"))
    db_lock_timeout_s: float = Field(30.0, ge=0, validation_alias=_env("DB_LOCK_TIMEOUT_S"))
    # Paket 19 (Audit 2026-10-31, M-11): Deckel des MCP-Werkzeug-Caches nach Größe (Zeichen).
    mcp_tool_cache_max_chars: int = Field(
        20_000_000, ge=0, validation_alias=_env("MCP_TOOL_CACHE_MAX_CHARS"))
    mcp_tool_cache_max_entry_chars: int = Field(
        1_000_000, ge=0, validation_alias=_env("MCP_TOOL_CACHE_MAX_ENTRY_CHARS"))
    rate_limit_storage_uri: str = Field(
        "memory://", validation_alias=_env("RATE_LIMIT_STORAGE_URI"),
        description="slowapi storage; valkey://... in cluster (P10-6)",
    )
    rate_limit_chat: str = Field(
        "120/minute", validation_alias=_env("RATE_LIMIT_CHAT"),
        description="default-on public chat limit (improvement V7); 120 since Paket 18F",
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
    @field_validator("rate_limit_chat")
    @classmethod
    def _pruefe_rate_limit_chat(cls, v: str) -> str:
        """Paket 18F: ein ungültiges Limit verhindert den Start. Bisher scheiterte slowapi erst
        je Anfrage am Parsen — eine Fehlerzeile je Anfrage, und das Limit war faktisch aus."""
        return pruefe_drosselgrenze(v)

    @field_validator("log_level")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()

    @field_validator("log_format")
    @classmethod
    def _coerce_log_format(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in ("json", "text") else "text"

    @field_validator("b_api_key_mode")
    @classmethod
    def _coerce_b_api_key_mode(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in _B_API_KEY_MODES else "auto"

    @field_validator("moderation_failure_mode")
    @classmethod
    def _coerce_moderation_failure_mode(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in _MODERATION_FAILURE_MODES else "open"

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

    @field_validator("llm_service_tier")
    @classmethod
    def _coerce_service_tier(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in _SERVICE_TIERS else ""

    @field_validator("studio_csp")
    @classmethod
    def _coerce_studio_csp(cls, v: str) -> str:
        v = v.strip().lower()
        return v if v in _STUDIO_CSP else "enforce"

    @field_validator("hsts_max_age")
    @classmethod
    def _floor_hsts(cls, v: int) -> int:
        return max(0, v)

    @field_validator("llm_max_concurrency")
    @classmethod
    def _floor_llm_conc(cls, v: int | None) -> int | None:
        return None if v is None else max(2, v)

    @field_validator("llm_read_timeout")
    @classmethod
    def _floor_timeout(cls, v: float) -> float:
        return max(15.0, v)

    @field_validator("classify_timeout_s")
    @classmethod
    def _floor_classify_timeout(cls, v: float) -> float:
        # 0 hieße: jeder Zug ohne Klassifikation.
        return max(1.0, v)

    @field_validator("mcp_call_timeout_s")
    @classmethod
    def _floor_mcp_timeout(cls, v: float) -> float:
        # Unter 5 s endete schon ein gewöhnlicher Handshake in der Frist.
        return max(5.0, v)

    @field_validator("bg_llm_max_concurrency")
    @classmethod
    def _floor_bg(cls, v: int) -> int:
        return max(1, v)

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


#: Paket 19 (Audit H-3, Entscheid P19-E2): kürzer bleibt das Studio (``STUDIO_PASSWORD``) bzw.
#: der Schlüssel (``STUDIO_API_KEY``) verschlossen — das Cookie ist eine reine Funktion des
#: Passworts und lässt sich ohne Server raten.
STUDIO_GEHEIMNIS_MINDESTLAENGE = 12


def _studio_schluessel_roh() -> str:
    key = get_settings().studio_api_key.get_secret_value().strip()
    return "" if key.upper().startswith("CHANGE_ME") else key


def studio_schluessel() -> str:
    """Der konfigurierte Studio-Schlüssel, oder "" ohne. ``CHANGE_ME…``-Platzhalter gelten als
    nicht gesetzt — ein vergessener Vorlagewert darf nie als Schlüssel wirken. Die eine Stelle
    für API (``api/deps.expected_studio_key``) und interne Aufrufer (Lasttest, Eval-Runner).

    Seit Paket 19 auch "" für einen zu kurzen Schlüssel (:func:`studio_schluessel_zu_kurz`): er
    passt dann auf keine Anfrage, und kein interner Aufrufer schickt ihn mit."""
    key = _studio_schluessel_roh()
    return key if len(key) >= STUDIO_GEHEIMNIS_MINDESTLAENGE else ""


def studio_schluessel_zu_kurz() -> bool:
    """Gesetzt, aber kürzer als :data:`STUDIO_GEHEIMNIS_MINDESTLAENGE` — dann bleiben die
    Verwaltungsrouten zu (503), auch mit ``BOERDI_ALLOW_OPEN_ADMIN``: wer einen Schlüssel setzt,
    wollte ein Schloss, kein offenes Tor."""
    return 0 < len(_studio_schluessel_roh()) < STUDIO_GEHEIMNIS_MINDESTLAENGE


def pruefe_drosselgrenze(wert: str, name: str = "RATE_LIMIT_CHAT") -> str:
    """Eine Grenze wie ``120/minute`` oder ``10/second;500/hour``, oder ein Aus-Wort
    (:data:`RATE_LIMIT_AUS`). Sonst ``ValueError`` — für ``RATE_LIMIT_CHAT`` beim Start, für die
    Zug-Grenzen im Studio beim Speichern (Paket 19, M-4)."""
    if wert.strip().lower() in RATE_LIMIT_AUS:
        return wert
    try:
        parse_many(wert)
    except ValueError as fehler:
        raise ValueError(
            f"{name}={wert!r} ist kein gültiges Limit — Form „120/minute“ oder "
            f"„10/second;500/hour“, abschalten mit {'|'.join(RATE_LIMIT_AUS)}") from fehler
    return wert


def ist_lockerer(wert: str, vorgabe: str) -> bool:
    """Erlaubt die Grenze ``wert`` in einem Fenster der ``vorgabe`` mehr Anfragen als diese?
    (Paket 19, Review Punkt 7: das Studio kann den Betreiber-Schutz ``RATE_LIMIT_CHAT`` lockern —
    das soll im Log stehen.) ``off`` ist lockerer als jede Grenze; ist die Vorgabe aus, ist
    nichts lockerer. Je Fenster der Vorgabe zählt das strengste Fenster von ``wert``: ein
    kürzeres wird auf die Fensterlänge hochgerechnet, ein längeres deckelt mit seiner Zahl."""
    if vorgabe.strip().lower() in RATE_LIMIT_AUS:
        return False
    if wert.strip().lower() in RATE_LIMIT_AUS:
        return True
    eigene = [(g.amount, g.get_expiry()) for g in parse_many(wert)]
    for menge, sekunden in ((g.amount, g.get_expiry()) for g in parse_many(vorgabe)):
        erlaubt = min(m * (sekunden // s) if s <= sekunden else m for m, s in eigene)
        if erlaubt > menge:
            return True
    return False
