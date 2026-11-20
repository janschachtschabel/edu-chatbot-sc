"""Plan 2026-11-20, P6: Modul-Parameter im Studio sichtbar, Werte in der Prüfung.

- Ein Modul, das der Treiber über seinen Dienst baut (``ui_upload`` …), bekommt nur die Parameter
  aus ``dienst.parameter`` — bisher prüfte ``_dienst_daten`` nur die Namen. Jetzt auch die Werte
  (erlaubte Werte, Typ); ein Verweis auf einen Teil des Vorgangs (``$teil``) ist erst im Lauf da und
  bleibt ungeprüft. Befund ``dienst_daten_wert`` (de/en).
- Das Studio liest die Parameter aus dem vorhandenen Katalog-Endpunkt ``GET /api/config/ui-module``
  (ganze Manifeste) — kein neuer Endpunkt.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import pruefung
from boerdi.services.ablauf.pruefung_texte import _T as TEXTE
from tests.test_ui_modul_schalter import _AUTH, client  # noqa: F401  (Fixture)

_HIER = pathlib.Path(__file__).parent
_SEEDS = sorted((_HIER.parent / "seeds" / "06-ablaeufe").glob("*.yaml"))
_BEISPIELE = sorted((_HIER / "ablauf_beispiele").glob("*.yaml"))


def _ablauf(daten: dict) -> AblaufArea:
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": False, "ausloeser": [{"art": "knopf"}],
        "schritte": [{"id": "laden", "typ": "modul", "modul": "ui_upload", "daten": daten},
                     {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}}]})


def _wert_befunde(daten: dict, lang: str = "de") -> list[str]:
    stuecke = [x for x in re.split(r"\{[^}]+\}", TEXTE["dienst_daten_wert"][lang]) if x]
    return [t for t in pruefung.pruefe(_ablauf(daten), lang) if all(x in t for x in stuecke)]


_GUT = {"zweck": "bereitstellen"}


@pytest.mark.parametrize(("feld", "wert", "erwartet"), [
    ("vorauswahl", "irgendwo", "auto, wlo, chat"),
    ("rolle_vorgabe", "struktur", "auto, gliederung, material, beides"),
    ("erschliessen", "ja", "Wahrheitswert (true/false)"),
    ("zweck", "hochladen", "bereitstellen, sammlungsstruktur"),
    ("orte", ["chat", "ftp"], "chat, wlo, namen"),
    ("hinweis", 3, "Text ≤ 300 Zeichen"),
])
def test_ein_unbekannter_wert_wird_gemeldet(feld, wert, erwartet):
    befunde = _wert_befunde({**_GUT, feld: wert})
    assert len(befunde) == 1
    assert "laden" in befunde[0] and "ui_upload" in befunde[0] and feld in befunde[0]
    assert erwartet in befunde[0]


@pytest.mark.parametrize(("feld", "wert", "erwartet"), [
    ("erschliessen", "ja", "true/false"),
    ("hinweis", 3, "text ≤ 300 characters"),
])
def test_der_typ_heisst_auf_englisch_menschlich(feld, wert, erwartet):
    """Zweites Review P4–P6, NIT 5: kein ``boolean``/``string`` im Befund."""
    [befund] = _wert_befunde({**_GUT, feld: wert}, "en")
    assert erwartet in befund and "boolean" not in befund and "string" not in befund


@pytest.mark.parametrize(("schema", "lang", "soll", "nicht"), [
    ({"type": "array", "items": {"enum": ["a"]}, "minItems": 1}, "de", "mindestens 1 Eintrag",
     "Einträge"),
    ({"type": "array", "items": {"enum": ["a"]}, "maxItems": 1}, "de", "höchstens 1 Eintrag",
     "Einträge"),
    ({"type": "array", "items": {"enum": ["a"]}, "minItems": 1}, "en", "at least 1 entry",
     "entries"),
    ({"type": "array", "items": {"enum": ["a"]}, "minItems": 2}, "de", "mindestens 2 Einträge",
     "Eintrag;"),
    ({"type": "integer"}, "de", "ganze Zahl", "integer"),
    ({"type": "integer"}, "en", "whole number", "integer"),
])
def test_erwartet_in_menschlichen_worten_und_mit_einzahl(schema, lang, soll, nicht):
    text = pruefung._erwartet(schema, lang)
    assert soll in text and nicht not in text, text


@pytest.mark.parametrize(("orte", "lang", "teile"), [
    (["chat", "chat"], "de", ("Liste", "chat, wlo, namen", "1–3 Einträge", "ohne Doppelte")),
    ([], "de", ("Liste", "1–3 Einträge")),
    (["chat", "wlo", "namen", "chat"], "en", ("list", "1–3 entries", "no duplicates")),
])
def test_eine_liste_nennt_ihre_grenzen(orte, lang, teile):
    """Review P5/P6, NIT 7: bei einer Liste (``orte``) sagt der Befund auch Länge und ob Doppelte
    erlaubt sind — sonst bliebe „chat, chat“ ohne Hinweis, was falsch ist."""
    [befund] = _wert_befunde({**_GUT, "orte": orte}, lang)
    assert all(t in befund for t in teile), befund


@pytest.mark.parametrize("daten", [
    {**_GUT, "vorauswahl": "auto", "rolle_vorgabe": "beides", "erschliessen": False},
    {**_GUT, "orte": ["chat"], "hinweis": "Wähle den Ordner."},
])
def test_erlaubte_werte_bleiben_ohne_befund(daten):
    assert pruefung.pruefe(_ablauf(daten)) == []


@pytest.mark.parametrize("daten", [
    {**_GUT, "vorauswahl": {"$teil": "ort"}},
    {**_GUT, "hinweis": {"$teil": "grundlage", "pfad": "satz"}},
])
def test_ein_verweis_ist_erst_im_lauf_da_und_bleibt_ungeprueft(daten):
    """Ob der Teil entsteht, melden andere Befunde (Datenfluss) — nicht ``dienst_daten_wert``."""
    assert _wert_befunde(daten) == []


def test_unbekannte_namen_meldet_weiter_modul_feld_nicht_der_wert():
    befunde = pruefung.pruefe(_ablauf({**_GUT, "vorwahl": "auto"}))
    assert len(befunde) == 1 and "vorwahl" in befunde[0]
    assert _wert_befunde({**_GUT, "vorwahl": "auto"}) == []


def test_der_befund_folgt_der_sprache_des_studios():
    de = _wert_befunde({**_GUT, "vorauswahl": "x"}, "de")
    en = _wert_befunde({**_GUT, "vorauswahl": "x"}, "en")
    assert len(de) == len(en) == 1 and de != en
    assert set(TEXTE["dienst_daten_wert"]) == {"de", "en"}


@pytest.mark.parametrize("pfad", [*_SEEDS, *_BEISPIELE], ids=lambda p: f"{p.parent.name}/{p.stem}")
def test_werkseeds_und_beispiele_tragen_nur_erlaubte_werte(pfad):
    ablauf = AblaufArea.model_validate(yaml.safe_load(pfad.read_text(encoding="utf-8")))
    stuecke = [x for x in re.split(r"\{[^}]+\}", TEXTE["dienst_daten_wert"]["de"]) if x]
    assert [t for t in pruefung.pruefe(ablauf) if all(x in t for x in stuecke)] == []


def test_das_studio_liest_die_parameter_aus_dem_katalog(client):  # noqa: F811
    """Die Hilfe im Studio braucht Name, Beschreibung und erlaubte Werte — der Katalog liefert sie
    im Manifest (``dienst.parameter``)."""
    antwort = client.get("/api/config/ui-module", headers=_AUTH)
    assert antwort.status_code == 200
    upload = next(m for m in antwort.json()["module"] if m["name"] == "ui_upload")
    felder = upload["manifest"]["dienst"]["parameter"]["properties"]
    assert felder["vorauswahl"]["enum"] == ["auto", "wlo", "chat"]
    assert felder["rolle_vorgabe"]["enum"] == ["auto", "gliederung", "material", "beides"]
    assert felder["erschliessen"]["type"] == "boolean"
    assert all(f.get("description") for f in felder.values())


def test_der_katalog_sagt_bei_welchem_modul_die_daten_parameter_sind(client):  # noqa: F811
    """Zweites Review P4–P6, MINOR 2: nur Module in ``MODUL_DIENST_OHNE_MODELL`` (heute
    ``ui_upload``) nehmen die Schritt-``daten`` als Parameter des Diensts; die übrigen (etwa
    ``ui_strukturentwurf``, auch mit ``dienst.parameter``) nehmen sie als Blockdaten — das Studio
    zeigt die Parameter-Hilfe nur bei ``daten_sind_parameter``."""
    from boerdi.services.ablauf.werkzeuge import MODUL_DIENST_OHNE_MODELL

    module = {m["name"]: m for m in client.get("/api/config/ui-module",
                                                 headers=_AUTH).json()["module"]}
    assert module["ui_upload"]["daten_sind_parameter"] is True
    assert module["ui_strukturentwurf"]["daten_sind_parameter"] is False
    assert module["ui_strukturabgleich"]["daten_sind_parameter"] is False
    assert {n for n, m in module.items() if m["daten_sind_parameter"]} == set(
        MODUL_DIENST_OHNE_MODELL)
