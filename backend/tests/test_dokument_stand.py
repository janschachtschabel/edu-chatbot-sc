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


def test_tb_e1_angemeldet_ohne_eigenes_dokument_uebernimmt_das_anonyme(monkeypatch):
    """Plan 2026-11-10, TB-E1: findet die angemeldete Person kein eigenes Dokument, übernimmt der
    Lader das anonyme derselben Sitzung (``ablage.zuschreiben``) und schreibt das fest."""
    gefragt = []

    async def aktuelles(s, session_id, aufrufer):
        gefragt.append(("aktuelles", aufrufer))
        return None

    async def zuschreiben(s, session_id, aufrufer):
        gefragt.append(("zuschreiben", aufrufer))
        return _zeile()

    async def beruehren(s, upload_id, *, ttl_h):
        return None

    monkeypatch.setattr(stand.ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(stand.ablage, "zuschreiben", zuschreiben)
    monkeypatch.setattr(stand.ablage, "beruehren", beruehren)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: True)
    monkeypatch.setattr(stand, "aufrufer_kennung", lambda: "person-a")
    s = _S()
    erg = asyncio.run(stand.laden(s, "sitzung-0123456789"))
    assert erg is not None and erg.upload_id == "u-1"
    assert gefragt == [("aktuelles", "person-a"), ("zuschreiben", "person-a")]
    assert s.commits == 1


def test_tb_e1_anonym_wird_nichts_zugeschrieben(monkeypatch):
    async def aktuelles(s, session_id, aufrufer):
        return None

    async def zuschreiben(s, session_id, aufrufer):  # pragma: no cover — darf nicht laufen
        raise AssertionError("anonym darf nichts übernehmen")

    monkeypatch.setattr(stand.ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(stand.ablage, "zuschreiben", zuschreiben)
    monkeypatch.setattr(stand, "has_personal_auth", lambda: False)
    assert asyncio.run(stand.laden(_S(), "sitzung-0123456789")) is None


def test_tb_e1_review_2_zwei_zuege_derselben_person_finden_beide_das_dokument(monkeypatch):
    """Review TB-E1, Befund 2: zwei Züge derselben Person zugleich — der zweite findet nach der
    Übernahme des ersten nichts mehr ohne Besitzerin; dann liest er noch einmal unter ihrer Kennung,
    statt ``kein_dokument`` zu melden."""
    from boerdi.services.dokumente import ablage

    antworten = iter([None, _zeile()])

    async def aktuelles(s, session_id, aufrufer):
        return next(antworten)

    async def zuschreiben(s, session_id, aufrufer):
        return None                                  # der andere Zug war schneller

    monkeypatch.setattr(ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(ablage, "zuschreiben", zuschreiben)
    erg = asyncio.run(ablage.fuer_aufrufer(_S(), "sitzung-0123456789", "person-a"))
    assert erg is not None and erg.id == "u-1"


def test_tb_e1_review_anonym_liest_fuer_aufrufer_nur_das_anonyme(monkeypatch):
    from boerdi.services.dokumente import ablage

    async def aktuelles(s, session_id, aufrufer):
        assert aufrufer is None
        return None

    async def zuschreiben(s, session_id, aufrufer):  # pragma: no cover — darf nicht laufen
        raise AssertionError("anonym wird nichts übernommen")

    monkeypatch.setattr(ablage, "aktuelles", aktuelles)
    monkeypatch.setattr(ablage, "zuschreiben", zuschreiben)
    assert asyncio.run(ablage.fuer_aufrufer(_S(), "sitzung-0123456789", None)) is None

