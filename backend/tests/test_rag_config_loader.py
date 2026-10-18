"""Paket 15 (A4): ``mode`` steuert nur den Muster-Weg, ``agent`` nur die Schleife.

Vorher verwarf ``load_rag_config`` jeden Bereich ohne ``mode`` — auch für die Agent-Schleife,
obwohl dort allein ``agent`` zählt. Ein Bereich „nur für den Agenten“ ging so nicht.
"""

from __future__ import annotations

from boerdi.domain.route_head import _resolve_rag_areas
from boerdi.services.agent_knowledge import fuer_die_schleife
from boerdi.services.config_loader import rag as rag_loader

_STORE = {
    "Immer": {"mode": "always"},
    "Nur-Agent": {"description": "ohne Muster-Modus"},
    "Kaputt": "kein Objekt",
}


def test_ein_bereich_ohne_modus_bleibt_fuer_den_agenten(monkeypatch) -> None:
    monkeypatch.setattr(rag_loader, "area", lambda _key: _STORE)
    config = rag_loader.load_rag_config()
    assert set(config) == {"Immer", "Nur-Agent"}
    assert fuer_die_schleife(config) == ["Immer", "Nur-Agent"]


def test_der_muster_weg_holt_einen_bereich_ohne_modus_nicht_vorab(monkeypatch) -> None:
    monkeypatch.setattr(rag_loader, "area", lambda _key: _STORE)
    config = rag_loader.load_rag_config()
    assert _resolve_rag_areas({}, config) == ["Immer"]
    assert _resolve_rag_areas({"sources": ["rag"]}, config) == ["Immer"]
    assert rag_loader.get_on_demand_rag_areas() == []
