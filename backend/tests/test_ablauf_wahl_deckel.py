"""Querschnitts-Review AS-3, Befund 1: die Chips einer Ablauf-Wahl übersteht jeder Deckel.

Ein Schritt mit Schnellantworten wartet; ohne Freitext sind seine Chips der einzige Weg weiter.
Im Werk steht ``display-rules.quick_replies.max_count`` auf 2 — die Chips (bis zu 8) dürfen weder
dort noch im Muster, beim Gastgeber, vor den Anmelde-Chips oder hinter den Facetten wegfallen.
Andere Vorschläge rücken nach hinten oder fallen weg.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment
from boerdi.domain.auth_qr import AUTH_QR_MARKER, inject_auth_qr
from boerdi.domain.wahl_knopf import ist_wahl_knopf, wahl_zuerst
from boerdi.services import config_loader
from boerdi.services import widget_postprocess as wp
from boerdi.services.ablauf import wahl_zug
from boerdi.services.guide_qr_injector import begrenze_pillen

_CHIPS = wahl_zug.knoepfe("w", {"schritt": "frage", "optionen": [
    (f"o{i}", f"Option {i}") for i in range(6)]})


def test_die_chips_werden_erkannt():
    assert all(ist_wahl_knopf(c) for c in _CHIPS)
    assert not ist_wahl_knopf("__action__|Weiter|ablauf_weiter|{}")
    assert not ist_wahl_knopf("Nur Videos")
    assert json.loads(_CHIPS[0].split("|", 3)[3]) == {"ablauf": "w", "schritt": "frage",
                                                       "wahl": "o0"}


def test_begrenze_pillen_zaehlt_sie_nicht():
    assert begrenze_pillen(["a", *_CHIPS, "b"], 1) == ["a", *_CHIPS]


def test_die_anmelde_chips_verdraengen_sie_nicht():
    qrs = inject_auth_qr([*_CHIPS, "x"], blocked=True, lang="de")
    assert qrs[0] == AUTH_QR_MARKER and qrs[2:8] == _CHIPS


def test_facetten_stehen_dahinter():
    assert wahl_zuerst(["Nur Videos", *_CHIPS]) == [*_CHIPS, "Nur Videos"]


_ABBRUCH = ('__action__|Ablauf abbrechen|ablauf_abbrechen|'
            '{"bestaetigt": true, "marke": "m1"}')


def test_der_knopf_der_abbruch_rueckfrage_zaehlt_wie_ein_wahl_chip():
    """Browser-Abnahme AS-U, L-2: die Rückfrage „Ablauf abbrechen?“ trägt ihren Knopf und die
    Chips des wartenden Schritts. Mit ``max_count: 2`` und zwei Chips verdrängten die Chips den
    Knopf — er ist aber der einzige Weg zur Antwort, wie „Neu starten?“."""
    assert ist_wahl_knopf(_ABBRUCH)
    # der Leisten-Knopf (ohne Bestätigung) ist kein solcher Knopf
    assert not ist_wahl_knopf('__action__|Ablauf abbrechen|ablauf_abbrechen|{}')


@pytest.mark.parametrize("max_count", [0, 2])
def test_der_widget_nachlauf_laesst_den_abbruch_knopf_stehen(monkeypatch, max_count):
    monkeypatch.setattr(config_loader, "load_display_rules_config",
                        lambda: {"quick_replies": {"max_count": max_count}})
    req = ChatRequest(session_id="sitzung-0123456789", message="x", environment=Environment())
    resp = ChatResponse(session_id=req.session_id, content="Wirklich?",
                        quick_replies=[_ABBRUCH, *_CHIPS[:2]])
    qrs = asyncio.run(wp._postprocess_response_for_widget_modes(req, resp)).quick_replies
    assert qrs == [_ABBRUCH, *_CHIPS[:2]]


@pytest.mark.parametrize("max_count", [0, 2])
def test_der_widget_nachlauf_laesst_alle_chips_stehen(monkeypatch, max_count):
    monkeypatch.setattr(config_loader, "load_display_rules_config",
                        lambda: {"quick_replies": {"max_count": max_count}})
    req = ChatRequest(session_id="sitzung-0123456789", message="x", environment=Environment())
    resp = ChatResponse(session_id=req.session_id, content="Wie weiter?",
                        quick_replies=[*_CHIPS, "andere"])
    qrs = asyncio.run(wp._postprocess_response_for_widget_modes(req, resp)).quick_replies
    assert qrs[:6] == _CHIPS
    # ohne Wahl-Chips gilt der Deckel wie bisher
    ohne = ChatResponse(session_id=req.session_id, content="x", quick_replies=["a", "b", "c"])
    assert len(asyncio.run(wp._postprocess_response_for_widget_modes(req, ohne)).quick_replies) \
        == max_count
