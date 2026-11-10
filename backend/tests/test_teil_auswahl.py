"""Paket AS-Da (Plan 2026-11-09 §5e, R1): Auswahl aus einem Teil.

Ein Verweis kann eine Liste im Teil filtern (``wo``) und ein Feld je Eintrag herausziehen
(``feld``) — etwa die nodeIds aller abgelegten Strukturdokumente für einen Auftrag. Ergebnis ist
immer eine Liste; ist die Stelle keine Liste, fehlt der Wert. Ein Objekt mit ``$teil``, das kein
gültiger Verweis ist, ist ein Befund der Prüfung (es bliebe sonst still als wörtlicher Wert stehen).
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services import teil_verweise
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf.pruefung import pruefe

_ABLAGE = {"format": "wlo.ablage@1", "inhalte": [
    {"titel": "Struktur", "stand": "stored", "rolle": "struktur", "node_id": "n-1"},
    {"titel": "Kapitel 1", "stand": "stored", "rolle": "inhalt", "node_id": "n-2"},
    {"titel": "Kapitel 2", "stand": "failed", "rolle": "inhalt"},
    {"titel": "Kapitel 3", "stand": "stored", "rolle": "inhalt", "node_id": "n-3"},
]}
_STRUKTUR = {"$teil": "ablage", "liste": "inhalte", "wo": {"rolle": "struktur", "stand": "stored"},
             "feld": "node_id"}
_INHALT = {"$teil": "ablage", "liste": "inhalte", "wo": {"rolle": "inhalt", "stand": "stored"},
           "feld": "node_id"}


def _lader(teile):
    async def lade(name):
        return teile.get(name)

    return lade


def _einsetzen(args, teile):
    return asyncio.run(teil_verweise.einsetzen(args, _lader(teile)))


def test_die_auswahl_filtert_und_zieht_ein_feld_heraus():
    args, fehlt = _einsetzen({"structure_node_ids": _STRUKTUR, "content_node_ids": _INHALT},
                             {"ablage": _ABLAGE})
    assert fehlt == []
    assert args == {"structure_node_ids": ["n-1"], "content_node_ids": ["n-2", "n-3"]}


def test_ohne_feld_die_eintraege_ohne_wo_alle():
    args, _ = _einsetzen({"a": {"$teil": "ablage", "liste": "inhalte",
                                "wo": {"stand": "failed"}}}, {"ablage": _ABLAGE})
    assert args["a"] == [_ABLAGE["inhalte"][2]]
    args, _ = _einsetzen({"a": {"$teil": "ablage", "liste": "inhalte", "feld": "titel"}},
                         {"ablage": _ABLAGE})
    assert args["a"] == ["Struktur", "Kapitel 1", "Kapitel 2", "Kapitel 3"]


def test_eine_leere_auswahl_ist_eine_leere_liste_keine_luecke():
    args, fehlt = _einsetzen({"a": {"$teil": "ablage", "liste": "inhalte",
                                    "wo": {"rolle": "gibtsnicht"}, "feld": "node_id"}},
                             {"ablage": _ABLAGE})
    assert args["a"] == [] and fehlt == []


def test_keine_liste_an_der_stelle_fehlt():
    _, fehlt = _einsetzen({"a": {"$teil": "ablage", "liste": "format", "feld": "x"}},
                          {"ablage": _ABLAGE})
    assert fehlt


def test_wo_vergleicht_genau_auch_den_typ():
    teil = {"l": [{"n": 1, "ok": True}, {"n": "1", "ok": 1}]}
    args, _ = _einsetzen({"a": {"$teil": "zz", "liste": "l", "wo": {"ok": True}, "feld": "n"}},
                         {"zz": teil})
    assert args["a"] == [1]


def test_ein_lesendes_mcp_werkzeug_bekommt_auch_keine_auswahl():
    ablauf = AblaufArea.model_validate({"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all",
         "argumente": {"query": {"$teil": "ablage", "liste": "inhalte", "feld": "titel"}},
         "schreibt": "treffer"},
        {"id": "e", "typ": "ende"}]})
    gesehen = {}

    async def mcp(name, args):
        gesehen.update(args)
        return "ok"

    asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=_lader({"ablage": _ABLAGE}),
                                                         mcp=mcp)))
    # lesende MCP-Werkzeuge bekommen nie einen Teil (V2) — auch keine Auswahl
    assert gesehen == {}


# ── Prüfung ────────────────────────────────────────────────────────────────

def _mit_argument(wert) -> AblaufArea:
    return AblaufArea.model_validate({"id": "a", "titel": {"de": "A"},
                                      "voraussetzungen": ["anmeldung"], "schritte": [
        {"id": "up", "typ": "modul", "modul": "ui_upload", "daten": {}, "bei_fehler": "e"},
        {"id": "lesen", "typ": "auftrag", "flow": "wlo/volltext", "argumente": {"x": wert},
         "schreibt": "texte", "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]})


@pytest.fixture(autouse=True)
def _flows(monkeypatch):
    from boerdi.settings import get_settings

    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/volltext")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_eine_gueltige_auswahl_hat_keine_befunde():
    befunde = pruefe(_mit_argument({"$teil": "structure", "liste": "struktur.kinder",
                                    "wo": {"dateien": 0}, "feld": "name"}))
    assert not any("Auswahl" in b or "Verweis" in b for b in befunde), befunde


@pytest.mark.parametrize("wert", [
    {"$teil": "structure", "pfad": "a", "liste": "b"},
    {"$teil": "structure", "liste": "a..b"},
    {"$teil": "structure", "liste": "a", "feld": "x y"},
    {"$teil": "structure", "liste": "a", "wo": {f"k{i}": 1 for i in range(6)}},
    {"$teil": "structure", "liste": "a", "wo": {"k": {"tief": 1}}},
    {"$teil": "structure", "liste": "a", "wie": "falsch"},
])
def test_eine_kaputte_auswahl_ist_ein_befund(wert):
    befunde = pruefe(_mit_argument(wert))
    assert any("Verweis" in b or "Auswahl" in b for b in befunde), befunde



# ── Review AS-Da ───────────────────────────────────────────────────────────

def test_der_treiber_gibt_die_auswahl_an_einen_auftrag():
    """Befund 3: der Anwendungsfall — ein Flow bekommt die nodeIds als Liste."""
    ablauf = AblaufArea.model_validate({"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "lesen", "typ": "auftrag", "flow": "wlo/volltext",
         "argumente": {"structure_node_ids": _STRUKTUR, "content_node_ids": _INHALT},
         "schreibt": "texte"},
        {"id": "e", "typ": "ende"}]})
    gesehen = {}

    async def starten(_flow, args):
        gesehen.update(args)
        return "job-1"

    asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=_lader({"ablage": _ABLAGE}),
                                                         auftrag_starten=starten)))
    assert gesehen == {"structure_node_ids": ["n-1"], "content_node_ids": ["n-2", "n-3"]}


def test_eine_zu_grosse_auswahl_geht_nicht_an_ein_werkzeug_der_ki(monkeypatch):
    monkeypatch.setattr(teil_verweise, "darf", lambda _w, _t: True)
    gross = {"l": [{"x": "y" * 1000} for _ in range(100)]}
    _, fehlt = asyncio.run(teil_verweise.einsetzen(
        {"a": {"$teil": "zz", "liste": "l"}}, _lader({"zz": gross}), "wlo_update_contents"))
    assert fehlt


def test_wo_mit_null_sucht_ein_gespeichertes_null_und_nur_objekte():
    """Befund 2: ``null`` ist nicht „fehlt“, Texte und Zahlen in der Liste passen nie."""
    teil = {"l": [{"k": None, "n": 1}, {"n": 2}, "text", 3]}
    args, _ = _einsetzen({"a": {"$teil": "zz", "liste": "l", "wo": {"k": None}, "feld": "n"}},
                         {"zz": teil})
    assert args["a"] == [1]


def test_zahlen_vergleicht_wo_als_zahl():
    """Befund 5: ``1.0`` ist ``1`` (JSON unterscheidet sie nicht), ``True`` bleibt nicht ``1``."""
    teil = {"l": [{"n": 1.0, "id": "a"}, {"n": True, "id": "b"}]}
    args, _ = _einsetzen({"a": {"$teil": "zz", "liste": "l", "wo": {"n": 1}, "feld": "id"}},
                         {"zz": teil})
    assert args["a"] == ["a"]


def test_eine_auswahl_als_ganze_moduldaten_ist_ein_befund():
    """Befund 1: sie ergibt eine Liste, Moduldaten brauchen ein Objekt."""
    ablauf = AblaufArea.model_validate({"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "up", "typ": "modul", "modul": "ui_upload", "daten": {}, "bei_fehler": "e",
         "weiter": "zeigen"},
        {"id": "zeigen", "typ": "modul", "modul": "ui_linkbox",
         "daten": {"$teil": "structure", "liste": "struktur.kinder"}, "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]})
    assert any("Moduldaten sind ein Objekt" in b for b in pruefe(ablauf))


def test_eine_kaputte_liste_meldet_sich_einmal():
    """Befund 4: nicht zugleich als Pfad und als Auswahl."""
    befunde = [b for b in pruefe(_mit_argument({"$teil": "structure", "liste": "a..b"}))
               if "a..b" in b or "liste" in b]
    assert len(befunde) == 1, befunde
