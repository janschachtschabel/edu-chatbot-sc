"""``TurnContext`` — der typisierte Zustand eines Chat-Turns (LangGraph-State).

In der ALT-App wandern die Turn-Daten als lange Tupel zwischen den Phasen-
Funktionen von ``_chat_impl`` (``app/routers/chat_turn_setup.py`` +
``chat.py``). NEU trägt ein einziges Zustands-Objekt diese Felder; die
Graph-Nodes (P4-2..P4-6) lesen/schreiben Teilmengen davon in-place. Der Bau des
LangGraph-Graphen selbst (Kanten, Checkpointer) ist P4-6 — dieses Modul bleibt
bewusst framework-frei (kein ``langgraph``-Import), damit der Zustand pur und
isoliert testbar ist.

Feld-Herkunft (ALT-Phasen-Signaturen):
- ``_setup_turn`` → ``(session_state, history, env, client_ip, ChatResponse|None)``
- ``_classify_and_merge`` (21-Tupel) → safety, classification, memories, signals,
  signal_history, new_state, context_snapshot, policy, usage-Accumulator, …
- ``_produce_answer`` / ``_assemble_cards_and_qrs`` → response_text, cards,
  quick_replies, page_action, pagination, web_links, …

Bewusst VERTAGT (kein Produzent/Typ vor der jeweiligen Slice — hier zu
deklarieren wäre ``Any``-Spekulation ohne Konsumenten; jede Slice fügt ihre
Felder mit eigenem Test hinzu):
- Routing (P4-4, unten deklariert): ``winner_id``/``winner_label``,
  ``pattern_output``, ``scores``, ``eliminated``, ``trans_check`` + RAG-Whitelist
  (``rag_config``, ``available_rag_areas``, ``memory_context``).
- Fast-Path-Tail (4-5, unten deklariert): ``lp_routed``/``canvas_routed``,
  ``canvas_payload``, ``canvas_forced_quick_replies``, ``tools_called``,
  ``effective_pattern_id``/``label``, ``qr_mode``/``qr_max``/``qr_spec_task``,
  ``fp_response_text``/``fp_wlo_cards_raw``. LP- und Canvas-Fast-Path setzen sie;
  der spekulative MCP-Prefetch (``qr_spec_task`` als Task) und der Tool-Loop
  (``tools_called``-Vollbefüllung) folgen als eigene Slices.
Prefetch/Tools-Felder (``spec_task`` …) sind seit R4d unten deklariert — der
``merge``-Node produziert sie (``run_speculative_prefetch``), der ``respond``-Node
konsumiert sie.

Terminal-Felder (``response_outcomes``, ``final_confidence``) sind nicht separat
deklariert — sie sind bereits über ``debug.outcomes`` bzw. ``debug.confidence``
(``DebugInfo``) abbildbar.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from boerdi.api.schemas import (
    ChatRequest,
    ChatResponse,
    ClassificationResult,
    ContextSnapshot,
    DebugInfo,
    PaginationInfo,
    PolicyDecision,
    SafetyDecision,
    WebLink,
    WloCard,
)
from boerdi.obs.usage import new_accumulator


class TurnContext(BaseModel):
    """Veränderlicher Turn-Zustand, den die Graph-Nodes durchreichen.

    Konstruierbar allein aus ``req``; alle übrigen Felder haben Defaults, sodass
    frühe Nodes sie schrittweise befüllen. Bewusst mutierbar (pydantic-Default,
    kein ``frozen``): ALT mutiert ``session_state``/``classification``/``safety``
    in-place, und LangGraph-Nodes aktualisieren einzelne Felder pro Phase.
    """

    # ── Input & Session (preflight/setup — 4-2) ─────────────────────────
    req: ChatRequest
    # Laufzeit-Env-Dict aus dem Setup (Repo-URLs, Flags, Config-Schnappschüsse
    # …) — ALT ``env: dict``; Inhalt befüllt der Setup-Node, nicht dieser Vertrag.
    env: dict[str, Any] = Field(default_factory=dict)
    client_ip: str = ""
    # Arbeits-Session-State als Dict (ALT-Parität: wird in-place mutiert). Der
    # DB-/Memory-Rand konvertiert gegen ``SessionState`` beim Laden/Speichern.
    session_state: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)
    # Früh-Ausstieg (Tour/Kontext-Begrüßung/Preflight) → im Graphen eine
    # bedingte Kante. Gesetzt ⇒ Assessment/Route/Respond werden übersprungen.
    early_response: ChatResponse | None = None

    # ── Assessment (Parallel-Gruppe safety∥classify∥memory + Merge — 4-3) ──
    safety: SafetyDecision | None = None
    classification: ClassificationResult | None = None
    # Session-Erinnerungen als {key, value, memory_type}-Dicts — ALT-Parität:
    # `get_memory` liefert Dicts, die die Pipeline unverändert weiterreicht.
    memories: list[dict[str, Any]] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    signal_history: list[str] = Field(default_factory=list)
    state_id: str = "S1"
    context_snapshot: ContextSnapshot | None = None
    policy: PolicyDecision | None = None
    # Token-Cost-Accumulator (ein Dict pro Turn). ALT legt ihn zu Turn-Beginn in
    # ``_setup_turn`` an; NEUs Gegenstück dieser lokalen Variable ist DIESES Feld,
    # nicht ein Seiteneffekt des setup-Nodes — so bringt jeder Zug ihn mit, auch
    # der in einem Node-Test direkt konstruierte. Ein leeres Dict ist hier kein
    # harmloser Default: ``add_usage`` kehrt bei falsy ``acc`` still zurück, d.h.
    # ohne Merkposten bucht niemand und ``debug.token_usage`` bleibt leer.
    usage: dict[str, Any] = Field(default_factory=new_accumulator)

    # ── Speculative MCP prefetch (merge produziert, respond konsumiert — P5) ──
    # ALT ``_launch_speculative_prefetch``-Ausgabe (``SpeculativePrefetch``-Tupel):
    # der ``merge``-Node startet je nach Intent/Entities MCP-Such-Tasks im
    # Hintergrund; der ``respond``-Node awaitet + injiziert sie in
    # ``generate_response`` (kein zweiter Tool-Round-Trip). ``spec_task`` und die
    # ``extra_spec_tasks`` sind laufende ``asyncio.Task``.
    spec_task: Any = None
    spec_tool_name: str | None = None
    spec_tool_args: dict[str, Any] | None = None
    spec_query: str = ""
    extra_spec_tasks: list[Any] = Field(default_factory=list)
    spec_is_search_all: bool = False
    search_all_extras: list[dict[str, Any]] = Field(default_factory=list)

    # ── Routing-Entscheidung (pattern/policy/state — 4-4) ──────────────────
    # ``policy`` steht oben (Assessment): ALT setzt sie im Setup, noch vor der
    # Pattern-Wahl. Der volle ``PatternDef`` wird NICHT gehalten — Downstream
    # braucht nur id/label (Effective-Pattern-Logik, Quality-Logs) + das
    # modulierte ``pattern_output``-Dict (alle phase3-Felder).
    winner_id: str = ""
    winner_label: str = ""
    pattern_output: dict[str, Any] = Field(default_factory=dict)
    scores: dict[str, float] = Field(default_factory=dict)
    eliminated: list[str] = Field(default_factory=list)
    trans_check: dict[str, Any] = Field(default_factory=dict)
    # RAG-Whitelist je Pattern + gerenderter Memory-Kontext (respond/tools lesen
    # sie); ALT bestimmt beides im Kopf von ``_route_pattern``.
    rag_config: dict[str, Any] = Field(default_factory=dict)
    available_rag_areas: list[str] = Field(default_factory=list)
    memory_context: str = ""

    # ── Fast-Path-Tail (Canvas/LP-Fast-Path + Effective-Pattern + QR — 4-5) ──
    # ALT ``_route_pattern``-Tail: ob ein Fast-Path den Turn beantwortet hat, das
    # TATSÄCHLICH ausgeführte Pattern (Fast-Path kann den Engine-Pick
    # überschreiben — Quality-Logs/Inline-Box lesen das effektive), die QR-Policy
    # am effektiven Pattern, und die Fast-Path-Marker, die der Respond-Node statt
    # des Standardpfads nutzt. ``lp_routed``/``canvas_routed`` setzen die beiden
    # Fast-Paths im Route-Node; ``tools_called`` bekommt in P5 zusätzlich die
    # Tool-Loop-Namen. ``qr_spec_task`` ist ein laufender asyncio.Task (LP-
    # Spekulativ-QR, vom LP-Body gestartet) oder None.
    lp_routed: bool = False
    canvas_routed: bool = False
    canvas_payload: dict[str, Any] | None = None
    canvas_forced_quick_replies: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    effective_pattern_id: str = ""
    effective_pattern_label: str = ""
    qr_mode: str | None = None
    qr_max: int | None = None
    qr_spec_task: Any = None
    fp_response_text: str | None = None
    fp_wlo_cards_raw: list[dict[str, Any]] | None = None

    # ── Answer (respond/assemble — 4-5; Form 1:1 wie ``ChatResponse``) ─────
    response_text: str = ""
    # Roh-Karten (MCP-Envelope-Dicts) aus ``respond``/``generate_response`` bzw.
    # dem Fast-Path — der ``turn_assembly``-Slice (P20-24) normalisiert sie erst
    # zu ``cards`` (``WloCard``). Standard-Pfad-Gegenstück zu ``fp_wlo_cards_raw``.
    wlo_cards_raw: list[dict[str, Any]] = Field(default_factory=list)
    cards: list[WloCard] = Field(default_factory=list)
    quick_replies: list[str] = Field(default_factory=list)
    page_action: dict[str, Any] | None = None
    pagination: PaginationInfo | None = None
    web_links: list[WebLink] = Field(default_factory=list)

    # ── Observability (turnweit; trägt outcomes/confidence/trace) ──────────
    debug: DebugInfo = Field(default_factory=DebugInfo)

    # ── Terminal-Output (persist-Node P29-33 baut die fertige ChatResponse) ──
    # Normalpfad-Antwort; der Endpoint (R4f) gibt ``early_response or response``
    # zurück. Getrennt von ``early_response`` (Preflight/Tour/Fast-Path-Früh-
    # ausstieg), damit beide Pfade unterscheidbar bleiben.
    response: ChatResponse | None = None
