"""Kennungen und Schutz der Ordner-Dokumente — eine Regel für Studio, Löschen und
Wiederherstellen (Paket 9, Review Paket 7: MAJOR 5, MINOR 32)."""

from __future__ import annotations

from boerdi.api.config_guards import is_restorable_area_key
from boerdi.api.config_kennungen import (
    kennungs_einwand,
    loeschbar,
    sicherheits_kennungen_aus,
)


def _muster(kennung: str) -> dict:
    return {"frontmatter": {"id": kennung, "label": kennung}, "body": "x"}


_SICHER = sicherheits_kennungen_aus({"crisis_pattern": "M07", "threat_pattern": ""})


class TestLoeschbar:
    def test_feste_bereiche_und_sicherheitsmuster_bleiben(self):
        """Ohne ``01-base/safety-config`` lief die Moderation mit ``mode: off``; M01/M02
        und das Krisenmuster der Konfiguration erzwingt das Gate."""
        assert not loeschbar("01-base/safety-config", {}, _SICHER)
        assert not loeschbar("01-base/policy", {}, _SICHER)
        assert not loeschbar("03-patterns/m01", _muster("M01"), _SICHER)
        assert not loeschbar("03-patterns/krise", _muster("m07"), _SICHER)

    def test_eigenes_bleibt_loeschbar(self):
        assert loeschbar("01-base/eigenbau", {"x": 1}, _SICHER)
        assert loeschbar("03-patterns/m42", _muster("M42"), _SICHER)
        assert loeschbar("04-personas/neu", _muster("P-NEU"), _SICHER)


def test_gestrichene_bereiche_kommen_nicht_zurueck():
    """Paket 7 (K4) hat sie mit Modell, Seed und Migration 0007 gestrichen; eine alte
    Sicherung legte sie als wirkungslose Rohdokumente wieder an."""
    assert not is_restorable_area_key("05-canvas/create-triggers")
    assert not is_restorable_area_key("05-canvas/edit-triggers")
    assert is_restorable_area_key("05-canvas/material-types")


class TestKennungen:
    def test_ein_gewoehnliches_muster_geht_durch(self):
        bestand = {"03-patterns/m01": _muster("M01")}
        assert kennungs_einwand({"03-patterns/m42": _muster("M42")}, bestand, _SICHER) is None

    def test_doppelte_kennung_in_der_sicherung(self):
        neu = {"03-patterns/a": _muster("M05"), "03-patterns/b": _muster("m05")}
        einwand = kennungs_einwand(neu, {}, _SICHER)
        assert einwand is not None and einwand.meldung == "documents.idTaken"
        assert einwand.art == "vergeben"

    def test_doppelte_kennung_gegen_den_bestand(self):
        einwand = kennungs_einwand({"03-patterns/krise2": _muster("M01")},
                                   {"03-patterns/m01": _muster("M01")}, _SICHER)
        assert einwand is not None and einwand.meldung == "documents.idTaken"

    def test_ein_sicherheitsmuster_behaelt_seine_kennung(self):
        einwand = kennungs_einwand({"03-patterns/m01": _muster("M99")},
                                   {"03-patterns/m01": _muster("M01")}, _SICHER)
        assert einwand is not None and einwand.meldung == "documents.idSafety"

    def test_ein_sicherheitsmuster_ohne_kennung_wird_abgewiesen(self):
        """Review Paket 9 (MAJOR 5): ein Dokument ohne Kennung passierte — auch M01 mit
        geleerter Kennung. Der Lader überspringt Muster ohne ``id``, und das Erzwingen
        bei Krise fände M01 nicht mehr."""
        bestand = {"03-patterns/m01": _muster("M01")}
        for leer in ({"frontmatter": {"id": "", "label": "Krise"}, "body": "x"}, {"body": "x"}):
            einwand = kennungs_einwand({"03-patterns/m01": leer}, bestand, _SICHER)
            assert einwand is not None and einwand.meldung == "documents.idSafety"

    def test_form_und_persona_schluessel(self):
        assert kennungs_einwand({"03-patterns/x": _muster("M 1")}, {},
                                _SICHER).meldung == "documents.idInvalid"
        assert kennungs_einwand({"04-personas/falsch": _muster("P-LK")}, {},
                                _SICHER).meldung == "documents.personaKey"

    def test_andere_bereiche_und_dokumente_ohne_kennung_gehen_durch(self):
        assert kennungs_einwand({"01-base/welcome-config": {"welcome": {}},
                                 "03-patterns/leer": {"body": "x"}}, {}, _SICHER) is None


def test_speichern_weist_ein_geleertes_sicherheitsmuster_ab(monkeypatch):
    """Review Paket 9 (MAJOR 5): ``pruefe_kennung`` kehrte ohne Kennung vorher zurück."""
    import asyncio

    import pytest
    from fastapi import HTTPException

    from boerdi.api import config_documents as cd

    async def _bestand():
        return {"03-patterns/m01": _muster("M01")}

    async def _sicher():
        return _SICHER

    monkeypatch.setattr(cd.cl, "current_config", _bestand)
    monkeypatch.setattr(cd, "sicherheits_kennungen", _sicher)
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(cd.pruefe_kennung("03-patterns/m01", {"frontmatter": {}, "body": "x"}, "de"))
    assert fehler.value.status_code == 400
