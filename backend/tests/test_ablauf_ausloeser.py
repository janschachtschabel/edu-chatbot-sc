"""Paket A2a: Auslöser eines Ablaufs außer dem Knopf — Wendung im Text, Antwort eines Moduls.

Gefunden wird nur unter **aktiven** Einträgen des Katalogs, die zum Modell passen. Eine Wendung ist
kein regulärer Ausdruck (Studio-Text im Zug), sondern eine Teilzeichenkette der Nachricht —
Groß-/Kleinschreibung und Leerraum egal. Ein Modul-Auslöser startet **nach** dem ersten Schritt mit
diesem Modul (die Antwort liegt schon vor), und nur, wenn die Antwort den Teil ``wenn_teil`` bringt.
"""

from __future__ import annotations

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD

_SCHRITTE = [
    {"id": "erfassen", "typ": "modul", "modul": UPLOAD, "daten": {"zweck": "sammlungsstruktur"}},
    {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
     "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft",
     "bei_fehler": "ohne"},
    {"id": "bearbeiten", "typ": "modul", "modul": STRUKTURENTWURF, "daten": {"$teil": "draft"}},
    {"id": "ende", "typ": "ende"},
    {"id": "ohne", "typ": "ende", "text": {"de": "Ohne Ordner."}},
]


def _roh(id_="baum", aktiv=True, ausloeser_=None, **mehr):
    return {"id": id_, "titel": {"de": "Baum"}, "aktiv": aktiv, "schritte": _SCHRITTE,
            "ausloeser": ausloeser_ or [], **mehr}


@pytest.fixture
def katalog(monkeypatch):
    eintraege: list = []
    monkeypatch.setattr(ausloeser, "area", lambda key: {"ablaeufe": eintraege}
                        if key == ausloeser.BEREICH else {})
    return eintraege


def test_laden_findet_nur_passende_eintraege(katalog):
    katalog += [_roh(), {"id": "kaputt", "schritte": "x"}, "kein dict"]
    assert ausloeser.laden("baum").id == "baum"
    assert ausloeser.laden("kaputt") is None and ausloeser.laden("fehlt") is None
    assert ausloeser.laden(None) is None and ausloeser.laden("../x") is None


def test_eine_wendung_startet_ihren_ablauf(katalog):
    katalog.append(_roh(ausloeser_=[{"art": "text",
                                     "wendungen": ["Themenbaum aus meinem Ordner"]}]))
    assert ausloeser.per_text("Mach mir einen  THEMENBAUM aus meinem\nOrdner bitte").id == "baum"
    assert ausloeser.per_text("Was ist ein Themenbaum?") is None
    assert ausloeser.per_text("") is None


def test_eine_wendung_ist_kein_regulaerer_ausdruck(katalog):
    katalog.append(_roh(ausloeser_=[{"art": "text", "wendungen": ["baum (aus|von) ordner"]}]))
    assert ausloeser.per_text("baum aus ordner") is None
    assert ausloeser.per_text("ein baum (aus|von) ordner").id == "baum"


def test_ausgeschaltet_oder_ohne_text_ausloeser_startet_nichts(katalog):
    katalog += [_roh("aus", aktiv=False, ausloeser_=[{"art": "text", "wendungen": ["themenbaum"]}]),
                _roh("knopf", ausloeser_=[{"art": "knopf"}])]
    assert ausloeser.per_text("themenbaum") is None


def test_eine_modul_antwort_startet_nach_dem_modul_schritt(katalog):
    katalog.append(_roh(ausloeser_=[{"art": "modul", "modul": UPLOAD, "wenn_teil": "structure"}]))
    geprueft = {"modul": UPLOAD, "block_id": "b1", "daten": {"aktion": "erfasst", "struktur": {
        "name": "P", "dateien": 0, "alle_dateien": 0, "kinder": []}}}
    ablauf, ab = ausloeser.per_modul(geprueft)
    assert ablauf.id == "baum" and ablauf.schritte[ab].id == "entwurf"


def test_ohne_den_teil_startet_der_modul_ausloeser_nicht(katalog):
    katalog.append(_roh(ausloeser_=[{"art": "modul", "modul": UPLOAD, "wenn_teil": "document"}]))
    geprueft = {"modul": UPLOAD, "block_id": "b1", "daten": {"aktion": "erfasst", "struktur": {
        "name": "P", "dateien": 0, "alle_dateien": 0, "kinder": []}}}
    assert ausloeser.per_modul(geprueft) is None
    assert ausloeser.per_modul({"modul": STRUKTURENTWURF, "daten": {}}) is None
    assert ausloeser.per_modul(None) is None


@pytest.mark.parametrize(("ausloeser_", "erwartet"), [
    ([{"art": "text"}], "Wendung"),
    ([{"art": "text", "wendungen": ["ab"]}], "Wendung"),
    ([{"art": "text", "wendungen": [f"wendung {i}" for i in range(11)]}], "Wendung"),
    ([{"art": "modul", "modul": "ui_entscheidung"}], "Schritt mit diesem Modul"),
    ([{"art": "modul", "modul": UPLOAD, "wenn_teil": "Böse"}], "Teil"),
])
def test_pruefung_der_ausloeser(ausloeser_, erwartet):
    befunde = pruefe(AblaufArea.model_validate(_roh(ausloeser_=ausloeser_)))
    assert any(erwartet in b for b in befunde), befunde


def test_gueltige_ausloeser_haben_keine_befunde():
    assert pruefe(AblaufArea.model_validate(_roh(ausloeser_=[
        {"art": "text", "wendungen": ["themenbaum aus meinem ordner"]},
        {"art": "modul", "modul": UPLOAD, "wenn_teil": "structure"}, {"art": "knopf"}]))) == []


# ── Review A2a, Befund 3/4 ──────────────────────────────────────────────────────────────────

def test_der_modul_start_folgt_dem_weiter_des_modul_schritts(katalog):
    schritte = [
        {"id": "erfassen", "typ": "modul", "modul": UPLOAD, "daten": {"zweck": "x"},
         "weiter": "danach"},
        {"id": "uebersprungen", "typ": "ende"},
        {"id": "danach", "typ": "ende", "text": {"de": "Gesprungen."}}]
    katalog.append(_roh(schritte=schritte, ausloeser_=[{"art": "modul", "modul": UPLOAD}]))
    ablauf, ab = ausloeser.per_modul({"modul": UPLOAD, "block_id": "b", "daten": {}})
    assert ablauf.schritte[ab].id == "danach"


def test_der_modul_start_nimmt_die_wahl_der_antwort_mit():
    import asyncio

    from boerdi.services.ablauf import treiber

    frage = {"frage": "Wie?", "optionen": [{"id": "ordner", "label": "Ordner"},
                                          {"id": "neu", "label": "Neu"}]}
    ablauf = AblaufArea.model_validate(_roh(schritte=[
        {"id": "frage", "typ": "modul", "modul": "ui_entscheidung", "daten": frage},
        {"id": "gabel", "typ": "verzweigung",
         "weiter": [{"wenn_gewaehlt": "ordner", "dann": "ja"}, {"sonst": "nein"}]},
        {"id": "ja", "typ": "ende", "text": {"de": "Ordner."}},
        {"id": "nein", "typ": "ende", "text": {"de": "Neu."}}]))

    async def lader(_name):
        return None

    aus = asyncio.run(treiber.starten(ablauf, treiber.Umgebung(teile=lader), 1,
                                      treiber.gewaehlt_aus({"gewaehlt": ["ordner"]})))
    assert aus.texte == ["Ordner."]


def test_die_ki_schlaegt_nichts_vor_was_der_knopf_abwiese(katalog, monkeypatch):
    monkeypatch.setattr(ausloeser, "has_personal_auth", lambda: False)
    katalog += [_roh("frei", ausloeser_=[{"art": "agent"}]),
                _roh("angemeldet", ausloeser_=[{"art": "agent"}], voraussetzungen=["anmeldung"])]
    assert [a.id for a in ausloeser.vorschlaege()] == ["frei"]
