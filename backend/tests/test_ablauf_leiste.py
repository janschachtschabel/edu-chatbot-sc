"""Paket AS-Ua (Plan 2026-11-09 §5h, D10): das Backend der Ablauf-Leiste im Widget.

- ``fortschritt.position``: „Schritt n von m“ über die längsten einfachen Wege (U-3) — Rückwege,
  ``bei_fehler`` und ``ende`` zählen nicht.
- ``fortschritt.stand``: der öffentliche Stand ``ui.ablauf`` aus dem Sitzungsverweis (U-1, U-2) —
  ohne den Teil ``start`` und ohne Kennungen.
- ``ui.fester_text`` an festen Texten des Ablaufs (U-7), auch im Verlauf.
- Direktaktion ``ablauf_abbrechen`` mit Rückfrage (U-5).
"""

from __future__ import annotations

import asyncio
import json

from boerdi.api import publikum
from boerdi.api.schemas import ChatResponse
from boerdi.api.schemas_ui import UiInfo
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.i18n.bot_text import bot_text
from boerdi.services.ablauf import abbruch_zug, fortschritt, zug
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)

_UUID = "0a1b2c3d-0000-4000-8000-000000000001"


def _ablauf(schritte, **mehr):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe", "en": "Probe EN"},
                                      "aktiv": True, "ausloeser": [{"art": "knopf"}],
                                      "schritte": schritte, **mehr})


def _n(id_, **mehr):
    return {"id": id_, "typ": "nachricht", "text": {"de": id_}, **mehr}


_ENDE = {"id": "e", "typ": "ende"}


# ── Schritt n von m ────────────────────────────────────────────────────────────────────────────


def test_ein_gerader_ablauf_zaehlt_ohne_das_ende():
    a = _ablauf([_n("a"), _n("b"), _n("c"), _ENDE])
    assert [fortschritt.position(a, s) for s in ("a", "b", "c")] == [(1, 3), (2, 3), (3, 3)]


def test_nach_einer_verzweigung_passt_m_zum_weg():
    a = _ablauf([
        {"id": "w", "typ": "nachricht", "text": {"de": "?"}, "optionen": [
            {"id": "x", "label": {"de": "X"}, "ziel": "kurz"},
            {"id": "y", "label": {"de": "Y"}, "ziel": "lang1"}]},
        _n("kurz", weiter="e"), _n("lang1"), _n("lang2"), _ENDE])
    assert fortschritt.position(a, "w") == (1, 3)
    assert fortschritt.position(a, "kurz") == (2, 2)
    assert fortschritt.position(a, "lang2") == (3, 3)


def test_rueckwege_und_bei_fehler_zaehlen_nicht():
    a = _ablauf([
        {"id": "w", "typ": "nachricht", "text": {"de": "?"}, "optionen": [
            {"id": "nochmal", "label": {"de": "Nochmal"}, "ziel": "w"},
            {"id": "fertig", "label": {"de": "Fertig"}, "ziel": "t"}]},
        {"id": "t", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
         "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "z", "bei_fehler": "f1"},
        _ENDE, _n("f1"), _n("f2"), _n("f3"), {"id": "f", "typ": "ende"}])
    assert fortschritt.position(a, "w") == (1, 2)
    assert fortschritt.position(a, "t") == (2, 2)


def test_ein_unbekannter_schritt_hat_keine_position():
    assert fortschritt.position(_ablauf([_n("a"), _ENDE]), "weg") is None


# ── Stand aus der Sitzung ──────────────────────────────────────────────────────────────────────


def _gestartet(umgebung, roh):  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    zustand: dict = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": roh["id"]}),
                            zustand))
    return zustand


_WARTET = [{"id": "frage", "typ": "nachricht", "text": {"de": "Weiter?"},
            "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]}, _ENDE]


def test_der_stand_eines_wartenden_laufs(umgebung):  # noqa: F811 — Fixture
    roh = _ablauf(_WARTET).model_dump(exclude_none=True)
    zustand = _gestartet(umgebung, roh)
    zustand["entities"]["_vorgang"]["teile"] = {
        "start": {"v": 1, "z": "Startdaten"},
        "draft": {"v": 2, "z": f"Entwurf für {_UUID} mit 5 Punkten"}}
    stand = fortschritt.stand(zustand["entities"], "person-a", "en")
    lauf = stand.pop("lauf")
    assert isinstance(lauf, str) and lauf      # Laufmarke (zweites Review AS-U, Befund 2)
    # ``persoenlich`` (zweites Review, Z-8): der Lauf einer angemeldeten Person — nach dem Abmelden
    # blendet das Widget ihre Leiste aus
    assert stand == {"id": "probe", "titel": "Probe EN", "nr": 1, "von": 1,
                     "status": "wartet_wahl", "persoenlich": True,
                     "teile": [{"name": "draft", "text": "Entwurf für … mit 5 Punkten"}]}


def test_ohne_lauf_oder_nach_dem_ende_kein_stand(umgebung):  # noqa: F811 — Fixture
    assert fortschritt.stand({}, "person-a", "de") is None
    roh = _ablauf([_n("a"), _ENDE]).model_dump(exclude_none=True)
    zustand = _gestartet(umgebung, roh)                      # läuft bis zum Ende durch
    assert fortschritt.stand(zustand["entities"], "person-a", "de") is None


def test_fremde_besitzerin_sieht_keinen_stand(umgebung):  # noqa: F811 — Fixture
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    assert fortschritt.stand(zustand["entities"], "person-b", "de") is None


# ── öffentlich: ui.ablauf und ui.fester_text ───────────────────────────────────────────────────


def test_antwort_fuer_behaelt_stand_und_festen_text():
    stand = {"id": "probe", "titel": "Probe", "nr": 1, "von": 2, "status": "laeuft", "lauf": "a1",
             "persoenlich": False,
             "teile": [], "weg": None}   # AS-7: ``weg`` nur bei ``wartet_seite``
    resp = ChatResponse(session_id="bb-1", content="x",
                        ui=UiInfo(ablauf=stand, fester_text=True))
    aus = publikum.antwort_fuer(resp, intern=False)
    assert aus.ui.ablauf is not None and aus.ui.ablauf.model_dump() == stand
    assert aus.ui.fester_text is True


def test_ein_fester_text_bleibt_es_im_verlauf():
    verlauf = publikum.verlauf_fuer([
        {"id": 1, "role": "assistant", "content": "Los.", "cards": [],
         "debug": {"_fester_text": True}},
        {"id": 2, "role": "assistant", "content": "KI", "cards": [], "debug": {}},
    ], intern=False)
    assert verlauf[0]["ui"]["fester_text"] is True
    assert "fester_text" not in verlauf[1]["ui"]


def test_der_verlauf_traegt_den_stand_an_der_letzten_antwort():
    stand = {"id": "probe", "titel": "Probe", "nr": 1, "von": 2, "status": "laeuft", "teile": []}
    verlauf = publikum.mit_ablauf_stand([
        {"id": 1, "role": "assistant", "content": "a", "ui": {}},
        {"id": 2, "role": "user", "content": "b", "ui": {}},
        {"id": 3, "role": "assistant", "content": "c", "ui": {}},
    ], stand)
    assert "ablauf" not in verlauf[0]["ui"] and verlauf[2]["ui"]["ablauf"] == stand
    assert publikum.mit_ablauf_stand([{"id": 1, "role": "user", "ui": {}}], stand)[0]["ui"] == {}
    # Review AS-Ub, Befund 4: eine leere Antwort stellt das Widget nicht wieder her
    leer = publikum.mit_ablauf_stand([
        {"id": 1, "role": "assistant", "content": "a", "ui": {}},
        {"id": 2, "role": "assistant", "content": "  ", "ui": {}}], stand)
    assert leer[0]["ui"]["ablauf"] == stand and "ablauf" not in leer[1]["ui"]


def test_feste_texte_des_ablaufs_tragen_den_merker(umgebung):  # noqa: F811 — Fixture
    roh = _ablauf(_WARTET).model_dump(exclude_none=True)
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                                 action_params={"ablauf": "probe"}),
                                      {"entities": {}}))
    assert antwort.ui.fester_text is True
    unbekannt = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                                   action_params={"ablauf": "weg"}),
                                        {"entities": {}}))
    assert unbekannt.ui.fester_text is True


# ── Abbrechen mit Rückfrage ────────────────────────────────────────────────────────────────────


def _abbrechen(zustand, **params):
    return asyncio.run(abbruch_zug.abbrechen(_S(), _req(action=abbruch_zug.AKTION,
                                                        action_params=params), zustand))


def _wartet_auftrag(umgebung, monkeypatch):  # noqa: F811 — Fixture
    """Ein Lauf, der auf einen Kestra-Auftrag wartet: dort fragt „Abbrechen“ erst nach."""
    from boerdi.services.auftraege import ablage

    async def kein_auftrag(*_a, **_k):
        return None

    monkeypatch.setattr(ablage, "offen", kein_auftrag)
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"]["status"] = "wartet_auftrag"
    zustand["entities"]["_vorgang"]["lauf"]["status"] = "wartet_auftrag"
    return zustand


def test_rueckmeldung_13_11_ein_ablauf_mit_fragen_bricht_sofort_ab(umgebung):  # noqa: F811
    """Rückmeldung 13.11.: der Knopf der Leiste ist schon die Entscheidung der Person. Eine zweite
    Frage ließ den Lauf stehen — der nächste Start fragte dann „neu starten?“. Ohne Auftrag und
    ohne Freigabe geht nichts verloren, was nicht im Arbeitsstand bleibt."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    antwort = _abbrechen(zustand)
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert antwort.content == bot_text("de", "action.ablauf.abgebrochenPerson")
    assert fortschritt.stand(zustand["entities"], "person-a", "de") is None
    assert asyncio.run(zug._aktiver_lauf(_S(), _req(), zustand)) is None


def test_ein_alter_abbruch_knopf_bricht_keinen_neuen_lauf_ab(umgebung):  # noqa: F811
    """Ein Knopf „Ablauf abbrechen“ aus einer früheren Rückfrage trägt die Marke seines Laufs —
    für einen anderen Lauf fragt er erst."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    antwort = _abbrechen(zustand, bestaetigt=True, marke="alt")
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_wahl"
    aktionen = [q.split("|", 3)[2] for q in antwort.quick_replies]
    assert aktionen[0] == abbruch_zug.AKTION
    # zweites Review AS-U, Befund 1: die Rückfrage bietet die Knöpfe des wartenden Schritts wieder
    # an — hier mit dem echten ``_zurueck`` (kein Ersatz)
    assert "ablauf_wahl" in aktionen[1:]


def test_eine_veraltete_leiste_bricht_keinen_anderen_lauf_ab(umgebung):  # noqa: F811
    """Review 13.11.: die Leiste schickt die Marke ihres Laufs (``ui.ablauf.lauf``) — zeigt sie
    einen anderen Lauf (zweiter Tab), fragt der Zug erst; passt sie, bricht er sofort ab."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    antwort = _abbrechen(zustand, lauf="anderer")
    assert v.akte["lauf"]["status"] == "wartet_wahl" and antwort.quick_replies
    _abbrechen(zustand, lauf=v.akte["lauf"]["start"])
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"


def test_die_richtige_marke_ohne_bestaetigung_bricht_an_einer_frage_ab(umgebung):  # noqa: F811
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    _abbrechen(zustand, marke=zug.lauf_marke(v, v.akte["lauf"]))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"


def test_am_ki_schritt_bricht_die_leiste_sofort_ab(umgebung):  # noqa: F811
    roh = _ablauf([{"id": "k", "typ": "agent", "text": {"de": "Los."},
                    "agent": {"werkzeuge": ["search_wlo_all"]}}, _ENDE])
    zustand = _gestartet(umgebung, roh.model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_ki"
    antwort = _abbrechen(zustand)
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert antwort.content == bot_text("de", "action.ablauf.abgebrochenPerson")


def test_abbrechen_fragt_erst_und_bricht_dann_ab(umgebung, monkeypatch):  # noqa: F811
    zustand = _wartet_auftrag(umgebung, monkeypatch)
    frage = _abbrechen(zustand)
    knopf = frage.quick_replies[0]          # danach der Weg zurück (zweites Review AS-U, 1)
    teile = knopf.split("|", 3)
    assert teile[2] == abbruch_zug.AKTION
    params = json.loads(teile[3])
    assert params["bestaetigt"] is True and params["marke"]
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_auftrag"
    _abbrechen(zustand, **params)
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert fortschritt.stand(zustand["entities"], "person-a", "de") is None


def test_eine_alte_bestaetigung_fragt_neu(umgebung, monkeypatch):  # noqa: F811 — Fixture
    zustand = _wartet_auftrag(umgebung, monkeypatch)
    antwort = _abbrechen(zustand, bestaetigt=True, marke="alt")
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_auftrag"
    assert antwort.quick_replies          # neue Rückfrage


def test_ohne_lauf_nichts_abzubrechen(umgebung):  # noqa: F811 — Fixture
    antwort = _abbrechen({"entities": {}})
    assert antwort.content and not antwort.quick_replies


def test_die_aktion_ist_als_direktaktion_erlaubt():
    from boerdi.graph.nodes import preflight, preflight_ablauf

    assert abbruch_zug.AKTION in preflight._DIRECT_ACTIONS
    assert abbruch_zug.AKTION in preflight_ablauf._IM_GESPERRTEN_LAUF


# ── Review AS-Ua ───────────────────────────────────────────────────────────────────────────────


def test_ein_text_mit_teil_platzhalter_ist_kein_fester_text(umgebung):  # noqa: F811 — Fixture
    """Befund 2 (schwer): ``{teil.…}`` kann KI-Ausgabe einsetzen — dann bleibt das Etikett."""
    schritte = [{"id": "frage", "typ": "nachricht", "text": {"de": "Stand: {teil.notiz}"},
                 "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]}, _ENDE]
    roh = _ablauf(schritte).model_dump(exclude_none=True)
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                                 action_params={"ablauf": "probe"}),
                                      {"entities": {}}))
    assert antwort.ui.fester_text is False


def test_startdaten_der_ki_im_text_sind_kein_fester_text(umgebung):  # noqa: F811 — Fixture
    felder = [{"name": "thema", "typ": "text", "beschreibung": {"de": "Thema"}}]
    schritte = [{"id": "frage", "typ": "nachricht", "text": {"de": "Thema: {start.thema}"},
                 "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]}, _ENDE]
    roh = _ablauf(schritte, start=felder, ausloeser=[{"art": "agent"}, {"art": "extern"}]
                  ).model_dump(exclude_none=True)
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}

    def starten(quelle):
        return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={
            "ablauf": "probe", "start": {"thema": "Optik"}, **quelle}), {"entities": {}}))

    assert starten({"start_quelle": "ki"}).ui.fester_text is False
    assert starten({"quelle": "gastseite"}).ui.fester_text is True


def test_ein_abbruch_am_freigabe_schritt_beendet_den_plan(umgebung, monkeypatch):  # noqa: F811
    """Befund 1 (schwer): wie „Ablauf abbrechen“ am Freigabe-Schritt — ein angelaufener Plan wird
    nicht fortgesetzt, und die Antwort sagt, dass schon geschrieben wurde. Ob ein Plan offen ist,
    prüft ``freigabe_zug.plan_offen`` (getestet in Paket S) — hier die Verdrahtung."""
    from boerdi.services import plan_fortsetzen
    from boerdi.services.ablauf import freigabe_zug

    gefragt: list = []
    monkeypatch.setattr(freigabe_zug, "plan_offen",
                        lambda entities, **k: gefragt.append(k.get("marke")) or True)

    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"].update({"status": "wartet_freigabe", "freigabe_id": "f1",
                           "plan_angelaufen": True})
    zustand["entities"]["_vorgang"]["lauf"]["status"] = "wartet_freigabe"
    zustand["entities"][plan_fortsetzen.KEY] = {"ablauf": "probe", "id": "f1"}
    frage = _abbrechen(zustand)
    params = json.loads(frage.quick_replies[0].split("|", 3)[3])
    antwort = _abbrechen(zustand, **params)
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    assert plan_fortsetzen.KEY not in zustand["entities"]
    assert gefragt == [{"ablauf": "probe", "id": "f1"}]
    from boerdi.i18n.bot_text import bot_text

    assert antwort.content == bot_text("de", "action.ablauf.freigabeAbgebrochenPlan")


def test_ohne_schluessel_endet_der_auftrag_nur_hier(umgebung, monkeypatch):  # noqa: F811
    """Befund 6: ohne den Schlüssel der Person läuft der Auftrag bei der b-api weiter — das sagt
    die Antwort, wie beim Abbruch am Auftragsschritt."""
    from boerdi.i18n.bot_text import bot_text
    from boerdi.services.ablauf import abbruch_zug as modul
    from boerdi.services.auftraege import ablage

    async def kein_auftrag(*_a, **_k):
        return None

    monkeypatch.setattr(ablage, "offen", kein_auftrag)
    monkeypatch.setattr(modul, "hat_zug_schluessel", lambda: False)
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    [v] = umgebung.speicher.v.values()
    v.akte["lauf"]["status"] = "wartet_auftrag"
    zustand["entities"]["_vorgang"]["lauf"]["status"] = "wartet_auftrag"
    params = json.loads(_abbrechen(zustand).quick_replies[0].split("|", 3)[3])
    antwort = _abbrechen(zustand, **params)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNurHierAbgebrochen")


def _fan(n: int, breite: int):
    """Ein Ablauf aus ``n`` Schritten, jeder mit Schnellantworten auf die folgenden."""
    schritte = []
    for i in range(n):
        ziele = [f"s{j}" for j in range(i + 1, min(n, i + 1 + breite))] or ["e"]
        schritte.append({"id": f"s{i}", "typ": "nachricht", "text": {"de": "?"},
                         "optionen": [{"id": f"o{k}", "label": {"de": "x"}, "ziel": z}
                                      for k, z in enumerate(ziele)]})
    return _ablauf([*schritte, _ENDE])


def test_ein_stark_verzweigter_ablauf_zaehlt_noch_sinnvoll():
    """Befund 3: eigenes Budget je Suche, ``bis`` nur über Schritte, die das Ziel erreichen —
    „Schritt 6 von 6“ bei 33 folgenden Schritten war falsch."""
    nr, von = fortschritt.position(_fan(40, 8), "s5")
    assert nr == 6 and von >= 30


def test_die_position_wird_zwischengespeichert():
    """Befund 4: je Fassung unveränderlich — die zweite Abfrage rechnet nicht noch einmal."""
    a = _fan(30, 6)
    fortschritt.position(a, "s3")
    vorher = fortschritt.zaehler()
    fortschritt.position(a, "s3")
    assert fortschritt.zaehler() == vorher


def test_ein_schritt_nur_hinter_bei_fehler_zaehlt_den_weg_dorthin():
    """Befund 5: der Fehlerzweig liegt hinter den Schritten davor."""
    a = _ablauf([
        _n("a"), {"id": "t", "typ": "werkzeug", "werkzeug": "abdeckung_zaehlen",
                  "argumente": {"entwurf": {"$teil": "draft"}}, "schreibt": "z",
                  "bei_fehler": "nochmal"},
        _ENDE, _n("nochmal"), {"id": "f", "typ": "ende"}])
    assert fortschritt.position(a, "nochmal")[0] == 3


def test_nach_einer_aenderung_der_fassung_kein_stand(umgebung):  # noqa: F811 — Fixture
    """Befund 9: der nächste Zug bricht den Lauf ab — die Leiste zeigt keine falsche Position."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    zustand["entities"]["_vorgang"]["lauf"]["fassung"] = "andere"
    assert fortschritt.stand(zustand["entities"], "person-a", "de") is None


# ── Zweites Review AS-U ────────────────────────────────────────────────────────────────────────


def test_die_rueckfrage_zum_abbruch_hat_einen_weg_zurueck(umgebung, monkeypatch):  # noqa: F811
    """Befund 1: der Klick auf „Abbrechen“ ist eine Direktaktion — sie verwirft die Knöpfe des
    wartenden Schritts. Die Rückfrage bietet sie wieder an. Seit 13.11. fragt der Zug nur noch an
    Auftrag und Freigabe (und bei fremder Marke): hier das Durchreichen, das echte ``_zurueck``
    prüft ``test_ein_alter_abbruch_knopf_bricht_keinen_neuen_lauf_ab``."""
    zurueck = "__action__|Stand prüfen|ablauf_auftrag|{}"
    monkeypatch.setattr(abbruch_zug, "_zurueck", lambda *a: [zurueck])
    zustand = _wartet_auftrag(umgebung, monkeypatch)
    frage = _abbrechen(zustand)
    assert frage.quick_replies[0].split("|", 3)[2] == abbruch_zug.AKTION
    assert frage.quick_replies[1:] == [zurueck]


def test_die_rueckfrage_trennt_abbrechen_und_weitermachen(umgebung, monkeypatch):  # noqa: F811
    """Browser-Abnahme AS-U, L-2: neben „Ja, abbrechen“ stand der Chip des Schritts („Ja,
    weiter“) — ohne Satz dazu las er sich wie eine zweite Bestätigung. Der Knopf heißt jetzt
    „Ablauf abbrechen“, und die Frage nennt den Weg zurück."""
    monkeypatch.setattr(abbruch_zug, "_zurueck", lambda *a: ["__action__|Stand prüfen|x|{}"])
    zustand = _wartet_auftrag(umgebung, monkeypatch)
    frage = _abbrechen(zustand)
    assert frage.quick_replies[0].split("|", 3)[1] == "Ablauf abbrechen"
    assert frage.content == bot_text("de", "action.ablauf.abbrechenFrageZurueck")
    assert "weitermachen" in frage.content


def test_ohne_weg_zurueck_bleibt_die_kurze_rueckfrage(umgebung, monkeypatch):  # noqa: F811
    zustand = _wartet_auftrag(umgebung, monkeypatch)
    monkeypatch.setattr(abbruch_zug, "_zurueck", lambda *a: [])
    frage = _abbrechen(zustand)
    assert frage.content == bot_text("de", "action.ablauf.abbrechenFrage")
    assert len(frage.quick_replies) == 1


def test_ein_neuer_lauf_desselben_ablaufs_hat_eine_neue_laufmarke(umgebung):  # noqa: F811
    """Befund 2: „Neu starten“ desselben Ablaufs — das Widget erkennt den neuen Lauf an der
    Marke."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    erste = fortschritt.stand(zustand["entities"], "person-a", "de")["lauf"]
    [v] = umgebung.speicher.v.values()
    params = json.loads(_abbrechen(zustand).quick_replies[0].split("|", 3)[3])
    _abbrechen(zustand, **params)
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "probe"}),
                            zustand))
    zweite = fortschritt.stand(zustand["entities"], "person-a", "de")["lauf"]
    assert erste and zweite and erste != zweite


def test_startdaten_ohne_herkunft_sind_kein_fester_text(umgebung):  # noqa: F811 — Fixture
    """Kleinigkeit 7: nur Daten der Gastseite gelten als fest."""
    felder = [{"name": "thema", "typ": "text", "beschreibung": {"de": "Thema"}}]
    schritte = [{"id": "frage", "typ": "nachricht", "text": {"de": "Thema: {start.thema}"},
                 "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]}, _ENDE]
    roh = _ablauf(schritte, start=felder, ausloeser=[{"art": "extern"}]
                  ).model_dump(exclude_none=True)
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={
        "ablauf": "probe", "start": {"thema": "Optik"}}), {"entities": {}}))
    assert antwort.ui.fester_text is False


def test_eine_abgeschnittene_kennung_bleibt_nicht_stehen(umgebung):  # noqa: F811 — Fixture
    """Kleinigkeit 11: der Kurztext ist auf 120 Zeichen gekürzt — auch ein UUID-Bruchstück am Ende
    fällt weg."""
    zustand = _gestartet(umgebung, _ablauf(_WARTET).model_dump(exclude_none=True))
    zustand["entities"]["_vorgang"]["teile"] = {"draft": {"v": 1, "z": "Ordner 0a1b2c3d-0000-40"}}
    [teil] = fortschritt.stand(zustand["entities"], "person-a", "de")["teile"]
    assert teil["text"] == "Ordner …"


def test_der_verlauf_traegt_den_stand_an_allen_antworten_nach_der_frage():
    """Befund 5: nach einem Strom-Abbruch nimmt das Widget die erste Antwort nach der Frage — eine
    Einlösung speichert zwei; beide tragen den Stand."""
    stand = {"id": "probe", "titel": "Probe", "nr": 1, "von": 2, "status": "laeuft", "teile": []}
    verlauf = publikum.mit_ablauf_stand([
        {"id": 1, "role": "assistant", "content": "alt", "ui": {}},
        {"id": 2, "role": "user", "content": "ja", "ui": {}},
        {"id": 3, "role": "assistant", "content": "Gespeichert.", "ui": {}},
        {"id": 4, "role": "assistant", "content": "Weiter?", "ui": {}},
    ], stand)
    assert "ablauf" not in verlauf[0]["ui"]
    assert verlauf[2]["ui"]["ablauf"] == stand and verlauf[3]["ui"]["ablauf"] == stand
