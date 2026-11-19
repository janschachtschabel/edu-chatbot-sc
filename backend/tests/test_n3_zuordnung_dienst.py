"""Paket N3: die Zuordnung im Dienst ``ui_strukturentwurf`` (``aus_inhalten``), im Format des
Moduls (Eingabe und Antwort), beim Speichern, Merken und Übernehmen."""

from __future__ import annotations

import asyncio
import copy

from boerdi.services import strukturentwurf_dienst
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.katalog import antwort_fehler, daten_fehler, katalog
from tests import zuordnung_beispiel as bsp

_NODE = "22222222-2222-4222-8222-222222222222"


def _roh() -> dict:
    knoten = copy.deepcopy(bsp.PUNKTE)
    knoten[0]["abschnitte"] = ["a1", "a2"]
    return {"titel": "Erdkunde", "quelle": "dokument", "thema": "Erdkunde", "knoten": knoten}


def _vorbereiten(monkeypatch, einbetten=None):
    from boerdi.ui_module import dienst

    async def erzeugen(auftrag, **_k):
        return strukturentwurf_dienst.Erzeugt(_roh())

    async def moderieren(_text):
        return {"flagged": False}

    async def nie(_texte):
        raise RuntimeError("keine Einbettung im Test")

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", erzeugen)
    monkeypatch.setattr(dienst, "_moderation", lambda: moderieren)
    monkeypatch.setattr(dienst, "_einbetten", lambda *_a: einbetten or nie)
    return dienst


def _rufe(dienst, teile: dict):
    async def lese(name):
        return teile.get(name)

    return asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Erdkunde", "aus_inhalten": True},
        Umgebung(teile=lese)))


def test_der_entwurf_traegt_inhalte_mit_node_id_und_nicht_zugeordnet(monkeypatch):
    dienst = _vorbereiten(monkeypatch)
    erg = _rufe(dienst, {"metadaten": bsp.teil(mit_node_ids=True)})
    daten = erg.block.daten
    assert [e["name"] for e in daten["knoten"][0]["inhalte"]] == [
        "Aufbau eines Schichtvulkans", "Der Ausbruch des Vesuv 79 n. Chr."]
    assert daten["knoten"][0]["inhalte"][0]["node_id"] == "00000000-0000-4000-8000-000000000000"
    # die Einbettung fällt im Test aus: der Rest ist nicht zugeordnet, kein Fehler
    assert len(daten["nicht_zugeordnet"]) == 14 and daten["quelle_block"] == "blockbsp01"
    assert daten_fehler(katalog()["ui_strukturentwurf"], daten) == []
    assert "14 Materialien keinem Punkt zugeordnet" in erg.text


def test_lokal_kommt_die_node_id_aus_der_gebundenen_ablage(monkeypatch):
    dienst = _vorbereiten(monkeypatch)
    ablage = {"block_id": "blockbsp01", "inhalte": [
        {"i": 0, "stand": "stored", "node_id": _NODE}]}
    erg = _rufe(dienst, {"metadaten": bsp.teil(), "struktur": {"block_id": "blockbsp01"},
                         "ablage": ablage})
    assert erg.block.daten["knoten"][0]["inhalte"][0] == {
        "i": 0, "name": "Aufbau eines Schichtvulkans", "node_id": _NODE}
    # eine Ablage aus einem anderen Feld zählt nicht
    erg = _rufe(dienst, {"metadaten": bsp.teil(), "struktur": {"block_id": "anderes01"},
                         "ablage": {**ablage, "block_id": "anderes01"}})
    assert "node_id" not in erg.block.daten["knoten"][0]["inhalte"][0]


def test_die_einbettung_des_dienstes_zieht_nach(monkeypatch):
    gesehen: list[list[str]] = []

    async def einbetten(texte):
        gesehen.append(texte)
        return [[1.0, 0.0]] * len(texte)       # alles gleich: alles an den ersten Punkt

    dienst = _vorbereiten(monkeypatch, einbetten)
    daten = _rufe(dienst, {"metadaten": bsp.teil()}).block.daten
    assert len(gesehen) == 1 and len(daten["knoten"][0]["inhalte"]) == 16
    assert "nicht_zugeordnet" not in daten


def test_ohne_aus_inhalten_keine_zuordnung(monkeypatch):
    dienst = _vorbereiten(monkeypatch)

    async def lese(_name):
        return None

    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Erdkunde"}, Umgebung(teile=lese)))
    assert "inhalte" not in erg.block.daten["knoten"][0]
    assert "nicht_zugeordnet" not in erg.block.daten


def _entwurf_mit_rest() -> dict:
    return {"titel": "E", "quelle": "ki", "quelle_block": "blockbsp01",
            "knoten": [{"id": "k1", "titel": "Vulkane",
                        "inhalte": [{"i": 0, "name": "A", "node_id": _NODE}]}],
            "nicht_zugeordnet": [{"i": 3, "name": "Bruch\nrechnung", "node_id": _NODE}]}


def test_die_antwort_darf_nicht_zugeordnet_zurueckschicken():
    antwort = {**_entwurf_mit_rest(), "uebernommen": True, "bearbeitet": False}
    antwort["nicht_zugeordnet"][0]["name"] = "Bruchrechnung"
    assert antwort_fehler(katalog()["ui_strukturentwurf"], antwort) == []


def test_node_ids_auch_der_nicht_zugeordneten_nur_vom_server():
    neu = se.mit_knoten_ids(_entwurf_mit_rest(), {3: "33333333-3333-4333-8333-333333333333"})
    assert neu["nicht_zugeordnet"][0]["node_id"] == "33333333-3333-4333-8333-333333333333"
    assert "node_id" not in neu["knoten"][0]["inhalte"][0]
    assert se.knoten_ids_im_entwurf(_entwurf_mit_rest()) == {0: _NODE, 3: _NODE}
    assert se.hat_inhalte({"knoten": [{"id": "k", "titel": "t"}],
                           "nicht_zugeordnet": [{"i": 1, "name": "x"}]})
    assert not se.hat_inhalte({"knoten": [{"id": "k", "titel": "t"}]})


def test_kuratieren_texte_und_grenzen_kennen_nicht_zugeordnet(monkeypatch):
    assert "nicht_zugeordnet" not in se.ohne_inhalte(_entwurf_mit_rest())
    assert se.normalisiert(_entwurf_mit_rest())["nicht_zugeordnet"][0]["name"] == "Bruch rechnung"
    monkeypatch.setattr(se, "HOECHSTENS_INHALTE", 1)
    assert any("2 Inhalte" in f for f in se.fehler(_entwurf_mit_rest()))


def test_merken_behaelt_nicht_zugeordnet_und_kuerzt_es_mit(monkeypatch):
    from boerdi.ui_module import strukturentwurf_merken as merken

    entities: dict = {}
    merken._merken(entities, _entwurf_mit_rest())
    assert entities[merken.KEY]["daten"]["nicht_zugeordnet"][0]["i"] == 3
    monkeypatch.setattr(merken, "HOECHSTENS_ZEICHEN", 10)
    merken._merken(entities, _entwurf_mit_rest())
    assert "nicht_zugeordnet" not in entities[merken.KEY]["daten"]


def test_vertiefen_einer_vorlage_behaelt_die_zuordnung():
    async def llm(_n, *_a):
        return {"knoten": [{"titel": "Neu A"}, {"titel": "Neu B"}]}

    vorlage = _entwurf_mit_rest()
    erzeugt = asyncio.run(strukturentwurf_dienst.erzeugen(
        strukturentwurf_dienst.Auftrag(thema="E", tiefe=2), llm=llm,
        frist_ende=asyncio.new_event_loop().time() + 600, vorlage=vorlage))
    assert erzeugt.daten["nicht_zugeordnet"] == vorlage["nicht_zugeordnet"]
    assert erzeugt.daten["knoten"][0]["inhalte"] == vorlage["knoten"][0]["inhalte"]


def test_anlegen_der_sammlungen_behaelt_inhalte_mit_node_id():
    from boerdi.ui_module.strukturentwurf_bestand import mit_kennungen

    wlo = "44444444-4444-4444-8444-444444444444"
    neu = mit_kennungen(_entwurf_mit_rest(), {"nodes": [
        {"path": "Vulkane", "nodeId": wlo, "status": "created"}]})
    assert neu["knoten"][0]["wlo_id"] == wlo
    assert neu["knoten"][0]["inhalte"] == [{"i": 0, "name": "A", "node_id": _NODE}]
    assert neu["nicht_zugeordnet"][0]["node_id"] == _NODE
