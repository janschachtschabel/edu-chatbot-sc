"""Paket AS-Dc (Plan 2026-11-09 §5e): die Sicht „Daten“ — je Teil Typ, Schreiber, Leser, Beispiel.

Im Backend gerechnet, aus derselben Quelle wie die Prüfung (``typen``), und mit „Prüfen“
geliefert (``POST /api/config/ablauf-pruefen``, Feld ``teile``).
"""

from __future__ import annotations

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import datensicht, typen

_ABLAUF = AblaufArea.model_validate({
    "id": "d", "titel": {"de": "D"},
    "ausloeser": [{"art": "modul", "modul": "ui_upload"}],
    "schritte": [
        {"id": "entwurf", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "eigener",
         "bei_fehler": "e"},
        {"id": "frage", "typ": "nachricht", "text": {"de": "Für {teil.eigener.titel}?"},
         "freitext": {"ziel": "wohin", "schreibt": "wunsch"}},
        {"id": "wohin", "typ": "verzweigung", "weiter": [
            {"wenn_wert": {"quelle": "teil.wunsch", "vergleich": "vorhanden"}, "dann": "e"},
            {"wenn_teil": "eigener", "dann": "e"}, {"sonst": "e"}]},
        {"id": "e", "typ": "ende"}],
    "tests": [{"name": "t", "werkzeuge": {"entwurf": {"titel": "Physik", "knoten": []}}}],
})


def _zeilen():
    return {z.name: z for z in datensicht.tabelle(_ABLAUF)}


def test_je_teil_typ_schreiber_und_leser():
    z = _zeilen()
    assert z["structure"].vor_dem_start and z["structure"].typen == [typen.ORDNERBAUM]
    assert z["structure"].leser == [0]
    assert z["eigener"].schreiber == [0] and z["eigener"].typen == [typen.STRUKTUR]
    # gelesen über Platzhalter (1) und wenn_teil (2)
    assert z["eigener"].leser == [1, 2]
    assert z["wunsch"].schreiber == [1] and z["wunsch"].typen == [typen.TEXT]
    assert z["wunsch"].leser == [2]


def test_ein_beispiel_aus_den_testfaellen():
    assert _zeilen()["eigener"].beispiel == '{"titel": "Physik", "knoten": []}'
    assert _zeilen()["wunsch"].beispiel is None


def test_der_endpunkt_liefert_die_sicht(monkeypatch):
    from fastapi.testclient import TestClient

    from boerdi.main import create_app
    from boerdi.settings import get_settings

    monkeypatch.setenv("STUDIO_API_KEY", "k" * 32)
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())
        r = client.post("/api/config/ablauf-pruefen", json=_ABLAUF.model_dump(mode="json"),
                        headers={"X-Studio-Key": "k" * 32})
        assert r.status_code == 200, r.text
        teile = {t["name"]: t for t in r.json()["teile"]}
        assert teile["eigener"]["schreiber"] == [0] and teile["eigener"]["leser"] == [1, 2]
    finally:
        get_settings.cache_clear()



# ── Review AS-Dc ───────────────────────────────────────────────────────────

def _tabelle(schritte, **mehr):
    ablauf = AblaufArea.model_validate({"id": "d", "titel": {"de": "D"}, "schritte": [
        *schritte, {"id": "e", "typ": "ende"}], **mehr})
    return {z.name: z for z in datensicht.tabelle(ablauf)}


def test_ein_teil_den_nichts_schreibt_kommt_nicht_aus_dem_gespraech():
    """Befund 1: ein Tippfehler ist kein Teil aus dem Gespräch."""
    z = _tabelle([{"id": "w", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
                   "argumente": {"entwurf": {"$teil": "entwrf"}}, "schreibt": "zz",
                   "bei_fehler": "e"}])
    assert not z["entwrf"].aus_gespraech and z["entwrf"].schreiber == []
    z = _tabelle([{"id": "w", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
                   "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "zz",
                   "bei_fehler": "e"}])
    assert z["draft"].aus_gespraech and z["draft"].typen == [typen.STRUKTUR]


def test_leser_wie_der_treiber_auch_auswahlen_nicht_zu_tief():
    """Befund 2: dieselbe Tiefe wie der Treiber; Auswahlen zählen."""
    tief = {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"$teil": "zu_tief"}}}}}}}}
    z = _tabelle([{"id": "w", "typ": "auftrag", "flow": "wlo/volltext", "argumente": {
        "x": {"$teil": "ablage", "liste": "inhalte", "feld": "node_id"}, **tief},
        "schreibt": "texte", "bei_fehler": "e"}])
    assert z["ablage"].leser == [0]
    assert "zu_tief" not in z


def test_ki_ausgabe_und_beispiele_aus_den_eingaben():
    """Befunde 3 und 7: ``?`` nur für die KI; Beispiele auch aus Eingaben, gekürzt."""
    ki = {"id": "ki", "typ": "agent",
          "agent": {"werkzeuge": ["search_wlo_all"], "ausgabe": "notiz"}, "weiter": "frage"}
    frage = {"id": "frage", "typ": "nachricht", "text": {"de": "?"},
             "freitext": {"ziel": "e", "schreibt": "wunsch"}}
    z = _tabelle([ki, frage], tests=[{"name": "t", "eingaben": [
        {"bei": "ki", "teile": {"notiz": "x" * 400}}, {"bei": "frage", "text": "Optik"}]}])
    assert z["notiz"].typen == [datensicht.KI]
    assert len(z["notiz"].beispiel) == datensicht.BEISPIEL_ZEICHEN
    assert z["wunsch"].beispiel == "Optik"


def test_zu_viele_schritte_keine_tabelle():
    schritte = [{"id": f"s{i}", "typ": "nachricht", "text": {"de": "x"}} for i in range(45)]
    assert _tabelle(schritte) == {}
