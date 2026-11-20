"""Kontrolle Paket F, MINOR 4: die Freigabe-Box eines Auftrags (Paket N4), deren Lauf in Gespräch A
wartet — „Freigeben“ und „Verwerfen“ aus einem anderen Gespräch B starten nichts beim MCP und
bewegen den Lauf nicht (Altbestand: B trägt Verweis und Box aus A)."""

from __future__ import annotations

import asyncio
import copy

import pytest

from boerdi.services import arbeitsstand
from boerdi.services.ablauf import auftrag_freigabe, auftrag_freigabe_zug, freigabe_zug, treiber
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_n4_freigabe import (  # noqa: F401 — Fixtures
    FREI,
    _antworten,
    _bestaetigungen,
    _box,
    _starte,
    freigeschaltet,
    im_zug,
    n4,
    ueber_mcp,
)
from tests.test_paket_n4_vorschau import _vorschau

_B = "sitzung-bbbbbbbbbb"


@pytest.mark.parametrize("aktion", [FREI, auftrag_freigabe_zug.AKTION_VERWERFEN])
def test_freigabe_box_aus_einem_anderen_gespraech(n4, aktion, monkeypatch):  # noqa: F811
    async def nichts(*_a, **_k):
        return None

    # der stille Weg in ``freigabe_zug._laden`` schreibt die Sitzung (ohne fremden Verweis)
    monkeypatch.setattr(freigabe_zug, "update_session", nichts)
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state_a: dict = {"entities": {}}
    daten = _box(_starte(state_a, freigeben=False))
    [v] = n4.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_FREIGABE
    vorher = copy.deepcopy(v.akte)
    b = {"entities": {k: copy.deepcopy(state_a["entities"][k])
                      for k in (arbeitsstand.VERWEIS, auftrag_freigabe.KEY)}}
    fn = (auftrag_freigabe_zug.freigeben if aktion == FREI else auftrag_freigabe_zug.verwerfen)
    anfrage = _req(action=aktion, action_params={"ablauf": "lesen",
                                                 "id": daten["freigabe"]["id"]})
    asyncio.run(fn(_S(), anfrage.model_copy(update={"session_id": _B}), b))
    assert arbeitsstand.VERWEIS not in b["entities"]
    assert _bestaetigungen(n4) == [] and n4.ablage.auftraege == []
    assert v.akte["lauf"] == vorher["lauf"] and v.session_id == "sitzung-0123456789"
