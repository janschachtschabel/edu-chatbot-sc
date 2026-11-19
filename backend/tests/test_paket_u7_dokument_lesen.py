"""Paket U7 (Plan 2026-11-17): ``dokument_lesen`` sieht im freien Chat auch die hier gelesenen
Inhalte (Rolle ``inhalt``), nicht nur Strukturdokumente — die Lesewege des Strukturentwurfs bleiben
bei Strukturdokumenten."""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import dokument_lesen
from boerdi.services.dokumente.stand import DokumentStand


@pytest.fixture(autouse=True)
def _erlaubt(monkeypatch):
    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)


def test_die_liste_des_werkzeugs_nennt_beide_rollen(monkeypatch):
    from boerdi.services import arbeitsstand

    gefragt = []

    async def lesbare(s, session_id, rolle="struktur"):
        gefragt.append(rolle)
        return [("k1", "Linsen.pdf")]

    monkeypatch.setattr(arbeitsstand, "lesbare_dokumente", lesbare)
    assert asyncio.run(dokument_lesen.dokumente(None, "s1")) == [("k1", "Linsen.pdf")]
    assert gefragt == [None]


def test_der_leser_laedt_beide_rollen(monkeypatch):
    from boerdi.services.dokumente import stand

    gefragt = []

    async def sitzungsdokumente(session, session_id, rolle="struktur"):
        gefragt.append(rolle)
        return [DokumentStand(upload_id="k1", name="Linsen.pdf", format="pdf", befund={},
                              abschnitte=[], markdown="Sammellinsen bündeln Licht.")]

    async def frei(_s):
        return None

    monkeypatch.setattr(stand, "sitzungsdokumente", sitzungsdokumente)
    monkeypatch.setattr(dokument_lesen, "verbindung_freigeben", frei)

    async def ohne_urteil(_t):
        return {"flagged": False, "categories": {}}

    lesen = dokument_lesen.leser(None, "s1", moderieren=ohne_urteil)
    antwort = asyncio.run(lesen({"dokument": "Linsen.pdf"}))
    assert gefragt == [None]
    assert "Linsen.pdf" in antwort


def test_der_strukturentwurf_liest_weiter_nur_strukturdokumente(monkeypatch):
    from boerdi.services.dokumente import ablage, stand

    gefragt = []

    async def alle(s, session_id, aufrufer, rolle="struktur"):
        gefragt.append(rolle)
        return []

    class _S:
        async def commit(self):
            return None

    monkeypatch.setattr(ablage, "alle_fuer_aufrufer", alle)
    asyncio.run(stand._sitzungsdokumente(_S(), "s1"))
    assert gefragt == ["struktur"]
