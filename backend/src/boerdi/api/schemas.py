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

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

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
    AuthStatusArgs,
    CollectionContentsArgs,
    CollectionStatsArgs,
    CollectionTreeArgs,
    CompendiumTextArgs,
    ContentSearchArgs,
    HealthCheckArgs,
    LookupVocabularyArgs,
    NodeBreadcrumbArgs,
    NodeCollectionsArgs,
    NodeDetailsArgs,
    NodesDetailsArgs,
    PublishersLookupArgs,
    RelatedContentArgs,
    SearchTopicPagesArgs,
    SearchWloArgs,
    SkillGetArgs,
    SkillRegistryArgs,
    SkillSearchArgs,
    SubjectPortalsArgs,
    UrlTextArgs,
    WikipediaSummaryArgs,
    WithinCollectionArgs,
)
from boerdi.api.schemas_mcp_curation import (
    CollectionCreateArgs,
    CollectionMembershipArgs,
    CollectionRenameArgs,
    CompendiumUpdateArgs,
    ContentCreateArgs,
    ContentSubmitArgs,
    ContentUpdateArgs,
    MetadataSuggestArgs,
    MetadataSuggestion,
    NodeOnlyArgs,
    SuggestionDecideArgs,
    SuggestionsListArgs,
    TopicPageSetArgs,
)

__all__ = [
    "ChatRequest", "ChatResponse", "ClassificationResult", "CollectionContentsArgs",
    "ContentSearchArgs",
    "CollectionCreateArgs", "CollectionMembershipArgs", "CollectionRenameArgs",
    "CollectionStatsArgs", "CollectionTreeArgs", "CompendiumTextArgs",
    "CompendiumUpdateArgs", "ConfigFile", "ContentCreateArgs", "ContentSubmitArgs",
    "ContentUpdateArgs",
    "ContextSnapshot", "DebugInfo", "Environment", "MAX_RESULT_SCHEMA_CHARS",
    "MetadataSuggestArgs", "MetadataSuggestion", "NodeOnlyArgs",
    "SuggestionDecideArgs", "SuggestionsListArgs", "TopicPageSetArgs",
    "HealthCheckArgs", "InlineDocument", "LookupVocabularyArgs", "MemoryEntry",
    "NodeBreadcrumbArgs", "NodeCollectionsArgs", "NodeDetailsArgs", "NodesDetailsArgs",
    "PageAction",
    "PaginationInfo", "PolicyDecision", "PublishersLookupArgs", "QueryMetaEntry",
    "RagDocument", "RagQuery", "RagResult",
    "SafetyDecision", "SearchTopicPagesArgs", "SearchWloArgs", "SessionState",
    "SkillGetArgs", "SkillRegistryArgs", "SkillSearchArgs",
    # H5 (2026-08-10): offenes Netz + Anmeldestatus.
    "AuthStatusArgs", "UrlTextArgs", "WikipediaSummaryArgs",
    "RelatedContentArgs", "SubjectPortalsArgs", "SwimlaneBox", "ToolOutcome",
    "TopicPageView", "TraceEntry", "WithinCollectionArgs",
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


#: Zeichendeckel des ``result_schema`` (serialisiert).
#:
#: Das Schema reist WÖRTLICH in die Parameter von ``submit_result`` und damit in
#: JEDEN Modellaufruf der Agent-Schleife — bis zu ``engine.agent.max_iterations``
#: (Vorgabe 12) pro Zug. ``/api/chat`` ist der öffentliche Router **ohne
#: Anmeldung**. Der Zwilling ``AgentRequest.result_schema`` bleibt bewusst
#: UNGEDECKELT: er sitzt hinter ``require_agent_caller``, seine Aufrufer sind
#: angemeldete Maschinen, und ein Deckel dort bräche einen berechtigten
#: Gastgeber mit großem Schema, ohne eine offene Flanke zu schließen.
#:
#: Warum ABLEHNEN und nicht kürzen — anders als beim Nachbarn ``page_context``,
#: der beim Verbraucher auf eine A4-Seite gekappt wird: ein halbes Schema ist
#: ein ANDERES Schema. Gekürzt bekäme der Gastgeber Ergebnisse in einer Form,
#: die er nie verlangt hat, und hätte keine Möglichkeit, das zu bemerken. Ein
#: 422 sagt es ihm.
#:
#: **200 000 Zeichen seit 2026-08-18** (vorher 10 000, damals dieselbe Grenze
#: wie ``ChatRequest.message``). Diese Kopplung gilt nicht mehr: ``message`` und
#: ``Environment.host_instruction`` haben seit demselben Tag GAR KEINEN Deckel,
#: dieser hier ist der letzte im öffentlichen Chat-Vertrag. Ein echtes
#: Ergebnis-Schema ist ein bis zwei Kilobyte groß — wer 200 000 überschreitet,
#: hat einen Fehler, keinen Wunsch.
MAX_RESULT_SCHEMA_CHARS = 200000


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
    # Erklärt der Gastgeber ein JSON-Schema, bekommt er das Ergebnis des Zuges
    # zusätzlich maschinenlesbar (``ChatResponse.result``) — je Einbau, über das
    # Attribut ``result-schema`` (Nutzer-Entscheid 2026-08-14). Wirkt NUR in der
    # Agent-Schleife und kostet dort einen zusätzlichen Modellzug (2–9 s
    # gemessen); deshalb opt-in und nicht die Vorgabe. Das Schema reist wörtlich
    # in die Parameter von ``submit_result``: die Form bestimmt der Gastgeber,
    # unser Code muss sie nicht kennen.
    #
    # ES IST EINE PROMPT-FLÄCHE, keine reine Datenstruktur: die ``description``-
    # und ``title``-Werte eines JSON-Schemas sind Fließtext, den das Modell
    # liest — und sie stehen in der WERKZEUG-Ebene, nicht in der Nutzerzeile.
    # Die Sicherheitsprüfung sieht nur ``message`` (``assess.py``), dieses Feld
    # also nicht. Wer es füllt, schreibt in den Prompt seiner eigenen Sitzung;
    # der Deckel unten begrenzt, wie viel.
    result_schema: dict[str, Any] | None = None

    @field_validator("result_schema")
    @classmethod
    def _schema_gedeckelt(cls, wert: dict[str, Any] | None) -> dict[str, Any] | None:
        if wert is None:
            return wert
        laenge = len(json.dumps(wert, ensure_ascii=False))
        if laenge > MAX_RESULT_SCHEMA_CHARS:
            raise ValueError(
                f"result_schema ist {laenge} Zeichen lang, erlaubt sind "
                f"{MAX_RESULT_SCHEMA_CHARS}")
        return wert

    # G1 — der Rahmen, den die einbettende Anwendung diesem Zug mitgibt: „so bist
    # du hier zu verstehen". Unsichtbar im Verlauf, weil es KEIN Zug ist, sondern
    # Kontext — dieselbe Sorte Wissen wie der Seitenblock daneben. Wirkt in allen
    # drei Maschinen, weil beide Prompt-Wege denselben Block einsetzen
    # (``domain/host_instruction``).
    #
    # Wie ``result_schema`` geht dieses Feld NICHT durch die Sicherheitsprüfung —
    # die sieht nur ``message`` (``assess.py``). Wer es füllt, schreibt in den
    # Prompt seiner eigenen Sitzung; der Block selbst sagt dem Modell, dass eine
    # Regel über der Anweisung steht.
    #
    # OHNE Zeichendeckel (Nutzer-Entscheid 2026-08-18) — Begründung in
    # ``domain/host_instruction``. Das Rate-Limit begrenzt den Missbrauch, nicht
    # dieses Feld; ``page_context`` daneben war ohnehin nie gedeckelt.
    host_instruction: str | None = None

    # N3/N4 (2026-08-18): darf der Master-Skill fuer DIESE Einbettung gelten?
    # ``None`` heisst „die Anwendung sagt nichts" — dann gilt
    # ``MASTER_SKILL_ENABLED``. Ein Wert uebersteuert die Vorgabe in BEIDE
    # Richtungen: ein Gastgeber kennt seinen Anwendungsfall besser als eine
    # globale Variable. Rangfolge steht in ``services/master_skill.ist_aktiv``.
    master_skill: bool | None = None

    # O-A/B/C (2026-08-18): was die Einbettung ANZEIGT und ERLAUBT. Alle drei
    # ``None``/leer = Vorgabe, also das heutige Verhalten.
    #
    # ``inline_result_grouping`` war bis dahin ein REINES Frontend-Attribut; das
    # Modell erfuhr nie, dass diese Anwendung Treffer nicht gruppiert, und
    # verwies auf Boxen, die es dort nicht gibt. Jetzt erreicht es den Prompt
    # (``domain/host_capabilities``).
    #
    # Ein ``show_cards`` steht hier BEWUSST NICHT: das gleichnamige Attribut
    # waehlt nur zwischen zwei Darstellungen (Kacheln oder Textlinks), es
    # schaltet die Treffer nicht ab. Begruendung im Kopf von
    # ``domain/host_capabilities``.
    inline_result_grouping: bool | None = None
    # read-only | curate | full. Benannte Modi statt freier Werkzeugliste: eine
    # Umbenennung im MCP wuerde sonst still die Rechte einer Einbettung aendern.
    tool_mode: str | None = None
    # Vom Gastgeber HART gesetzte Schnellantworten fuer DIESEN Zug. Der Chip-Text
    # IST die Nachricht, die beim Klick gesendet wird — deshalb wird nichts
    # gekuerzt; zu viele werden abgeschnitten (Anzahl, nicht Text).
    forced_quick_replies: list[str] = Field(default_factory=list)
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
    # Ohne Deckel (Nutzer-Entscheid 2026-08-18; vorher 10000). Eine
    # Gastanwendung reicht hier ganze Seiteninhalte herein.
    message: str
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


class PreparedWriteOut(BaseModel):
    """Eine bestätigte Änderung, beschrieben statt ausgeführt (E3).

    Im eingebetteten Betrieb schreibt der MCP-Server nicht selbst; die Anfrage
    wird in der Repository-Seite abgesetzt, mit der dort bestehenden Anmeldung —
    so trägt die Änderung den Namen der Person und nicht den eines Sammelkontos.
    Gelesen und geprüft wird sie in ``domain/prepared_write.py``; die
    Erlaubnisliste, welcher Aufruf überhaupt abgesetzt werden darf, liegt im
    Widget, das ihn absetzt (E4).

    **Ein eigenes Feld und kein weiterer ``page_action``-Typ.** ``page_action``
    ist ein einzelner Platz und schon von Canvas/Guide belegt — ein Zug, der eine
    Leinwand öffnet *und* eine Änderung vorbereitet, überschriebe sich selbst.
    """

    method: str
    #: Pfad ab der Herkunft; die Seite setzt ihre eigene davor.
    path: str
    body: str | None = None
    #: Was dem Menschen zu sagen ist, wenn das Repositorium zugestimmt hat.
    done_message: str = ""


class ChatResponse(BaseModel):
    session_id: str
    content: str
    cards: list[WloCard] = Field(default_factory=list)
    follow_up: str = "none"
    quick_replies: list[str] = Field(default_factory=list)
    debug: DebugInfo = Field(default_factory=DebugInfo)
    page_action: dict[str, Any] | None = None
    # Maschinenlesbares Ergebnis des Zuges — nur wenn der Gastgeber ein
    # ``Environment.result_schema`` erklärt hat UND die Agent-Schleife über
    # ``submit_result`` geendet ist. ``None`` ist der Normalfall: „Hallo" ergibt
    # kein Ergebnis, und eine Unterhaltung ist kein Auftrag.
    result: dict[str, Any] | None = None
    # Warum der Lauf endete (``submit`` | ``text`` | ``deadline`` | …). Gehört
    # zur Antwort und nicht ins Protokoll: ein an der Frist abgeschnittener Lauf
    # sähe von außen sonst aus wie einer, der fertig geworden ist. Leer, wenn
    # der Zug nicht über die Agent-Schleife lief.
    result_stop_reason: str = ""
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
    # E3 — im eingebetteten Betrieb: die bestätigte Änderung als *beschriebene*
    # Anfrage, die das Widget mit der Anmeldung der Seite absetzt. None im
    # Normalbetrieb, in dem der MCP-Server selbst schreibt.
    prepared_write: PreparedWriteOut | None = None


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
