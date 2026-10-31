"""Welche Seite in welcher Sprache schon begrüßt wurde (``domain/gruss_vermerk``)."""

from __future__ import annotations

import hashlib

import pytest

from boerdi.domain.gruss_vermerk import (
    eintrag,
    neues_salz,
    schon_begruesst,
    verdeckt,
    vermerken,
)

#: Eine fremde Seite, deren Adresse den Trenner der Sprache selbst enthält — die
#: Signatur trägt Adresse und Suchbegriff, beides kommt von außen.
_MIT_TRENNER = "external|||example.org|https://example.org/suche?q=a|lang:en"
_SALZ = "0f" * 16


@pytest.mark.parametrize("signatur", ["topic|c-1|||", _MIT_TRENNER])
def test_hin_und_zurueck_gruesst_wieder(signatur):
    # Nutzer-Entscheid 2026-10-09: nach einem Sprachwechsel der passende Gruß —
    # auch zurück. Paket 9 (Review Paket 7, NIT): mit „|lang:“ in der Adresse
    # schnitt das Zerlegen die Seite falsch, der deutsche Eintrag blieb stehen.
    liste = vermerken([], signatur, "de", 30, _SALZ)
    assert schon_begruesst(liste, signatur, "de", _SALZ)
    liste = vermerken(liste, signatur, "en", 30, _SALZ)
    assert not schon_begruesst(liste, signatur, "de", _SALZ)
    assert schon_begruesst(liste, signatur, "en", _SALZ)
    assert len(liste) == 1


def test_andere_seiten_bleiben_vermerkt():
    liste = vermerken(vermerken([], "a|", "de", 30, _SALZ), "b|", "en", 30, _SALZ)
    liste = vermerken(liste, "a|", "en", 30, _SALZ)
    assert schon_begruesst(liste, "b|", "en", _SALZ)
    assert liste == [eintrag(verdeckt("b|", _SALZ), "en"), eintrag(verdeckt("a|", _SALZ), "en")]


def test_die_liste_bleibt_gedeckelt():
    liste: list[str] = []
    for i in range(5):
        liste = vermerken(liste, f"s{i}", "de", 3, _SALZ)
    assert liste == [verdeckt(f"s{i}", _SALZ) for i in (2, 3, 4)]


# ── Paket 19 (M-8): kein Klartext im Vermerk ────────────────────────────────
# Die Signatur trägt die Adresse fremder Seiten (samt Query) und Suchbegriffe — der
# Browserverlauf der Person, 30 Tage in ``sessions.entities``. Vermerkt wird ein HMAC mit
# einem Salz je Sitzung (Review 19-1): ein bloßer SHA-256 ließe sich für bekannte Adressen
# per Wörterbuch umkehren.

def test_der_vermerk_traegt_weder_adresse_noch_suchbegriff():
    liste = vermerken([], _MIT_TRENNER, "de", 30, _SALZ)
    assert "example.org" not in str(liste) and "suche" not in str(liste)
    assert liste == [verdeckt(_MIT_TRENNER, _SALZ)]
    assert verdeckt("x", _SALZ).startswith("hmac:") and len(verdeckt("x", _SALZ)) == 5 + 64


def test_ohne_das_salz_der_sitzung_ist_der_vermerk_nicht_nachzurechnen():
    wert = verdeckt(_MIT_TRENNER, _SALZ)
    assert wert != verdeckt(_MIT_TRENNER, "1e" * 16)
    assert wert.split(":", 1)[1] != hashlib.sha256(_MIT_TRENNER.encode()).hexdigest()
    salze = {neues_salz() for _ in range(5)}
    assert len(salze) == 5 and all(len(s) == 32 for s in salze)


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_ein_klartext_vermerk_von_vor_dem_deploy_gilt_weiter(sprache):
    """Laufende Sitzungen tragen noch Klartext — sie werden nicht ein zweites Mal begrüßt,
    auch wenn sie noch kein Salz haben."""
    assert schon_begruesst([eintrag("topic|c-1|||", sprache)], "topic|c-1|||", sprache, None)
    assert schon_begruesst([eintrag("topic|c-1|||", sprache)], "topic|c-1|||", sprache, _SALZ)


def test_ein_ungesalzener_vermerk_aus_dem_ersten_stand_gilt_weiter():
    alt = "sha256:" + hashlib.sha256(b"topic|c-1|||").hexdigest()
    assert schon_begruesst([alt], "topic|c-1|||", "de", None)


def test_ein_neuer_vermerk_ersetzt_klartext_und_ungesalzenen_hash():
    alt = "sha256:" + hashlib.sha256(b"topic|c-1|||").hexdigest()
    liste = vermerken(["topic|c-1|||", alt, "andere"], "topic|c-1|||", "en", 30, _SALZ)
    assert liste == ["andere", eintrag(verdeckt("topic|c-1|||", _SALZ), "en")]
