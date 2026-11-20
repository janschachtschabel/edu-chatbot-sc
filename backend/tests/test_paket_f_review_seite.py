"""Kontrolle Paket F, MINOR 1: der Seiten-Ping läuft vor dem Preflight (ohne ``auffrischen``).
Zeigt der Verweis eines anderen Gesprächs B auf eine Führung, die in A wartet (Altbestand), rechnet
der Ping nichts, zeigt keine fremden Chips und nimmt den Verweis weg."""

from __future__ import annotations

import asyncio
import copy

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import seite_zug, treiber
from tests.test_ablauf_seite_zug import _ENDE, _HIN, _roh, _starten
from tests.test_ablauf_zug import _S, umgebung  # noqa: F401 — Fixture

_A = "sitzung-0123456789"
_B = "sitzung-bbbbbbbbbb"
_FRAGE = {"id": "frage", "typ": "nachricht", "text": {"de": "Wer bist du?"},
          "optionen": [{"id": "l", "label": {"de": "Lehrkraft"}, "ziel": "hin"}]}


def _ping_b(zustand, seite):
    return asyncio.run(seite_zug.angekommen(_S(), ChatRequest(
        session_id=_B, message="[ablauf-seite]",
        environment=Environment(page=seite, page_event=seite_zug.PING)), zustand))


def _b(zustand_a):
    return {"entities": {arbeitsstand.VERWEIS: copy.deepcopy(
        zustand_a["entities"][arbeitsstand.VERWEIS])}}


def test_der_ping_aus_b_rechnet_nichts_an_einem_seiten_schritt(umgebung):  # noqa: F811
    zustand_a, _ = _starten(umgebung, _roh())
    [v] = umgebung.speicher.v.values()
    vorher = copy.deepcopy(v.akte)
    b = _b(zustand_a)
    antwort = _ping_b(b, "/mitmachen/")                 # die Zielseite: aus A ginge es weiter
    assert antwort.content == "" and antwort.quick_replies == []
    assert v.akte["lauf"] == vorher["lauf"] and v.akte["lauf"]["status"] == treiber.WARTET_SEITE
    assert arbeitsstand.VERWEIS not in b["entities"]


def test_der_ping_aus_b_zeigt_keine_fremde_frage(umgebung):  # noqa: F811
    zustand_a, _ = _starten(umgebung, _roh(_FRAGE, _HIN, _ENDE))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_WAHL and v.session_id == _A
    b = _b(zustand_a)
    antwort = _ping_b(b, "/home/")
    assert antwort.content == "" and antwort.quick_replies == []
    assert arbeitsstand.VERWEIS not in b["entities"]
