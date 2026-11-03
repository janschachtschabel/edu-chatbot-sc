"""Paket U1-e: der Themenbaum im Muster-Modus (U-F4, Plan §15 E-11).

Ein Muster nennt ``ui_themenbaum`` in ``tools:``; angeboten wird es nur, wenn das Widget es meldet
UND sein Werkzeug ``browse_collection_tree`` in diesem Zug nicht gesperrt ist. In der Vorrunde
der Muster-Schleife ruft das Backend die Datenquelle; an die KI geht nur die Quittung.
"""

from __future__ import annotations

import json

import pytest

from boerdi.services import response_tool_selection as rts
from boerdi.services.tool_loop_module import MODUL_BLOECKE_KEY
from boerdi.ui_module import datenquelle
from boerdi.ui_module.namen import UI_WERKZEUGE_KEY
from tests.test_tool_loop import _resp_text, _resp_tools, _run_loop
from tests.test_ui_themenbaum import ALLE_KNOTEN, THEMENBAUM, WERKZEUG, _Rufer


@pytest.fixture
def _ohne_schnellantwort(monkeypatch):
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "0")


def _angebot(*, ui_module, gesperrt=()) -> list[str]:
    po = {"tools": ["search_wlo_all"], UI_WERKZEUGE_KEY: [THEMENBAUM]}
    tools, *_ = rts._select_active_tools({"entities": {}}, po, None, None, False, False,
                                         ui_module=ui_module, gesperrt=gesperrt)
    return [t["function"]["name"] for t in tools]


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_genannt_gemeldet_und_verfuegbar_wird_angeboten():
    assert _angebot(ui_module=[THEMENBAUM]).count(THEMENBAUM) == 1


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_eine_sperre_auf_das_werkzeug_nimmt_den_themenbaum_mit():
    assert THEMENBAUM not in _angebot(ui_module=[THEMENBAUM], gesperrt=[WERKZEUG])


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_ohne_meldung_des_widgets_kein_themenbaum():
    assert THEMENBAUM not in _angebot(ui_module=["ui_entscheidung"])


def test_die_vorrunde_holt_den_baum_und_quittiert_ohne_knoten(monkeypatch):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    _fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("c1", THEMENBAUM, json.dumps({"subject": "Mathe"}))]),
        _resp_text("Hier die Themen."),
    ])

    text, _karten, gerufen, _outs = result
    assert text == "Hier die Themen."
    assert rufer.calls == [(WERKZEUG, {"subject": "Mathe", "depth": 2, "maxResults": 31})]
    [block] = st["session_state"][MODUL_BLOECKE_KEY]
    assert block.modul == THEMENBAUM and len(block.daten["knoten"]) == 2
    assert gerufen == [THEMENBAUM]             # protokolliert (Review U1-e, Befund 6), keine Karten
    an_das_modell = json.dumps(st["messages"], ensure_ascii=False, default=str)
    for teil in ALLE_KNOTEN:
        assert teil not in an_das_modell


def test_ein_fehler_der_datenquelle_geht_an_die_ki(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer("MCP error: weg", "transport"))
    _fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("c1", THEMENBAUM, json.dumps({"subject": "Mathe"}))]),
        _resp_text("Ohne Baum."),
    ])
    assert result[0] == "Ohne Baum."
    assert not st["session_state"].get(MODUL_BLOECKE_KEY)
    fehler = next(m["content"] for m in st["messages"] if m.get("tool_call_id") == "c1")
    assert fehler.startswith("Fehler")
