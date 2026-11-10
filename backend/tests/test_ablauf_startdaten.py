"""Paket AS-4a (Plan 2026-11-09 §5f, E2 A): Startschema, Teil ``start`` und Auslöser ``extern``.

Ein Ablauf beschreibt seine Startdaten (``start: [{name, typ, pflicht, beschreibung}]``). Nur
mit dem Auslöser ``extern`` (Gastseite: Widget-API und Attribut) nimmt er welche an. Sie gehen
durch eine Prüfung (Typ, Pflicht, unbekannte Felder, Länge, Steuerzeichen) und landen als Teil
``start`` im Vorgang — ``{start.feld}`` ist ``{teil.start.feld}``. Startdaten sind Eingaben, nie
Rechte.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import simulation, startdaten, treiber, typen, zug
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)

_UUID = "0a1b2c3d-0000-4000-8000-000000000001"
_FELDER = [
    {"name": "sammlung", "typ": "nodeid", "pflicht": True,
     "beschreibung": {"de": "Die Sammlung", "en": "The collection"}},
    {"name": "thema", "typ": "text", "max_zeichen": 20},
    {"name": "stufe", "typ": "zahl"},
    {"name": "neu", "typ": "ja_nein"},
]


def _ablauf(start=_FELDER, ausloeser=("extern",), schritte=None, **mehr):
    return AblaufArea.model_validate({
        "id": "mit_start", "titel": {"de": "Mit Start"}, "aktiv": True,
        "ausloeser": [{"art": a} for a in ausloeser], "start": start,
        "schritte": schritte or [
            {"id": "hallo", "typ": "nachricht",
             "text": {"de": "Sammlung {start.sammlung}, Thema {start.thema}."}},
            {"id": "e", "typ": "ende"}], **mehr})


# ── Modell ──────────────────────────────────────────────────────────────────

def test_ohne_startschema_bleibt_die_fassung_gleich():
    ohne = AblaufArea.model_validate({"id": "x", "titel": {"de": "X"}, "schritte": [
        {"id": "e", "typ": "ende"}]})
    assert ohne.start is None
    assert AblaufArea.model_validate({**ohne.model_dump(), "start": []}).start is None
    assert "start" not in ohne.model_dump(exclude_none=True)


def test_feldnamen_und_typen_sind_begrenzt():
    with pytest.raises(ValueError):
        _ablauf(start=[{"name": "Gross", "typ": "text"}])
    with pytest.raises(ValueError):
        _ablauf(start=[{"name": "x1", "typ": "datei"}])
    with pytest.raises(ValueError):
        _ablauf(start=[{"name": f"f{i}", "typ": "text"} for i in range(11)])


# ── Prüfung der Daten ───────────────────────────────────────────────────────

def test_gueltige_daten_werden_bereinigt():
    sauber, fehler = startdaten.pruefen(_ablauf(), {
        "sammlung": _UUID, "thema": "  Optik​ und\u0007 Licht  ", "stufe": 7, "neu": True})
    assert fehler == []
    assert sauber == {"sammlung": _UUID, "thema": "Optik und Licht", "stufe": 7, "neu": True}


def test_fehler_nennen_feld_und_art_nie_den_wert():
    _sauber, fehler = startdaten.pruefen(_ablauf(), {
        "thema": "x" * 21, "stufe": "sieben", "neu": "ja", "fremd": "geheim",
        "sammlung": "keine-uuid\n"})
    assert sorted(fehler) == sorted(["zu_lang:thema", "typ:stufe", "typ:neu", "unbekannt:fremd",
                                     "typ:sammlung"])
    assert not any("geheim" in f or "sieben" in f for f in fehler)


def test_pflichtfelder_muessen_da_sein():
    sauber, fehler = startdaten.pruefen(_ablauf(), {"thema": "Optik"})
    assert sauber is None and fehler == ["pflicht:sammlung"]
    sauber, fehler = startdaten.pruefen(_ablauf(), None)
    assert sauber is None and fehler == ["pflicht:sammlung"]


def test_zahlen_sind_endlich_und_kein_wahrheitswert():
    for schlecht in (float("nan"), float("inf"), True, "7"):
        _s, fehler = startdaten.pruefen(_ablauf(), {"sammlung": _UUID, "stufe": schlecht})
        assert fehler == ["typ:stufe"], schlecht


def test_ohne_startschema_sind_alle_daten_fremd():
    sauber, fehler = startdaten.pruefen(_ablauf(start=None), {"aa": 1, "X": 2})
    # ein Schlüssel, der kein Feldname sein kann, steht nur als „?“ da
    assert sauber is None and fehler == ["unbekannt:aa", "unbekannt:?"]
    assert startdaten.pruefen(_ablauf(start=None), None) == ({}, [])


def test_zu_grosse_daten_werden_abgewiesen():
    _s, fehler = startdaten.pruefen(_ablauf(), "kein objekt")
    assert fehler == ["form"]
    _s, fehler = startdaten.pruefen(_ablauf(), {f"k{i}": 1 for i in range(50)})
    assert fehler == ["form"]


# ── Treiber und Platzhalter ─────────────────────────────────────────────────

def test_der_teil_start_entsteht_vor_dem_ersten_schritt():
    async def keine(_name):
        return None

    umgebung_ = treiber.Umgebung(teile=keine, sprache="de")
    aus = asyncio.run(treiber.starten(_ablauf(), umgebung_,
                                      start={"sammlung": _UUID, "thema": "Optik"}))
    assert aus.neue_teile[0][:3] == ("start", typen.START, {"sammlung": _UUID, "thema": "Optik"})
    assert any(f"Sammlung {_UUID.replace('-', chr(92) + '-')}" in t for t in aus.texte), aus.texte
    assert any("Thema Optik" in t for t in aus.texte), aus.texte


# ── Prüfung des Ablaufs ─────────────────────────────────────────────────────

def test_ein_bekanntes_startfeld_im_platzhalter_ist_kein_befund():
    assert pruefe(_ablauf()) == []


def test_ein_unbekanntes_startfeld_im_platzhalter_ist_ein_befund():
    befunde = pruefe(_ablauf(schritte=[
        {"id": "a", "typ": "nachricht", "text": {"de": "{start.gibtsnicht}"}},
        {"id": "e", "typ": "ende"}]))
    assert any("gibtsnicht" in b for b in befunde), befunde


def test_start_ist_als_teilname_reserviert():
    befunde = pruefe(_ablauf(schritte=[
        {"id": "w", "typ": "werkzeug", "werkzeug": "baum_aus_entwurf",
         "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "start", "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]))
    assert any("start" in b and "reserviert" in b for b in befunde), befunde


def test_pflichtfelder_ohne_auslöser_extern_starten_nie():
    befunde = pruefe(_ablauf(ausloeser=("knopf",)))
    assert any("extern" in b for b in befunde), befunde
    # ohne Pflichtfeld startet der Knopf ohne Daten — kein Befund
    ohne_pflicht = [{**f, "pflicht": False} for f in _FELDER]
    assert pruefe(_ablauf(start=ohne_pflicht, ausloeser=("knopf",))) == []


def test_der_verweis_auf_start_mit_pfad_kennt_den_teil():
    """Review AS-4a, Befund 10: an einem Modul (lesende WLO-Werkzeuge bekommen keine Teile)."""
    befunde = pruefe(_ablauf(schritte=[
        {"id": "m", "typ": "modul", "modul": "ui_strukturentwurf",
         "daten": {"titel": {"$teil": "start", "pfad": "thema"}}, "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]))
    assert befunde == [], befunde
    assert typen.start_teile(_ablauf(), {})["start"] == typen.START


# ── Zug ─────────────────────────────────────────────────────────────────────

def _starten(umgebung, ablauf, params):  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    state: dict = {"entities": {}}
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": ablauf.id, **params})
    return asyncio.run(zug.starten(_S(), anfrage, state)), state


def test_der_zug_nimmt_gueltige_startdaten(umgebung):  # noqa: F811 — Fixture
    antwort, _state = _starten(umgebung, _ablauf(), {"start": {"sammlung": _UUID}})
    assert "Sammlung" in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["start"]["wert"] == {"sammlung": _UUID}
    assert v.akte["teile"]["start"]["typ"] == typen.START


def test_der_zug_startet_nicht_mit_ungueltigen_daten(umgebung):  # noqa: F811 — Fixture
    antwort, _state = _starten(umgebung, _ablauf(), {"start": {"sammlung": "boese"}})
    assert umgebung.speicher.v == {}
    assert "boese" not in antwort.content
    antwort, _state = _starten(umgebung, _ablauf(), {})
    assert umgebung.speicher.v == {}


def test_ohne_auslöser_extern_keine_startdaten(umgebung):  # noqa: F811 — Fixture
    ohne_pflicht = [{**f, "pflicht": False} for f in _FELDER]
    _antwort, _state = _starten(umgebung, _ablauf(start=ohne_pflicht, ausloeser=("knopf",)),
                                {"start": {"sammlung": _UUID}})
    assert umgebung.speicher.v == {}
    # ohne Daten startet der Knopf wie bisher — mit Startschema ist der Teil ``start`` leer
    _antwort, _state = _starten(umgebung, _ablauf(start=ohne_pflicht, ausloeser=("knopf",)), {})
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["start"]["wert"] == {}


def test_extern_startet_auch_ohne_startschema(umgebung):  # noqa: F811 — Fixture
    _antwort, _state = _starten(umgebung, _ablauf(start=None), {})
    assert len(umgebung.speicher.v) == 1


# ── Simulation ──────────────────────────────────────────────────────────────

def _test(ablauf, test):
    return asyncio.run(simulation.testen(ablauf, AblaufTest.model_validate(test)))


def test_die_simulation_nimmt_startdaten():
    ergebnis = _test(_ablauf(), {"name": "s", "start": {"sammlung": _UUID, "thema": "Optik"},
                                 "erwartet": {"weg": ["hallo", "e"], "teile": ["start"]}})
    assert ergebnis.ok, ergebnis.abweichungen
    assert any("Thema Optik" in t for t in ergebnis.texte)


def test_ungueltige_startdaten_sind_eine_abweichung():
    ergebnis = _test(_ablauf(), {"name": "s", "start": {"stufe": "x"}})
    assert not ergebnis.ok
    assert any("sammlung" in a for a in ergebnis.abweichungen), ergebnis.abweichungen


# ── Review AS-4a ────────────────────────────────────────────────────────────

def test_andere_ausloeser_mit_pflichtfeldern_waehlen_den_ablauf_nicht(monkeypatch):
    """Befund 1: Wendung und Modul bringen nie Startdaten. Seit AS-5a (A5-4) bringt die KI sie —
    ein Ablauf mit Pflichtfeldern ist vorschlagbar und kein Befund für ``agent``."""
    from boerdi.services.ablauf import ausloeser

    roh = _ablauf(ausloeser=("extern", "text", "agent")).model_dump(exclude_none=True)
    roh["ausloeser"][1]["wendungen"] = ["sammlung pflegen"]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: [roh])
    assert ausloeser.per_text("bitte sammlung pflegen") is None
    assert [a.id for a in ausloeser.vorschlaege()] == [roh["id"]]
    befunde = pruefe(AblaufArea.model_validate(roh))
    assert sum("startet nie" in b for b in befunde) == 1, befunde


def test_startdaten_laufen_durch_die_sicherheitspruefung():
    """Befund 2: Text der Gastseite in ``start`` geht durch dieselbe Prüfung wie jede
    Direktaktion."""
    from boerdi.api.schemas import ChatRequest
    from boerdi.services.direct_actions import _direct_action_safety_text

    anfrage = ChatRequest(session_id="sitzung-0123456789", message="", action=zug.AKTION,
                          action_params={"ablauf": "x", "start": {"thema": "geheimer Text"}})
    assert "start.thema: geheimer Text" in _direct_action_safety_text(anfrage)


def test_zeilenumbrueche_trennen_woerter_und_surrogate_fallen_weg():
    """Befunde 3 und 4."""
    sauber, fehler = startdaten.pruefen(_ablauf(), {
        "sammlung": _UUID, "thema": "Zeile1\nZeile2\tTab\ud800"})
    assert fehler == [] and sauber["thema"] == "Zeile1 Zeile2 Tab"


def test_riesige_zahlen_sind_kein_absturz():
    _s, fehler = startdaten.pruefen(_ablauf(), {"sammlung": _UUID, "stufe": 10 ** 400})
    assert fehler == ["typ:stufe"]


def test_jeder_start_mit_startschema_bringt_den_teil(umgebung):  # noqa: F811 — Fixture
    """Befund 5: auch eine Wendung — sonst gälten alte Daten eines früheren Laufs."""
    ohne_pflicht = [{**f, "pflicht": False} for f in _FELDER]
    ablauf = _ablauf(start=ohne_pflicht, ausloeser=("text",))
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    state: dict = {"entities": {}}
    asyncio.run(zug.starten_mit(_S(), _req(), state, ablauf))
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["start"]["wert"] == {}


def test_doppelte_feldnamen_sind_ein_befund():
    befunde = pruefe(_ablauf(start=[{"name": "aa", "typ": "text"}, {"name": "aa", "typ": "zahl"}]))
    assert any("aa" in b and "doppelt" in b for b in befunde), befunde


def test_die_sicht_daten_kennt_leser_und_beispiel_von_start():
    """Befund 7."""
    from boerdi.services.ablauf import datensicht

    ablauf = _ablauf(tests=[{"name": "t", "start": {"sammlung": _UUID}}])
    zeile = {z.name: z for z in datensicht.tabelle(ablauf, module={})}["start"]
    assert zeile.leser == [0] and _UUID in (zeile.beispiel or "")


def test_auch_teil_start_und_verweise_kennen_nur_felder_des_schemas():
    """Befund 8."""
    befunde = pruefe(_ablauf(schritte=[
        {"id": "a", "typ": "nachricht", "text": {"de": "{teil.start.tippfehler}"}},
        {"id": "m", "typ": "modul", "modul": "ui_strukturentwurf",
         "daten": {"titel": {"$teil": "start", "pfad": "thma"}}, "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}]))
    assert any("tippfehler" in b for b in befunde), befunde
    assert any("thma" in b for b in befunde), befunde


def test_simulation_nur_mit_startdaten_wie_im_betrieb():
    """Befund 9: ohne Auslöser ``extern`` oder mit „Beginnen ab“ gibt es keine Startdaten."""
    ohne_pflicht = [{**f, "pflicht": False} for f in _FELDER]
    ergebnis = _test(_ablauf(start=ohne_pflicht, ausloeser=("knopf",)),
                     {"name": "s", "start": {"thema": "x"}})
    assert not ergebnis.ok and any("Gastseite" in a for a in ergebnis.abweichungen)


def test_start_in_einem_auftrag_ohne_rueckfrage_ist_eine_warnung():
    """Befund 11."""
    from boerdi.services.ablauf.pruefung import warnungen

    ablauf = _ablauf(voraussetzungen=["anmeldung"], schritte=[
        {"id": "a", "typ": "auftrag", "flow": "wlo/volltext", "schreibt": "texte",
         "argumente": {"sammlung": {"$teil": "start", "pfad": "sammlung"}}, "bei_fehler": "e"},
        {"id": "e", "typ": "ende"}])
    assert any("Rückfrage" in w for w in warnungen(ablauf)), warnungen(ablauf)


# ── Review AS-4b, Befund 1: ein Start der Gastseite setzt einen laufenden Lauf nicht zurück ──

_WARTET = [{"id": "frage", "typ": "nachricht", "text": {"de": "Weiter?"},
            "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]},
           {"id": "e", "typ": "ende"}]


def _gast(umgebung, ablauf, start):  # noqa: F811 — Fixture
    state = umgebung.state
    anfrage = _req(action=zug.AKTION, action_params={
        "ablauf": ablauf.id, "start": start, "quelle": "gastseite"})
    return asyncio.run(zug.starten(_S(), anfrage, state))


def test_derselbe_start_der_gastseite_setzt_den_lauf_fort(umgebung):  # noqa: F811 — Fixture
    ablauf = _ablauf(schritte=_WARTET)
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    umgebung.state = {"entities": {}}
    _gast(umgebung, ablauf, {"sammlung": _UUID})
    [v] = umgebung.speicher.v.values()
    lauf_vorher = dict(v.akte["lauf"])
    antwort = _gast(umgebung, ablauf, {"sammlung": _UUID})
    assert "läuft" in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"] == lauf_vorher
    assert v.akte["teile"]["start"]["version"] == 1




# ── Querschnitts-Review AS-4, Befund 1 (kritisch): die Gastseite ersetzt nie still ──────────

def test_die_gastseite_ersetzt_einen_anderen_wartenden_lauf_nicht(umgebung):  # noqa: F811
    """Ein Start der Gastseite (ohne Geste der Person) fragt, statt einen wartenden Lauf — samt
    Auftrag — zu beenden; „Neu starten“ ist ein Knopf ohne ``quelle``."""
    import json

    anderer = _ablauf(schritte=_WARTET, ausloeser=("knopf",), start=None).model_dump(
        exclude_none=True) | {"id": "anderer"}
    gast = _ablauf(schritte=_WARTET)
    umgebung.katalog["wert"] = {"ablaeufe": [anderer, gast.model_dump(exclude_none=True)]}
    umgebung.state = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "anderer"}),
                            umgebung.state))
    [v] = umgebung.speicher.v.values()
    vorher = dict(v.akte["lauf"])

    antwort = _gast(umgebung, gast, {"sammlung": _UUID})

    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"] == vorher and v.status != "fertig"
    [neu] = [q for q in antwort.quick_replies if "ablauf_starten" in q]
    params = json.loads(neu.split("|", 3)[3])
    assert params["ablauf"] == gast.id and params["start"] == {"sammlung": _UUID}
    assert "quelle" not in params and params["ersetzt"]   # kein Recht, nur an diesen Lauf gebunden


def test_andere_startdaten_fragen_ebenfalls(umgebung):  # noqa: F811 — Fixture
    ablauf = _ablauf(schritte=_WARTET)
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    umgebung.state = {"entities": {}}
    _gast(umgebung, ablauf, {"sammlung": _UUID})
    antwort = _gast(umgebung, ablauf, {"sammlung": _UUID[:-1] + "2"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["teile"]["start"]["wert"] == {"sammlung": _UUID}
    assert any("ablauf_starten" in q for q in antwort.quick_replies)


def test_texte_der_startdaten_sind_hoechstens_500_zeichen():
    """Querschnitts-Review AS-4, Befund 3: so prüft das Safety-Gate jedes Feld ganz."""
    with pytest.raises(ValueError):
        _ablauf(start=[{"name": "lang", "typ": "text", "max_zeichen": 501}])
    from boerdi.api.schemas import ChatRequest
    from boerdi.services.direct_actions import _direct_action_safety_text

    start = {f"f{i}": "x" * 500 for i in range(10)}
    anfrage = ChatRequest(session_id="sitzung-0123456789", message="", action=zug.AKTION,
                          action_params={"ablauf": "x", "start": start})
    text = _direct_action_safety_text(anfrage)
    assert all(f"start.f{i}: " + "x" * 500 in text for i in range(10))


# ── Nachprüfung Querschnitt AS-4 ───────────────────────────────────────────

def test_das_gate_prueft_startdaten_bereinigt_und_vor_allem_anderen():
    """Befund 1: führender Leerraum und Füll-Parameter schoben die Nutzlast aus der Prüfung."""
    from boerdi.api.schemas import ChatRequest
    from boerdi.services.direct_actions import _direct_action_safety_text

    nutzlast = "GEHEIM" + "y" * 400
    leer = ChatRequest(session_id="sitzung-0123456789", message="", action=zug.AKTION,
                       action_params={"ablauf": "x", "start": {"thema": " " * 600 + nutzlast}})
    assert nutzlast in _direct_action_safety_text(leer)
    fuell = {f"f{i}": "z" * 500 for i in range(4)}
    voll = ChatRequest(session_id="sitzung-0123456789", message="", action=zug.AKTION,
                       action_params={**fuell, "ablauf": "x", "start": {"thema": "GEHEIM"}})
    assert "start.thema: GEHEIM" in _direct_action_safety_text(voll)


def _lauf_auf_auftrag(umgebung):  # noqa: F811 — Fixture
    """Ein anderer Ablauf, dessen Lauf (wie nach einem Auftrag) auf Kestra wartet."""
    anderer = _ablauf(schritte=_WARTET, ausloeser=("knopf",), start=None).model_dump(
        exclude_none=True) | {"id": "anderer"}
    gast = _ablauf(schritte=_WARTET)
    umgebung.katalog["wert"] = {"ablaeufe": [anderer, gast.model_dump(exclude_none=True)]}
    umgebung.state = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "anderer"}),
                            umgebung.state))
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"]["status"] = "wartet_auftrag"
    v.status = "wartet_auftrag"
    return gast, v


def test_gastseite_gegen_einen_wartenden_auftrag(umgebung, monkeypatch):  # noqa: F811
    """Befund 7: der eigentliche kritische Fall — kein Abbruch, die Knöpfe sind da."""
    from boerdi.services.ablauf import zug_basis

    abgebrochen: list = []
    monkeypatch.setattr(zug_basis, "bei_der_b_api_abbrechen", lambda job: abgebrochen.append(job))
    gast, v = _lauf_auf_auftrag(umgebung)
    antwort = _gast(umgebung, gast, {"sammlung": _UUID})
    [v2] = umgebung.speicher.v.values()
    assert v2.akte["lauf"]["status"] == "wartet_auftrag" and v2.status == "wartet_auftrag"
    assert [j for j in abgebrochen if j] == []   # ``None``: der erste Start hatte keinen alten
    aktionen = [q.split("|", 3)[2] for q in antwort.quick_replies]
    assert aktionen == ["ablauf_starten", "ablauf_auftrag_pruefen"]


def test_der_knopf_neu_starten_ersetzt_nur_den_lauf_den_er_meinte(umgebung, monkeypatch):  # noqa: F811
    """Befunde 4 und 7: Rundlauf — der Knopf ersetzt; ein alter Knopf nach einer Bewegung des
    Laufs fragt erneut."""
    import json

    from boerdi.services.auftraege import ablage as auftraege_ablage

    async def kein_auftrag(*_a, **_k):
        return None

    monkeypatch.setattr(auftraege_ablage, "offen", kein_auftrag)

    gast, v = _lauf_auf_auftrag(umgebung)
    antwort = _gast(umgebung, gast, {"sammlung": _UUID})
    [knopf] = [q for q in antwort.quick_replies if "|ablauf_starten|" in q]
    params = json.loads(knopf.split("|", 3)[3])
    assert params["ersetzt"]
    # der Lauf bewegt sich, bevor geklickt wird
    umgebung.speicher.v[v.id].akte["lauf"]["schritt"] = "e"
    nochmal = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params=params),
                                      umgebung.state))
    assert any("|ablauf_starten|" in q for q in nochmal.quick_replies)
    assert umgebung.speicher.v[v.id].akte["lauf"]["ablauf"] == "anderer"
    # mit der neuen Marke ersetzt er
    [knopf2] = [q for q in nochmal.quick_replies if "|ablauf_starten|" in q]
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                       action_params=json.loads(knopf2.split("|", 3)[3])),
                            umgebung.state))
    laeufe = [x.akte["lauf"] for x in umgebung.speicher.v.values() if x.status != "fertig"]
    assert any(lauf and lauf["ablauf"] == gast.id for lauf in laeufe)
    # Querschnitts-Review RB, Befund 1: die Herkunft reist positiv im Knopf mit
    assert params["start_quelle"] == startdaten.QUELLE_GASTSEITE
    assert any(lauf and lauf["ablauf"] == gast.id
               and lauf.get("start_quelle") == startdaten.QUELLE_GASTSEITE for lauf in laeufe)


def test_die_knoepfe_der_rueckfrage_uebersteht_jeder_deckel():
    """Befund 3: wie die Wahl-Chips — sonst fragte der Text ohne Weg zur Antwort."""
    from boerdi.domain.wahl_knopf import ist_wahl_knopf

    assert ist_wahl_knopf('__action__|Neu starten|ablauf_starten|{"ablauf": "x", "ersetzt": "m"}')
    assert ist_wahl_knopf('__action__|Stand|ablauf_auftrag_pruefen|{"ablauf": "x", "ersetzt": "m"}')
    assert not ist_wahl_knopf('__action__|Start|ablauf_starten|{"ablauf": "x"}')


# ── Entscheid zu AS-4a, Befund 10 (Option 2): eine Kennung der Gastseite an lesende Werkzeuge ──

def _lesen(argumente):
    return {"id": "lesen", "typ": "werkzeug", "werkzeug": "get_collection_contents",
            "argumente": argumente, "schreibt": "inhalte", "bei_fehler": "e"}


def test_eine_kennung_aus_den_startdaten_darf_an_ein_lesendes_werkzeug():
    ablauf = _ablauf(schritte=[_lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}),
                               {"id": "e", "typ": "ende"}])
    assert pruefe(ablauf) == []


def test_nur_kennungen_nur_ganz_nur_aus_start():
    for argumente in (
        {"nodeId": {"$teil": "start", "pfad": "thema"}},           # Freitext
        {"x": {"y": {"$teil": "start", "pfad": "sammlung"}}},      # verschachtelt
        {"nodeId": {"$teil": "start"}},                             # der ganze Teil
        {"nodeId": {"$teil": "inhalte"}},                           # anderer Teil
        {"nodeId": {"$teil": "start", "liste": "sammlung"}},        # Auswahl (Review RB-1, 2)
    ):
        befunde = pruefe(_ablauf(schritte=[_lesen(argumente), {"id": "e", "typ": "ende"}]))
        assert any("lesende" in b for b in befunde), argumente


def test_ein_fremdwerkzeug_bekommt_auch_keine_kennung():
    """Review RB-1, Befund 2: Werkzeuge eines Fremdservers kennt ein Ablauf gar nicht."""
    schritt = {**_lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}),
               "werkzeug": "srv__get_collection_contents"}
    befunde = pruefe(_ablauf(schritte=[schritt, {"id": "e", "typ": "ende"}]))
    assert befunde, befunde


def _treiber_lauf(start, quelle):
    ablauf = _ablauf(schritte=[_lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}),
                               {"id": "e", "typ": "ende"}])
    gerufen: list = []

    async def keine(_name):
        return None

    async def mcp(name, args):
        gerufen.append((name, args))
        return "Inhalte"

    umgebung_ = treiber.Umgebung(teile=keine, sprache="de", mcp=mcp)
    aus = asyncio.run(treiber.starten(ablauf, umgebung_, start=start, start_quelle=quelle))
    return aus, gerufen


def test_der_treiber_setzt_die_kennung_nur_von_der_gastseite_ein():
    aus, gerufen = _treiber_lauf({"sammlung": _UUID}, "gastseite")
    assert gerufen == [("get_collection_contents", {"nodeId": _UUID})]
    assert aus.lauf["status"] == "fertig"
    # ohne Herkunft „Gastseite“ (etwa später von der KI) kein Aufruf — bei_fehler
    aus, gerufen = _treiber_lauf({"sammlung": _UUID}, None)
    assert gerufen == [] and aus.lauf["schritt"] == "e"


# ── Review RB-1, Befund 2: die Herkunft der Startdaten über Zug, Folgezug und Simulation ──────────


def test_der_zug_merkt_sich_die_herkunft_nur_bei_daten_von_aussen(umgebung):  # noqa: F811
    _starten(umgebung, _ablauf(schritte=_WARTET),
             {"start": {"sammlung": _UUID}, "quelle": "gastseite"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["start_quelle"] == startdaten.QUELLE_GASTSEITE


def test_ein_knopf_ohne_daten_hat_keine_herkunft(umgebung):  # noqa: F811 — Fixture
    ablauf = _ablauf(start=[{"name": "sammlung", "typ": "nodeid"}], ausloeser=("extern", "knopf"),
                     schritte=_WARTET)
    _starten(umgebung, ablauf, {})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") is None


def test_die_kennung_gilt_auch_im_folgezug():
    """Der Lauf wartet erst auf die Person; die Kennung reist mit dem gespeicherten Lauf weiter."""
    ablauf = _ablauf(schritte=[
        {"id": "frage", "typ": "nachricht", "text": {"de": "Weiter?"},
         "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "lesen"}]},
        _lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}),
        {"id": "e", "typ": "ende"}])
    gerufen: list = []

    async def teile(name):
        return {"sammlung": _UUID} if name == typen.START_TEIL else None

    async def mcp(name, args):
        gerufen.append((name, args))
        return "Inhalte"

    def umgebung_():
        return treiber.Umgebung(teile=teile, sprache="de", mcp=mcp)

    async def ablaufen(quelle):
        aus = await treiber.starten(ablauf, umgebung_(), start={"sammlung": _UUID},
                                    start_quelle=quelle)
        assert aus.lauf["status"] == "wartet_wahl"
        gespeichert = dict(aus.lauf)          # wie in ``akte.lauf``
        return await treiber.weiter_wahl(ablauf, gespeichert, "ja", None, umgebung_())

    weiter = asyncio.run(ablaufen(startdaten.QUELLE_GASTSEITE))
    assert gerufen == [("get_collection_contents", {"nodeId": _UUID})]
    assert weiter is not None and weiter.lauf["status"] == "fertig"
    gerufen.clear()
    weiter = asyncio.run(ablaufen(None))
    assert gerufen == [] and weiter is not None and weiter.lauf["schritt"] == "e"


def test_die_simulation_setzt_die_kennung_wie_der_betrieb_ein():
    ablauf = _ablauf(schritte=[
        {**_lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}), "bei_fehler": "fehler"},
        {"id": "e", "typ": "ende"},
        {"id": "fehler", "typ": "ende"}])
    ergebnis = _test(ablauf, {"name": "s", "start": {"sammlung": _UUID},
                              "werkzeuge": {"lesen": "Inhalte"},
                              "erwartet": {"weg": ["lesen", "e"], "teile": ["inhalte"]}})
    assert ergebnis.ok, ergebnis.abweichungen


# ── Querschnitts-Review RB, Befunde 1, 3 und 9: die Herkunft nur positiv ────────────────────────


def test_startdaten_ohne_quelle_haben_keine_herkunft(umgebung):  # noqa: F811 — Fixture
    """Ein Knopf mit Daten (etwa ab AS-5 ein Vorschlag der KI) bekommt nie die Rechte der
    Gastseite — die folgen nur aus ``quelle: gastseite``, nicht aus vorhandenen Startdaten."""
    _starten(umgebung, _ablauf(schritte=_WARTET), {"start": {"sammlung": _UUID}})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") is None


def test_from_host_ist_nie_eine_herkunft(umgebung):  # noqa: F811 — Fixture
    """``from_host`` ist nur Anzeige (RB-3) — es macht Startdaten nicht zu Daten der Gastseite."""
    ablauf = _ablauf(schritte=_WARTET)
    umgebung.katalog["wert"] = {"ablaeufe": [ablauf.model_dump(exclude_none=True)]}
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": "mit_start",
                                                      "start": {"sammlung": _UUID}})
    anfrage = anfrage.model_copy(update={"from_host": True})
    asyncio.run(zug.starten(_S(), anfrage, {"entities": {}}))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") is None


def test_eine_kennung_der_startdaten_braucht_den_ausloeser_gastseite():
    """Ohne Auslöser ``extern`` kommen nie Daten der Gastseite — die Ausnahme greift dann nicht,
    die Prüfung meldet es statt eines stillen ``bei_fehler`` im Betrieb."""
    schritte = [_lesen({"nodeId": {"$teil": "start", "pfad": "sammlung"}}),
                {"id": "e", "typ": "ende"}]
    felder = [{"name": "sammlung", "typ": "nodeid"}]
    assert pruefe(_ablauf(start=felder, schritte=schritte)) == []
    befunde = pruefe(_ablauf(start=felder, ausloeser=("knopf",), schritte=schritte))
    assert any("Gastseite" in b for b in befunde), befunde
