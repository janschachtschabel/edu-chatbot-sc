"""Observability/decision models (DebugInfo cluster) — ported 1:1 from ALT
``app/models/schemas.py``. Part of the facade ``boerdi.api.schemas``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolOutcome(BaseModel):
    """Outcome of a tool call — separate from final content (T-23/24).

    Tracks what happened with a tool call beyond the raw result text:
    success/error/empty status, error messages, item counts, latency.
    Used to feedback into Confidence (T-25) and State (T-27).
    """
    tool: str = ""
    status: str = "success"  # success | empty | error | timeout
    item_count: int = 0
    error: str = ""
    latency_ms: int = 0


class PolicyDecision(BaseModel):
    """Policy layer decision (T-13/14).

    Org/regulatory policy gating that runs alongside Safety. Distinguishes
    between hard blocks (required by policy) and soft warnings.
    """
    allowed: bool = True
    blocked_tools: list[str] = Field(default_factory=list)
    required_disclaimers: list[str] = Field(default_factory=list)
    matched_rules: list[str] = Field(default_factory=list)


class ContextSnapshot(BaseModel):
    """Context layer snapshot (T-04/05).

    Formalised conversation/session context: aggregated entities, relevant
    history slice, environment, memory keys. Drives pattern fit + LLM prompts.
    """
    page: str = ""
    device: str = ""
    locale: str = ""
    session_duration: int = 0
    turn_count: int = 0
    entities: dict[str, Any] = Field(default_factory=dict)
    recent_signals: list[str] = Field(default_factory=list)
    memory_keys: list[str] = Field(default_factory=list)
    last_intent: str = ""
    last_state: str = ""


class TraceEntry(BaseModel):
    """Single trace step (T-29/30/31).

    Observability records for each layer transition: when, what, outcome.
    Built up over the request lifecycle and shipped in DebugInfo.
    """
    # safety | policy | classify | context | pattern | tools | response | feedback
    step: str = ""
    label: str = ""             # human-readable description
    duration_ms: int = 0
    data: dict[str, Any] = Field(default_factory=dict)


class SafetyDecision(BaseModel):
    """Safety layer decision (T-12/19).

    Risk-based gating that can block tools or enforce specific patterns
    independently of pattern selection.
    """
    risk_level: str = "low"  # low | medium | high
    blocked_tools: list[str] = Field(default_factory=list)
    enforced_pattern: str = ""
    reasons: list[str] = Field(default_factory=list)
    # Multi-stage details
    stages_run: list[str] = Field(default_factory=list)  # regex | openai_moderation | llm_legal
    categories: dict[str, float] = Field(default_factory=dict)  # cat → score
    flagged_categories: list[str] = Field(default_factory=list)
    # strafrecht | jugendschutz | persoenlichkeit | datenschutz
    legal_flags: list[str] = Field(default_factory=list)
    escalated: bool = False  # True if any LLM stage was invoked


class DebugInfo(BaseModel):
    persona: str = ""
    intent: str = ""
    state: str = ""
    turn_type: str = ""  # initial | follow_up | topic_switch | correction | clarification
    signals: list[str] = Field(default_factory=list)
    pattern: str = ""
    entities: dict[str, Any] = Field(default_factory=dict)
    tools_called: list[str] = Field(default_factory=list)
    # Welle E v4 (2026-05-25): Phase 1 (Gate) + Phase 2 (Score) entfernt.
    # ``phase1_eliminated`` ist immer leer, ``phase2_scores`` enthält nur noch
    # {winner.id: 1.0} (Backward-Compat-Form für Studio-Trace + Eval).
    phase1_eliminated: list[str] = Field(default_factory=list)
    phase2_scores: dict[str, float] = Field(default_factory=dict)
    phase3_modulations: dict[str, Any] = Field(default_factory=dict)
    # NEW (Triple-Schema v2)
    outcomes: list[ToolOutcome] = Field(default_factory=list)
    safety: SafetyDecision | None = None
    confidence: float = 1.0  # final confidence after all adjustments
    policy: PolicyDecision | None = None
    context: ContextSnapshot | None = None
    trace: list[TraceEntry] = Field(default_factory=list)
    # NEW (Phase 1, Pattern-Hint Shadow-Mode):
    #   pattern_id_hint   = vom LLM-Klassifikator vorgeschlagenes Pattern
    #   pattern_reasoning = LLM-Begründung (1-2 Sätze)
    #   llm_engine_match  = bool — stimmt LLM-Hint mit Engine-Wahl überein?
    # Pattern-Engine bleibt authoritativ; Felder sind reine Mess-Telemetrie.
    pattern_id_hint: str | None = None
    pattern_reasoning: str | None = None
    llm_engine_match: bool | None = None
    # Token-Cost-Tracking (Phase A2) — aggregiert über ALLE LLM-Calls eines
    # Turns (Klassifikator + Tool-Loop + Response-Generierung). Ermöglicht
    # Cost-Analytics, Cache-Hit-Rate-Monitoring und Modell-Kosten-Vergleich.
    # Format: {"prompt_tokens": int, "completion_tokens": int,
    #          "cached_tokens": int, "calls": int,
    #          "models": {"<model_name>": {"prompt": …, "completion": …, …}}}
    token_usage: dict[str, Any] = Field(default_factory=dict)
