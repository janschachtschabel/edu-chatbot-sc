"""Plan 2026-11-10, TB-F2: das Ablauf-Werkzeug ``metadaten_lesen``.

Der Bericht des Kestra-Flows nennt nur, welche Felder geschrieben wurden, nicht ihre Werte. Für den
Themenbaum aus Inhalten liest ein Schritt danach die Metadaten der hochgeladenen Nodes:

- die nodeIds kommen aus dem Teil ``ablage`` (vom eigenen Endpunkt geschrieben, nicht vom Modell);
  nur abgelegte Einträge (``stand: stored``) des jetzigen Stapels;
- höchstens 50 Nodes, je Node gekürzt auf das, was ein Themenbaum braucht;
- ``get_nodes_details`` nur unter der persönlichen Anmeldung, ohne Lesen aus dem Cache (frisch);
- scheitert der Aufruf oder ist kein Node lesbar, entsteht kein Teil (``bei_fehler``).
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import metadaten, pruefung, typen, werkzeuge

_A = "11111111-1111-4111-8111-111111111111"
_B = "22222222-2222-4222-8222-222222222222"
_C = "33333333-3333-4333-8333-333333333333"


def _ablage() -> dict:
    return {"format": "wlo.ablage@1", "ordner": "Optik", "inhalte": [
        {"index": 0, "titel": "Linsen.pdf", "stand": "stored", "node_id": _A, "rolle": "inhalt"},
        {"index": 1, "titel": "Spiegel.pdf", "stand": "failed", "rolle": "inhalt"},
        {"index": 2, "titel": "Lehrplan.pdf", "stand": "stored", "node_id": _B,
         "rolle": "struktur"},
        {"index": 3, "titel": "doppelt", "stand": "stored", "node_id": _A, "rolle": "inhalt"},
        {"index": 4, "titel": "boese", "stand": "stored", "node_id": "../x", "rolle": "inhalt"}],
        "frueher": [{"titel": "Alt.pdf", "node_id": _C, "rolle": "inhalt"}]}


@pytest.fixture
def mcp(monkeypatch):
    aufrufe: list = []

    async def antwort(name, args, *, use_cache=True):
        aufrufe.append((name, args, use_cache))
        ergebnis = {_A: {"title": "Linsen", "description": "Sammellinsen " * 100,
                         "keywords": [f"k{i}" for i in range(20)], "disciplines": ["Physik"],
                         "educationalContexts": ["Sekundarstufe I"],
                         "learningResourceTypes": ["Arbeitsblatt"], "url": "x"},
                    _C: {"title": "Alt", "keywords": [], "disciplines": []}}
        return SimpleNamespace(art="", text=json.dumps({"requested": 3, "resolved": 2,
                                                       "failed": [_B], "results": ergebnis}))

    from boerdi.services.mcp import auth, client
    monkeypatch.setattr(client, "call_mcp_tool_antwort", antwort)
    monkeypatch.setattr(auth, "has_personal_auth", lambda: True)
    return aufrufe


def test_liest_die_abgelegten_nodes_ohne_cache(mcp):
    teil = asyncio.run(metadaten.lesen(_ablage()))
    [(name, args, cache)] = mcp
    assert name == "get_nodes_details" and cache is False
    # nur gespeicherte des jetzigen Stapels, ohne Doppel und Unsinn — ``frueher`` nicht (wie der
    # Flow; Querschnitts-Review F/T, Befund 6)
    assert args == {"nodeIds": [_A, _B]}
    assert teil["format"] == "wlo.metadaten@1"
    assert [i["node_id"] for i in teil["inhalte"]] == [_A]
    linsen = teil["inhalte"][0]
    assert linsen["titel"] == "Linsen" and linsen["faecher"] == ["Physik"]
    assert linsen["stufen"] == ["Sekundarstufe I"] and linsen["arten"] == ["Arbeitsblatt"]
    assert len(linsen["beschreibung"]) <= metadaten.MAX_BESCHREIBUNG
    assert len(linsen["schlagworte"]) <= metadaten.MAX_SCHLAGWORTE
    assert linsen["rolle"] == "inhalt" and "url" not in linsen
    assert teil["fehlend"] == [_B]


def test_hoechstens_fuenfzig(mcp):
    viele = {"format": "wlo.ablage@1", "inhalte": [
        {"index": i, "stand": "stored", "node_id": f"{i:08d}-0000-4000-8000-000000000000"}
        for i in range(80)]}
    asyncio.run(metadaten.lesen(viele))
    assert len(mcp[0][1]["nodeIds"]) == metadaten.MAX_NODES == 50


def test_ohne_abgelegte_nodes_oder_bei_fehler_kein_teil(monkeypatch, mcp):
    assert asyncio.run(metadaten.lesen({"format": "wlo.ablage@1", "inhalte": []})) is None
    assert asyncio.run(metadaten.lesen("kein teil")) is None
    assert mcp == []

    async def kaputt(name, args, *, use_cache=True):
        return SimpleNamespace(art="transport", text="Fehler")

    from boerdi.services.mcp import client
    monkeypatch.setattr(client, "call_mcp_tool_antwort", kaputt)
    assert asyncio.run(metadaten.lesen(_ablage())) is None


def test_angemeldet_im_ablauf_werkzeug_und_typen():
    assert "metadaten_lesen" in werkzeuge.DIENSTE
    assert werkzeuge.DIENST_MCP["metadaten_lesen"] == frozenset({"get_nodes_details"})
    assert typen.DIENST_EINGABE["metadaten_lesen"] == {"ablage": typen.ABLAGE}
    assert typen.DIENST_AUSGABE["metadaten_lesen"] == typen.METADATEN
    assert typen.LISTEN[typen.METADATEN] == frozenset({"inhalte", "fehlend"})


def test_ein_schritt_nach_dem_upload_ist_ohne_befund():
    ablauf = AblaufArea.model_validate({
        "id": "meta_probe", "titel": {"de": "Probe"}, "aktiv": False,
        "voraussetzungen": ["anmeldung"], "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "hochladen", "typ": "modul", "modul": "ui_upload",
             "text": {"de": "Wähle deine Dateien."}, "daten": {"zweck": "sammlungsstruktur"}},
            {"id": "lesen", "typ": "werkzeug", "werkzeug": "metadaten_lesen",
             "argumente": {"ablage": {"$teil": "ablage"}}, "schreibt": "metadaten",
             "bei_fehler": "ende"},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]})
    assert pruefung.pruefe(ablauf) == []


# ── Review TB-F2 ──────────────────────────────────────────────────────────────────────────────

def _antwort_mit(monkeypatch, text):
    async def antwort(name, args, *, use_cache=True):
        return SimpleNamespace(art="", text=text)

    from boerdi.services.mcp import client
    monkeypatch.setattr(client, "call_mcp_tool_antwort", antwort)


@pytest.mark.parametrize("text", [
    json.dumps({"requested": 3, "resolved": 0, "failed": [_A, _B, _C], "results": {}}),
    "kein json", json.dumps({"results": [{"title": "x"}]})])
def test_review_1_nichts_lesbar_ergibt_keinen_teil(monkeypatch, mcp, text):
    """Befund 1: ``results: {}`` (alle in ``failed``), kein JSON, ``results`` als Liste — kein Teil,
    damit der Schritt zu ``bei_fehler`` geht statt still leer weiterzulaufen."""
    _antwort_mit(monkeypatch, text)
    assert asyncio.run(metadaten.lesen(_ablage())) is None


def test_review_2_ohne_persoenliche_anmeldung_kein_aufruf(monkeypatch, mcp):
    from boerdi.services.mcp import auth
    monkeypatch.setattr(auth, "has_personal_auth", lambda: False)
    assert asyncio.run(metadaten.lesen(_ablage())) is None
    assert mcp == []


def test_review_2_pruefung_verlangt_die_anmeldung():
    ablauf = AblaufArea.model_validate({
        "id": "meta_ohne", "titel": {"de": "Probe"}, "aktiv": False,
        "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "lesen", "typ": "werkzeug", "werkzeug": "metadaten_lesen",
             "argumente": {"ablage": {"$teil": "ablage"}}, "schreibt": "metadaten",
             "bei_fehler": "ende"},
            {"id": "ende", "typ": "ende", "text": {"de": "Fertig."}}]})
    assert any("metadaten_lesen" in b and "Anmeldung" in b for b in pruefung.pruefe(ablauf))


def test_review_4_der_teil_bleibt_unter_der_grenze(monkeypatch, mcp):
    from boerdi.services.teil_verweise import MAX_BYTES

    viele = {"format": "wlo.ablage@1", "inhalte": [
        {"index": i, "stand": "stored", "node_id": f"{i:08d}-0000-4000-8000-000000000000"}
        for i in range(50)]}
    voll = {"title": "T" * 300, "description": "D" * 900, "keywords": ["k" * 200] * 20,
            "disciplines": ["f" * 200] * 9, "educationalContexts": ["s" * 200] * 9,
            "learningResourceTypes": ["a" * 200] * 9}
    _antwort_mit(monkeypatch, json.dumps({"results": {
        k["node_id"]: voll for k in viele["inhalte"]}}))
    teil = asyncio.run(metadaten.lesen(viele))
    assert teil is not None and teil["inhalte"]
    assert len(json.dumps(teil, ensure_ascii=False).encode("utf-8")) < MAX_BYTES
    assert teil["titel"] == f"Metadaten zu {len(teil['inhalte'])} Inhalten"
    # Review TB-T1, Befund 6: was weggelassen wurde, steht in fehlend
    assert len(teil["inhalte"]) + len(teil["fehlend"]) == 50


def test_ft2_ueber_fuenfzig_steht_der_rest_in_fehlend(monkeypatch, mcp):
    """Querschnitts-Review F/T, Befund 2: ein Stapel hat bis 200 Dateien — nie still weg."""
    kennungen = [f"{i:08d}-0000-4000-8000-000000000000" for i in range(60)]
    _antwort_mit(monkeypatch, json.dumps({"results": {k: {"title": k[:8]} for k in kennungen}}))
    teil = asyncio.run(metadaten.lesen({"format": "wlo.ablage@1", "inhalte": [
        {"stand": "stored", "node_id": k} for k in kennungen]}))
    assert len(teil["inhalte"]) == 50 and teil["fehlend"] == kennungen[50:]

