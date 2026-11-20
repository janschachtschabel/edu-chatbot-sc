"""Plan 2026-11-19, A6 (E7, Wunsch Rückkontrolle): der Entwurf aus einem Dokument trägt ``gelesen``.

Je Dokument Name, Zeichen, Weg (``ganz``/``gliederung``), die ersten ``GELESEN_ANFANG`` Zeichen des
gelesenen Texts und bis zu ``GELESEN_ABSCHNITTE`` Abschnittstitel. Das Feld setzt nur das System
(``x-nur-system``) — die KI sieht und setzt es nie, und es geht weder in die Quittung noch in den
gemerkten Entwurf noch in eine Vertiefung (nur Anzeige).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

from boerdi.domain.dokument_gliederung import gliederung
from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services import strukturentwurf_dokument as sd
from boerdi.services.ablauf.metadaten import DOKUMENT_FORMAT
from boerdi.services.dokumente import stand
from boerdi.ui_module import katalog
from boerdi.ui_module import strukturentwurf_merken as merken
from boerdi.ui_module.namen import STRUKTURENTWURF
from boerdi.ui_module.werkzeuge import _fuer_die_ki
from tests.test_strukturentwurf_dienst import Attrappe, _k
from tests.test_strukturentwurf_dokument import _MD


def _dokument(md: str = _MD, name: str = "Lehrplan.pdf", **mehr):
    abschnitte, _ = gliederung(md)
    return SimpleNamespace(markdown=md, abschnitte=abschnitte, name=name, **mehr)


def _stand(name: str, md: str) -> stand.DokumentStand:
    abschnitte, art = gliederung(md)
    return stand.DokumentStand(upload_id=name, name=name, format="md", befund={},
                               abschnitte=abschnitte, markdown=md)


def test_ein_kurzes_dokument_ganz_gelesen():
    [g] = sd.gelesen(_dokument(), ganz=True)
    assert g == {"name": "Lehrplan.pdf", "zeichen": len(_MD), "weg": "ganz", "anfang": _MD,
                 "abschnitte": [a.titel for a in gliederung(_MD)[0]]}


def test_ein_langes_dokument_ueber_die_gliederung():
    md = "# Plan\n" + "".join(f"## Kapitel {i}\n{'Wort ' * 400}\n" for i in range(1, 60))
    [g] = sd.gelesen(_dokument(md))
    assert g["weg"] == "gliederung" and g["zeichen"] == len(md) > sd.GANZTEXT_ZEICHEN
    assert g["anfang"] == md[:sd.GELESEN_ANFANG]
    assert len(g["abschnitte"]) == sd.GELESEN_ABSCHNITTE and g["abschnitte"][1] == "Kapitel 1"


def test_mehrere_dokumente_je_ein_eintrag():
    md_b = "# Wärme\nTemperatur.\n## Energie\nJoule.\n"
    vereint = stand.vereint([_stand("A.pdf", _MD), _stand("B.pdf", md_b)])
    a, b = sd.gelesen(vereint, ganz=True)
    assert (a["name"], a["zeichen"], a["anfang"]) == ("A.pdf", len(_MD), _MD)
    assert (b["name"], b["zeichen"], b["anfang"]) == ("B.pdf", len(md_b), md_b)
    assert b["abschnitte"] == [x.titel for x in gliederung(md_b)[0]]
    assert a["abschnitte"] == [x.titel for x in gliederung(_MD)[0]]
    assert a["weg"] == b["weg"] == "ganz"


def test_die_materialien_der_person_tragen_nichts():
    assert sd.gelesen(_dokument(format=DOKUMENT_FORMAT)) == []
    assert sd.gelesen(None) == []


def test_hoechstens_zehn_dokumente():
    vereint = stand.vereint([_stand(f"{n}.pdf", f"# T{n}\nText.\n") for n in range(12)])
    assert len(sd.gelesen(vereint)) == sd.GELESEN_DOKUMENTE == 10


async def test_der_dienst_setzt_gelesen_nur_mit_dokument():
    ende = asyncio.get_running_loop().time() + 60
    mit = await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=1), llm=Attrappe(
        [_k("Mechanik")]), frist_ende=ende, dokument=_dokument())
    assert mit.daten["gelesen"][0]["name"] == "Lehrplan.pdf"
    ohne = await dienst.erzeugen(dienst.Auftrag(thema="Physik", tiefe=1), llm=Attrappe(
        [_k("Mechanik")]), frist_ende=ende)
    assert "gelesen" not in ohne.daten


def test_das_manifest_kennt_gelesen_nur_fuer_das_system():
    manifest = katalog.katalog()[STRUKTURENTWURF]
    feld = manifest["eingabe"]["properties"]["gelesen"]
    assert feld["x-nur-system"] is True
    assert "gelesen" not in _fuer_die_ki(manifest["eingabe"])["properties"]
    assert "gelesen" not in manifest["dienst"]["parameter"]["properties"]
    daten = {"titel": "Physik", "quelle": "dokument", "knoten": [{"id": "k1", "titel": "Mechanik"}],
             "gelesen": sd.gelesen(_dokument())}
    assert katalog.daten_fehler(manifest, daten) == []


async def test_der_block_traegt_gelesen_die_quittung_nicht(monkeypatch):
    from boerdi.ui_module import aufruf
    from boerdi.ui_module import dienst as modul_dienst

    async def erzeugen(auftrag, **k):
        return dienst.Erzeugt({"titel": "Physik", "quelle": "dokument", "thema": "Physik",
                               "knoten": [{"id": "k1", "titel": "Mechanik"}],
                               "gelesen": sd.gelesen(k["dokument"])})

    async def lader():
        return _dokument()

    async def unbedenklich(_text, stufe=None, **_):
        return None

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    monkeypatch.setattr(modul_dienst, "_ebene_eins_pruefen", unbedenklich)
    ende = asyncio.get_running_loop().time() + 60
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Physik", "aus_dokument": True},
                                 aufruf.Umgebung(frist_ende=ende, dokument=lader))
    assert erg.block is not None and erg.block.daten["gelesen"][0]["anfang"] == _MD
    assert "Newton" not in erg.text and "Newton" not in erg.block.text


def test_merken_und_vertiefen_behalten_gelesen_nicht():
    assert "gelesen" not in merken._FELDER and "gelesen" not in dienst._WURZEL_FELDER


async def test_eine_vertiefung_traegt_gelesen_nicht():
    vorlage = {"titel": "Physik", "quelle": "dokument", "knoten": [{"id": "k1", "titel": "Optik"}],
               "gelesen": [{"name": "A", "zeichen": 1, "weg": "ganz", "anfang": "x",
                            "abschnitte": []}]}
    ende = asyncio.get_running_loop().time() + 60
    erg = await dienst.erzeugen(dienst.Auftrag(thema="Physik", vertiefen=("Optik",)),
                                llm=Attrappe([], {"Optik": [_k("Linsen"), _k("Licht")]}),
                                frist_ende=ende, vorlage=vorlage)
    assert erg.daten is not None and "gelesen" not in erg.daten
    assert "Linsen" in json.dumps(erg.daten)                      # vertieft ist trotzdem


def test_ueber_dem_deckel_faellt_gelesen_weg_der_entwurf_bleibt(monkeypatch):
    """Review A, NIT 16: ``gelesen`` ist nur Anzeige — es darf einen Entwurf nicht über den
    Deckel der Blockdaten heben (der Block ginge sonst nicht in Antwort und Verlauf)."""
    from boerdi.domain import ui_bloecke
    from boerdi.ui_module import dienst as modul_dienst

    manifest = katalog.katalog()[STRUKTURENTWURF]
    daten = {"titel": "Physik", "quelle": "dokument", "knoten": [{"id": "k1", "titel": "Mechanik"}],
             "gelesen": sd.gelesen(_dokument())}
    groesse = len(json.dumps(daten, ensure_ascii=False))
    monkeypatch.setattr(ui_bloecke, "DATEN_DECKEL_ZEICHEN", groesse - 10)
    erg = modul_dienst._block(manifest, daten, 0)
    assert erg.block is not None and "gelesen" not in erg.block.daten
    monkeypatch.setattr(ui_bloecke, "DATEN_DECKEL_ZEICHEN", 256_000)
    assert "gelesen" in modul_dienst._block(manifest, daten, 0).block.daten
