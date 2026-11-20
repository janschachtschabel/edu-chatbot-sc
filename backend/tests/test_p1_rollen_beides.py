"""Plan 2026-11-20 (Upload-Ort und Erschließung), P1 / UO-4: die Rolle ``beides``.

Je Datei wählt die Person **Gliederung** (``struktur``: liefert die Struktur, wird nicht
einsortiert), **Material** (``inhalt``: wird einsortiert), **Gliederung und Material** (``beides``)
oder „Nicht verwenden“ (``ignorieren``). ``beides`` gilt überall als Strukturdokument UND als
Inhalt; alte Einträge mit ``struktur``/``inhalt`` bleiben gültig. Die Höchstzahl der
Strukturdokumente (5) und die lesbaren Formate zählen bzw. gelten für ``struktur`` und ``beides``.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from boerdi.services import arbeitsstand_teile as at
from boerdi.services.ablage import mcp_ablage
from boerdi.services.ablage import vorgang_teil as vt
from boerdi.services.ablauf import inhalte_aus_dateien, metadaten
from boerdi.services.dokumente import ablage as dok_ablage
from boerdi.services.dokumente import metadaten_lokal as ml
from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.ui_module import katalog, upload_antwort, upload_bereitgestellt
from boerdi.ui_module.namen import UPLOAD
from boerdi.ui_module.rollen import GLIEDERUNG, MATERIAL, ist_gliederung, ist_material
from boerdi.ui_module.strukturentwurf_ordner import aus_ordnern
from tests.test_ablage_mcp import _ok, mcp  # noqa: F401 — Fixture
from tests.test_paket_u4_orte import _A, _B, bereitgestellt
from tests.test_ui_ablage_api import (  # noqa: F401 — Fixtures
    _EINTRAEGE,
    _PLAN,
    _umgebung,
    _vorbereiten,
    client,
    lage,
)

_NODE_S = "33333333-3333-4333-8333-333333333333"
_NODE_I = "44444444-4444-4444-8444-444444444444"


# --- die Hilfen ---------------------------------------------------------------------------

@pytest.mark.parametrize(("rolle", "gliederung", "material"), [
    ("struktur", True, False), ("inhalt", False, True), ("beides", True, True),
    ("ignorieren", False, False), (None, False, False), ("structure", False, False),
])
def test_rollen_hilfen(rolle, gliederung, material):
    assert ist_gliederung(rolle) is gliederung
    assert ist_material(rolle) is material


def test_rollen_mengen():
    assert frozenset({"struktur", "beides"}) == GLIEDERUNG
    assert frozenset({"inhalt", "beides"}) == MATERIAL


# --- „Hier im Chat“ -----------------------------------------------------------------------

def _beides_struktur() -> dict:
    return {"name": "Unterlagen", "dateien": 2, "alle_dateien": 2, "kinder": [], "dateiliste": [
        {"i": 0, "name": "Linsen.pdf", "endung": "pdf", "groesse": 10, "rolle": "inhalt"},
        {"i": 1, "name": "Lehrplan.pdf", "endung": "pdf", "groesse": 10, "rolle": "beides"}]}


def _chat_beides() -> dict:
    return bereitgestellt(
        "chat", struktur=_beides_struktur(),
        zahlen={"ordner": 1, "dateien": 2, "inhalte": 1, "ignoriert": 0, "strukturdokumente": 1,
                "bytes": 20},
        dateien=[{"i": 0, "rolle": "inhalt", "upload_id": _A},
                 {"i": 1, "rolle": "beides", "upload_id": _B}])


def test_antwortpruefung_nimmt_beides():
    daten = _chat_beides()
    assert katalog.antwort_fehler(katalog.katalog()[UPLOAD], daten) == []
    assert upload_antwort.grund(daten) is None


def test_beides_zaehlt_als_strukturdokument_in_der_antwortpruefung():
    daten = {**_chat_beides(), "zahlen": {**_chat_beides()["zahlen"], "strukturdokumente": 0},
             "strukturdokument": None}
    assert upload_antwort.grund(daten) == "Strukturdokument in der Liste ohne Zahl"


def test_dateisatz_zaehlt_beides_als_strukturdokument():
    assert upload_antwort.dateien_satz(_chat_beides()) == (
        "2 Dateien in 1 Ordner, davon 1 Strukturdokument")


def test_chat_beides_ergibt_strukturdokument_und_lokale_metadaten():
    teile = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        {"modul": "ui_upload", "block_id": "b0000001", "daten": _chat_beides()}))
    assert teile["strukturdokument"]["dokumente"] == [
        {"quelle": "chatbot", "ref": f"dokument:{_B}", "name": "Lehrplan.pdf"}]
    inhalte = teile["metadaten"]["inhalte"]
    assert sorted((e["i"], e["lesbar"], e.get("upload_id")) for e in inhalte) == [
        (0, True, _A), (1, True, _B)]
    assert next(e for e in inhalte if e["i"] == 1)["rolle"] == "beides"


def test_lokale_metadaten_nehmen_eine_gespeicherte_zeile_mit_beides():
    roh = dict((t[0], t[2]) for t in at.teile_aus_antwort(
        {"modul": "ui_upload", "block_id": "b0000001", "daten": _chat_beides()}))["metadaten"]
    zeile = SimpleNamespace(id=_B, name="Lehrplan.pdf",
                            befund={"rolle": "beides", "angaben": {"titel": "Rahmenlehrplan"}})
    assert dok_ablage.rolle(zeile) == "beides"
    neu, _ = ml.neu_berechnet(roh, [zeile])
    e = next(e for e in neu["inhalte"] if e["i"] == 1)
    assert (e["lesbar"], e["upload_id"], e["titel"], e["rolle"]) == (
        True, _B, "Rahmenlehrplan", "beides")


def test_bereitgestellt_zeilen_zaehlen_beides_doppelt():
    _frame, zeilen = upload_bereitgestellt.zeilen(
        _chat_beides(), ablage_zeilen=None, ordner=None,
        auswahl=upload_antwort.dateien(_beides_struktur()))
    assert zeilen[0].startswith("Ort: hier im Chat gelesen — 2 Inhalte")
    assert "1 Strukturdokumente" in zeilen[0]


# --- POST /api/ui/dokumente ---------------------------------------------------------------

# Der Endpunkt selbst (``rolle=beides``): ``test_paket_u2_dokumente_api``.


def test_ocr_frist_beides_wie_inhalt():
    from boerdi.api.ui_dokumente import ocr_frist

    assert ocr_frist("beides") == ocr_frist("inhalt") < ocr_frist("struktur")


# --- In WLO ablegen -----------------------------------------------------------------------

def test_mcp_bekommt_beides_als_structure(mcp):  # noqa: F811
    mcp["antworten"]["wlo_prepare_file_batch"] = _ok({
        "batchToken": "tok-1234567890", "layout": "flat", "folderName": "X", "count": 1,
        "totalBytes": 1, "entries": [{"index": 0, "title": "Lehrplan", "ext": "pdf", "size": 1,
                                      "fileName": "l.pdf", "role": "structure"}]})
    asyncio.run(mcp_ablage.vorbereiten("X", [
        {"titel": "Lehrplan", "sha256": "a" * 64, "groesse": 1, "art": "pdf",
         "rolle": "beides"}]))
    [(_name, args)] = mcp["gerufen"]
    assert [e["role"] for e in args["entries"]] == ["structure"]


@pytest.mark.parametrize(("server", "bestaetigt"), [("structure", True), (None, False)])
def test_teil_behaelt_beides(server, bestaetigt):
    plan = {**_PLAN, "entries": [{**e, **({"role": server} if server else {})}
                                 for e in _PLAN["entries"]]}
    teil = vt.aus_plan(plan, "tok-0123456789", "b1", rollen=["beides", "inhalt"])
    assert teil["inhalte"][0]["rolle"] == "beides"
    assert teil["inhalte"][0]["rolle_bestaetigt"] is bestaetigt


def test_ersetzter_stapel_behaelt_beides():
    vorher = {"inhalte": [{"titel": "Lehrplan", "node_id": _NODE_S, "rolle": "beides",
                           "stand": "stored"}]}
    teil = vt.aus_plan(_PLAN, "tok-0123456789", "b1", vorher)
    assert teil["frueher"][0]["rolle"] == "beides"


def _ablage_beides() -> dict:
    return {"block_id": "b1", "inhalte": [
        {"index": 0, "i": 0, "titel": "Lehrplan", "name": "Lehrplan.pdf", "rolle": "beides",
         "stand": "stored", "node_id": _NODE_S},
        {"index": 1, "i": 1, "titel": "Linsen", "name": "Linsen.pdf", "rolle": "inhalt",
         "stand": "stored", "node_id": _NODE_I}],
        "frueher": [{"titel": "Alt", "node_id": "55555555-5555-4555-8555-555555555555",
                     "rolle": "beides"}]}


def test_strukturdokument_teil_aus_beides():
    aus = sd.aus_ablage(_ablage_beides())
    assert [e["ref"] for e in aus] == [_NODE_S, "55555555-5555-4555-8555-555555555555"]


def test_metadaten_rollen_kennen_beides():
    assert metadaten._kennungen(_ablage_beides()) == {_NODE_S: ("beides", 0),
                                                      _NODE_I: ("inhalt", 1)}


def test_endpunkt_nimmt_beides_und_reicht_es_durch(client, lage):  # noqa: F811
    lage.plan = {**_PLAN, "entries": [{**_PLAN["entries"][0], "role": "structure"},
                                      {**_PLAN["entries"][1], "role": "content"}]}
    r = _vorbereiten(client, eintraege=[{**_EINTRAEGE[0], "rolle": "beides"}, _EINTRAEGE[1]])
    assert r.status_code == 200, r.text
    [(_art, _ordner, gesendet)] = [m for m in lage.mcp if m[0] == "vorbereiten"]
    assert [e["rolle"] for e in gesendet] == ["beides", "inhalt"]
    assert [e["rolle"] for e in lage.teil["inhalte"]] == ["beides", "inhalt"]


def _eintrag(n: int, rolle: str, art: str = "pdf") -> dict:
    return {**_EINTRAEGE[0], "titel": f"Datei {n}", "rolle": rolle, "art": art, "i": n}


@pytest.mark.parametrize("eintraege", [
    [_eintrag(n, "struktur") for n in range(5)] + [_eintrag(5, "beides")],
    [_eintrag(0, "beides", art="png")],
], ids=["sechs_mit_beides", "beides_als_bild"])
def test_hoechstzahl_und_formate_gelten_fuer_beides(client, lage, eintraege):  # noqa: F811
    assert _vorbereiten(client, eintraege=eintraege).status_code == 422
    assert not [m for m in lage.mcp if m[0] == "vorbereiten"]


def test_fuenf_mit_beides_sind_erlaubt():
    from boerdi.api.ui_ablage import Vorbereiten

    v = Vorbereiten(session_id="sitzung-0123456789", block_id="b0000001", ordner="Physik",
                    eintraege=[_eintrag(n, "struktur") for n in range(4)]
                    + [_eintrag(4, "beides"), _eintrag(5, "inhalt")])
    assert [e.rolle for e in v.eintraege][-2:] == ["beides", "inhalt"]


# --- Entwürfe aus Dateien -----------------------------------------------------------------

def test_inhalte_aus_dateien_nimmt_beides():
    teil = inhalte_aus_dateien.aus_struktur({"block_id": "b1", "struktur": _beides_struktur()})
    assert teil is not None
    assert [(e["i"], e["rolle"]) for e in teil["inhalte"]] == [(0, "inhalt"), (1, "beides")]


def test_ordner_entwurf_nimmt_beides_als_inhalt():
    struktur = {"name": "W", "dateien": 0, "alle_dateien": 2, "dateiliste": [], "kinder": [
        {**_beides_struktur(), "name": "Optik"}]}
    daten = aus_ordnern(struktur)
    assert daten is not None
    assert [e["i"] for e in daten["knoten"][0]["inhalte"]] == [0, 1]


# --- Review P1, Befund 1: eine reine Gliederung wird nicht einsortiert (WLO-Weg) ----------

_NODE_B = "66666666-6666-4666-8666-666666666666"


def _metadaten_teil(mit_rolle: bool = True) -> dict:
    """Der Teil ``metadaten`` nach ``metadaten_lesen``: er trägt ALLE abgelegten Einträge, auch
    reine Gliederungen (für die Vorbelegung) — einsortiert werden nur ``inhalt`` und ``beides``."""
    eintraege = [(_NODE_S, "struktur", 0, "Lehrplan"), (_NODE_I, "inhalt", 1, "Linsen"),
                 (_NODE_B, "beides", 2, "Rahmenplan")]
    return metadaten._teil([{"node_id": k, "i": i, "titel": t,
                             **({"rolle": r} if mit_rolle else {})}
                            for k, r, i, t in eintraege], [], "b0000001")


def test_materialien_ohne_reine_gliederung():
    assert [e["titel"] for e in metadaten.materialien(_metadaten_teil())] == [
        "Linsen", "Rahmenplan"]


def test_als_dokument_nimmt_keine_reine_gliederung():
    dokument = metadaten.als_dokument(_metadaten_teil())
    assert dokument is not None
    assert [a.titel for a in dokument.abschnitte] == ["Linsen", "Rahmenplan"]
    assert "Lehrplan" not in dokument.markdown


def test_zuordnen_sortiert_keine_reine_gliederung_ein():
    from boerdi.services import strukturentwurf_zuordnung as sz

    daten = {"titel": "Optik", "knoten": [{"titel": "Linsen", "abschnitte": ["a1", "a2", "a3"]}]}
    neu = asyncio.run(sz.zuordnen(daten, _metadaten_teil())).daten
    assert [e["name"] for e in neu["knoten"][0]["inhalte"]] == ["Linsen", "Rahmenplan"]
    assert [e["node_id"] for e in neu["knoten"][0]["inhalte"]] == [_NODE_I, _NODE_B]


def test_alte_teile_ohne_rolle_zaehlen_weiter_alle():
    assert len(metadaten.materialien(_metadaten_teil(mit_rolle=False))) == 3


# --- Review P1, Befund 3: Vorbelegung und ``bereitgestellt`` mit ``beides`` --------------------

def test_vorbelegung_liest_fach_und_stufe_aus_einem_dokument_mit_beides():
    """``beides`` ist ein Strukturdokument: Fach, Stufe und Thema kommen aus seinen Metadaten."""
    from tests.test_paket_k5_strukturdokumente import _belegt, _eintrag
    from tests.test_paket_k5_strukturdokumente import _metadaten as _meta

    ablage = {"format": "wlo.ablage@1", "block_id": "b1", "inhalte": [
        {"index": 0, "i": 0, "titel": "Linsen.pdf", "stand": "stored", "node_id": _NODE_I,
         "rolle": "inhalt"},
        {"index": 1, "i": 1, "titel": "Plan.pdf", "stand": "stored", "node_id": _NODE_B,
         "rolle": "beides"}]}
    belegt = _belegt({"ablage": ablage, "metadaten": _meta(
        _eintrag(_NODE_I, "inhalt", titel="Linsen", faecher=["Chemie"], stufen=["Primarstufe"]),
        _eintrag(_NODE_B, "beides", titel="Rahmenlehrplan Physik", faecher=["Physik"],
                 stufen=["Sekundarstufe I"]))})
    assert (belegt["fach"], belegt["bildungsstufe"], belegt["thema"]) == (
        "Physik", "Sekundarstufe I", "Rahmenlehrplan Physik")


def test_bereitgestellt_zaehlt_beides_als_datei_und_als_inhalt():
    from boerdi.services.ablauf import werkzeuge

    struktur = _beides_struktur()
    struktur["dateiliste"] += [
        {"i": 2, "name": "Gliederung.pdf", "endung": "pdf", "groesse": 10, "rolle": "struktur"},
        {"i": 3, "name": "Notiz.txt", "endung": "txt", "groesse": 10, "rolle": "ignorieren"}]

    async def lader(name):
        return {"struktur": {"struktur": struktur}}.get(name)

    bereit = asyncio.run(werkzeuge.DIENSTE["bereitgestellt"](
        {}, werkzeuge.DienstKontext(teile=lader)))
    # inhalt + beides + struktur = 3 Dateien; einsortiert werden inhalt + beides = 2
    assert (bereit["dateien"], bereit["inhaltsdateien"]) == (3, 2)
