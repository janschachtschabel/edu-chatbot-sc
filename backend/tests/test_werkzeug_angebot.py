"""B-M1 (Audit 2026-09-29): ausgeführt wird nur, was dem Modell angeboten war."""

from __future__ import annotations

from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN, angebotene_namen


def _werkzeug(name):
    return {"type": "function", "function": {"name": name, "parameters": {}}}


def test_namen_aus_dem_angebot():
    assert angebotene_namen([_werkzeug("search_wlo_content"), _werkzeug("get_skill")]) == {
        "search_wlo_content", "get_skill"}


def test_leeres_oder_fehlendes_angebot():
    assert angebotene_namen([]) == frozenset()
    assert angebotene_namen(None) == frozenset()


def test_eintraege_ohne_namen_zaehlen_nicht():
    assert angebotene_namen([{"type": "function"}, {"function": {"name": ""}},
                             {"function": {"name": None}}]) == frozenset()


def test_der_hinweis_nennt_den_grund_ohne_werkzeugliste():
    # Die Antwort geht ans Modell. Sie soll ihm sagen, dass nichts geschah —
    # und nicht etwa das ganze Angebot noch einmal aufzählen.
    assert "Nicht ausgeführt" in NICHT_ANGEBOTEN
