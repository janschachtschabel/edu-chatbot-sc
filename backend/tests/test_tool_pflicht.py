"""Die Werkzeugpflicht eines Musters (A1-Reflexion) als reine Funktion — Plan
``2026-10-01-token-streaming``, T9. Der Tool-Loop fragt sie im Reflexions-Block
und, seit T10, vor jeder Runde: kann die Reflexion diese Antwort noch verwerfen?
"""

from __future__ import annotations

from boerdi.domain.tool_pflicht import fehlende_pflichtwerkzeuge, gerufene_werkzeuge

_EINES = {"force_tool_use": True, "tools": ["search_wlo_content", "search_wlo_collections"]}
_ALLE = {**_EINES, "requires_all_tools": True}


def test_ohne_pflicht_fehlt_nichts():
    assert fehlende_pflichtwerkzeuge({}, []) == []
    assert fehlende_pflichtwerkzeuge({"tools": ["search_wlo_content"]}, []) == []
    assert fehlende_pflichtwerkzeuge({"force_tool_use": True}, []) == []


def test_eines_genuegt():
    assert fehlende_pflichtwerkzeuge(_EINES, []) == ["search_wlo_content",
                                                     "search_wlo_collections"]
    assert fehlende_pflichtwerkzeuge(_EINES, ["search_wlo_collections"]) == []


def test_alle_verlangt():
    assert fehlende_pflichtwerkzeuge(_ALLE, ["search_wlo_content"]) == ["search_wlo_collections"]
    assert fehlende_pflichtwerkzeuge(
        _ALLE, ["search_wlo_content", "search_wlo_collections"]) == []


def test_gezaehlt_wird_der_blanke_name():
    """Vorabruf-Einträge tragen einen Zusatz hinter dem Namen."""
    assert gerufene_werkzeuge(["search_wlo_content (prefetch)", "", None]) == {
        "search_wlo_content", ""}
    assert fehlende_pflichtwerkzeuge(_EINES, ["search_wlo_content (prefetch)"]) == []
