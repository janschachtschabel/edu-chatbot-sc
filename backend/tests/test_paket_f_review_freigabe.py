"""Review Paket F (Entscheid E-F): der Freigabe-Schritt eines Laufs, der in Gespräch A wartet —
„Vorschau erneut zeigen“ und „Ablauf abbrechen“ aus einem anderen Gespräch B bewegen ihn nicht;
im ersten Zug von B fällt der fremde Verweis ohnehin weg (``arbeitsstand.auffrischen``)."""

from __future__ import annotations

import asyncio
import copy

from boerdi.services import arbeitsstand
from boerdi.services.ablauf import freigabe_zug, treiber
from tests.test_ablauf_zug import _S
from tests.test_paket_s_zug import _SITZUNG, _req, _starte, im_zug  # noqa: F401 — Fixture

_B = "sitzung-bbbbbbbbbb"


def _a_und_b(im_zug):  # noqa: F811
    state_a: dict = {"entities": {}}
    _starte(state_a)
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_FREIGABE and v.session_id == _SITZUNG
    b = {"entities": {arbeitsstand.VERWEIS: copy.deepcopy(
        state_a["entities"][arbeitsstand.VERWEIS])}}
    return v, copy.deepcopy(v.akte), b


def _in_b(aktion):
    return _req(action=aktion, action_params={"ablauf": "anhaengen"}).model_copy(
        update={"session_id": _B})


def test_freigabe_abbrechen_aus_einem_anderen_gespraech(im_zug):  # noqa: F811
    v, vorher, b = _a_und_b(im_zug)
    asyncio.run(freigabe_zug.abbrechen(_S(), _in_b(freigabe_zug.AKTION_ABBRECHEN), b))
    assert v.akte["lauf"] == vorher["lauf"] and v.session_id == _SITZUNG


def test_freigabe_erneut_aus_einem_anderen_gespraech(im_zug):  # noqa: F811
    v, vorher, b = _a_und_b(im_zug)
    asyncio.run(freigabe_zug.erneut(_S(), _in_b(freigabe_zug.AKTION_ERNEUT), b))
    assert v.akte["lauf"] == vorher["lauf"] and v.session_id == _SITZUNG


def test_freigabe_der_erste_zug_in_b_nimmt_den_verweis_weg(im_zug):  # noqa: F811
    _v, _vorher, b = _a_und_b(im_zug)
    asyncio.run(arbeitsstand.auffrischen(_S(), _B, b["entities"]))
    assert arbeitsstand.VERWEIS not in b["entities"]
    assert freigabe_zug.weiter_knopf(_B, b, "de") is None
