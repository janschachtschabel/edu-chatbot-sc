"""Paket N4 (Plan 2026-11-19): die Freigabe-Box vor dem Start eines schreibenden Auftrags.

Vorschau → Box → „Freigeben“ → Start; Abbrechen; abgelaufener Schlüssel; Stapel über 50 (hier:
über ``hoechstens``); Doppelklick; andere Person; ohne Anmeldung keine Box; Probleme des MCP.
Der Zug läuft wie in ``test_paket_k_zug`` (Fixture ``ueber_mcp``: echter Starter, MCP-Drahtform).
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from boerdi.i18n import bot_text
from boerdi.services.ablauf import auftrag_freigabe, auftrag_freigabe_zug, ausloeser, treiber
from boerdi.services.auftraege import mcp_starter
from boerdi.services.mcp import auth
from tests.test_ablauf_auftrag import (  # noqa: F401
    _SCHRITTE,
    _pruefe,
    _roh,
    _starte,
    freigeschaltet,
    im_zug,
)
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_k_mcp_starter import GESTARTET, JOB, TOKEN, _abgelehnt, _ok
from tests.test_paket_k_zug import KENNUNG, ueber_mcp  # noqa: F401
from tests.test_paket_n4_vorschau import _vorschau

IDS = ["n-1", "n-2", "n-3"]
FREI = "ablauf_auftrag_freigeben"


def _katalog(monkeypatch, *, aufteilen=None, ids=IDS):
    schritt = {**_SCHRITTE[0], "repo_schreibt": True,
               "argumente": {"node_ids": list(ids), "language": "de"}}
    if aufteilen:
        schritt["aufteilen"] = aufteilen
    katalog = [_roh(schritte=[schritt, *_SCHRITTE[1:]])]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: katalog)


@pytest.fixture
def n4(ueber_mcp, monkeypatch):  # noqa: F811
    _katalog(monkeypatch)
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = []
    return ueber_mcp


def _antworten(lage, *folge):
    lage.mcp["antworten"]["wlo_start_flow"].extend(folge)


def _box(antwort) -> dict:
    [block] = [b for b in antwort.ui.ui_bloecke if b.modul == "ui_inhaltsrahmen"]
    return block.daten


def _aktion(state, name, daten, ablauf="lesen"):
    anfrage = _req(action=name, action_params={"ablauf": ablauf, "id": daten["freigabe"]["id"]})
    fn = (auftrag_freigabe_zug.freigeben if name == FREI else auftrag_freigabe_zug.verwerfen)
    return asyncio.run(fn(_S(), anfrage, state))


def _lauf(state) -> dict:
    from boerdi.services import arbeitsstand
    return arbeitsstand.verweis(state["entities"], "person-a")["lauf"]


def _bestaetigungen(lage) -> list:
    return [a["confirmToken"] for n, a in lage.mcp["gerufen"]
            if n == "wlo_start_flow" and "confirmToken" in a]


def test_vorschau_box_freigeben_start(n4, caplog):
    _antworten(n4, _vorschau(["n-1 „Bruch“", "n-2 „Quiz“", "n-3 „Test“"]), GESTARTET)
    state: dict = {"entities": {}}
    with caplog.at_level(logging.DEBUG):
        antwort = _starte(state, freigeben=False)
        # nur die Vorschau — nichts gestartet, der Lauf wartet an der Freigabe
        assert _bestaetigungen(n4) == [] and n4.ablage.auftraege == []
        assert _lauf(state)["status"] == treiber.WARTET_FREIGABE
        daten = _box(antwort)
        assert daten["art"] == "schreib_vorschau" and daten["freigabe"]["anzahl"] == 3
        assert [e["titel"] for e in daten["freigabe"]["eintraege"]] == ["Bruch", "Quiz", "Test"]
        assert antwort.quick_replies == []          # die Knöpfe stehen in der Box
        sichtbar = json.dumps(antwort.model_dump(mode="json"), ensure_ascii=False)
        assert TOKEN not in sichtbar and "n-1" not in sichtbar
        assert state["entities"][auftrag_freigabe.KEY]["token"] == TOKEN
        gestartet = _aktion(state, FREI, daten)
    assert _bestaetigungen(n4) == [TOKEN]
    [a] = n4.ablage.auftraege
    assert a.job_id == KENNUNG and _lauf(state)["status"] == treiber.WARTET_AUFTRAG
    assert auftrag_freigabe.KEY not in state["entities"]
    assert "freigabe_args" not in _lauf(state)
    assert TOKEN not in caplog.text and JOB not in caplog.text
    assert JOB not in json.dumps(gestartet.model_dump(mode="json"), ensure_ascii=False)


def test_abbrechen_nimmt_den_ersatzweg_mit_einem_satz(n4):
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    antwort = _aktion(state, "ablauf_auftrag_verwerfen", daten)
    assert antwort.content.startswith(bot_text("de", "action.ablauf.auftragVerworfen"))
    assert "Das Lesen hat nicht geklappt." in antwort.content
    assert _bestaetigungen(n4) == [] and n4.ablage.auftraege == []
    assert auftrag_freigabe.KEY not in state["entities"]


@pytest.mark.parametrize("wie", ["frist", "mcp"])
def test_abgelaufener_schluessel_holt_eine_neue_vorschau(n4, wie):
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    if wie == "frist":
        state["entities"][auftrag_freigabe.KEY]["laeuft_ab"] = 0
    else:
        _antworten(n4, _abgelehnt("confirm_expired", outcome_open=False))
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"], token="ct_neu"))
    antwort = _aktion(state, FREI, daten)
    assert antwort.content.startswith(bot_text("de", "action.ablauf.auftragFreigabeNeu"))
    neu = _box(antwort)
    assert neu["freigabe"]["id"] != daten["freigabe"]["id"]
    assert state["entities"][auftrag_freigabe.KEY]["token"] == "ct_neu"
    assert n4.ablage.auftraege == [] and _lauf(state)["status"] == treiber.WARTET_FREIGABE
    _antworten(n4, GESTARTET)
    _aktion(state, FREI, neu)
    assert _bestaetigungen(n4)[-1] == "ct_neu" and len(n4.ablage.auftraege) == 1


def test_doppelklick_startet_keinen_zweiten_job(n4):
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]), GESTARTET)
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    _aktion(state, FREI, daten)
    zweites = _aktion(state, FREI, daten)
    assert zweites.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")
    assert _bestaetigungen(n4) == [TOKEN] and len(n4.ablage.auftraege) == 1


def test_andere_person_loest_nicht_ein(n4, monkeypatch):
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    monkeypatch.setattr(auftrag_freigabe, "aufrufer_kennung", lambda: "jemand-anderes")
    antwort = _aktion(state, FREI, daten)
    assert antwort.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")
    assert _bestaetigungen(n4) == []
    assert auftrag_freigabe.KEY in state["entities"]           # bleibt für die richtige Person


def test_andere_sitzung_kennt_die_freigabe_nicht(n4):
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“", "n-3 „C“"]))
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    fremd: dict = {"entities": {}}                 # eine andere Sitzung: eigene ``entities``
    antwort = _aktion(fremd, FREI, daten)
    assert antwort.content == bot_text("de", "action.ablauf.freigabeNichtMehrOffen")
    assert _bestaetigungen(n4) == []


def test_ohne_anmeldung_keine_box_und_kein_einloesen(n4, monkeypatch):
    for modul in (auth, mcp_starter):
        monkeypatch.setattr(modul, "has_personal_auth", lambda: False)
    from boerdi.services.ablauf import auftrag_zug
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: False)
    state: dict = {"entities": {}}
    antwort = _starte(state, freigeben=False)
    assert not [b for b in (antwort.ui.ui_bloecke if antwort.ui else [])
                if b.modul == "ui_inhaltsrahmen"]
    assert n4.mcp["gerufen"] == [] and auftrag_freigabe.KEY not in state["entities"]
    antwort = _aktion(state, FREI, {"freigabe": {"id": "x"}})
    assert antwort.content == bot_text("de", "action.ablauf.freigabeOhneAnmeldung")


def test_probleme_des_mcp_gehen_nicht_mit(n4):
    problem = {"nodeId": "n-2", "problem": "not_writable"}
    _antworten(n4, _abgelehnt("bad_inputs", problems=[problem]),
               _vorschau(["n-1 „A“", "n-3 „C“"]), GESTARTET)
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))["freigabe"]
    assert daten["anzahl"] == 2 and [p["grund"] for p in daten["probleme"]] == ["not_writable"]
    assert n4.mcp["gerufen"][1][1]["inputs"]["node_ids"] == ["n-1", "n-3"]
    _aktion(state, FREI, {"freigabe": daten})
    assert [a["inputs"]["node_ids"] for n, a in n4.mcp["gerufen"] if "confirmToken" in a] == [
        ["n-1", "n-3"]]


def test_stapel_eine_box_fuer_alle_teile(n4, monkeypatch):
    """Über ``hoechstens``: je Teil die Vorschau, EINE Box, einmal freigeben; Teil 2 holt seinen
    Schlüssel beim Start neu, ohne neue Freigabe (die ganze Liste ist freigegeben)."""
    _katalog(monkeypatch, aufteilen={"argument": "node_ids", "hoechstens": 2})
    _antworten(n4, _vorschau(["n-1 „A“", "n-2 „B“"]), _vorschau(["n-3 „C“"], token="ct_2"),
               GESTARTET)
    state: dict = {"entities": {}}
    daten = _box(_starte(state, freigeben=False))
    assert daten["freigabe"]["anzahl"] == 3
    assert state["entities"][auftrag_freigabe.KEY]["args"]["node_ids"] == ["n-1", "n-2"]
    gestartet = _aktion(state, FREI, daten)
    assert _bestaetigungen(n4) == [TOKEN]
    assert bot_text("de", "action.ablauf.auftragTeile", n=2) in gestartet.content
    _antworten(n4, _vorschau(["n-3 „C“"], token="ct_3"),
               _ok({"status": "started", "jobId": "job-2", "flow": "wlo/volltext"}))
    n4.mcp["antworten"]["wlo_flow_status"] = [_ok({"status": "succeeded", "outputs": {}})]
    _pruefe(state)
    assert _bestaetigungen(n4) == [TOKEN, "ct_3"]
    assert [a.job_id for a in n4.ablage.auftraege] == [KENNUNG, mcp_starter.PRAEFIX + "job-2"]


# ── Box, Manifest und Verlauf ────────────────────────────────────────────────────────────────

def test_die_ki_sieht_das_feld_freigabe_nicht():
    from boerdi.ui_module import katalog
    from boerdi.ui_module.werkzeuge import werkzeug_aus_manifest

    parameter = werkzeug_aus_manifest(katalog.katalog()["ui_inhaltsrahmen"])["function"][
        "parameters"]
    assert "freigabe" not in parameter["properties"]


def test_die_box_passt_zum_manifest_und_traegt_keine_kennungen(monkeypatch):
    from jsonschema import Draft202012Validator

    from boerdi.ui_module import katalog

    monkeypatch.setattr(auftrag_freigabe, "aufrufer_kennung", lambda: "person-a")
    entities: dict = {}
    freigabe = {"flow": "f/meta", "erst": {"node_ids": ["n-1"]}, "token": TOKEN,
                "laeuft_ab": 9e9, "eintraege": [("n-1", "Bruch"), ("n-2", "")],
                "probleme": [("n-3", "not_writable")], "schritt": "lesen", "id": "abc"}
    ablage = {"ordner": "Mathe", "inhalte": [
        {"node_id": "n-1", "name": "Klasse 7/bruch.pdf", "titel": "bruch"},
        {"node_id": "n-2", "name": "quiz.pdf", "titel": "Quiz"},
        {"node_id": "n-3", "name": "x.pdf", "titel": "Gesperrt"}]}
    block = auftrag_freigabe.merken(entities, freigabe, "lesen", "de", ablage)
    Draft202012Validator(katalog.katalog()["ui_inhaltsrahmen"]["eingabe"]).validate(block.daten)
    liste = block.daten["freigabe"]
    assert liste["eintraege"] == [{"titel": "Bruch", "ordner": "Klasse 7"},
                                  {"titel": "Quiz", "ordner": "Mathe"}]
    assert liste["probleme"] == [{"titel": "Gesperrt", "grund": "not_writable"}]
    sichtbar = json.dumps(block.model_dump(mode="json"), ensure_ascii=False)
    assert TOKEN not in sichtbar and "n-1" not in sichtbar
    assert entities[auftrag_freigabe.KEY]["caller"] == "person-a"


def test_im_verlauf_ist_die_box_nach_dem_naechsten_zug_eine_quittung():
    from boerdi.ui_module.antwort import status_ableiten

    box = {"modul": "ui_inhaltsrahmen", "status": "nur_anzeige", "art": "anzeigen",
           "daten": {"art": "schreib_vorschau", "freigabe": {"id": "x"}}}
    nachrichten = [{"role": "assistant"}, {"role": "user"}]
    uis = [{"ui_bloecke": [box]}, {}]
    status_ableiten(nachrichten, uis)
    assert box["status"] == "veraltet"
    offen = {**box, "status": "nur_anzeige"}
    status_ableiten([{"role": "assistant"}], [{"ui_bloecke": [offen]}])
    assert offen["status"] == "nur_anzeige"


# ── Leiste: der Freigabe-Halt zählt einmal ────────────────────────────────────────────────────

def test_die_leiste_zaehlt_den_freigabe_halt_einmal(monkeypatch):
    """Rückfrage (Halt 1) → Box (Halt 2) → nach „Freigeben“ wartet derselbe Schritt auf den
    Auftrag: kein neuer Halt, „Schritt 2 von m“ bleibt; ``m`` ändert sich nicht."""
    from boerdi.services.ablauf import auftrag_zug, fortschritt
    from tests.test_paket_k_traeger import _ablauf, _mcp_startet, _nichts

    monkeypatch.setattr(mcp_starter, "verfuegbar", lambda: True)
    monkeypatch.setattr(auftrag_zug, "has_personal_auth", lambda: True)

    async def starten(_flow, _eingaben):
        return mcp_starter.PRAEFIX + "job-1"

    _mcp_startet(monkeypatch, starten)
    ablauf = _ablauf(True)
    umgebung = treiber.Umgebung(teile=_nichts, auftrag_starten=auftrag_zug.starter())
    frage = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    box = asyncio.run(treiber.weiter_wahl(ablauf, frage, "ja", None, umgebung))
    assert box.lauf["status"] == treiber.WARTET_FREIGABE and box.lauf["halte"] == 2
    gestartet = asyncio.run(treiber.weiter_nach_freigabe(ablauf, box.lauf, umgebung,
                                                         mcp_starter.PRAEFIX + "job-1"))
    assert gestartet.lauf["status"] == treiber.WARTET_AUFTRAG and gestartet.lauf["halte"] == 2
    assert (fortschritt.position(ablauf, "lauf", box.lauf["halte"])
            == fortschritt.position(ablauf, "lauf", gestartet.lauf["halte"]))
