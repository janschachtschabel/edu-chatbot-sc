"""Offen seit AS-5b (offene-befunde §1): Wartet ein Lauf an einer Wahl mit vier oder mehr Chips,
hält ``vorschlag.anhaengen(alle=True)`` sie ganz — ein Ablauf-Knopf daneben fiele weg, obwohl das
Werkzeug angeboten war und die KI ihn angekündigt hätte. Dann bietet der Zug keinen Ablauf an."""

from __future__ import annotations

import inspect

import pytest

from boerdi.services.ablauf import vorschlag, wahl_zug


def _chips(monkeypatch, n: int) -> None:
    monkeypatch.setattr(wahl_zug, "aktuelle_knoepfe",
                        lambda *_a, **_k: [f"chip-{i}" for i in range(n)])


@pytest.mark.parametrize(("chips", "hoechstens", "platz"), [
    (0, None, True), (3, None, True), (4, None, False), (6, None, False),
    (1, 2, True), (2, 2, False),
])
def test_platz_fuer_einen_vorschlag(monkeypatch, chips, hoechstens, platz):
    _chips(monkeypatch, chips)
    assert wahl_zug.platz_fuer_vorschlag("s", {}, "de", hoechstens) is platz


def test_die_grenze_ist_die_von_anhaengen():
    # dieselbe Zahl wie beim Zusammenstellen der Chips — sonst passte die Entscheidung nicht dazu
    assert vorschlag.grenze(None) == 4 and vorschlag.grenze(2) == 2 and vorschlag.grenze(9) == 4
    wahl = [f"w{i}" for i in range(4)]
    assert vorschlag.anhaengen(["ablauf-knopf"], wahl, alle=True) == wahl


def test_beide_wege_fragen_nach_dem_platz():
    from boerdi.graph.nodes import respond, respond_agent

    assert "platz_fuer_vorschlag(" in inspect.getsource(respond_agent)
    assert "platz_fuer_vorschlag(" in inspect.getsource(respond)
