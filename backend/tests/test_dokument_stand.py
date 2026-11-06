"""Paket U3-2b: das Dokument der Sitzung für den Zug — einmal laden, Frist verlängern, freigeben."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import OperationalError

from boerdi.domain.dokument_gliederung import Abschnitt
from boerdi.services.dokumente import stand
from boerdi.ui_module import dienst_upload


@pytest.fixture(autouse=True)
def _erlaubt(monkeypatch):
    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: True)


class _S:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.commits -= 100


def _zeile():
    return SimpleNamespace(
        id="u-1", name="Lehrplan.pdf", format="pdf", befund={"abschnitte": 2},
        gliederung=[{"id": "a1", "ebene": 1, "titel": "Mechanik", "start": 0, "ende": 10},
                    {"id": "a2", "ebene": 1, "titel": "Optik", "start": 10, "ende": 20}],
        markdown="# Mechanik\n# Optik\n")


def test_der_lader_liest_einmal_beruehrt_und_gibt_den_stand(monkeypatch):
    gelesen, beruehrt = [], []

    async def aktuelles(s, session_id, aufrufer):
        gelesen.append((session_id, aufrufer))
        return _zeile()

    async def beruehren(s, upload_id, *, ttl_h):
        beruehrt.append((upload_id, ttl_h))

    monkeypatch.setattr(stand.ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(stand.ablage, "beruehren", beruehren)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: True)
    monkeypatch.setattr(stand, "aufrufer_kennung", lambda: "person-a")
    s = _S()
    laden = stand.lader(s, "sitzung-0123456789")

    async def zweimal():
        return await laden(), await laden()

    eins, zwei = asyncio.run(zweimal())
    assert eins is zwei and eins.upload_id == "u-1" and eins.name == "Lehrplan.pdf"
    assert eins.abschnitte == [Abschnitt("a1", 1, "Mechanik", 0, 10),
                               Abschnitt("a2", 1, "Optik", 10, 20)]
    assert gelesen == [("sitzung-0123456789", "person-a")]
    assert beruehrt == [("u-1", 24)] and s.commits == 1


def test_ohne_anmeldung_ohne_aufrufer_und_ohne_dokument_none(monkeypatch):
    gelesen = []

    async def aktuelles(s, session_id, aufrufer):
        gelesen.append(aufrufer)

    monkeypatch.setattr(stand.ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None
    assert gelesen == [None]


def test_eine_kaputte_gliederung_zaehlt_als_kein_dokument(monkeypatch):
    async def aktuelles(s, session_id, aufrufer):
        z = _zeile()
        z.gliederung = [{"id": "a1"}]
        return z

    monkeypatch.setattr(stand.ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None


def test_abgeschaltet_gibt_es_kein_dokument_ohne_abfrage(monkeypatch):
    """Review U3-2 Befund 7: schaltet das Studio ab, bleibt ein gespeichertes Dokument ungenutzt."""
    async def nie(*_a):
        raise AssertionError("keine Abfrage, wenn es nicht erlaubt ist")

    monkeypatch.setattr(dienst_upload, "dokument_erlaubt", lambda: False)
    monkeypatch.setattr(stand.ablage, "aktuelles", nie)
    assert asyncio.run(stand.lader(_S(), "sitzung-0123456789")()) is None


def test_ein_datenbankfehler_ergibt_kein_dokument_statt_einer_ausnahme(monkeypatch):
    async def streikt(*_a):
        raise OperationalError("select", {}, Exception("weg"))

    monkeypatch.setattr(stand.ablage, "aktuelles", streikt)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    s = _S()
    assert asyncio.run(stand.lader(s, "sitzung-0123456789")()) is None
    assert s.commits == -100                  # zurückgerollt
