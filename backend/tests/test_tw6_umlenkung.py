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
