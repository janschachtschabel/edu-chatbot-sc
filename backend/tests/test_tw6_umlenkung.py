"""TW-6 (zweites Review, Befunde 1, 2, 4): die Umlenkung eines Modul-Aufrufs auf einen Ablauf, in
beiden Maschinen von Anfang bis Ende.

Ruft die KI ``ui_upload`` ohne Arbeitsgrundlage auf, während ein passender Ablauf angeboten ist,
läuft das Modul nicht. Eine Antwort **derselben Runde** gilt dann nicht (sonst endete der Zug mit
„lade hier hoch“ ohne Feld und ohne Ablauf) — die nächste Runde ruft den Ablauf.
"""

from __future__ import annotations

import json

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import ausloeser, vorschlag
from boerdi.ui_module import datenquelle, strukturentwurf_merken
from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call
from tests.test_tool_loop import _run_loop

RESPOND = "respond_to_user"
UPLOAD = "ui_upload"
ABLAUF = "ablauf-mit_upload"


@pytest.fixture
def ablauf_mit_upload(monkeypatch):
    ablauf = AblaufArea.model_validate({
        "id": "mit_upload", "titel": {"de": "Aus Ordnern"}, "aktiv": True,
        "ausloeser": [{"art": "agent"}],
        "schritte": [{"id": "u", "typ": "modul", "modul": UPLOAD,
                      "daten": {"zweck": "sammlungsstruktur"}},
                     {"id": "e", "typ": "ende", "text": {"de": "fertig"}}]})
    monkeypatch.setattr(ausloeser, "vorschlaege", lambda: [ablauf])
    return ablauf


def _inhalt(msgs, call_id):
    return next(m["content"] for m in msgs if m.get("tool_call_id") == call_id)


def test_agent_umlenkung_verwirft_die_antwort_derselben_runde(ablauf_mit_upload, monkeypatch):
    zustand: dict = {"entities": {}}

    def umlenkung(name, args, angeboten, merken=True):
        return vorschlag.umlenkung(name, args, angeboten, zustand, merken=merken)

    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(UPLOAD, {"zweck": "sammlungsstruktur"}, "c1"),
                     _tool_call(RESPOND, {"text": "Lade deine Dateien hier hoch."}, "c2")]),
        _resp_tools([_tool_call(ABLAUF, {}, "c3")]),
        _resp_text("Der geführte Ablauf startet."),
    ], tools=[UPLOAD, RESPOND, ABLAUF], modul_umlenkung=umlenkung)

    assert "ablauf-mit_upload" in _inhalt(msgs, "c1")
    assert _inhalt(msgs, "c2") == datenquelle.ANTWORT_UMGELENKT       # nicht „lade hier hoch“
    assert run.ui_bloecke == []
    assert run.ablauf_vorschlaege and run.ablauf_vorschlaege[0]["ablauf"] == "mit_upload"


def test_agent_ein_umgelenktes_modul_ist_keine_frage_der_runde(ablauf_mit_upload, monkeypatch):
    """Zweites Review TW-6, Befund 2: Modul und Ablauf in derselben Runde — der Ablauf bekam
    „nach der Frage“, obwohl keine Frage erschien."""
    zustand: dict = {"entities": {}}

    def umlenkung(name, args, angeboten, merken=True):
        return vorschlag.umlenkung(name, args, angeboten, zustand, merken=merken)

    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(UPLOAD, {"zweck": "sammlungsstruktur"}, "c1"),
                     _tool_call(ABLAUF, {}, "c2")]),
        _resp_text("Der geführte Ablauf startet."),
    ], tools=[UPLOAD, ABLAUF], modul_umlenkung=umlenkung)

    assert run.ablauf_vorschlaege and run.ablauf_vorschlaege[0]["ablauf"] == "mit_upload"
    from boerdi.services import agent_loop

    assert _inhalt(msgs, "c2") != agent_loop._NACH_DER_FRAGE


def test_muster_umlenkung_verwirft_die_antwort_derselben_runde(ablauf_mit_upload, monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("c1", UPLOAD, json.dumps({"zweck": "sammlungsstruktur"})),
                     ("c2", RESPOND, json.dumps({"text": "Lade deine Dateien hier hoch."}))]),
        _resp_text("Der geführte Ablauf hilft dir."),
    ], active_tools=[{"type": "function", "function": {"name": n}}
                     for n in (UPLOAD, RESPOND, ABLAUF)])

    assert "ablauf-mit_upload" in _inhalt(st["messages"], "c1")
    assert _inhalt(st["messages"], "c2") == datenquelle.ANTWORT_UMGELENKT
    assert result[0] == "Der geführte Ablauf hilft dir." and len(fake.calls) == 2


def test_mit_arbeitsgrundlage_wird_nicht_umgelenkt(ablauf_mit_upload):
    """Zweites Review TW-6, Befund 5: der gemerkte Entwurf ist eine Grundlage."""
    entities = {strukturentwurf_merken.KEY: {"daten": {"knoten": []}, "zuege": 3}}
    assert vorschlag.arbeitsgrundlage(entities, "a") is True
    zustand = {"entities": entities, vorschlag.GRUNDLAGE_KEY: True}
    assert vorschlag.umlenkung(UPLOAD, {}, {UPLOAD, ABLAUF}, zustand) is None
    assert vorschlag.umlenkung(UPLOAD, {}, {UPLOAD, ABLAUF}, {"entities": {}}) is not None


def test_pruefen_ohne_merken_zaehlt_keinen_versuch(ablauf_mit_upload):
    zustand: dict = {"entities": {}}
    assert vorschlag.umlenkung(UPLOAD, {}, {UPLOAD, ABLAUF}, zustand, merken=False)
    assert vorschlag.umlenkung(UPLOAD, {}, {UPLOAD, ABLAUF}, zustand)      # noch umgelenkt
    assert vorschlag.umlenkung(UPLOAD, {}, {UPLOAD, ABLAUF}, zustand) is None  # Fluchtweg


def test_tg2_ein_zielneutrales_upload_feld_lenkt_nur_mit_themenbaum_bezug_um(ablauf_mit_upload):
    """Plan 2026-11-16, TG-2, nach Review M3 (c): mit ``zweck: bereitstellen`` kann das Feld ebenso
    einem Dokument oder dem Übertragen nach WLO dienen — dann nicht umlenken. Nennt die Nachricht
    des Zugs aber einen Themenbaum (``THEMENBAUM_KEY``, gesetzt von ``respond``), greift das Netz
    aus TW-6 weiter. Der alte Zweck ``sammlungsstruktur`` lenkt wie bisher immer um."""
    assert vorschlag.umlenkung(UPLOAD, {"zweck": "bereitstellen"}, {UPLOAD, ABLAUF},
                               {"entities": {}}) is None
    mit_bezug = {"entities": {}, vorschlag.THEMENBAUM_KEY: True}
    assert vorschlag.umlenkung(UPLOAD, {"zweck": "bereitstellen"}, {UPLOAD, ABLAUF},
                               mit_bezug) is not None
    assert vorschlag.umlenkung(UPLOAD, {"zweck": "sammlungsstruktur"}, {UPLOAD, ABLAUF},
                               {"entities": {}}) is not None


@pytest.mark.parametrize(("nachricht", "bezug"), [
    ("Mach mir aus meinem Lehrplan einen Themenbaum", True),
    ("Zwei Themenbäume aus meinen Ordnern", True),
    ("Mach mir aus meinem Lehrplan eine Struktur", True),
    ("Ich will eine Gliederung aus meinen Ordnern", True),
    ("Eine Sammlungsstruktur bitte", True),
    ("Baue einen Sammlungsbaum", True),
    ("Create a topic tree from my folder", True),
    # Nachprüfung TG-2, NIT 7
    ("Make a topic-tree from it", True),
    ("Build a collection structure", True),
    ("Two collection trees please", True),
    ("Einen Themen-Baum bitte", True),
    ("Einen Themen baum bitte", True),
    ("Kann ich ein PDF hochladen?", False),
    ("Ich will meine Dateien nach WLO übertragen", False),
    # Zweites Review TG-2, MINOR 3: Komposita mit „struktur“ sind kein Themenbaum-Wunsch
    ("Das ist mein Strukturdokument", False),
    ("Meine Ordnerstruktur ist chaotisch", False),
    ("Material zur Infrastruktur", False),
    ("Arbeitsblatt zur Zellstruktur", False),
    ("Unterricht zum Strukturwandel", False),
    ("", False),
])
def test_tg2_themenbaum_bezug_der_nachricht(nachricht, bezug):
    assert vorschlag.themenbaum_bezug(nachricht) is bezug


def test_zweites_review_m7_der_zugstand_wird_je_zug_neu_gesetzt():
    """Zweites Review TG-2, MINOR 7: ``zug_merken`` setzt Grundlage und Themenbaum-Bezug je Zug neu
    und vergisst die Umlenkung des vorigen Zugs — beide Antwort-Knoten rufen es."""
    import inspect

    from boerdi.graph.nodes import respond, respond_agent

    zustand: dict = {vorschlag.UMGELENKT_KEY: ["ui_upload"]}
    vorschlag.zug_merken(zustand, {}, "person-a", "Mach mir einen Themenbaum")
    assert zustand[vorschlag.THEMENBAUM_KEY] is True and vorschlag.UMGELENKT_KEY not in zustand
    assert zustand[vorschlag.GRUNDLAGE_KEY] is False
    vorschlag.zug_merken(zustand, {}, "person-a", "Kann ich ein PDF hochladen?")
    assert zustand[vorschlag.THEMENBAUM_KEY] is False
    for knoten in (respond, respond_agent):
        quelle = inspect.getsource(knoten)
        assert "ablauf_vorschlag.zug_merken(" in quelle
        assert "THEMENBAUM_KEY]" not in quelle and "GRUNDLAGE_KEY]" not in quelle
