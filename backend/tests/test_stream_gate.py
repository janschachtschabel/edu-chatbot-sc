"""Sperre des Token-Streamings (Plan ``2026-10-01-token-streaming``, T8, E-S1/E-S6).

Gesperrt wird, was die Endverarbeitung sicher umschreibt oder verschiebt — dort
spränge die Blase beim Austausch. Der Grund steht in der Logzeile.
"""

from __future__ import annotations

import pytest

from boerdi.domain.stream_gate import sperrgrund

_OFFEN = {"eingeschaltet": True, "antwort_werkzeug": True, "muster_id": "M04", "risiko": "low"}


def test_ein_gewoehnlicher_wissenszug_streamt():
    assert sperrgrund(**_OFFEN) is None


def test_der_agent_zug_streamt_ohne_muster_sperre():
    assert sperrgrund(**{**_OFFEN, "muster_id": "AGENT"}) is None


@pytest.mark.parametrize("abweichung, grund", [
    ({"eingeschaltet": False}, "aus"),
    ({"antwort_werkzeug": False}, "ohne_antwort_werkzeug"),
    ({"risiko": "medium"}, "risiko"),
    ({"risiko": "high"}, "risiko"),
    ({"muster_id": "M05"}, "suchmuster"),
    ({"muster_id": "M06"}, "suchmuster"),
    ({"muster_id": "M09"}, "dokumentmuster"),
    ({"muster_id": "M10"}, "dokumentmuster"),
    ({"muster_id": "M11"}, "dokumentmuster"),
    ({"muster_id": "M16"}, "aufloeser"),
])
def test_sperrgruende(abweichung, grund):
    assert sperrgrund(**{**_OFFEN, **abweichung}) == grund


def test_der_schalter_geht_jedem_anderen_grund_vor():
    assert sperrgrund(eingeschaltet=False, antwort_werkzeug=False,
                      muster_id="M05", risiko="high") == "aus"
