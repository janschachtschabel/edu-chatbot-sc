"""Paket RB-3 (2026-11-09): die Auftrags-Blase der Gastseite übersteht das Neuladen.

Ein Zug von ``startTask``/``startAblauf`` trägt ``from_host``. Die Nutzernachricht merkt es sich im
Debug-Block, und der öffentliche Verlauf gibt es als ``ui.from_host`` zurück. Damit zeigt das
Widget die Blase nach dem Neuladen wieder als „Auftrag der Seite“ (Review AS-4b, Befund 5). Das
ist nur Anzeige und kein Recht: eine Person, die es selbst setzt, färbt nur ihre eigene Blase.
"""

from __future__ import annotations

import asyncio

from boerdi.api import publikum
from boerdi.api.schemas import ChatRequest
from boerdi.graph import build as build_mod
from boerdi.graph import state as state_mod
from boerdi.services.db_sessions import VOM_GASTGEBER_KEY
from boerdi.ui_module.antwort import DEBUG_KEY


class _Spy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return 1


def _speichern(monkeypatch, *, from_host: bool, ui_antwort=None) -> dict:
    spy = _Spy()
    monkeypatch.setattr(build_mod, "save_message", spy)
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="bb-1", message="Leg los",
                                                from_host=from_host))
    ctx.ui_antwort = ui_antwort
    asyncio.run(build_mod._persist_user_message(ctx, object()))
    return spy.calls[0]["kwargs"]


def test_ein_zug_der_gastseite_merkt_sich_das_an_der_nutzernachricht(monkeypatch):
    assert _speichern(monkeypatch, from_host=True)["debug"] == {VOM_GASTGEBER_KEY: True}
    assert not _speichern(monkeypatch, from_host=False).get("debug")


def test_der_merker_steht_neben_einer_modul_antwort(monkeypatch):
    antwort = {"block_id": "b", "modul": "ui_entscheidung"}
    debug = _speichern(monkeypatch, from_host=True, ui_antwort=antwort)["debug"]
    assert debug == {DEBUG_KEY: antwort, VOM_GASTGEBER_KEY: True}


def test_ohne_angabe_ist_ein_zug_keiner_der_gastseite():
    assert ChatRequest(session_id="bb-1", message="x").from_host is False


def test_der_oeffentliche_verlauf_traegt_den_merker():
    verlauf = publikum.verlauf_fuer([
        {"id": 1, "role": "user", "content": "Leg los", "cards": [],
         "debug": {VOM_GASTGEBER_KEY: True}},
        {"id": 2, "role": "user", "content": "Hallo", "cards": [], "debug": None},
        # unerwartete Form: kein Merker, kein Fehler
        {"id": 3, "role": "user", "content": "x", "cards": [], "debug": {VOM_GASTGEBER_KEY: "ja"}},
    ], intern=False)
    assert verlauf[0]["ui"] == {"from_host": True}
    assert "from_host" not in verlauf[1]["ui"]
    assert "from_host" not in verlauf[2]["ui"]
    assert all("debug" not in n for n in verlauf)


def test_auch_der_weg_der_tour_merkt_sich_die_gastseite(monkeypatch):
    """Review RB-3, Befund 3: der zweite Ort, der Nutzernachrichten speichert — ein echter Start
    der Tour mit und ohne ``from_host``."""
    from tests.test_tour_node import _ctx, _patch, _run

    for from_host, erwartet in ((True, {VOM_GASTGEBER_KEY: True}), (False, None)):
        _upd, save = _patch(monkeypatch)
        ctx = _ctx("start", message="Los geht's", page="/home/")
        ctx.req = ctx.req.model_copy(update={"from_host": from_host})
        _run(ctx)
        [nutzer] = [c for c in save.calls if c["args"][2] == "user"]
        assert nutzer["kwargs"].get("debug") == erwartet
