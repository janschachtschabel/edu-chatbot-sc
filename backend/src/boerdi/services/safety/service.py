"""Safety orchestrator (T-12/T-19) — multi-stage risk assessment that runs BEFORE
pattern selection and tool execution, independent of persona/pattern logic so it
cannot be bypassed. Byte-parity port of ALT ``safety_service.assess_safety`` plus
the preset/gating helpers and the moderation/legal merge logic.

Stages (in the sibling modules): 1. regex gate (always) · 2. moderation
(``litellm.amoderation``) · 3. legal classifier (``services.llm``). Escalation is
configured in ``01-base/safety-config`` under ``presets`` / ``escalation``. Every
LLM stage may fail; the regex gate remains the hard backstop.

Deviation vs ALT (documented in ``docs/plans/p3-safety-contract.md``): the single
165-line ``assess_safety`` is split — the three post-gather merges live in
``_merge_moderation`` / ``_merge_legal`` / ``_maybe_downgrade`` (behaviour-preserving
extraction), and a dead ``if ...: pass`` no-op in ALT's injection stage is dropped.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from boerdi.api.schemas import SafetyDecision
from boerdi.services.config_loader import load_safety_config
from boerdi.services.safety import legal, moderation
from boerdi.services.safety.regex_gate import (
    INJECTION_PATTERNS,
    LEGAL_TRIGGER_PATTERNS,
    regex_gate,
)

logger = logging.getLogger(__name__)

# OpenAI moderation category → deutsches Rechtsfeld (ALT llm merge map).
_CAT_TO_LEGAL = {
    "self_harm": "jugendschutz",
    "self_harm/intent": "jugendschutz",
    "sexual/minors": "jugendschutz",
    "violence": "strafrecht",
    "violence/graphic": "strafrecht",
    "hate": "strafrecht",
    "hate/threatening": "strafrecht",
    "harassment": "persoenlichkeitsrechte",
    "harassment/threatening": "persoenlichkeitsrechte",
    "illicit": "strafrecht",
    "illicit/violent": "strafrecht",
}


def _resolve_preset(cfg: dict) -> dict:
    """Resolve active preset from security_level. Falls back to legacy escalation."""
    level = (cfg.get("security_level") or "standard").lower()
    # Backwards-compat: "basic" was renamed/merged into "standard"
    if level == "basic":
        level = "standard"
    presets = cfg.get("presets") or {}
    preset = presets.get(level)
    if preset:
        return {
            "level": level,
            "moderation": preset.get("moderation", "smart"),
            "legal_classifier": preset.get("legal_classifier", "smart"),
            "prompt_injection": bool(preset.get("prompt_injection", False)),
            "legal_trigger_override": bool(preset.get("legal_trigger_override", False)),
            "threshold_multiplier": float(preset.get("threshold_multiplier", 1.0)),
            "double_check": bool(preset.get("double_check", False)),
        }
    # Legacy fallback
    esc = cfg.get("escalation", {}) or {}
    mode = esc.get("mode", "off")
    return {
        "level": "legacy",
        "moderation": "always" if mode == "always" else ("smart" if mode == "smart" else "never"),
        "legal_classifier": "smart" if esc.get("legal_classifier", True) else "never",
        "prompt_injection": False,
        "legal_trigger_override": True,
        "threshold_multiplier": 1.0,
        "double_check": False,
    }


def _stage_should_run(stage_mode: str, current_risk: str) -> bool:
    if stage_mode == "always":
        return True
    if stage_mode == "smart":
        return current_risk in ("medium", "high")
    return False


def _merge_moderation(
    decision: SafetyDecision, openai_data: dict[str, Any], cfg: dict, esc: dict, tmul: float
) -> None:
    """Fold omni-moderation scores into ``decision`` (mutates in place):
    threshold-flag categories, map to legal fields, and hard-block → high with
    the crisis/threat pattern (self-harm always wins). ALT llm merge, lines 374-430."""
    thresholds = esc.get("thresholds", {}) or {}
    hard_blocks = set(esc.get("hard_block_categories", []) or [])
    flagged_now: list[str] = []
    if openai_data:
        scores = openai_data.get("scores", {})
        for cat, score in scores.items():
            decision.categories[cat] = score
            thr = float(thresholds.get(cat, 0.95)) * tmul
            if score >= thr:
                flagged_now.append(cat)

    decision.flagged_categories = flagged_now

    for cat in flagged_now:
        mapped = _CAT_TO_LEGAL.get(cat)
        if mapped and mapped not in decision.legal_flags:
            decision.legal_flags.append(mapped)

    # Hard-Block-Kategorien sofort high. Pattern-Wahl: Selbstgefährdung hat
    # immer Vorrang (M01), sonst Drohungs-Kategorien → M02, Rest → M01.
    hard_hit = [c for c in flagged_now if c in hard_blocks]
    if hard_hit:
        decision.risk_level = "high"
        threat_cats = {"hate/threatening", "harassment/threatening"}
        crisis_cats = {"self_harm", "self_harm/intent", "sexual/minors"}
        if set(hard_hit) & crisis_cats:
            decision.enforced_pattern = cfg.get("crisis_pattern", "M01")
        elif set(hard_hit) & threat_cats:
            decision.enforced_pattern = cfg.get("threat_pattern", "M02")
        else:
            decision.enforced_pattern = cfg.get("crisis_pattern", "M01")
        for t in cfg.get("crisis_blocked_tools", []):
            if t not in decision.blocked_tools:
                decision.blocked_tools.append(t)
        decision.reasons.append(f"hard_block:{','.join(hard_hit)}")


def _merge_legal(
    decision: SafetyDecision, legal_data: dict[str, dict], esc: dict, tmul: float
) -> None:
    """Fold the LLM legal-classifier risks into ``decision`` (mutates in place):
    flag at ``flag`` threshold, escalate strafrecht/jugendschutz to high at
    ``high``, otherwise lift low→medium. ALT llm merge, lines 432-449."""
    legal_thr = esc.get("legal_thresholds", {}) or {}
    flag_thr = float(legal_thr.get("flag", 0.4)) * tmul
    high_thr = float(legal_thr.get("high", 0.7)) * tmul
    if not legal_data:
        return
    for cat, entry in legal_data.items():
        risk = entry.get("risk", 0.0)
        reason = entry.get("reason", "")[:80]
        decision.categories[f"legal:{cat}"] = risk
        if risk >= flag_thr:
            if cat not in decision.legal_flags:
                decision.legal_flags.append(cat)
            if (
                risk >= high_thr
                and cat in ("strafrecht", "jugendschutz")
                and decision.risk_level != "high"
            ):
                decision.risk_level = "high"
                decision.reasons.append(f"legal:{cat} {risk:.2f} ({reason})")
            elif decision.risk_level == "low":
                decision.risk_level = "medium"
                decision.reasons.append(f"legal:{cat} {risk:.2f}")


def _maybe_downgrade(decision: SafetyDecision, esc: dict, legal_data: dict[str, dict]) -> None:
    """Downgrade a lone medium back to low when both LLM stages came back clean
    (keeps prompt-injection and crisis hits at medium). ALT llm merge, lines 451-464."""
    if (
        esc.get("downgrade_false_positives", True)
        and decision.risk_level == "medium"
        and not decision.flagged_categories
        and not any(e.get("risk", 0) >= 0.5 for e in legal_data.values())
        and "crisis_signal_detected" not in decision.reasons
        and "possible_prompt_injection" not in decision.reasons
    ):
        decision.risk_level = "low"
        decision.reasons.append("downgraded_by_llm_check")


async def assess_safety(message: str, signals: list[str] | None = None) -> SafetyDecision:
    """Multi-stage safety assessment.

    Always runs the regex gate. Escalates to the LLM stages per the active
    preset. Failure-mode: every LLM stage may fail; the regex gate is the hard
    backstop.
    """
    signals = signals or []
    decision = regex_gate(message, signals)

    # Bereits hartes High aus Regex → nicht weiter eskalieren, sofort blocken.
    if decision.risk_level == "high":
        return decision

    cfg = load_safety_config()
    preset = _resolve_preset(cfg)
    esc = cfg.get("escalation", {}) or {}
    decision.reasons.append(f"level:{preset['level']}")
    msg_lower = (message or "").lower()

    # Stage: Prompt-Injection (regex, optional per preset).
    if preset["prompt_injection"]:
        decision.stages_run.append("prompt_injection")
        for pat in INJECTION_PATTERNS:
            if re.search(pat, msg_lower):
                if decision.risk_level == "low":
                    decision.risk_level = "medium"
                decision.reasons.append("possible_prompt_injection")
                break

    # Decide which LLM stages to run.
    run_moderation = _stage_should_run(preset["moderation"], decision.risk_level)
    run_legal = _stage_should_run(preset["legal_classifier"], decision.risk_level)

    # Heuristik-Override: smart-Mode + Triggerwort → Legal trotzdem laufen lassen
    # (nur wenn das Preset es via legal_trigger_override erlaubt).
    if (
        preset.get("legal_trigger_override")
        and preset["legal_classifier"] == "smart"
        and not run_legal
        and any(re.search(p, msg_lower) for p in LEGAL_TRIGGER_PATTERNS)
    ):
        run_legal = True
        decision.reasons.append("legal_trigger_match")

    tasks: list[tuple[str, Any]] = []
    if run_moderation:
        tasks.append(("openai", moderation.moderate(message)))
        decision.stages_run.append("openai_moderation")
    if run_legal:
        tasks.append(("legal", legal.classify_legal(message)))
        decision.stages_run.append("llm_legal")

    if not tasks:
        return decision

    decision.escalated = True
    _t0 = time.perf_counter()
    results = await asyncio.gather(*(t[1] for t in tasks), return_exceptions=True)
    _elapsed_ms = (time.perf_counter() - _t0) * 1000
    logger.info(
        "safety stages=%s level=%s took %.0fms",
        ",".join(n for n, _ in tasks), preset["level"], _elapsed_ms,
    )

    openai_data: dict[str, Any] = {}
    legal_data: dict[str, dict] = {}
    for (name, _), res in zip(tasks, results, strict=True):
        if isinstance(res, Exception):
            continue
        if name == "openai":
            openai_data = res or {}
        elif name == "legal":
            legal_data = res or {}

    tmul = preset.get("threshold_multiplier", 1.0)
    _merge_moderation(decision, openai_data, cfg, esc, tmul)
    _merge_legal(decision, legal_data, esc, tmul)
    _maybe_downgrade(decision, esc, legal_data)
    return decision
