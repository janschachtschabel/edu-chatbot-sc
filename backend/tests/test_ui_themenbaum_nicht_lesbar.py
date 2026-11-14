"""N5 (Plan 2026-11-14): der Themenbaum zeigt Zweige, die nicht gelesen werden konnten oder durften.

Der MCP kennzeichnet je Knoten ``childrenUnread`` (Ausfall, seit dem 13.11.) und
``childrenRefused`` (das Repository gibt sie nicht heraus, Stand 14.11.). Das Modul übernahm je
Knoten nur Kennung, Titel, Adresse, Anzahl und Kinder — ein solcher Zweig sah aus wie ein Thema ohne
Unterthemen, und die Quittung an die KI sagte nichts.
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from boerdi.ui_module import datenquelle, katalog, themenbaum
from tests.test_ui_themenbaum import THEMENBAUM, WERKZEUG, _knoten, _payload, _Rufer
from tests.test_ui_themenbaum_zweig import _KNOTEN, _PFAD, _SITZUNG, auf, client  # noqa: F401


def _baum(**kennzeichen_oben) -> dict:
    return _payload(truncated=False, results=[
        _knoten("bbbb-2222", "Algebra", **kennzeichen_oben),
        _knoten("eeee-5555", "Geometrie", children=[_knoten("cccc-3333", "Dreiecke")]),
    ])


# ── Daten: ein Feld je Knoten ───────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kennzeichen, erwartet", [
    ({"childrenUnread": True}, "ausfall"),
    ({"childrenRefused": True}, "gesperrt"),
])
def test_ein_nicht_lesbarer_zweig_traegt_sein_kennzeichen(kennzeichen, erwartet):
    daten = themenbaum.daten_aus(_baum(**kennzeichen))
    algebra, geometrie = daten["knoten"]
    assert algebra["nicht_lesbar"] == erwartet
    assert "nicht_lesbar" not in geometrie and "nicht_lesbar" not in geometrie["kinder"][0]
    assert not katalog.daten_fehler(katalog.katalog()[THEMENBAUM], daten)


def test_ohne_kennzeichen_bleiben_die_daten_wie_bisher():
    daten = themenbaum.daten_aus(_payload())
    assert "nicht_lesbar" not in json.dumps(daten)


def test_nur_ein_echtes_true_zaehlt():
    """Die Felder kommen vom Server; ``"true"`` oder ``1`` sind kein Kennzeichen."""
    daten = themenbaum.daten_aus(_baum(childrenUnread="true", childrenRefused=1))
    assert "nicht_lesbar" not in daten["knoten"][0]


# ── Was die KI erfährt ──────────────────────────────────────────────────────────────────────────

def test_die_quittung_nennt_die_nicht_lesbaren_zweige_ohne_ihre_namen():
    ausfall = themenbaum.quittung(themenbaum.daten_aus(_baum(childrenUnread=True)))
    gesperrt = themenbaum.quittung(themenbaum.daten_aus(_baum(childrenRefused=True)))
    assert "1 Thema" in ausfall and "gerade nicht lesen" in ausfall
    assert "1 Thema" in gesperrt and "nicht zugänglich" in gesperrt
    for text in (ausfall, gesperrt):
        assert "Algebra" not in text                    # die Knoten kennt die KI weiterhin nicht
        assert "keine Unterthemen" not in text          # … und sie behauptet nicht das Gegenteil
        # Review N5, Befund 4: eine Schlussanweisung, nicht je Grund eine.
        assert text.count("Begleitsatz") == 1 and "Sag das in einem Satz" not in text
        assert text.rstrip().endswith("nicht lesbar war.")
    ohne = themenbaum.quittung(themenbaum.daten_aus(_payload()))
    assert "nicht lesbar" not in ohne and "nicht zugänglich" not in ohne


def test_die_quittung_zaehlt_beide_gruende_und_die_zweite_ebene():
    """Review N5, Befund 7: Mehrzahl, beide Gründe zugleich, Kennzeichen an einem Kind."""
    daten = themenbaum.daten_aus(_payload(truncated=False, results=[
        _knoten("bbbb-2222", "Algebra", childrenUnread=True),
        _knoten("ffff-6666", "Analysis", childrenUnread=True),
        _knoten("eeee-5555", "Geometrie", children=[
            _knoten("cccc-3333", "Dreiecke", childrenRefused=True)]),
    ]))
    assert daten["knoten"][2]["kinder"][0]["nicht_lesbar"] == "gesperrt"
    assert not katalog.daten_fehler(katalog.katalog()[THEMENBAUM], daten)
    text = themenbaum.quittung(daten)
    assert "Bei 2 Themen ließen sich" in text and "Bei 1 Thema sind" in text
    assert text.count("Begleitsatz") == 1


def test_abgelehnt_geht_vor_ausfall():
    """Trägt ein Knoten beide Kennzeichen, bleibt es beim Abgelehnten: neu laden hülfe nicht."""
    daten = themenbaum.daten_aus(_baum(childrenUnread=True, childrenRefused=True))
    assert daten["knoten"][0]["nicht_lesbar"] == "gesperrt"


def test_die_textfassung_sagt_es_am_thema():
    text = themenbaum.textfassung(themenbaum.daten_aus(_baum(childrenRefused=True)))
    assert "Algebra" in text and "Unterthemen nicht zugänglich" in text
    text = themenbaum.textfassung(themenbaum.daten_aus(_baum(childrenUnread=True)))
    assert "gerade nicht lesbar" in text


# ── Die Sammlung selbst ist nicht lesbar ────────────────────────────────────────────────────────

@pytest.mark.anyio
@pytest.mark.parametrize("code", ["forbidden", "not_found"])
async def test_eine_abgelehnte_sammlung_wird_nicht_wiederholt_und_der_ki_gesagt(monkeypatch, code):
    """Der MCP meldet einen abgelehnten Startknoten als Fehler mit Code. Ein zweiter Versuch
    ändert nichts, und „prüfe das Argument“ führte die KI in die Irre."""
    r = _Rufer(f"MCP error [{code}]: Fehler beim Sub-Sammlungs-Abruf: Die Sammlung x wurde nicht "
               "gefunden oder ist mit dieser Anmeldung nicht lesbar (HTTP 403).", "tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, text, outcome = await datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"})
    assert block is None and outcome.error == "abgelehnt"
    assert len(r.calls) == 1                                   # kein zweiter Versuch
    assert "nicht zugänglich" in text and "nicht noch einmal mit derselben Angabe" in text
    assert "Anmeldung" not in text                             # die meisten sind nicht angemeldet
    assert "HTTP 403" not in text and "Sammlung x" not in text   # kein Text des Servers


@pytest.mark.anyio
async def test_ein_unbekanntes_fach_ist_keine_abgelehnte_sammlung(monkeypatch):
    """Review N5, M1: zu ``subject`` heißt ``not_found`` „kein Fachportal mit diesem Namen“
    (``browse.ts``). Die KI soll das Argument berichtigen (etwa die Sammlung suchen und ihre
    Kennung nennen), nicht ein Rechteproblem melden."""
    r = _Rufer('MCP error [not_found]: Kein Fachportal für "Optik" gefunden. Verfügbar: '
               "Biologie, Chemie, Physik.", "tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, text, outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Optik"})
    assert block is None and outcome.error == "fach_unbekannt"
    assert len(r.calls) == 1                                   # ein zweiter Versuch hülfe nicht
    assert "Prüfe das Argument" in text and "nicht zugänglich" not in text
    assert "Verfügbar" not in text                             # kein Text des Servers


@pytest.mark.anyio
async def test_ein_abgelehntes_fachportal_bleibt_abgelehnt(monkeypatch):
    """``forbidden`` heißt auch zu ``subject`` abgelehnt: die Liste der Portale ist nicht lesbar."""
    r = _Rufer("MCP error [forbidden]: Fehler beim Sub-Sammlungs-Abruf: nicht lesbar.", "tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    _block, _text, outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Physik"})
    assert outcome.error == "abgelehnt" and len(r.calls) == 1


@pytest.mark.anyio
async def test_ein_anderer_werkzeugfehler_wird_weiter_einmal_wiederholt(monkeypatch):
    r = _Rufer("MCP error [upstream_error]: Fehler beim Sub-Sammlungs-Abruf: upstream 502", "tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    block, _text, outcome = await datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"})
    assert block is None and outcome.error == "tool" and len(r.calls) == 2


# ── Aufklappen im Widget ────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["forbidden", "not_found"])
def test_ein_abgelehnter_zweig_kommt_beim_aufklappen_als_gesperrt_an(
        client: TestClient, auf, monkeypatch, code):  # noqa: F811
    """Kein 502 („nicht geladen“ mit „Erneut laden“): ein neuer Versuch hülfe nicht."""
    r = _Rufer(f"MCP error [{code}]: Fehler beim Sub-Sammlungs-Abruf: nicht lesbar (HTTP 403).",
               "tool")
    monkeypatch.setattr(datenquelle, "_rufen", r)
    antwort = client.post(_PFAD, json={"session_id": _SITZUNG, "node_id": _KNOTEN})
    assert antwort.status_code == 200
    assert antwort.json()["daten"] == {"knoten": [], "nicht_lesbar": "gesperrt"}
    assert [c[0] for c in r.calls] == [WERKZEUG]


def test_ein_ausfall_beim_aufklappen_bleibt_nicht_geladen(
        client: TestClient, auf, monkeypatch):  # noqa: F811
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer("MCP error: keine Antwort", "transport"))
    antwort = client.post(_PFAD, json={"session_id": _SITZUNG, "node_id": _KNOTEN})
    assert antwort.status_code == 502
