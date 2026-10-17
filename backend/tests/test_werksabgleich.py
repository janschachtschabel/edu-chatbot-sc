"""Paket 12, W4: der Werksabgleich als Ablauf (ohne Datenbank, Rückrufe als Attrappen).

Seed lesen und prüfen wie jeder andere Seed-Weg, den gelebten Stand einmal lesen, planen
(``werkfassung.plane_werksabgleich``), dann bedingt schreiben — mit der gelesenen Version und der
Werks-Prüfsumme je Bereich (Review #2) — und gleichende Bereiche nur zuordnen. Bereiche mit
Kennungs-Kollision werden übersprungen und gemeldet, nicht abgebrochen (Review #6): der Abgleich
läuft beim Start, ein Abbruch hielte den Deploy an.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from boerdi.services import seed_sync
from boerdi.services.werkfassung import pruefsumme


def _seed(tmp_path: Path) -> Path:
    (tmp_path / "03-patterns").mkdir()
    for nr in ("m01", "m02", "m03", "m04"):
        (tmp_path / "03-patterns" / f"{nr}.md").write_text(
            f"---\nid: {nr.upper()}\n---\nneu\n", encoding="utf-8")
    return tmp_path


def _werk(kennung: str, body: str = "neu\n") -> dict:
    return {"frontmatter": {"id": kennung}, "body": body}


class _Attrappe:
    def __init__(self, zeilen, *, verlieren: frozenset[str] = frozenset()):
        self.zeilen = zeilen
        self.verlieren = verlieren  # Bereiche, die „dazwischen“ geändert wurden
        self.eintraege: dict = {}
        self.zugeordnet: dict = {}

    async def lesen(self):
        return self.zeilen

    async def entfernte(self):
        return set()

    async def schreiben(self, eintraege):
        self.eintraege = dict(eintraege)
        return {a: 1 for a in eintraege if a not in self.verlieren}

    async def zuordnen(self, hashes):
        self.zugeordnet.update(hashes)


def _lauf(pfad, a: _Attrappe, kollisionen=None):
    return asyncio.run(seed_sync.werksabgleich(
        pfad, pruefen=lambda s: s, lesen=a.lesen, entfernte=a.entfernte, schreiben=a.schreiben,
        zuordnen=a.zuordnen, kollisionen=kollisionen))


def test_ablauf_schreibt_bedingt_mit_version_und_pruefsumme(tmp_path):
    pfad = _seed(tmp_path)
    alt = _werk("M01", "alt\n")
    a = _Attrappe([
        {"area": "03-patterns/m01", "data": alt, "werk_hash": pruefsumme(alt),
         "updated_by": "x", "version": 4},
        {"area": "03-patterns/m02", "data": _werk("M02"), "werk_hash": None,
         "updated_by": "x", "version": 2},
        {"area": "03-patterns/m04", "data": _werk("M04", "eigen\n"),
         "werk_hash": pruefsumme(_werk("M04")), "updated_by": "studio", "version": 9},
    ])
    bericht = _lauf(pfad, a)

    assert a.eintraege == {
        "03-patterns/m01": (_werk("M01"), pruefsumme(_werk("M01")), 4, None),
        "03-patterns/m03": (_werk("M03"), pruefsumme(_werk("M03")), None, None),
    }
    assert a.zugeordnet == {"03-patterns/m02": pruefsumme(_werk("M02"))}
    assert bericht == {"neu": 1, "aktualisiert": 1, "zugeordnet": 1, "neues_werk": 0,
                       "uebersprungen": 0, "konflikt": 0}


def test_was_dazwischen_geaendert_wurde_zaehlt_als_uebersprungen(tmp_path):
    pfad = _seed(tmp_path)
    a = _Attrappe([], verlieren=frozenset({"03-patterns/m01"}))
    bericht = _lauf(pfad, a)
    # Review 2 #3: gezählt wird, was geschrieben wurde — nicht, was geplant war.
    assert bericht["neu"] == 3 and bericht["uebersprungen"] == 1


def test_kennungs_kollision_wird_uebersprungen_statt_abzubrechen(tmp_path):
    pfad = _seed(tmp_path)
    a = _Attrappe([])

    def kollisionen(zu_schreiben, _bestand):
        return {"03-patterns/m02"} & set(zu_schreiben)

    bericht = _lauf(pfad, a, kollisionen)
    assert "03-patterns/m02" not in a.eintraege
    assert bericht["konflikt"] == 1 and bericht["neu"] == 3


def test_ungueltiger_seed_bricht_vor_dem_lesen_ab(tmp_path):
    pfad = _seed(tmp_path)

    def pruefen(_seed):
        raise ValueError("ungültig")

    async def nie(*_a):
        raise AssertionError("darf nicht laufen")

    with pytest.raises(ValueError):
        asyncio.run(seed_sync.werksabgleich(pfad, pruefen=pruefen, lesen=nie, entfernte=nie,
                                            schreiben=nie, zuordnen=nie))


def test_seed_wird_je_prozess_einmal_gelesen_und_bei_aenderung_neu(tmp_path, monkeypatch):
    """Review #4: jeder Studio-Aufruf las den ganzen Seed synchron auf dem Event-Loop (~360 ms).
    Der Seed ist im Abbild unveränderlich — gelesen wird einmal, neu nur nach einer Änderung."""
    from boerdi.services import seed_io

    pfad = _seed(tmp_path)
    echt = seed_io.import_tree
    aufrufe = []

    async def zaehlend(src, put):
        aufrufe.append(src)
        return await echt(src, put)

    monkeypatch.setattr(seed_io, "import_tree", zaehlend)
    erst = asyncio.run(seed_sync.seed_lesen(pfad))
    erst["03-patterns/m01"]["body"] = "verändert vom Aufrufer"  # darf den Speicher nicht treffen
    zweit = asyncio.run(seed_sync.seed_lesen(pfad))
    assert len(aufrufe) == 1
    assert zweit["03-patterns/m01"]["body"] == "neu\n"

    (pfad / "03-patterns" / "m01.md").write_text("---\nid: M01\n---\ngeändert\n", encoding="utf-8")
    dritt = asyncio.run(seed_sync.seed_lesen(pfad))
    assert len(aufrufe) == 2 and dritt["03-patterns/m01"]["body"] == "geändert\n"


def test_anhebung_nur_ueber_die_import_kennung_legt_den_alten_inhalt_still(tmp_path):
    """Review 2 #4: ein Bestand ohne Basis, zuletzt per Import geschrieben, kann ein eigener Baum
    gewesen sein (Umzug per export-/import-config vor 0011) — die Anhebung bleibt umkehrbar."""
    pfad = _seed(tmp_path)
    alt = _werk("M01", "aus einem eigenen Baum")
    a = _Attrappe([{"area": "03-patterns/m01", "data": alt, "werk_hash": None,
                    "updated_by": "import", "version": 3}])
    _lauf(pfad, a)
    assert a.eintraege["03-patterns/m01"] == (_werk("M01"), pruefsumme(_werk("M01")), 3, alt)
