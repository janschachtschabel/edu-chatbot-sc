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
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from boerdi.domain.config_models.base_governance import KRISENTEXT_VORGABE
from boerdi.obs.usage import new_accumulator
from boerdi.services import agent_gate
from boerdi.services.safety import legal as legal_mod
from boerdi.services.safety import moderation as moderation_mod
from boerdi.services.safety import service as ss

_SEED = Path(__file__).resolve().parents[1] / "seeds" / "01-base" / "safety-config.yaml"

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


def _run(monkeypatch, message, *, mod=None, legal=None, cfg=None, usage_acc=None,
         seen=None):
    monkeypatch.setattr(ss, "load_safety_config", lambda: dict(cfg or _CFG))

    async def _mod(_m):
        return mod or {}

    async def _legal(_m, usage_acc=None):
        if seen is not None:
            seen["usage_acc"] = usage_acc
        return legal or {}

    monkeypatch.setattr(moderation_mod, "moderate", _mod)
    monkeypatch.setattr(legal_mod, "classify_legal", _legal)
    return asyncio.run(ss.assess_safety(message, usage_acc=usage_acc))


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
    # Seit Paket 18A nur mit einer Moderation, die wirklich geprüft hat — eine leere
    # gilt als Ausfall (``test_safety_ausfall``).
    d = _run(monkeypatch, "harmlos", mod={"scores": {"violence": 0.01}},
             legal={"persoenlichkeitsrechte": {"risk": 0.45}})
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


# ── K1d: die Rechtsprüfung bucht auf den Zug-Merkposten ───────────────────

def test_assess_safety_reicht_den_merkposten_an_die_rechtspruefung(monkeypatch):
    seen: dict = {}
    acc = new_accumulator()
    _run(monkeypatch, "ich hasse diese plattform", usage_acc=acc, seen=seen)
    assert seen["usage_acc"] is acc


def test_assess_safety_ohne_merkposten_bleibt_lauffaehig(monkeypatch):
    seen: dict = {}
    d = _run(monkeypatch, "harmlos", seen=seen)
    assert seen["usage_acc"] is None
    assert d.risk_level in {"low", "medium", "high"}


# ── Suizid-Absicht mit dem ausgelieferten Seed (Befund 2026-09-27) ────────

def _gemessene_form(scores: dict[str, float]) -> dict[str, float]:
    """``scores`` (API-Namen) so, wie die Moderation sie liefert: SDK-Feldname
    UND API-Name nebeneinander (golden-20260927-131857-e6b-an-3.json)."""
    sdk = {k.replace("-", "_").replace("/", "_"): v for k, v in scores.items()}
    return {**sdk, **scores}


def test_suizid_absicht_greift_mit_seed_schwelle_und_harter_kategorie(monkeypatch):
    """Seed: ``self_harm/intent`` Schwelle 0,25 und harte Kategorie. Die
    Moderation meldete die Kategorie aber nur als ``self-harm/intent`` und
    ``self_harm_intent`` — so galt die Vorgabe 0,95, und eine Absicht mit 0,30
    blieb „gering", solange ``self_harm`` unter 0,5 lag. Echter Seed, echtes
    Parsing, nur der Netzaufruf ist ersetzt."""
    seed = yaml.safe_load(_SEED.read_text(encoding="utf-8"))
    monkeypatch.setattr(ss, "load_safety_config", lambda: seed)
    monkeypatch.setattr(agent_gate, "load_safety_config", lambda: seed)
    monkeypatch.setattr(moderation_mod, "_moderation_target",
                        lambda: ("https://api.openai.com/v1", "sk-x", None))
    scores = _gemessene_form({"self-harm": 0.10, "self-harm/intent": 0.30, "violence": 0.02})

    async def _fake(**_kwargs):
        ergebnis = SimpleNamespace(flagged=True,
                                   categories={k: v >= 0.25 for k, v in scores.items()},
                                   category_scores=scores)
        return SimpleNamespace(results=[ergebnis])

    monkeypatch.setattr(moderation_mod, "_amoderation", _fake)
    d = asyncio.run(ss.assess_safety("harmlos klingende nachricht"))
    assert d.flagged_categories == ["self_harm/intent"]
    assert d.risk_level == "high"
    assert d.enforced_pattern == "M01"
    assert "hard_block:self_harm/intent" in d.reasons
    assert "jugendschutz" in d.legal_flags
    # Der Agent-Endpunkt erkennt die Krise an derselben Kategorie.
    assert agent_gate.stopp_text(d, "de") == KRISENTEXT_VORGABE


# ── Leere Werte aus dem Studio wie fehlende behandeln ─────────────────────

@pytest.mark.parametrize("wert", ["", None], ids=["leer", "null"])
def test_leerer_preset_wert_wirkt_wie_fehlender(wert):
    """Ein im Studio neu angelegtes Preset trägt ``moderation: ""`` und
    ``legal_classifier: ""`` (Vorgabe des Modells). Das galt als ``never``:
    die neue Stufe prüfte gar nichts. Wie ein fehlender Schlüssel: ``smart``."""
    cfg = {"security_level": "neu", "presets": {"neu": {
        "prompt_injection": True, "moderation": wert, "legal_classifier": wert,
    }}}
    preset = ss._resolve_preset(cfg)
    assert (preset["moderation"], preset["legal_classifier"]) == ("smart", "smart")


def test_gesetzter_preset_wert_bleibt():
    cfg = {"security_level": "s", "presets": {"s": {
        "moderation": "never", "legal_classifier": "always",
    }}}
    preset = ss._resolve_preset(cfg)
    assert (preset["moderation"], preset["legal_classifier"]) == ("never", "always")


@pytest.mark.parametrize("scores,muster", [
    ({"self_harm": 0.9}, "M01"),          # Krise
    ({"hate/threatening": 0.8}, "M02"),   # Drohung
    ({"violence": 0.9}, "M01"),           # sonstige harte Kategorie
], ids=["krise", "drohung", "rest"])
def test_leeres_muster_faellt_auf_die_vorgabe_zurueck(monkeypatch, scores, muster):
    """Geleertes ``crisis_pattern``/``threat_pattern``: bisher erzwang eine harte
    Kategorie dann gar kein Muster — hohes Risiko, aber die normale
    Musterwahl. Leer heißt jetzt „nicht gepflegt" → M01 bzw. M02."""
    cfg = dict(_CFG, crisis_pattern="", threat_pattern="")
    d = _run(monkeypatch, "harmlos", mod={"scores": scores}, cfg=cfg)
    assert d.risk_level == "high"
    assert d.enforced_pattern == muster


# ── Audit 2026-09-29 (6.9): die Studio-Vorgabe ist die der Laufzeit ──────────
# ``service`` liest ``legal_classifier`` und ``downgrade_false_positives`` mit dem
# Rückfall ``True``. Stand das Modell auf ``False``, zeigte das Studio beide
# Schalter aus, während sie wirkten.


def test_ein_block_mit_den_modell_vorgaben_wirkt_wie_ein_leerer():
    from boerdi.api.schemas import SafetyDecision
    from boerdi.domain.config_models.base_governance import EscalationBlock

    gefuellt = EscalationBlock().model_dump()
    altweg = {"security_level": "ohne-voreinstellung"}
    assert (ss._resolve_preset({**altweg, "escalation": gefuellt})["legal_classifier"]
            == ss._resolve_preset({**altweg, "escalation": {}})["legal_classifier"])

    def stufe_nach_dem_abgleich(esc: dict) -> str:
        entscheidung = SafetyDecision(risk_level="medium")
        ss._maybe_downgrade(entscheidung, esc, {})
        return entscheidung.risk_level

    assert stufe_nach_dem_abgleich(gefuellt) == stufe_nach_dem_abgleich({})
