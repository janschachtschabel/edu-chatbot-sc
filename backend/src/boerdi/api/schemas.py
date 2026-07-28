"""Pydantic models for the boerdi-chat API — ported 1:1 from ALT
``badboerdi/backend/app/models/schemas.py`` (P0-5, spec §5.1).

Facade module: ALT exposed every model from one file; here the models are
split by responsibility (≤300-line rule) but re-exported so imports stay
``from boerdi.api.schemas import <Model>``:

- schemas_cards.py  — WloCard, QueryMetaEntry, PaginationInfo, WebLink,
                      SwimlaneBox, TopicPageView
- schemas_inline.py — InlineDocument
- schemas_debug.py  — ToolOutcome, PolicyDecision, ContextSnapshot,
                      TraceEntry, SafetyDecision, DebugInfo
- schemas_mcp.py    — MCP tool-argument models (spec §5.2)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from boerdi.api.schemas_cards import (
    PaginationInfo,
    QueryMetaEntry,
    SwimlaneBox,
    TopicPageView,
    WebLink,
    WloCard,
)
from boerdi.api.schemas_debug import (
    ContextSnapshot,
    DebugInfo,
    PolicyDecision,
    SafetyDecision,
    ToolOutcome,
    TraceEntry,
)
from boerdi.api.schemas_inline import InlineDocument
from boerdi.api.schemas_mcp import (
    CollectionContentsArgs,
    CollectionTreeArgs,
    HealthCheckArgs,
    LookupVocabularyArgs,
    NodeDetailsArgs,
    NodesDetailsArgs,
    SearchTopicPagesArgs,
    SearchWloArgs,
    SubjectPortalsArgs,
)

__all__ = [
    "ChatRequest", "ChatResponse", "ClassificationResult", "CollectionContentsArgs",
    "CollectionTreeArgs", "ConfigFile", "ContextSnapshot", "DebugInfo", "Environment",
    "HealthCheckArgs", "InlineDocument", "LookupVocabularyArgs", "MemoryEntry",
    "NodeDetailsArgs", "NodesDetailsArgs", "PageAction", "PaginationInfo",
    "PolicyDecision", "QueryMetaEntry", "RagDocument", "RagQuery", "RagResult",
    "SafetyDecision", "SearchTopicPagesArgs", "SearchWloArgs", "SessionState",
    "SubjectPortalsArgs", "SwimlaneBox", "ToolOutcome", "TopicPageView", "TraceEntry",
    "WebLink", "WloCard",
]


# ── Classification result (validated LLM output) ──────────────────
class ClassificationResult(BaseModel):
    """Validated output from LLM classification (the 7 input dimensions).

    `pattern_id_hint` is an *advisory* field set by the LLM in addition to
    persona/intent/state. It is purely a measurement signal in Phase 1
    (Shadow-Mode): the deterministic Pattern-Engine still chooses the
    final pattern; we just log how often the LLM-Hint matches the engine
    decision, and how often the Judge agrees with each. Phase 2 may
    promote the hint to a Tie-Breaker for Tight-Race situations.
    """
    persona_id: str = "P-AND"
    persona_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    intent_id: str = "I03"
    intent_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    entities: dict[str, Any] = Field(default_factory=dict)
    turn_type: str = "initial"
    next_state: str = "S1"
    # Phase 1 (Shadow-Mode): LLM-suggested pattern + reasoning.
    # Both optional — old classifier outputs (no pattern hint) still validate.
    pattern_id_hint: str | None = None
    pattern_reasoning: str | None = None
    # Welle E (2026-05-23): LLM-suggested MCP-Tool für Speculative Prefetch.
    # Backend fällt auf Heuristik zurück wenn Hint leer ist oder nicht in der
    # Tool-Whitelist des gewählten Pattern liegt.
    tool_id_hint: str | None = None
    tool_reasoning: str | None = None


# ── Environment (sent by frontend every turn) ──────────────────────
class Environment(BaseModel):
    page: str = "/"
    page_context: dict[str, Any] = Field(default_factory=dict)
    device: str = "desktop"
    locale: str = "de-DE"
    session_duration: int = 0
    referrer: str = "direkt"
    # Webseiten-Guide-Mode (Welle E, 2026-05-23 — Default-Flip): Default True.
    # Das Backend annotiert Karten mit ``guide_url`` (Repo-Render-Link laut
    # 01-base/guide-mode.yaml); der ``host``-Check in guide_mode_service
    # bleibt als Sicherheitsnetz — auf nicht-allowlisteten Hosts fällt das
    # Backend automatisch auf die externe URL zurück. Alte Embeds ohne das
    # Feld bekommen damit automatisch das (gewollte) neue Verhalten.
    guide_mode: bool = True
    # The widget's host hostname (window.location.hostname). Used by the
    # backend allow-list check — guide_url is only attached when this
    # matches one of the configured allowed_hosts patterns.
    host: str = ""
    # DEPRECATED (2026-06-10): keine Wirkung mehr — KI-generierte Inhalte sind
    # immer zugelassen. Bleibt toleriert, damit ältere Embeds, die es noch
    # senden, keinen Validierungsfehler bekommen.
    ai_content_enabled: bool | None = None
    # Webseiten-Tour (geführte Besucherführung). Explizites UI-Signal:
    #   "start" → Tour beginnen (Button "Web-Tour starten")
    #   "tick"  → unsichtbarer Page-Load-Ping (Ankunfts-Erkennung)
    # None / "" → kein Tour-Signal (normale Nachricht). Siehe domain/tour.py.
    tour_action: str | None = None
    # Seitenkontext-Ereignis (2026-07-10). Explizites Signal des Widgets, dass
    # es beim Öffnen/Fortsetzen auf einer erkannten WLO-Seite (Sammlung/Inhalt/
    # Themenseite) steht und eine proaktive Kontext-Begrüßung anfragt:
    #   "context_open" → Kontext-Begrüßungs-Dispatcher
    # None / "" → kein Kontext-Signal (normaler Turn). Der Dispatcher greift NUR
    # bei "context_open"; getippte Rückfragen laufen weiter den Normalfluss.
    page_event: str | None = None


# ── Chat request / response ────────────────────────────────────────
class ChatRequest(BaseModel):
    session_id: str
    message: str = Field(..., max_length=10000)
    environment: Environment = Field(default_factory=Environment)
    # browse_collection | generate_learning_path | curate_collection | None
    action: str | None = None
    action_params: dict[str, Any] = Field(default_factory=dict)  # e.g. {collection_id, title}
    # Snapshot of what the user currently sees in the canvas pane. The
    # frontend sends this with every turn so the classifier / LLM knows
    # the user's visible context (e.g. when asking "was bedeutet hier
    # der Zaehler?" about an on-screen worksheet).
    # {title, material_type, markdown, mode: 'material'|'cards'|'empty', cards_count?}
    canvas_state: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    session_id: str
    content: str
    cards: list[WloCard] = Field(default_factory=list)
    follow_up: str = "none"
    quick_replies: list[str] = Field(default_factory=list)
    debug: DebugInfo = Field(default_factory=DebugInfo)
    page_action: dict[str, Any] | None = None
    pagination: PaginationInfo | None = None
    query_metas: list[QueryMetaEntry] = Field(default_factory=list)
    web_links: list[WebLink] = Field(default_factory=list)
    # Welle E (2026-05-23) — Lernpfade / KI-Materialien / Edits werden als
    # gerahmte Box direkt im Chat-Verlauf gerendert (``InlineDocument``).
    inline_documents: list[InlineDocument] = Field(default_factory=list)
    # M16 — Themenseiten-Inhalte (Schwimmlinien-Boxen). Wenn gesetzt, rendert
    # das Frontend NUR diese Boxen (+ Absprung-Button) statt der normalen
    # Sammlungs-/Inhalts-/Themenseiten-Boxen.
    topic_page: TopicPageView | None = None
    # Echo der aktuellen Display-Regeln (aus 01-base/display-rules.yaml).
    # Frontend stylet Boxen anhand dieses Echo-Blocks ohne Hard-Coding —
    # Änderung im Studio greift damit ohne Frontend-Deploy.
    display_rules: dict[str, Any] = Field(default_factory=dict)
    # Webseiten-Tour-Status. Gesetzt nur bei Tour-Antworten:
    #   {"active": bool, "step": str, "group": str}
    # Das Frontend pflegt damit sein localStorage-Flag (active=false →
    # Flag löschen, keine weiteren Tour-Ticks). None bei Normal-Antworten.
    tour: dict[str, Any] | None = None


# ── Session / Memory ──────────────────────────────────────────────
class SessionState(BaseModel):
    session_id: str
    persona_id: str = ""
    state_id: str = "S1"
    entities: dict[str, Any] = Field(default_factory=dict)
    signal_history: list[str] = Field(default_factory=list)
    turn_count: int = 0
    # 1:1 ALT port; naive-UTC semantics. P1 moves timestamps to Postgres
    # timestamptz — revisit then.
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryEntry(BaseModel):
    session_id: str
    key: str
    value: str
    memory_type: str = "short"  # short | long
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── RAG ───────────────────────────────────────────────────────────
class RagDocument(BaseModel):
    id: str = ""
    area: str = "general"
    title: str = ""
    source: str = ""
    content: str = ""
    chunks: int = 0


class RagQuery(BaseModel):
    query: str
    area: str = "general"
    top_k: int = 3


class RagResult(BaseModel):
    chunk: str
    score: float
    source: str
    area: str


# ── Config / Studio ──────────────────────────────────────────────
class ConfigFile(BaseModel):
    path: str
    content: str
    file_type: str = "markdown"


class PageAction(BaseModel):
    """Action to send back to host page or widget canvas (search results, navigate, etc.).

    Values:
      Host-Page:
        navigate, show_collection, show_results, share_content
      Widget-Canvas (Phase 1):
        canvas_open          payload: {title, material_type, markdown}
        canvas_update        payload: {markdown}
        canvas_show_cards    payload: {cards, query}
        canvas_close         payload: {}
    """
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)
