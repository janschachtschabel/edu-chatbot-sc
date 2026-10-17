"""Einstellungen ohne Leser sind gestrichen (Paket 7, P4/L7 — Nutzer-Entscheid 2026-10-09).

Das Studio zeigte Felder, die nichts bewirkten — ihre Hilfetexte sagten es schon
(„wird derzeit nicht ausgewertet“). Entschieden: streichen. Dazu zwei Funde der
Bestandsaufnahme derselben Art: ``escalation.provider`` (``none`` schaltete die
Moderation nie ab) und ``MCP_MAX_CONNECTIONS`` (kein Leser im Code).

Bestehende Dokumente mit diesen Schlüsseln bleiben gültig (``AreaModel`` lässt
Unbekanntes zu); der Seed liefert sie nicht mehr aus.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.base_governance import (
    EscalationBlock,
    GuideModeBlock,
    SafetyConfigArea,
)
from boerdi.domain.config_models.engine import AgentLimits
from boerdi.services import seed_sync
from boerdi.settings import Settings


@pytest.mark.parametrize(("modell", "feld"), [
    (AgentLimits, "safety"),                       # das Sicherheits-Gate läuft immer
    (GuideModeBlock, "default_enabled"),           # das Widget liest es nicht
    (SafetyConfigArea, "confidence_adjustments"),  # Code nutzt feste Werte
    (EscalationBlock, "provider"),                 # „none“ schaltete nichts ab
])
def test_ein_feld_ohne_leser_ist_gestrichen(modell, feld):
    assert feld not in modell.model_fields


def test_mcp_max_connections_ist_gestrichen():
    assert "mcp_max_connections" not in Settings.model_fields


def test_der_seed_liefert_die_gestrichenen_felder_nicht_mehr_aus():
    seed = asyncio.run(seed_sync.seed_lesen(seed_sync.seed_pfad("seeds")))
    assert "safety" not in seed["01-base/engine"].get("agent", {})
    assert "default_enabled" not in seed["01-base/guide-mode"].get("guide_mode", {})
    assert "confidence_adjustments" not in seed["01-base/safety-config"]
    assert "provider" not in seed["01-base/safety-config"].get("escalation", {})


def test_der_lotse_meldet_kein_default_enabled_mehr():
    from boerdi.services.config_loader.safety import load_guide_mode_config

    assert "default_enabled" not in load_guide_mode_config()
