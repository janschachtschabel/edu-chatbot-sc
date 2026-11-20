"""Plan 2026-11-20, Paket G2 (Führung 1:1 wie die Tour): vier Fähigkeiten des Baukastens.

- G2a ``text_antworten``: ein Chip, der wie getippter Text zählt (Wahl ``_text``, der Vorlauf
  macht daraus Text — nicht an der Frage eines anderen Laufs) — „Bin mir nicht sicher“ ist in der
  Tour ein Fehlversuch, keine Wahl.
- G2b: in einem Ablauf mit ``endet_bei_text`` ist eine Wendung desselben Ablaufs an einer Frage
  ohne Freitext getippter Text (wie die Tour im Gruppen-Schritt).
- G2c: der Tour-Chip der Begrüßung (``tour_action: start``) startet den Ablauf wie sein Knopf —
  ein wartender Lauf beginnt neu an der aktuellen Seite.
- G2d: wartet eine Führung an einer Frage, zeigt der Seiten-Ping die Frage erneut (ungespeichert)
  — wie der Tour-Tick im Gruppen-Schritt; der Stand sagt dem Widget ``fuehrung``.
"""

from __future__ import annotations

import asyncio
import json

from boerdi.api.chat import turn_kontext
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.wahl_knopf import ist_wahl_knopf
from boerdi.graph.nodes import preflight_ablauf
from boerdi.graph.state import TurnContext
from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import (
    ausloeser,
    fortschritt,
    pruefung,
    seite_zug,
    treiber,
    wahl_zug,
    wendung_zug,
    zug,
)
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_seite_zug import _SID, _ping, _req, _starten
from tests.test_ablauf_zug import _S, umgebung  # noqa: F401 — Fixture

_UNSICHER = {"label": {"de": "Bin mir nicht sicher", "en": "I'm not sure"}}
_HINWEIS = {"de": "Sag mir grob, was dich herführt."}


def _option(id_, label, ziel="e", **mehr):
    return {"id": id_, "label": {"de": label}, "ziel": ziel, **mehr}


_GRUPPEN = [_option("lehrkraft", "Lehrkraft", synonyme=["lehrer"]), _option("presse", "Presse")]


def _frage(**mehr):
    return {"id": "w", "typ": "nachricht", "text": {"de": "Wer bist du?"}, "schreibt": "gruppe",
            "optionen": _GRUPPEN, "kein_treffer": _HINWEIS, **mehr}


_ENDE = {"id": "e", "typ": "ende", "text": {"de": "Danke."}}


def _roh(*schritte, **ablauf):
    return AblaufArea.model_validate({
        "id": "fuehrung", "titel": {"de": "Führung"}, "aktiv": True,
        "ausloeser": [{"art": "knopf"}, {"art": "text", "wendungen": ["tour starten"]}],
        "schritte": list(schritte), **ablauf}).model_dump(exclude_none=True)


def _getippt(state, text):
    return asyncio.run(wahl_zug.getippt(_S(), _req(message=text), state))


def _lauf(state):
    return arbeitsstand.verweis(state["entities"], arbeitsstand.aufrufer_fuer(_SID))["lauf"]


# ── G2a: Antwort-Chip als Text ───────────────────────────────────────────────────────────────

def test_g2a_der_text_chip_steht_hinter_den_optionen_und_uebersteht_jeden_deckel(umgebung):  # noqa: F811
    _zustand, antwort = _starten(umgebung, _roh(_frage(text_antworten=[_UNSICHER]), _ENDE))
    *optionen, text_chip = antwort.quick_replies
    assert [q.split("|")[1] for q in optionen] == ["Lehrkraft", "Presse"]
    praefix, label, aktion, params = text_chip.split("|", 3)
    assert (praefix, label, aktion) == ("__action__", "Bin mir nicht sicher", wahl_zug.AKTION)
    assert json.loads(params) == {"ablauf": "fuehrung", "schritt": "w", "wahl": wahl_zug.TEXT}
    assert ist_wahl_knopf(text_chip)


def _vorlauf(state, req):
    ctx = TurnContext(req=req, session_state=state)

    async def lauf():
        preflight_ablauf.text_chip_als_text(ctx)
        a = await preflight_ablauf.bestimmen(ctx, _S())
        return ctx, a, await preflight_ablauf.antwort(ctx, _S(), a, [])
    return asyncio.run(lauf())


def _text_chip(ablauf="fuehrung", schritt="w", label="Bin mir nicht sicher"):
    return _req(message=label, action=wahl_zug.AKTION,
                action_params={"ablauf": ablauf, "schritt": schritt, "wahl": wahl_zug.TEXT})


def test_g2a_der_vorlauf_macht_aus_dem_text_chip_der_wartenden_frage_getippten_text(umgebung):  # noqa: F811
    state, _ = _starten(umgebung, _roh(_frage(text_antworten=[_UNSICHER]), _ENDE))
    ctx, a, antwort = _vorlauf(state, _text_chip())
    assert (ctx.req.action, ctx.req.action_params, ctx.req.message) == (
        None, {}, "Bin mir nicht sicher")
    assert a.freitext and antwort.antwort.content == _HINWEIS["de"]


_ANDERER = {"id": "anderer", "titel": {"de": "Anderer"}, "aktiv": True,
            "ausloeser": [{"art": "knopf"}],
            "schritte": [{"id": "f", "typ": "nachricht", "text": {"de": "Wozu?"},
                          "schreibt": "zweck", "optionen": [_option("a", "A")],
                          "freitext": {"schreibt": "zweck", "ziel": "e"}}, _ENDE]}


def _anderer_wartet(umgebung, fuehrung):  # noqa: F811
    """Review G2, Befunde 1/2: die Führung im Katalog, ein anderer Ablauf wartet an seiner Frage."""
    state, _ = _starten(umgebung, AblaufArea.model_validate(_ANDERER).model_dump(
        exclude_none=True))
    umgebung.katalog["wert"] = {"ablaeufe": [fuehrung, _ANDERER]}
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_WAHL)
    return state


def test_review_g2_1_ein_alter_text_chip_beantwortet_keinen_anderen_ablauf(umgebung):  # noqa: F811
    """MAJOR 1: der alte „Bin mir nicht sicher“-Chip der Führung wurde zum Freitext ``zweck`` des
    anderen Laufs. Jetzt „gilt nicht mehr“ mit den Chips, die gelten — der Lauf wartet weiter."""
    state = _anderer_wartet(umgebung, _roh(_frage(text_antworten=[_UNSICHER]), _ENDE))
    # der Endpunkt wandelt nicht blind um (er kennt den Zustand der Sitzung nicht)
    assert turn_kontext(_text_chip(), False).req.action == wahl_zug.AKTION
    ctx, _a, antwort = _vorlauf(state, _text_chip(schritt="w"))
    assert ctx.req.action == wahl_zug.AKTION
    assert antwort.antwort.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert [q.split("|")[1] for q in antwort.antwort.quick_replies] == ["A"]
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_WAHL)
    [v] = umgebung.speicher.v.values()
    assert "zweck" not in (v.akte.get("teile") or {})


def test_g2a_der_text_chip_zaehlt_wie_ein_fehlversuch(umgebung):  # noqa: F811
    """Wie die Tour: erst der Hilfetext mit denselben Chips, beim zweiten Mal nimmt der Schritt den
    Text nicht mehr — ``endet_bei_text`` beendet den Lauf, der Zug geht an die KI."""
    state, _ = _starten(umgebung, _roh(_frage(text_antworten=[_UNSICHER]), _ENDE,
                                       endet_bei_text=True))
    assert wahl_zug.nimmt_getippt(_SID, state, "Bin mir nicht sicher")
    antwort = _getippt(state, "Bin mir nicht sicher")
    assert antwort.content == _HINWEIS["de"]
    assert antwort.quick_replies[-1].split("|")[1] == "Bin mir nicht sicher"
    assert not wahl_zug.nimmt_getippt(_SID, state, "Bin mir nicht sicher")
    assert asyncio.run(wahl_zug.still_beenden(_S(), _SID, state))


def test_g2a_der_text_chip_spricht_die_sprache_des_zuges(umgebung):  # noqa: F811
    roh = _roh(_frage(text_antworten=[_UNSICHER]), _ENDE)
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    s = AblaufArea.model_validate(roh).schritte[0]
    assert treiber.wahl_angebot(s, "en")["texte"] == ["I'm not sure"]


def test_g2a_pruefung():
    def befunde(**schritt):
        return pruefe(AblaufArea.model_validate(_roh({**_frage(), **schritt}, _ENDE)))

    assert befunde(text_antworten=[_UNSICHER]) == []
    ohne_optionen = {"optionen": None, "kein_treffer": None, "text_antworten": [_UNSICHER]}
    assert any("text_antworten" in b for b in befunde(**ohne_optionen))
    # Review G2 (zweite Runde, NIT 5): ohne Hinweis beendete der erste Druck die Führung
    assert any("text_antworten" in b for b in befunde(kein_treffer=None,
                                                         text_antworten=[_UNSICHER]))
    # trifft der Text eine Option (Beschriftung oder Synonym), wäre der Chip eine Wahl
    for label in ("Presse", "Ich bin Lehrer"):
        assert any("text_antworten" in b
                   for b in befunde(text_antworten=[{"label": {"de": label}}]))


def test_review_g2_1_ein_alter_text_chip_derselben_fuehrung_ist_getippter_text(umgebung):  # noqa: F811
    """Wie in der Tour: ist die Führung weiter (sie wartet auf eine Seite), zählt der alte Chip wie
    getippt — ``endet_bei_text`` beendet sie, die KI antwortet. Nur eine fremde wartende Frage
    oder ein fremder Lauf bekommt „gilt nicht mehr“."""
    hin = {**_INTRO, "id": "hin", "weiter": "e"}
    frage = _frage(text_antworten=[_UNSICHER])
    frage["optionen"] = [{**o, "ziel": "hin"} for o in frage["optionen"]]
    state, _ = _starten(umgebung, _roh(frage, hin, _ENDE, endet_bei_text=True), "/home/")
    asyncio.run(wahl_zug.waehlen(_S(), _req(action=wahl_zug.AKTION, action_params={
        "ablauf": "fuehrung", "schritt": "w", "wahl": "presse"}), state))
    assert _lauf(state)["status"] == treiber.WARTET_SEITE
    ctx, a, antwort = _vorlauf(state, _text_chip())
    assert ctx.req.action is None and antwort is None          # an die KI
    assert _lauf(state)["status"] == "abgebrochen"


def test_review_g2_zweite_runde_2_ein_fremder_lauf_ohne_frage_behaelt_den_chip_als_wahl(umgebung):  # noqa: F811
    """MINOR 2 (zweite Runde): wartet ein anderer Ablauf nicht an einer Frage (hier ``seite``),
    bleibt der Chip eine Wahl — sonst bekäme etwa ein fremder KI-Schritt ihn als Eingabe."""
    seite = {"id": "s", "typ": "seite", "text": {"de": "Geh hin."}, "url": "/x/",
             "label": {"de": "Hin"}, "ankunft": ["/x"]}
    andere = {**_ANDERER, "schritte": [seite, _ENDE]}
    state, _ = _starten(umgebung, AblaufArea.model_validate(andere).model_dump(exclude_none=True))
    umgebung.katalog["wert"] = {"ablaeufe": [_roh(_frage(text_antworten=[_UNSICHER]), _ENDE),
                                             andere]}
    ctx, _a, antwort = _vorlauf(state, _text_chip())
    assert ctx.req.action == wahl_zug.AKTION
    assert antwort.antwort.content == bot_text("de", "action.ablauf.wahlVeraltet")
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_SEITE)


def test_review_g2_zweite_runde_2_ohne_lauf_ist_der_chip_gewoehnlicher_text(umgebung):  # noqa: F811
    umgebung.katalog["wert"] = {"ablaeufe": [_roh(_frage(text_antworten=[_UNSICHER]), _ENDE)]}
    ctx, _a, antwort = _vorlauf({"entities": {}}, _text_chip())
    assert (ctx.req.action, ctx.req.message, antwort) == (None, "Bin mir nicht sicher", None)


def test_review_g2_zweite_runde_3_tour_chip_braucht_einen_knopf_und_keine_pflichtfelder(umgebung):  # noqa: F811
    """MINOR 3 (zweite Runde): ohne Knopf-Auslöser meldet die Prüfung ``tour_chip``; ein Ablauf mit
    Pflichtfeld in den Startdaten startet nicht über den Chip (er bringt keine Daten)."""
    nur_text = _roh(_frage(), _ENDE, tour_chip=True)
    nur_text["ausloeser"] = [{"art": "text", "wendungen": ["tour starten"]}]
    assert any("tour_chip" in b for b in pruefe(AblaufArea.model_validate(nur_text)))
    assert not any("tour_chip" in b for b in pruefe(AblaufArea.model_validate(
        _roh(_frage(), _ENDE, tour_chip=True))))
    mit_pflicht = _roh(_frage(), _ENDE, tour_chip=True, start=[
        {"name": "sammlung", "typ": "text", "pflicht": True}])
    umgebung.katalog["wert"] = {"ablaeufe": [mit_pflicht]}
    assert ausloeser.per_tour_chip() is None
    umgebung.katalog["wert"] = {"ablaeufe": [_roh(_frage(), _ENDE, tour_chip=True)]}
    assert ausloeser.per_tour_chip().id == "fuehrung"


# ── G2b: Wendung an der Frage einer Führung ──────────────────────────────────────────────────

def test_g2b_in_einer_fuehrung_ist_die_wendung_an_der_frage_getippter_text(umgebung):  # noqa: F811
    state, _ = _starten(umgebung, _roh(_frage(), _ENDE, endet_bei_text=True))
    assert wendung_zug.wendung_trifft(_SID, state, "tour starten") is None
    assert wahl_zug.nimmt_getippt(_SID, state, "tour starten")
    assert _getippt(state, "tour starten").content == _HINWEIS["de"]


def test_g2b_ohne_endet_bei_text_bleibt_schon_mitten(umgebung):  # noqa: F811
    state, _ = _starten(umgebung, _roh(_frage(), _ENDE))
    assert wendung_zug.wendung_trifft(_SID, state, "tour starten").id == "fuehrung"


# ── G2c: der Tour-Chip ist der Knopf ─────────────────────────────────────────────────────────

_WO = {"id": "wo", "typ": "verzweigung",
       "weiter": [{"wenn_seite": ["/home"], "dann": "w"}, {"sonst": "intro"}]}
_INTRO = {"id": "intro", "typ": "seite", "text": {"de": "Los geht's auf der Startseite."},
          "url": "/home/", "label": {"de": "Zur Startseite"}, "ankunft": ["/home"], "weiter": "w"}


def _tour_chip(state, seite):
    ctx = TurnContext(req=_req(seite, message="Web-Tour starten",
                               env={"tour_action": "start"}), session_state=state)

    async def lauf():
        a = await preflight_ablauf.bestimmen(ctx, _S())
        return await preflight_ablauf.antwort(ctx, _S(), a, [])
    return asyncio.run(lauf())


def test_g2c_der_tour_chip_beginnt_die_fuehrung_neu_an_der_aktuellen_seite(umgebung):  # noqa: F811
    state, antwort = _starten(umgebung, _roh(_WO, _INTRO, _frage(), _ENDE, endet_bei_text=True,
                                             tour_chip=True), "/impressum/")
    assert antwort.content == "Los geht's auf der Startseite."
    neu = _tour_chip(state, "/home/").antwort
    assert neu.content == "Wer bist du?"
    assert _lauf(state)["status"] == treiber.WARTET_WAHL


def test_g2c_ohne_lauf_startet_der_tour_chip_wie_bisher(umgebung):  # noqa: F811
    umgebung.katalog["wert"] = {"ablaeufe": [_roh(_WO, _INTRO, _frage(), _ENDE, tour_chip=True)]}
    state: dict = {"entities": {}}
    assert _tour_chip(state, "/impressum/").antwort.content == "Los geht's auf der Startseite."


def test_review_g2_7_der_tour_chip_folgt_dem_merkmal_nicht_einer_wendung(umgebung):  # noqa: F811
    """MINOR 7: das Ziel hing an der Wendung „tour starten“ im Text „Web-Tour starten“. Jetzt
    startet der Ablauf mit ``tour_chip`` — auch ohne passende Wendung."""
    roh = _roh(_WO, _INTRO, _frage(), _ENDE, tour_chip=True)
    roh["ausloeser"] = [{"art": "knopf"}]
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    state: dict = {"entities": {}}
    assert _tour_chip(state, "/impressum/").antwort.content == "Los geht's auf der Startseite."


def test_review_g2_7_zwei_aktive_mit_tour_chip_warnen():
    a = AblaufArea.model_validate(_roh(_frage(), _ENDE, tour_chip=True))
    b = AblaufArea.model_validate({**_roh(_frage(), _ENDE, tour_chip=True), "id": "zweite"})
    assert any("tour_chip" in w for w in pruefung.tour_chip_warnungen(a, [a, b]))
    assert pruefung.tour_chip_warnungen(a, [a]) == []
    aus = AblaufArea.model_validate({**_roh(_frage(), _ENDE, tour_chip=True), "id": "zweite",
                                     "aktiv": False})
    assert pruefung.tour_chip_warnungen(a, [a, aus]) == []


def test_review_g2_2_der_tour_chip_fragt_vor_dem_ersetzen_eines_anderen_ablaufs(umgebung):  # noqa: F811
    """MAJOR 2: der Tour-Chip ersetzte den wartenden anderen Lauf ohne Rückfrage. Jetzt die
    Ersetzen-Rückfrage mit „Hier weitermachen“ — der andere Lauf wartet weiter."""
    state = _anderer_wartet(umgebung, _roh(_WO, _INTRO, _frage(), _ENDE, tour_chip=True))
    antwort = _tour_chip(state, "/home/").antwort
    labels = [q.split("|")[1] for q in antwort.quick_replies]
    assert labels == [bot_text("de", "action.ablauf.neuStarten"),
                      bot_text("de", "action.ablauf.hierWeiter")]
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_WAHL)
    # Review G2 (zweite Runde, MINOR 1): beide Knöpfe der Rückfrage bis zum Ende gedrückt
    neu_starten, hier = ((teile[2], json.loads(teile[3]))
                         for teile in (q.split("|", 3) for q in antwort.quick_replies))
    vorher = {k: dict(v.akte.get("teile") or {}) for k, v in umgebung.speicher.v.items()}
    weiter = asyncio.run(wahl_zug.waehlen(_S(), _req("/home/", action=hier[0],
                                                     action_params=hier[1]), state))
    assert weiter.content == "Wozu?"
    assert [q.split("|")[1] for q in weiter.quick_replies] == ["A"]
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_WAHL)
    assert {k: dict(v.akte.get("teile") or {}) for k, v in umgebung.speicher.v.items()} == vorher
    start = asyncio.run(zug.starten(_S(), _req("/home/", action=neu_starten[0],
                                               action_params=neu_starten[1]), state))
    assert start.content == "Wer bist du?"            # an der aktuellen Seite (/home → Frage)
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("fuehrung", treiber.WARTET_WAHL)
    assert not any((v.akte.get("lauf") or {}).get("ablauf") == "anderer"
                   and v.status != "fertig" for v in umgebung.speicher.v.values())


def test_review_g2_2_auch_wenn_der_andere_nicht_an_einer_frage_wartet(umgebung):  # noqa: F811
    seite = {"id": "s", "typ": "seite", "text": {"de": "Geh hin."}, "url": "/x/",
             "label": {"de": "Hin"}, "ankunft": ["/x"]}
    andere = {**_ANDERER, "schritte": [seite, _ENDE]}
    state, _ = _starten(umgebung, AblaufArea.model_validate(andere).model_dump(exclude_none=True))
    umgebung.katalog["wert"] = {"ablaeufe": [_roh(_WO, _INTRO, _frage(), _ENDE, tour_chip=True),
                                             andere]}
    antwort = _tour_chip(state, "/home/").antwort
    assert [q.split("|")[1] for q in antwort.quick_replies] == [
        bot_text("de", "action.ablauf.neuStarten")]
    assert (_lauf(state)["ablauf"], _lauf(state)["status"]) == ("anderer", treiber.WARTET_SEITE)


# ── Review G2, MINOR 3: der erneut gezeigte Seiten-Schritt ───────────────────────────────────

def test_review_g2_3_eine_wendung_zeigt_den_wartenden_schritt_mit_text_erneut(umgebung):  # noqa: F811
    """Die Tour zeigt den Schritt nach einer Wendung neu gerendert („Lösungen“ statt der
    Einstiegsbegrüßung) — ``text_erneut`` am ``seite``-Schritt; ohne bleibt es ``text``."""
    einstieg = {**_INTRO, "id": "einstieg", "text": {"de": "Schön, du bist schon da!"},
                "text_erneut": {"de": "Das sind die Lösungen."}}
    einstieg.pop("weiter")
    state, antwort = _starten(umgebung, _roh(einstieg, _ENDE), "/impressum/")
    assert antwort.content == "Schön, du bist schon da!"
    erneut = asyncio.run(seite_zug.wiederholen(_S(), _req("/impressum/", message="tour starten"),
                                               state))
    assert erneut.content == "Das sind die Lösungen."
    intro = {**_INTRO}
    intro.pop("weiter")
    ohne, _ = _starten(umgebung, _roh(intro, _ENDE), "/impressum/")
    assert asyncio.run(seite_zug.wiederholen(_S(), _req("/impressum/", message="tour starten"),
                                             ohne)).content == "Los geht's auf der Startseite."


# ── G2d: die Frage einer Führung nach einem Seitenwechsel ────────────────────────────────────

def test_g2d_der_stand_einer_fuehrung_sagt_es_dem_widget(umgebung):  # noqa: F811
    state, _ = _starten(umgebung, _roh(_WO, _INTRO, _frage(), _ENDE), "/home/")
    stand = fortschritt.stand(state["entities"], arbeitsstand.aufrufer_fuer(_SID), "de")
    assert stand["status"] == treiber.WARTET_WAHL and stand["fuehrung"] is True
    ohne, _ = _starten(umgebung, _roh(_frage(), _ENDE))
    assert "fuehrung" not in fortschritt.stand(ohne["entities"], arbeitsstand.aufrufer_fuer(_SID),
                                               "de")


def test_g2d_der_ping_zeigt_die_frage_erneut_ohne_sie_zu_speichern(umgebung):  # noqa: F811
    state, erste = _starten(umgebung, _roh(_WO, _INTRO, _frage(text_antworten=[_UNSICHER]), _ENDE),
                            "/home/")
    gespeichert = len(umgebung.gesendet)
    antwort = _ping(state, "/home/oer-community/")
    assert antwort.content == "Wer bist du?"
    assert antwort.quick_replies == erste.quick_replies
    assert antwort.ui.fester_text
    assert len(umgebung.gesendet) == gespeichert
    assert _lauf(state)["status"] == treiber.WARTET_WAHL


def test_g2d_ohne_seite_schritt_bleibt_der_ping_an_der_frage_leer(umgebung):  # noqa: F811
    state, _ = _starten(umgebung, _roh(_frage(), _ENDE))
    assert _ping(state, "/home/").content == ""
