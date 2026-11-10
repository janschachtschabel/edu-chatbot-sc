"""Review AS-0, Befund 2: Sicherungen von vor AS-0 tragen ``06-ablaeufe/katalog`` —
``katalog_aufteilen`` macht daraus ein Dokument je Ablauf, wie Migration 0021."""

from __future__ import annotations

from boerdi.domain.ablauf_altbestand import katalog_aufteilen


def test_ohne_katalog_bleibt_alles_wie_es_ist():
    bereiche = {"01-base/policy": {"rules": []}}
    assert katalog_aufteilen(bereiche) is bereiche


def test_der_katalog_wird_dokumente_und_ein_mitgesichertes_dokument_hat_vorrang():
    eigen = {"id": "lesen", "titel": {"de": "eigen"}}
    ergebnis = katalog_aufteilen({
        "06-ablaeufe/katalog": {"ablaeufe": [
            {"id": "lesen", "titel": {"de": "aus dem Katalog"}},
            {"id": "neu"}, {"id": "../boese"}, {"id": "katalog"}, "kein objekt",
            {"id": "neu", "titel": {"de": "zweiter mit derselben Kennung"}}]},
        "06-ablaeufe/lesen": eigen,
        "01-base/policy": {"rules": []},
    })
    assert set(ergebnis) == {"06-ablaeufe/lesen", "06-ablaeufe/neu", "01-base/policy"}
    assert ergebnis["06-ablaeufe/lesen"] is eigen
    assert ergebnis["06-ablaeufe/neu"] == {"id": "neu"}


def test_ein_kaputter_katalog_ergibt_keine_dokumente():
    assert katalog_aufteilen({"06-ablaeufe/katalog": {"ablaeufe": "nein"}}) == {}
