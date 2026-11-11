"""Paket AS-5a (Plan 2026-11-09 §5g, D1): Abläufe als Werkzeuge der KI im Agent-Modus.

- Je aktivem Ablauf mit Auslöser ``agent`` ein Werkzeug ``ablauf-<id>`` (A5-1, A5-2); seine
  Parameter sind das Startschema (Typen, Pflicht, Länge, Muster, Beschreibung in der Sprache).
- Ein Aufruf startet nichts: die Schleife prüft die Daten (``startdaten.pruefen``) und merkt sich
  den Vorschlag; die Zusammenstellung macht daraus einen Knopf mit ``start`` und
  ``start_quelle: "ki"`` (A5-3).
- ``zug.starten`` nimmt Daten auch bei ``agent`` — aber KI-Daten tragen nie die Rechte der
  Gastseite (Entscheid AS-4a Befund 10, Querschnitts-Review RB Befund 1).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import ausloeser, simulation, startdaten, vorschlag, zug
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)
from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call

_UUID = "0a1b2c3d-0000-4000-8000-000000000001"
_FELDER = [
    {"name": "sammlung", "typ": "nodeid", "pflicht": True,
     "beschreibung": {"de": "Die Sammlung", "en": "The collection"}},
    {"name": "thema", "typ": "text", "max_zeichen": 40, "beschreibung": {"de": "Das Thema"}},
    {"name": "stufe", "typ": "zahl", "beschreibung": {"de": "Klassenstufe"}},
    {"name": "neu", "typ": "ja_nein", "beschreibung": {"de": "Neu anlegen?"}},
]
_SCHRITTE = [{"id": "a", "typ": "nachricht", "text": {"de": "Los: {start.thema}."},
              "optionen": [{"id": "ja", "label": {"de": "Ja"}, "ziel": "e"}]},
             {"id": "e", "typ": "ende"}]


def _roh(id_, start=None, art="agent", **mehr):
    return {"id": id_, "titel": {"de": f"Titel {id_}", "en": f"Title {id_}"}, "aktiv": True,
            "wann": [f"wenn {id_}"], "nicht_wann": [f"nicht {id_}"], "schritte": _SCHRITTE,
            "ausloeser": [{"art": art}], **({"start": start} if start is not None else {}), **mehr}


@pytest.fixture
def katalog(monkeypatch):
    eintraege: list = []
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: eintraege)
    return eintraege


# ── Werkzeuge ──────────────────────────────────────────────────────────────────────────────────


def test_je_ablauf_ein_werkzeug_mit_dem_startschema(katalog):
    katalog += [_roh("baum", start=_FELDER), _roh("knopf", art="knopf")]
    [w] = vorschlag.werkzeuge("de")
    f = w["function"]
    assert f["name"] == "ablauf-baum" and vorschlag.ist_ablauf_werkzeug(f["name"])
    assert vorschlag.kennung(f["name"]) == "baum"
    assert "Titel baum" in f["description"] and "wenn baum" in f["description"]
    assert "nicht baum" in f["description"]
    p = f["parameters"]
    assert p["type"] == "object" and p["additionalProperties"] is False
    assert p["required"] == ["sammlung"]
    assert p["properties"]["sammlung"]["type"] == "string"
    assert "pattern" in p["properties"]["sammlung"]
    assert p["properties"]["thema"] == {"type": "string", "maxLength": 40,
                                        "description": "Das Thema"}
    assert p["properties"]["stufe"]["type"] == "number"
    assert p["properties"]["neu"]["type"] == "boolean"


def test_die_beschreibung_folgt_der_sprache_mit_rueckfall(katalog):
    katalog.append(_roh("baum", start=_FELDER))
    p = vorschlag.werkzeuge("en")[0]["function"]["parameters"]["properties"]
    assert p["sammlung"]["description"] == "The collection"
    assert p["thema"]["description"] == "Das Thema"      # Rückfall auf de


def test_ohne_startschema_ein_werkzeug_ohne_parameter(katalog):
    katalog.append(_roh("baum"))
    p = vorschlag.werkzeuge("de")[0]["function"]["parameters"]
    assert p == {"type": "object", "properties": {}, "additionalProperties": False}


def test_hoechstens_sechs_werkzeuge_und_kurze_beschreibungen(katalog):
    katalog += [_roh(f"a{i}", wann=["x" * 100] * 5, nicht_wann=["y" * 100] * 5) for i in range(9)]
    werkzeuge = vorschlag.werkzeuge("de")
    assert len(werkzeuge) == vorschlag.MAX_WERKZEUGE == 6
    assert all(len(w["function"]["description"]) <= vorschlag._BESCHREIBUNG_ZEICHEN
               for w in werkzeuge)  # seit Querschnitts-Review TW: 800


def test_pflichtfelder_hindern_den_vorschlag_nicht_mehr(katalog):
    """Die KI bringt Daten (A5-4) — ein Ablauf mit Pflichtfeldern ist vorschlagbar."""
    katalog.append(_roh("baum", start=_FELDER))
    assert [a.id for a in ausloeser.vorschlaege()] == ["baum"]


def test_ohne_vorschlagbaren_ablauf_keine_werkzeuge(katalog):
    katalog.append(_roh("knopf", art="knopf"))
    assert vorschlag.werkzeuge("de") == []


# ── Schleife ───────────────────────────────────────────────────────────────────────────────────


def test_die_schleife_merkt_den_vorschlag_samt_daten(monkeypatch, katalog):
    katalog.append(_roh("baum", start=_FELDER))
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", {"sammlung": _UUID, "thema": "  Optik "})]),
        _resp_text("Du kannst den Ablauf mit dem Knopf starten."),
    ], tools=vorschlag.werkzeuge("de"))
    assert run.ablauf_vorschlaege == [{"ablauf": "baum",
                                       "start": {"sammlung": _UUID, "thema": "Optik"}}]
    assert run.tools_called == [] and "Knopf" in msgs[2]["content"]


def test_ungueltige_daten_ergeben_keinen_vorschlag(monkeypatch, katalog):
    katalog.append(_roh("baum", start=_FELDER))
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", {"sammlung": "keine-uuid"})]),
        _resp_text("ok"),
    ], tools=vorschlag.werkzeuge("de"))
    assert run.ablauf_vorschlaege == []
    assert "Knopf" not in msgs[2]["content"]


def test_hoechstens_ein_vorschlag_je_zug(monkeypatch, katalog):
    katalog += [_roh("baum"), _roh("ast")]
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", {}), _tool_call("ablauf-ast", {}, "c2")]),
        _resp_text("ok"),
    ], tools=vorschlag.werkzeuge("de"))
    assert run.ablauf_vorschlaege == [{"ablauf": "baum"}]


def test_zu_lange_daten_ergeben_keinen_knopf(katalog):
    lang = [{"name": f"t{i}", "typ": "text", "max_zeichen": 500, "beschreibung": {"de": "x"}}
            for i in range(6)]
    katalog.append(_roh("baum", start=lang))
    gemerkt: list = []
    antwort = vorschlag.merken(gemerkt, "ablauf-baum", {f"t{i}": "a" * 500 for i in range(6)})
    assert gemerkt == [] and antwort == vorschlag.ZU_LANG


# ── Knopf ──────────────────────────────────────────────────────────────────────────────────────


def test_der_knopf_traegt_daten_und_die_herkunft_ki(katalog):
    katalog += [_roh("baum", start=_FELDER), _roh("ast")]
    qrs = vorschlag.schnellantworten(
        [{"ablauf": "baum", "start": {"sammlung": _UUID}}, {"ablauf": "ast"}, {"ablauf": "weg"}],
        "de")
    params = [json.loads(q.split("|", 3)[3]) for q in qrs]
    # Querschnitts-Review AS-5, Befund 1: jeder KI-Knopf trägt die Marke — auch ohne Angaben
    assert params == [{"ablauf": "baum", "start": {"sammlung": _UUID},
                       "start_quelle": startdaten.QUELLE_KI},
                      {"ablauf": "ast", "start_quelle": startdaten.QUELLE_KI}]


# ── Zug: Daten der KI ohne die Rechte der Gastseite ────────────────────────────────────────────


def _knopf_start(umgebung, roh, params):  # noqa: F811 — Fixture
    umgebung.katalog["wert"] = {"ablaeufe": [AblaufArea.model_validate(roh).model_dump(
        exclude_none=True)]}
    anfrage = _req(action=zug.AKTION, action_params={"ablauf": roh["id"], **params})
    return asyncio.run(zug.starten(_S(), anfrage, {"entities": {}}))


def test_der_knopf_der_ki_startet_mit_ihren_daten_ohne_rechte(umgebung):  # noqa: F811 — Fixture
    antwort = _knopf_start(umgebung, _roh("baum", start=_FELDER),
                           {"start": {"sammlung": _UUID, "thema": "Optik"},
                            "start_quelle": startdaten.QUELLE_KI})
    assert "Los: Optik." in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["start_quelle"] == startdaten.QUELLE_KI
    assert v.akte["lauf"]["start_quelle"] != startdaten.QUELLE_GASTSEITE


def test_ein_blosser_knopf_ablauf_nimmt_keine_daten(umgebung):  # noqa: F811 — Fixture
    antwort = _knopf_start(umgebung, _roh("baum", art="knopf"),
                           {"start": {"x": 1}, "start_quelle": startdaten.QUELLE_KI})
    assert umgebung.speicher.v == {}
    assert antwort.content


def test_eine_fremde_herkunft_wird_nicht_uebernommen(umgebung):  # noqa: F811 — Fixture
    _knopf_start(umgebung, _roh("baum", start=_FELDER),
                 {"start": {"sammlung": _UUID}, "start_quelle": "admin"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") is None


# ── Prüfung und Simulation ─────────────────────────────────────────────────────────────────────


def test_bei_ausloeser_agent_braucht_jedes_feld_eine_beschreibung():
    felder = [{"name": "sammlung", "typ": "nodeid", "pflicht": True}]
    befunde = pruefe(AblaufArea.model_validate(_roh("baum", start=felder)))
    assert any("Beschreibung" in b and "sammlung" in b for b in befunde), befunde
    assert pruefe(AblaufArea.model_validate(_roh("baum", start=_FELDER))) == []


def test_pflichtfelder_sind_bei_agent_kein_befund_mehr():
    befunde = pruefe(AblaufArea.model_validate(_roh("baum", start=_FELDER)))
    assert befunde == []


def _sim(roh, test):
    return asyncio.run(simulation.testen(AblaufArea.model_validate(roh),
                                         AblaufTest.model_validate(test)))


def test_die_simulation_kennt_die_herkunft_ki():
    """Querschnitts-Review RB, Befund 2: ein KI-Start läuft in der Simulation ohne die Rechte."""
    roh = _roh("baum", start=_FELDER, schritte=[
        {"id": "lesen", "typ": "werkzeug", "werkzeug": "get_collection_contents",
         "argumente": {"nodeId": {"$teil": "start", "pfad": "sammlung"}}, "schreibt": "inhalte",
         "bei_fehler": "fehler"},
        {"id": "e", "typ": "ende"}, {"id": "fehler", "typ": "ende"}],
        ausloeser=[{"art": "agent"}, {"art": "extern"}])
    gast = _sim(roh, {"name": "g", "start": {"sammlung": _UUID}, "werkzeuge": {"lesen": "x"},
                      "erwartet": {"weg": ["lesen", "e"]}})
    assert gast.ok, gast.abweichungen
    ki = _sim(roh, {"name": "k", "start": {"sammlung": _UUID}, "quelle": "ki",
                    "werkzeuge": {"lesen": "x"}, "erwartet": {"weg": ["lesen", "fehler"]}})
    assert ki.ok, ki.abweichungen


def test_die_simulation_nimmt_ki_daten_auch_ohne_gastseite():
    ergebnis = _sim(_roh("baum", start=_FELDER),
                    {"name": "k", "start": {"sammlung": _UUID, "thema": "Optik"}, "quelle": "ki",
                     "erwartet": {"weg": ["a"]}})
    assert ergebnis.ok, ergebnis.abweichungen
    gast = _sim(_roh("baum", start=_FELDER), {"name": "g", "start": {"sammlung": _UUID}})
    assert not gast.ok      # Gastseite ohne den Auslöser extern bleibt eine Abweichung


# ── Review AS-5a ───────────────────────────────────────────────────────────────────────────────


def test_ohne_ausloeser_gastseite_gibt_es_keine_herkunft_gastseite(umgebung):  # noqa: F811
    """Befund 1: ein Ablauf nur mit ``agent`` nimmt Daten — aber ``quelle: gastseite`` gibt ihm
    nie die Rechte der Gastseite (die gibt es nur mit dem Auslöser ``extern``)."""
    _knopf_start(umgebung, _roh("baum", start=_FELDER),
                 {"start": {"sammlung": _UUID}, "quelle": "gastseite"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") != startdaten.QUELLE_GASTSEITE


def test_nach_der_antwort_kein_vorschlag_mit_daten(monkeypatch, katalog):
    """Befund 2 (A5-8): der Satz über dem Knopf muss nach der Quittung entstehen — nach
    ``respond_to_user`` gibt es keinen Vorschlag mit Angaben mehr."""
    from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER, antwort_werkzeug

    katalog.append(_roh("baum", start=_FELDER))
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(RESPOND_TO_USER, {"text": "Hier ist der Knopf."}),
                     _tool_call("ablauf-baum", {"sammlung": _UUID}, "c2")]),
    ], tools=[*vorschlag.werkzeuge("de"), antwort_werkzeug(2, 500)])
    assert run.ablauf_vorschlaege == []


def test_ein_fremdwerkzeug_mit_dem_praefix_ist_kein_ablauf_werkzeug():
    """Befund 3: ein Fremdserver namens ``ablauf-x`` ergäbe ``ablauf-x__suche``."""
    assert vorschlag.ist_ablauf_werkzeug("ablauf-baum")
    assert not vorschlag.ist_ablauf_werkzeug("ablauf-x__suche")
    assert not vorschlag.ist_ablauf_werkzeug("ablauf-Baum")
    assert not vorschlag.ist_ablauf_werkzeug("ablauf-")


def test_die_beschreibung_behaelt_den_schlusssatz(katalog):
    """Befund 4: gekürzt werden ``wann``/``nicht_wann``, nie der feste Satz."""
    katalog.append(_roh("baum", wann=["w" * 200] * 5, nicht_wann=["n" * 200] * 5))
    text = vorschlag.werkzeuge("de")[0]["function"]["description"]
    assert len(text) <= vorschlag._BESCHREIBUNG_ZEICHEN
    assert "startet nichts" in text and "Titel baum" in text


def test_dieselben_falschen_angaben_zweimal_sind_stillstand(monkeypatch, katalog):
    """Befund 5: wie beim Ergebnis — der zweite gleiche Fehlversuch beendet die Schleife."""
    katalog.append(_roh("baum", start=_FELDER))
    falsch = {"sammlung": "keine-uuid"}
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", falsch)]),
        _resp_tools([_tool_call("ablauf-baum", falsch, "c2")]),
        _resp_text("nie erreicht"),
    ], tools=vorschlag.werkzeuge("de"))
    assert run.stop_reason == "no_progress" and run.ablauf_vorschlaege == []


def test_mehr_als_sechs_ki_ablaeufe_sind_ein_hinweis():
    """Befund 8: ab dem siebten aktiven ``agent``-Ablauf bietet der Zug nicht mehr alle an."""
    from boerdi.services.ablauf.pruefung import agent_warnungen

    andere = [AblaufArea.model_validate(_roh(f"a{i}")) for i in range(7)]
    eigener = AblaufArea.model_validate(_roh("baum"))
    assert any("6" in w for w in agent_warnungen(eigener, andere))
    assert agent_warnungen(eigener, andere[:3]) == []


# ── Querschnitts-Review AS-5 ───────────────────────────────────────────────────────────────────


def test_ein_ki_knopf_ersetzt_keinen_laufenden_lauf_still(umgebung):  # noqa: F811 — Fixture
    """Befund 1 (schwer): wie bei der Gastseite fragt der Zug, bevor er einen laufenden Lauf
    (samt Auftrag) beendet — der Knopf „Neu starten“ behält die Herkunft ``ki``."""
    alt = AblaufArea.model_validate(_roh("alt"))
    neu = AblaufArea.model_validate(_roh("neu", start=_FELDER))
    umgebung.katalog["wert"] = {"ablaeufe": [a.model_dump(exclude_none=True) for a in (alt, neu)]}
    zustand = {"entities": {}}
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "alt"}),
                            zustand))
    [v] = umgebung.speicher.v.values()
    lauf_vorher = dict(v.akte["lauf"])
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={
        "ablauf": "neu", "start": {"sammlung": _UUID}, "start_quelle": "ki"}), zustand))
    assert [x.akte["lauf"] for x in umgebung.speicher.v.values()] == [lauf_vorher]
    [knopf] = [q for q in antwort.quick_replies if "|ablauf_starten|" in q]
    params = json.loads(knopf.split("|", 3)[3])
    assert params["ersetzt"] and params["start_quelle"] == startdaten.QUELLE_KI
    asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params=params), zustand))
    laeufe = [x.akte["lauf"] for x in umgebung.speicher.v.values() if x.akte.get("lauf")]
    assert any(lauf["ablauf"] == "neu" and lauf.get("start_quelle") == "ki" for lauf in laeufe)


def test_die_marke_gastseite_gilt_nur_am_knopf_neu_starten(umgebung):  # noqa: F811 — Fixture
    """Befund 9: ``start_quelle: gastseite`` ohne ``ersetzt`` gibt keine Rechte."""
    _knopf_start(umgebung, _roh("baum", start=_FELDER, ausloeser=[{"art": "extern"}]),
                 {"start": {"sammlung": _UUID}, "start_quelle": "gastseite"})
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"].get("start_quelle") != startdaten.QUELLE_GASTSEITE


def test_die_antwort_vor_oder_nach_dem_vorschlag_gilt_gleich(monkeypatch, katalog):
    """Befund 4 (A5-8): auch in der Reihenfolge [Vorschlag, Antwort] kein Vorschlag mit Angaben."""
    from boerdi.domain.antwort_werkzeug import RESPOND_TO_USER, antwort_werkzeug

    katalog.append(_roh("baum", start=_FELDER))
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", {"sammlung": _UUID}),
                     _tool_call(RESPOND_TO_USER, {"text": "Hier."}, "c2")]),
    ], tools=[*vorschlag.werkzeuge("de"), antwort_werkzeug(2, 500)])
    assert run.ablauf_vorschlaege == []


def test_neben_einer_frage_kein_vorschlag(monkeypatch, katalog):
    """Befund 10: unter einer Frage gibt es keinen Knopf — auch wenn die Frage danach kommt."""
    katalog.append(_roh("baum"))
    frage = {"frage": "Wie weiter?", "optionen": [{"id": "a", "label": "A"},
                                                  {"id": "b", "label": "B"}]}
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("ablauf-baum", {}), _tool_call("ui_entscheidung", frage, "c2")]),
        _resp_text("ok"),
    ], tools=[*vorschlag.werkzeuge("de"), "ui_entscheidung"])
    assert run.ablauf_vorschlaege == []


def test_eine_lesende_einbettung_bekommt_keine_schreibenden_ablaeufe(katalog):
    """Befund 6 (Entscheid): ``tool_mode`` ohne „full“ — kein Ablauf mit schreibenden Schritten
    oder Aufträgen als Werkzeug der KI."""
    schreibt = [{"id": "w", "typ": "werkzeug", "werkzeug": "wlo_create_collection_tree",
                 "argumente": {}, "freigabe": {"de": "Anlegen?"}, "schreibt": "x",
                 "bei_fehler": "e"}, {"id": "e", "typ": "ende"}]
    katalog += [_roh("baum", schritte=schreibt), _roh("ast")]
    assert [w["function"]["name"] for w in vorschlag.werkzeuge("de", tool_mode="read-only")] == [
        "ablauf-ast"]
    assert len(vorschlag.werkzeuge("de", tool_mode="full")) == 2
    assert len(vorschlag.werkzeuge("de")) == 2


def test_erst_filtern_dann_kuerzen(katalog):
    """Review AS-5b, Befund 1 (schwer): ein genannter Ablauf auf Platz 7 wird angeboten."""
    katalog += [_roh(f"a{i}") for i in range(7)]
    assert [w["function"]["name"] for w in vorschlag.werkzeuge("de", nur={"ablauf-a6"})] == [
        "ablauf-a6"]


# ── Zweites Review AS-5 ────────────────────────────────────────────────────────────────────────


def test_derselbe_ki_start_laeuft_schon(umgebung):  # noqa: F811 — Fixture
    """Befund 4: derselbe Ablauf mit denselben Angaben — kein Neustart, „läuft schon“."""
    roh = _roh("baum", start=_FELDER)
    umgebung.katalog["wert"] = {"ablaeufe": [AblaufArea.model_validate(roh).model_dump(
        exclude_none=True)]}
    zustand: dict = {"entities": {}}
    anfrage = _req(action=zug.AKTION, action_params={
        "ablauf": "baum", "start": {"sammlung": _UUID}, "start_quelle": "ki"})
    asyncio.run(zug.starten(_S(), anfrage, zustand))
    [v] = umgebung.speicher.v.values()
    vorher = dict(v.akte["lauf"])
    antwort = asyncio.run(zug.starten(_S(), anfrage, zustand))
    assert "läuft" in antwort.content
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"] == vorher


def test_ein_ki_knopf_ohne_angaben_fragt_auch(umgebung, monkeypatch):  # noqa: F811 — Fixture
    """Befund 4: ohne Angaben gegen einen wartenden Auftrag — Rückfrage samt „Stand prüfen“,
    kein Abbruch des Auftrags."""
    from boerdi.services.ablauf import zug_basis
    from tests.test_ablauf_startdaten import _lauf_auf_auftrag

    abgebrochen: list = []
    monkeypatch.setattr(zug_basis, "bei_der_b_api_abbrechen", lambda job: abgebrochen.append(job))
    _gast, v = _lauf_auf_auftrag(umgebung)
    roh = _roh("neu")
    umgebung.katalog["wert"]["ablaeufe"].append(
        AblaufArea.model_validate(roh).model_dump(exclude_none=True))
    antwort = asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={
        "ablauf": "neu", "start_quelle": "ki"}), umgebung.state))
    [v2] = umgebung.speicher.v.values()
    assert v2.akte["lauf"]["status"] == "wartet_auftrag"
    assert [j for j in abgebrochen if j] == []
    aktionen = [q.split("|", 3)[2] for q in antwort.quick_replies]
    assert aktionen == ["ablauf_starten", "ablauf_auftrag_pruefen"]


@pytest.mark.parametrize("modus, schreibende", [
    ("read-only", False), ("READ-ONLY", False), (" read-only ", False), ("curate", False),
    ("full", True), ("FULL", True), (None, True), ("", True), ("unbekannt", True)])
def test_die_erlaubnis_der_einbettung_wie_beim_mcp(katalog, modus, schreibende):
    """Befund 1: derselbe Modus wie ``host_capabilities.erlaubt`` — normalisiert; ein unbekannter
    Wert gilt wie dort als voll."""
    schreibt = [{"id": "a", "typ": "auftrag", "flow": "wlo/x", "argumente": {}, "schreibt": "t",
                 "bei_fehler": "e"}, {"id": "e", "typ": "ende"}]
    katalog += [_roh("baum", schritte=schreibt), _roh("ast")]
    namen = [w["function"]["name"] for w in vorschlag.werkzeuge("de", tool_mode=modus)]
    assert ("ablauf-baum" in namen) is schreibende and "ablauf-ast" in namen


def test_die_beschreibung_sagt_wie_angaben_ankommen(katalog):
    """Befund 3: neben der Antwort ginge ein Vorschlag mit Angaben verloren — das Modell erfährt
    es aus der Beschreibung, nicht erst aus einer Abweisung, die es nie liest."""
    katalog.append(_roh("baum", start=_FELDER))
    text = vorschlag.werkzeuge("de")[0]["function"]["description"]
    assert "allein" in text and "Quittung" in text
