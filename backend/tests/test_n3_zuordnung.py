"""Paket N3 (Plan 2026-11-19): Zuordnung Datei → Punkt im Entwurf ``aus_inhalten``.

Deterministisch mit festen Vektoren (kein Netz): Übernahme der ``abschnitte`` des Modells als
``inhalte``, ``node_id`` vor ``i``, Nachziehen über Einbettungen oberhalb der Schwelle, sonst
„nicht zugeordnet“, ein Aufruf für alle, Ausfall ohne Fehler. Der Beispielsatz
(``zuordnung_beispiel``) prüft die Güte der Logik; die Güte des echten Modells misst
``scripts/zuordnung_messen.py``.
"""

from __future__ import annotations

import asyncio
import copy
import math

from boerdi.services import strukturentwurf_zuordnung as zu
from tests import zuordnung_beispiel as bsp

_THEMEN = ("k1", "k2", "k3", "k4")


def _vektor(punkt: str | None, staerke: float = 1.0) -> list[float]:
    """Achse je Thema plus eine fünfte für „fachfremd“."""
    v = [0.05] * 5
    v[_THEMEN.index(punkt) if punkt else 4] = staerke
    return v


class _Einbettung:
    """Feste Vektoren: Punkte nach ihrem Titel, Materialien nach ihrem Titel im Beispiel."""

    def __init__(self, fehler: Exception | None = None) -> None:
        self.aufrufe: list[list[str]] = []
        self.fehler = fehler
        titel = {e["titel"]: bsp.ERWARTET[f"a{n}"]
                 for n, e in enumerate(bsp.teil()["inhalte"], 1)}
        self.material = titel
        self.punkt = {p["titel"]: p["id"] for p in bsp.PUNKTE}

    async def __call__(self, texte: list[str]) -> list[list[float]]:
        self.aufrufe.append(list(texte))
        if self.fehler:
            raise self.fehler
        aus = []
        for t in texte:
            kopf = t.split("\n", 1)[0]
            if kopf in self.punkt:
                aus.append(_vektor(self.punkt[kopf]))
            else:
                aus.append(_vektor(self.material[kopf]))
        return aus


def _entwurf(abschnitte: dict[str, list[str]] | None = None) -> dict:
    knoten = copy.deepcopy(bsp.PUNKTE)
    for k in knoten:
        if abschnitte and k["id"] in abschnitte:
            k["abschnitte"] = abschnitte[k["id"]]
    return {"titel": "Erdkunde", "quelle": "ki", "knoten": knoten}


def _zuordnen(daten, teil, einbetten=None, **kw):
    return asyncio.run(zu.zuordnen(daten, teil, einbetten=einbetten, **kw))


def _punkt_von(daten) -> dict[int, list[str]]:
    """``i`` → Kennungen der Punkte, an denen der Inhalt hängt."""
    aus: dict[int, list[str]] = {}
    for k in daten["knoten"]:
        for e in k.get("inhalte") or []:
            aus.setdefault(e["i"], []).append(k["id"])
    return aus


def test_das_modell_ordnet_zu_und_der_eintrag_traegt_node_id_und_titel():
    teil = bsp.teil(mit_node_ids=True)
    erg = _zuordnen(_entwurf({"k1": ["a1", "a2"], "k2": ["a5"]}), teil)
    k1 = erg.daten["knoten"][0]
    assert k1["inhalte"] == [
        {"i": 0, "name": "Aufbau eines Schichtvulkans",
         "node_id": "00000000-0000-4000-8000-000000000000"},
        {"i": 1, "name": "Der Ausbruch des Vesuv 79 n. Chr.",
         "node_id": "00000000-0000-4000-8000-000000000001"}]
    assert erg.modell == 3


def test_lokal_ohne_node_id_traegt_der_eintrag_i_und_titel():
    erg = _zuordnen(_entwurf({"k3": ["a9"]}), bsp.teil())
    assert erg.daten["knoten"][2]["inhalte"] == [{"i": 8, "name": "Erdbebenwellen und Seismograph"}]


def test_node_id_aus_der_ablage_wenn_das_material_keine_traegt():
    erg = _zuordnen(_entwurf({"k3": ["a9"]}), bsp.teil(),
                    node_ids={8: "11111111-1111-4111-8111-111111111111"})
    assert erg.daten["knoten"][2]["inhalte"][0]["node_id"] == "11111111-1111-4111-8111-111111111111"


def test_unbekannte_kennungen_zaehlen_nicht_und_der_rest_ist_nicht_zugeordnet():
    erg = _zuordnen(_entwurf({"k1": ["a1", "a99", "x", "a1"]}), bsp.teil())
    assert [e["i"] for e in erg.daten["knoten"][0]["inhalte"]] == [0]
    assert erg.modell == 1 and erg.einbettung == 0 and erg.uebrig == 15
    assert len(erg.daten["nicht_zugeordnet"]) == 15
    assert erg.daten["nicht_zugeordnet"][0] == {"i": 1, "name": "Der Ausbruch des Vesuv 79 n. Chr."}


def test_die_einbettung_zieht_nach_in_einem_aufruf_fuer_alle():
    einbetten = _Einbettung()
    erg = _zuordnen(_entwurf({"k1": ["a1"]}), bsp.teil(), einbetten)
    assert len(einbetten.aufrufe) == 1
    # vier Punkte und 15 offene Materialien — das zugeordnete nicht noch einmal
    assert len(einbetten.aufrufe[0]) == 4 + 15
    zuordnung = _punkt_von(erg.daten)
    for n, erwartet in bsp.ERWARTET.items():
        i = int(n[1:]) - 1
        assert zuordnung.get(i, [None]) == [erwartet], n
    assert erg.modell == 1 and erg.einbettung == 13 and erg.uebrig == 2
    assert [e["i"] for e in erg.daten["nicht_zugeordnet"]] == [14, 15]


def test_unter_der_schwelle_bleibt_ein_material_nicht_zugeordnet(monkeypatch):
    class Schwach(_Einbettung):
        async def __call__(self, texte):
            vektoren = await super().__call__(texte)
            # „Klimazonen“ zwischen Klima und Vulkanen: Ähnlichkeit zu k4 rund 0,78, zu k1 0,71
            return [v if t.split("\n", 1)[0] != "Klimazonen der Erde" else [0.9, .05, .05, 1, .05]
                    for t, v in zip(texte, vektoren, strict=True)]

    def klimazonen(erg):
        return _punkt_von(erg.daten).get(12)

    monkeypatch.setitem(zu.SCHWELLEN, "text-embedding-3-small", 0.70)
    assert klimazonen(_zuordnen(_entwurf(), bsp.teil(), Schwach())) == ["k4"]
    monkeypatch.setitem(zu.SCHWELLEN, "text-embedding-3-small", 0.80)
    erg = _zuordnen(_entwurf(), bsp.teil(), Schwach())
    assert klimazonen(erg) is None and 12 in [e["i"] for e in erg.daten["nicht_zugeordnet"]]


def test_faellt_die_einbettung_aus_bleibt_es_ohne_nachziehen_und_ohne_fehler():
    einbetten = _Einbettung(fehler=RuntimeError("Anbieter weg"))
    erg = _zuordnen(_entwurf({"k2": ["a5", "a6"]}), bsp.teil(), einbetten)
    assert erg.modell == 2 and erg.einbettung == 0 and erg.uebrig == 14
    assert len(erg.daten["nicht_zugeordnet"]) == 14


def test_falsche_zahl_von_vektoren_gilt_als_ausfall():
    async def kaputt(texte):
        return [[1.0, 0.0]]

    erg = _zuordnen(_entwurf(), bsp.teil(), kaputt)
    assert erg.einbettung == 0 and erg.uebrig == 16


def test_ohne_offene_materialien_kein_aufruf():
    einbetten = _Einbettung()
    alle = {f"k{p}": [n for n, e in bsp.ERWARTET.items() if e == f"k{p}"] for p in range(1, 5)}
    teil = bsp.teil()
    teil["inhalte"] = teil["inhalte"][:14]          # ohne die fachfremden
    erg = _zuordnen(_entwurf(alle), teil, einbetten)
    assert einbetten.aufrufe == [] and erg.modell == 14 and "nicht_zugeordnet" not in erg.daten


def test_einträge_ohne_nummer_fallen_weg_die_kennungen_bleiben_wie_im_dokument():
    teil = bsp.teil(mit_node_ids=True)
    del teil["inhalte"][0]["i"]          # ein Stapel vor TG-3b: ohne feste Nummer
    erg = _zuordnen(_entwurf({"k1": ["a1", "a2"]}), teil)
    assert [e["i"] for e in erg.daten["knoten"][0]["inhalte"]] == [1]
    assert all(e.get("i") != 0 for e in erg.daten.get("nicht_zugeordnet", []))


def test_die_auswahl_steht_im_entwurf_und_das_original_bleibt():
    daten = _entwurf({"k1": ["a1"]})
    vorher = copy.deepcopy(daten)
    erg = _zuordnen(daten, bsp.teil(block_id="abc12345"))
    assert erg.daten["quelle_block"] == "abc12345" and daten == vorher
    assert "quelle_block" not in _zuordnen(_entwurf(), bsp.teil(block_id="NICHT GUT!")).daten


def test_ein_material_darf_an_zwei_punkten_haengen():
    erg = _zuordnen(_entwurf({"k2": ["a11"], "k3": ["a11"]}), bsp.teil())
    assert _punkt_von(erg.daten)[10] == ["k2", "k3"] and erg.modell == 1


def test_die_grenze_der_inhalte_gilt_fuer_den_ganzen_entwurf(monkeypatch):
    from boerdi.ui_module import strukturentwurf as se

    monkeypatch.setattr(se, "HOECHSTENS_INHALTE", 3)
    erg = _zuordnen(_entwurf({"k1": ["a1", "a2", "a3", "a4"]}), bsp.teil())
    zahl = sum(len(k.get("inhalte") or []) for k in erg.daten["knoten"])
    assert zahl + len(erg.daten.get("nicht_zugeordnet") or []) == 3
    assert erg.daten["gekuerzt"] is True


def test_texte_fuer_die_einbettung():
    material = zu.materialien(bsp.teil())[0]
    assert material.text.startswith("Aufbau eines Schichtvulkans\n")
    assert "Magmakammer" in material.text and "Krater" in material.text
    punkt = zu.punkt_text(bsp.PUNKTE[0])
    assert punkt.startswith("Vulkane\n") and "Aufbau eines Vulkans" in punkt


def test_kosinus():
    assert math.isclose(zu.kosinus([1, 0], [1, 0]), 1.0)
    assert math.isclose(zu.kosinus([1, 0], [0, 1]), 0.0)
    assert zu.kosinus([0, 0], [1, 0]) == 0.0
