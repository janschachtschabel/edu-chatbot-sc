"""Querschnitts-Review 2026-11-06, M1: das automatische Abholen von ``ui_fortschritt`` ist kein
Zug der Person — es schließt keine offene Frage (ein laufender Upload-Stapel, ein Strukturentwurf
bleiben offen). Es ist aber sichtbar: eine Schreib-Abnahme verfällt wie sonst (Review Q1, Befund
1). Ein Klick auf „Stand prüfen“ bleibt ein gewöhnlicher Zug.
"""

from __future__ import annotations

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.domain.hintergrund_zug import AUTOMATISCH_AKTIONEN, ist_automatisches_abholen
from boerdi.graph.nodes.setup import _hintergrund_zug
from boerdi.services.ablauf import auftrag_zug


def _req(**mehr) -> ChatRequest:
    return ChatRequest(session_id="sitzung-0123456789", message="", environment=Environment(),
                       **mehr)


def test_die_aktion_ist_die_des_auftrags():
    assert AUTOMATISCH_AKTIONEN == frozenset({auftrag_zug.AKTION})


def test_automatisches_abholen_ist_kein_hintergrund_zug_aber_erkannt():
    """Review Q1, Befund 1: sichtbar — die Abnahme verfällt; nur die offene Frage bleibt (``setup``,
    ``test_setup_node``)."""
    req = _req(action=auftrag_zug.AKTION, action_params={"ablauf": "lesen", "automatisch": True})
    assert ist_automatisches_abholen(req.action, req.action_params)
    assert _hintergrund_zug(req, {}) is False


def test_ein_klick_auf_stand_pruefen_bleibt_ein_zug_der_person():
    req = _req(action=auftrag_zug.AKTION, action_params={"ablauf": "lesen"})
    assert _hintergrund_zug(req, {}) is False


def test_nur_echtes_true_und_nur_diese_aktion():
    assert not ist_automatisches_abholen(auftrag_zug.AKTION, {"automatisch": "true"})
    assert not ist_automatisches_abholen("ablauf_starten", {"automatisch": True})
    assert not ist_automatisches_abholen(None, None)
