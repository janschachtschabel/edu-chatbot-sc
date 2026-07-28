"""Safety-Layer — Eskalations-/Merge-Logik von ``service.assess_safety``.

Port von ALT ``test_safety_escalation.py``. Ergänzt ``test_safety_regex_gate``
(Regex-Stufe + Nicht-Eskalations-Pfade). Die LLM-Stufen werden GEMOCKT — nach
dem Modul-Split (3-4) über die Stufenmodule ``moderation.moderate`` /
``legal.classify_legal``, die der Orchestrator per Attribut aufruft — um die
sicherheitskritische Merge-Logik zu prüfen: Moderation-Hard-Block → high +
Pattern-Wahl, Legal-Classifier → high/medium, Downgrade schwacher Treffer,
Trigger-Override.
"""

from __future__ import annotations

import asyncio

from boerdi.services.safety import legal as legal_mod
from boerdi.services.safety import moderation as moderation_mod
from boerdi.services.safety import service as ss

_CFG = {
    "security_level": "max",
    "presets": {"max": {
        "moderation": "always", "legal_classifier": "always",
        "prompt_injection": True, "threshold_multiplier": 1.0,
        "legal_trigger_override": True,
    }},
    "escalation": {
        "thresholds": {
            "self_harm": 0.5, "hate/threatening": 0.5, "violence": 0.5, "harassment": 0.5,
        },
        "hard_block_categories": ["self_harm", "hate/threatening", "violence"],
        "legal_thresholds": {"flag": 0.4, "high": 0.7},
        "downgrade_false_positives": True,
    },
    "crisis_pattern": "M01", "threat_pattern": "M02",
    "crisis_blocked_tools": ["search_wlo_content"],
}


def _run(monkeypatch, message, *, mod=None, legal=None, cfg=None):
    monkeypatch.setattr(ss, "load_safety_config", lambda: dict(cfg or _CFG))

    async def _mod(_m):
        return mod or {}

    async def _legal(_m):
        return legal or {}

    monkeypatch.setattr(moderation_mod, "moderate", _mod)
    monkeypatch.setattr(legal_mod, "classify_legal", _legal)
    return asyncio.run(ss.assess_safety(message))


def test_moderation_hard_block_self_harm_is_m01(monkeypatch):
    d = _run(monkeypatch, "harmlos klingende nachricht", mod={"scores": {"self_harm": 0.9}})
    assert d.risk_level == "high"
    assert d.enforced_pattern == "M01"           # Selbstgefährdung → empathisches Pattern
    assert "jugendschutz" in d.legal_flags       # self_harm → jugendschutz
    assert d.escalated is True
    assert "search_wlo_content" in d.blocked_tools


def test_moderation_hard_block_threat_is_m02(monkeypatch):
    d = _run(monkeypatch, "harmlos", mod={"scores": {"hate/threatening": 0.8}})
    assert d.risk_level == "high"
    assert d.enforced_pattern == "M02"           # Drohung → sachliche Ablehnung
    assert "strafrecht" in d.legal_flags


def test_legal_classifier_high_strafrecht_is_high(monkeypatch):
    d = _run(monkeypatch, "harmlos", legal={"strafrecht": {"risk": 0.9, "reason": "Bedrohung"}})
    assert d.risk_level == "high"
    assert "strafrecht" in d.legal_flags


def test_legal_classifier_medium_flags_without_high(monkeypatch):
    # 0.55: >= flag(0.4) und >= 0.5 (kein Downgrade), aber < high(0.7) und keine
    # strafrecht/jugendschutz-Eskalation → bleibt medium.
    d = _run(monkeypatch, "harmlos", legal={"persoenlichkeitsrechte": {"risk": 0.55}})
    assert d.risk_level == "medium"
    assert "persoenlichkeitsrechte" in d.legal_flags


def test_legal_weak_flag_is_downgraded_to_low(monkeypatch):
    # 0.45: flaggt (>= 0.4) → medium, aber < 0.5 → Downgrade-Bedingung greift → low.
    d = _run(monkeypatch, "harmlos", legal={"persoenlichkeitsrechte": {"risk": 0.45}})
    assert d.risk_level == "low"
    assert "downgraded_by_llm_check" in d.reasons


def test_clean_llm_keeps_low_but_escalated(monkeypatch):
    d = _run(monkeypatch, "erkläre mir photosynthese",
             mod={"scores": {"violence": 0.01}}, legal={"strafrecht": {"risk": 0.0}})
    assert d.risk_level == "low"
    assert d.escalated is True  # Stufen liefen, kamen aber sauber zurück


def test_legal_trigger_override_forces_legal_stage(monkeypatch):
    cfg = dict(_CFG, presets={"max": {
        "moderation": "never", "legal_classifier": "smart",
        "legal_trigger_override": True, "threshold_multiplier": 1.0,
    }})
    d = _run(monkeypatch, "ich hasse dich", legal={"strafrecht": {"risk": 0.9}}, cfg=cfg)
    assert "legal_trigger_match" in d.reasons
    assert "llm_legal" in d.stages_run
    assert d.risk_level == "high"
