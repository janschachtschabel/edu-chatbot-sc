"""Welche Seite in welcher Sprache schon begrüßt wurde (``domain/gruss_vermerk``)."""

from __future__ import annotations

import pytest

from boerdi.domain.gruss_vermerk import schon_begruesst, vermerken

#: Eine fremde Seite, deren Adresse den Trenner der Sprache selbst enthält — die
#: Signatur trägt Adresse und Suchbegriff, beides kommt von außen.
_MIT_TRENNER = "external|||example.org|https://example.org/suche?q=a|lang:en"


@pytest.mark.parametrize("signatur", ["topic|c-1|||", _MIT_TRENNER])
def test_hin_und_zurueck_gruesst_wieder(signatur):
    # Nutzer-Entscheid 2026-10-09: nach einem Sprachwechsel der passende Gruß —
    # auch zurück. Paket 9 (Review Paket 7, NIT): mit „|lang:“ in der Adresse
    # schnitt das Zerlegen die Seite falsch, der deutsche Eintrag blieb stehen.
    liste = vermerken([], signatur, "de", 30)
    assert schon_begruesst(liste, signatur, "de")
    liste = vermerken(liste, signatur, "en", 30)
    assert not schon_begruesst(liste, signatur, "de")
    assert schon_begruesst(liste, signatur, "en")
    assert len(liste) == 1


def test_andere_seiten_bleiben_vermerkt():
    liste = vermerken(vermerken([], "a|", "de", 30), "b|", "en", 30)
    liste = vermerken(liste, "a|", "en", 30)
    assert schon_begruesst(liste, "b|", "en")
    assert liste == ["b||lang:en", "a||lang:en"]


def test_die_liste_bleibt_gedeckelt():
    liste: list[str] = []
    for i in range(5):
        liste = vermerken(liste, f"s{i}", "de", 3)
    assert liste == ["s2", "s3", "s4"]
