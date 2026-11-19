"""Anschluss N2 → Entwurf: Fach und Stufe, die das Modell in einen Entwurf schreibt, gehen durch das
WLO-Vokabular (``mcp/vokabular_labels``). Kein Treffer → leer (wie die Vorbelegung). Ohne Vokabular
(``conftest._kein_netz_fuer_vokabular``) bleibt alles wie bisher."""

from __future__ import annotations

import asyncio
import copy

import pytest

from boerdi.services import strukturentwurf_dienst, strukturentwurf_vokabular
from boerdi.services.mcp import vokabular_labels as vl
from boerdi.ui_module.aufruf import Umgebung
from boerdi.ui_module.katalog import daten_fehler, katalog

_FACH = "http://w3id.org/openeduhub/vocabs/discipline/"
_STUFE = "http://w3id.org/openeduhub/vocabs/educationalContext/"
_VOKABULAR = {
    "discipline": vl.Vokabular(
        schluessel={"geografie": _FACH + "220", "erdkunde": _FACH + "220",
                    "mathematik": _FACH + "380", "mathe": _FACH + "380"},
        labels={_FACH + "220": "Geografie", _FACH + "380": "Mathematik"}),
    "educationalContext": vl.Vokabular(
        schluessel={"sekundarstufe i": _STUFE + "s1", "sek i": _STUFE + "s1",
                    "allgemeinbildende schule": _STUFE + "ab"},
        labels={_STUFE + "s1": "Sekundarstufe I", _STUFE + "ab": "Allgemeinbildende Schule"}),
}


@pytest.fixture
def vokabular(monkeypatch):
    """Überschreibt ``conftest._kein_netz_fuer_vokabular`` gezielt: ein festes Vokabular."""
    async def geladen(vocab: str):
        return _VOKABULAR.get(vocab)

    monkeypatch.setattr(vl, "_vokabular", geladen)


def _entwurf() -> dict:
    return {"titel": "Erde", "quelle": "ki", "fach": "Erdkunde", "bildungsstufe": "Sekundarstufe I",
            "knoten": [
                {"id": "k1", "titel": "Vulkane", "fach": "Erdkunde"},
                {"id": "k2", "titel": "Maßstab", "fach": "Mathe",
                 "kinder": [{"id": "k2-1", "titel": "Rechnen", "fach": "Quatschfach 123"}]}]}


def _angleichen(daten: dict) -> dict:
    return asyncio.run(strukturentwurf_vokabular.angleichen(daten)).daten


def test_erdkunde_wird_geografie_und_punkte_wie_die_wurzel_entfallen(vokabular):
    daten = _entwurf()
    neu = _angleichen(daten)
    assert neu["fach"] == "Geografie" and neu["bildungsstufe"] == "Sekundarstufe I"
    assert "fach" not in neu["knoten"][0]               # gleich der Wurzel: wie ``knoten_aus``
    assert neu["knoten"][1]["fach"] == "Mathematik"
    assert "fach" not in neu["knoten"][1]["kinder"][0]  # kein Treffer: leer
    assert daten == _entwurf()                           # das Original bleibt


def test_kein_treffer_macht_leer_auch_an_der_wurzel(vokabular):
    neu = _angleichen({**_entwurf(), "fach": "Quatschfach 123", "bildungsstufe": "Hochschule"})
    assert "fach" not in neu and "bildungsstufe" not in neu
    # der Punkt „Erdkunde“ unterscheidet sich jetzt von der (leeren) Wurzel und bleibt
    assert neu["knoten"][0]["fach"] == "Geografie"


def test_eine_stufe_ausserhalb_der_labels_des_entwurfs_entfaellt(vokabular):
    neu = _angleichen({**_entwurf(), "bildungsstufe": "Allgemeinbildende Schule"})
    assert "bildungsstufe" not in neu
    assert daten_fehler(katalog()["ui_strukturentwurf"], neu) == []


def test_ohne_vokabular_bleibt_alles_wie_bisher():
    # wie ``knoten_aus`` ihn baut: ein Punkt trägt kein Fach, das gleich dem der Wurzel ist
    entwurf = _entwurf()
    del entwurf["knoten"][0]["fach"]
    assert _angleichen(entwurf) == entwurf


def test_der_dienst_gleicht_den_entwurf_an(monkeypatch, vokabular):
    from boerdi.ui_module import dienst

    async def erzeugen(auftrag, **_k):
        return strukturentwurf_dienst.Erzeugt(copy.deepcopy(_entwurf()))

    monkeypatch.setattr(strukturentwurf_dienst, "erzeugen", erzeugen)

    async def lese(_name):
        return None

    erg = asyncio.run(dienst._strukturentwurf(
        katalog()["ui_strukturentwurf"], {"thema": "Erde"}, Umgebung(teile=lese)))
    assert erg.block.daten["fach"] == "Geografie"
    assert erg.block.daten["knoten"][1]["fach"] == "Mathematik"
    # N1/N2-Review, Befund 3: das verworfene Fach des Punkts steht als Hinweis im Text an die KI
    assert "„Quatschfach 123“ ist nicht im WLO-Vokabular" in erg.text


# ── Review N3, MINOR 7: Stufen fallen nicht still weg ───────────────────────────────────────────

def test_eine_verworfene_stufe_steht_im_log(vokabular, caplog):
    import logging

    with caplog.at_level(logging.INFO, logger=strukturentwurf_vokabular.__name__):
        _angleichen({**_entwurf(), "bildungsstufe": "Allgemeinbildende Schule"})
    assert any("Allgemeinbildende Schule" in r.getMessage() for r in caplog.records)


def test_jedes_label_des_echten_vokabulars_kennt_der_entwurf():
    """Schnappschuss von ``educationalContext`` (Staging-MCP, 19.11.): jedes Label muss eine
    Bildungsstufe des Entwurfs sein — sonst verwürfe ``angleichen`` einen echten Treffer."""
    import json
    from pathlib import Path

    from boerdi.ui_module import strukturentwurf as se

    schnappschuss = json.loads((Path(__file__).parent / "schnappschuss_bildungsstufen.json")
                               .read_text(encoding="utf-8"))
    assert set(schnappschuss["labels"].values()) <= set(se.BILDUNGSSTUFEN)
    manifest = katalog()["ui_strukturentwurf"]
    for teil in (manifest["eingabe"], manifest["antwort"]):
        assert teil["$defs"]["stufe"]["enum"] == list(se.BILDUNGSSTUFEN)


# ── N1/N2-Review, Befund 3: ein verworfenes Fach ist sichtbar ────────────────────────────────────

def test_wirtschaft_wird_leer_mit_hinweis(vokabular):
    erg = asyncio.run(strukturentwurf_vokabular.angleichen(
        {**_entwurf(), "fach": "Wirtschaft", "bildungsstufe": "Allgemeinbildende Schule"}))
    assert "fach" not in erg.daten and "bildungsstufe" not in erg.daten
    assert "Fach „Wirtschaft“ ist nicht im WLO-Vokabular – deshalb leer." in erg.hinweise
    assert any(h.startswith("Bildungsstufe „Allgemeinbildende Schule“") for h in erg.hinweise)
    # je Wert ein Hinweis, auch wenn er an mehreren Stellen steht
    assert len(erg.hinweise) == len(set(erg.hinweise))


def test_nur_genau_oder_alias_unscharfes_zaehlt_nicht(vokabular):
    erg = asyncio.run(strukturentwurf_vokabular.angleichen(
        {**_entwurf(), "fach": "Erdkundeunterricht"}))
    assert "fach" not in erg.daten and erg.hinweise


def test_ohne_vokabular_keine_hinweise():
    erg = asyncio.run(strukturentwurf_vokabular.angleichen({**_entwurf(), "fach": "Wirtschaft"}))
    assert erg.daten["fach"] == "Wirtschaft" and erg.hinweise == []
