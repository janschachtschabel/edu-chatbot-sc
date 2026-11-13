"""Paket R2-e (Plan 2026-11-12): kein Deckel der Schnellantworten streicht einen Steuer-Knopf.

Der Deckel (``display-rules.quick_replies.max_count``, Muster, Gastgeber) strich auch „Stand
prüfen“, „Auftrag abbrechen“, „Vorschau erneut zeigen“, „Neues Vorhaben“ oder „Plan weiter“, sobald
er kleiner war als ihre Zahl — bisher geschützt waren nur die Chips einer Wahl, „Weiter im Ablauf“
und (im gesperrten Lauf) die Auftrags-Knöpfe. Steuer-Knöpfe sind der Weg weiter; Vorschläge
(Text-Chips, „Ablauf starten“ der KI, „Arbeitsstand löschen“) bleiben gedeckelt.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse
from boerdi.domain.wahl_knopf import ist_steuer_knopf
from boerdi.services import config_loader
from boerdi.services import widget_postprocess as wp


def _knopf(aktion: str, **params) -> str:
    return f"__action__|K {aktion}|{aktion}|{json.dumps(params)}"


@pytest.mark.parametrize("aktion", ["ablauf_auftrag_pruefen", "ablauf_auftrag_abbrechen",
                                    "ablauf_freigabe_erneut", "ablauf_freigabe_abbrechen",
                                    "vorgang_neu", "plan_weiter", "ablauf_weiter", "ablauf_wahl"])
def test_steuer_knoepfe(aktion):
    assert ist_steuer_knopf(_knopf(aktion, ablauf="a"))


@pytest.mark.parametrize("qr", ["Mehr zeigen", _knopf("ablauf_starten", ablauf="a"),
                                _knopf("vorgang_loeschen"), "__action__|kaputt", None])
def test_keine_steuer_knoepfe(qr):
    assert not ist_steuer_knopf(qr)


def test_der_deckel_laesst_steuer_knoepfe_stehen(monkeypatch):
    monkeypatch.setattr(config_loader, "load_display_rules_config",
                        lambda: {"quick_replies": {"max_count": 1}})
    stand = _knopf("ablauf_auftrag_pruefen", ablauf="a")
    neu = _knopf("vorgang_neu")
    resp = ChatResponse(session_id="s-0123456789", content="Hinweis",
                        quick_replies=["Mehr zeigen", stand, neu, "Noch etwas"])
    req = ChatRequest(session_id="s-0123456789", message="x")
    qrs = asyncio.run(wp._postprocess_response_for_widget_modes(req, resp)).quick_replies
    assert qrs == [stand, neu]


def test_review_r2_11_die_namen_folgen_den_konstanten():
    """Review R2, NIT 11: eine Umbenennung ließe den Deckel sonst still wieder greifen."""
    from boerdi.domain import wahl_knopf
    from boerdi.services import plan_fortsetzen, vorgang_aktion
    from boerdi.services.ablauf import auftrag_zug, freigabe_zug, ki_schritt

    assert wahl_knopf._STEUER_AKTIONEN == {
        auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN, freigabe_zug.AKTION_ERNEUT,
        freigabe_zug.AKTION_ABBRECHEN, vorgang_aktion.AKTION_NEU, plan_fortsetzen.AKTION,
        ki_schritt.AKTION}
