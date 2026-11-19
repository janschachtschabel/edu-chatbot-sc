"""Paket K4/K8 (Plan 2026-11-17) im Zug: ein Auftrag über den MCP — Stand, Bericht, Abbruch.

Die MCP-Antworten in der Drahtform von ``wlo-mcp-server-sc`` (``test_paket_k_mcp_starter``). Der
Zug läuft wie in ``test_ablauf_auftrag`` (Fixture ``im_zug``), nur trägt der MCP den Auftrag.
"""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from boerdi.i18n import bot_text
from boerdi.services import arbeitsstand, vorgang_aktion
from boerdi.services.ablauf import auftrag_zug, ausloeser, treiber
from boerdi.services.auftraege import client, mcp_starter
from boerdi.services.mcp import auth, faehigkeiten
from tests.test_ablauf_auftrag import (  # noqa: F401
    _SCHRITTE,
    _pruefe,
    _roh,
    _starte,
    freigeschaltet,
    im_zug,  # noqa: F401
)
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_k_mcp_starter import JOB, TOKEN, VORSCHAU, _abgelehnt, _ok
from tests.test_paket_k_traeger import _ablauf, _am_auftrag

KENNUNG = mcp_starter.PRAEFIX + JOB
NICHT_DA = {"error": {"kind": "tool",
                      "message": "MCP error -32602: Tool wlo_flow_status not found"}}


@pytest.fixture
def ueber_mcp(im_zug, monkeypatch):  # noqa: F811 — Fixture aus test_ablauf_auftrag
    gerufen: list = []
    antworten: dict[str, list] = {
        "wlo_start_flow": [VORSCHAU, _ok({"status": "started", "jobId": JOB,
                                          "flow": "wlo/volltext"})]}
    erkundet: list = []

    async def call_tool(name, args, **_k):
        gerufen.append((name, args))
        return antworten[name].pop(0)

    async def erkunden():
        erkundet.append(True)
        return False

    faehigkeiten.vergessen()
    faehigkeiten.uebernehmen([{"name": n} for n in mcp_starter.WERKZEUGE])
    # Review A4: der MCP trägt nur Schritte mit ``repo_schreibt`` — auch der gesperrte Katalog
    # (``_gesperrt_katalog``) baut aus ``_SCHRITTE``
    monkeypatch.setitem(_SCHRITTE[0], "repo_schreibt", True)
    katalog = [_roh(schritte=[{**_SCHRITTE[0], "argumente": {"text": "fest"}}, *_SCHRITTE[1:]])]
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: katalog)
    monkeypatch.setattr(mcp_starter.transport, "call_tool", call_tool)
    monkeypatch.setattr(mcp_starter, "has_personal_auth", lambda: True)
    monkeypatch.setattr(mcp_starter, "_zug_block", lambda: "wlo2.block-der-person")
    monkeypatch.setattr(mcp_starter, "_neu_geholt", None)      # Takt des Nachholens je Test neu
    monkeypatch.setattr(auth, "has_personal_auth", lambda: True)
    monkeypatch.setattr(faehigkeiten, "nachfragen", erkunden)
    monkeypatch.setattr(auftrag_zug, "darf_jobs", lambda: False)     # Delegation: kein Direktweg
    im_zug.mcp = {"gerufen": gerufen, "antworten": antworten, "erkundet": erkundet}
    yield im_zug
    faehigkeiten.vergessen()


def _gestartet(lage) -> dict:
    state: dict = {"entities": {}}
    _starte(state)
    [a] = lage.ablage.auftraege
    assert a.job_id == KENNUNG
    return state


def _alles_ohne_job(antwort, state, lage) -> None:
    """K8: die jobId nie an die Person, ins Modell (Kennzeile, Teile) oder in den Vorgang."""
    sichtbar = json.dumps([antwort.content, antwort.quick_replies,
                           antwort.model_dump(mode="json")], ensure_ascii=False)
    assert JOB not in sichtbar
    assert JOB not in arbeitsstand.kennzeile(state["entities"], "person-a")
    for v in lage.speicher.v.values():
        assert JOB not in json.dumps(v.akte, ensure_ascii=False, default=str)


def test_start_stand_und_bericht_nur_als_zahlen(ueber_mcp, caplog):
    with caplog.at_level(logging.DEBUG):
        state = _gestartet(ueber_mcp)
        assert [n for n, _a in ueber_mcp.mcp["gerufen"]] == ["wlo_start_flow"] * 2
        bericht = {"report": [
            {"nodeId": "n-1", "status": "success",
             "written": {"changedKeys": ["cclom:title"], "ignoredKeys": []}, "httpCode": 200,
             "characters": 900},
            {"nodeId": "n-2", "status": "failed", "written": {"changedKeys": [], "ignoredKeys": []},
             "httpCode": 403, "characters": 0}]}
        ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [
            _ok({"status": "running", "progress": {"started": 2, "running": 1, "succeeded": 1,
                                                   "warning": 0, "failed": 0}}),
            _ok({"status": "succeeded", "rawStatus": "SUCCEEDED", "outputs": bericht})]
        laeuft = _pruefe(state)
        assert laeuft.content == bot_text("de", "action.ablauf.auftragLaeuftFortschritt",
                                          fertig=1, gesamt=2)
        antwort = _pruefe(state)
    assert antwort.content.startswith(bot_text("de", "action.ablauf.auftragBericht", n=1, m=1))
    assert "Gelesen." in antwort.content
    assert ("wlo_flow_status", {"jobId": JOB}) in ueber_mcp.mcp["gerufen"]
    _alles_ohne_job(antwort, state, ueber_mcp)
    assert JOB not in caplog.text and TOKEN not in caplog.text


def test_unknown_job_ist_kein_fehlschlag(ueber_mcp):
    """E17/K8: nach einem Neustart des MCP ist auch ein eigener Job ``unknown_job`` — weiter zum
    nächsten Schritt, mit Hinweis; nicht der Ersatzweg ``bei_fehler``."""
    state = _gestartet(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [_abgelehnt("unknown_job")]
    antwort = _pruefe(state)
    assert antwort.content == (bot_text("de", "action.ablauf.auftragStandWeg") + "\n\nGelesen.")
    assert ueber_mcp.ablage.auftraege[0].status == "fertig"
    _alles_ohne_job(antwort, state, ueber_mcp)


def test_unbekanntes_werkzeug_beim_stand_ist_voruebergehend(ueber_mcp):
    """Nachtrag MCP 18.11.: nach einem Neustart fehlt das Werkzeug kurz — wie ``upstream_error``:
    erneut abfragbar, nicht ``unknown_job``, nicht weiter zu ``lesen``; die Fähigkeiten werden neu
    geholt."""
    state = _gestartet(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [NICHT_DA]
    antwort = _pruefe(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragNichtAbrufbar")
    assert antwort.quick_replies and ueber_mcp.ablage.auftraege[0].status == "laeuft"
    assert ueber_mcp.mcp["erkundet"] == [True]


def test_unbekanntes_werkzeug_beim_start_fuehrt_zur_rueckfrage(ueber_mcp, monkeypatch):
    """Kein endgültiger Fehlschlag: die Person bekommt „gleich noch einmal“ und die Frage davor."""
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({"f/meta"}))
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [
        {"error": {"kind": "tool", "message": "MCP error -32602: Tool wlo_start_flow not found"}}]
    aus = _am_auftrag(_ablauf(True), auftrag_zug.starter())
    assert aus.lauf["status"] == treiber.WARTET_WAHL and aus.lauf["schritt"] == "frage"
    assert aus.texte[0] == bot_text("de", "action.ablauf.auftragNichtVerfuegbar")
    assert aus.texte[-1] == "Metadaten erzeugen?" and "Ohne Metadaten." not in aus.texte
    assert ueber_mcp.mcp["erkundet"] == [True]


def test_ein_offener_start_liest_beim_stand_pruefen_die_datensaetze(ueber_mcp):
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [
        VORSCHAU, _abgelehnt("upstream_error", outcome_open=True)]
    state: dict = {"entities": {}}
    antwort = _starte(state)
    assert bot_text("de", "action.ablauf.auftragOffen") in antwort.content
    [a] = ueber_mcp.ablage.auftraege
    assert mcp_starter.ist_offen(a.job_id)
    gerufen = len(ueber_mcp.mcp["gerufen"])
    antwort = _pruefe(state)
    assert len(ueber_mcp.mcp["gerufen"]) == gerufen          # kein Stand, kein zweiter Start
    assert antwort.content.endswith("Gelesen.")


# ── K4: Abbruch im Zug ───────────────────────────────────────────────────────────────────────

def _abbrechen(state):
    anfrage = _req(action=auftrag_zug.AKTION_ABBRECHEN, action_params={
        "ablauf": "lesen", "bestaetigt": True, "kuerzel": client.kuerzel(KENNUNG)})
    return asyncio.run(auftrag_zug.abbrechen(_S(), anfrage, state))


@pytest.mark.parametrize(("antwort", "satz"), [
    (_ok({"status": "cancelled"}), "action.ablauf.auftragAbgebrochen"),
    (_ok({"status": "already_finished"}), "action.ablauf.auftragAbgebrochen"),
    (_abgelehnt("upstream_error", outcome_open=True), "action.ablauf.auftragStandUnklar"),
    ({"error": {"kind": "timeout", "message": "x"}}, "action.ablauf.auftragStandUnklar"),
    (_ok({"status": "unknown_job"}), "action.ablauf.auftragStandUnklar"),
    (_abgelehnt("rejected"), "action.ablauf.auftragLaeuftWeiter"),
])
def test_abbrechen_bricht_den_job_im_zug_ab(ueber_mcp, antwort, satz):
    state = _gestartet(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_cancel_flow"] = [antwort]
    ergebnis = _abbrechen(state)
    assert ergebnis.content == bot_text("de", satz)
    assert ueber_mcp.mcp["gerufen"][-1] == ("wlo_cancel_flow", {"jobId": JOB})
    assert not client._abbrueche                                 # nichts im Hintergrund
    assert ueber_mcp.ablage.auftraege[0].status == "abgebrochen"


def test_ein_offener_start_wird_nicht_beim_mcp_abgebrochen(ueber_mcp):
    ueber_mcp.mcp["antworten"]["wlo_start_flow"] = [VORSCHAU, {"error": {"kind": "transport",
                                                                         "message": "x"}}]
    state: dict = {"entities": {}}
    _starte(state)
    offen = ueber_mcp.ablage.auftraege[0].job_id
    anfrage = _req(action=auftrag_zug.AKTION_ABBRECHEN, action_params={
        "ablauf": "lesen", "bestaetigt": True, "kuerzel": client.kuerzel(offen)})
    antwort = asyncio.run(auftrag_zug.abbrechen(_S(), anfrage, state))
    assert antwort.content == bot_text("de", "action.ablauf.auftragStandUnklar")
    assert "wlo_cancel_flow" not in [n for n, _a in ueber_mcp.mcp["gerufen"]]


def test_arbeitsstand_loeschen_bricht_im_zug_ab_und_sagt_wenn_es_offen_bleibt(ueber_mcp,
                                                                              monkeypatch):
    from boerdi.services.dokumente import ablage as dokumente

    async def kein_dokument(*_a, **_k):
        return 0

    monkeypatch.setattr(dokumente, "der_sitzung_loeschen", kein_dokument)
    state = _gestartet(ueber_mcp)
    ueber_mcp.mcp["antworten"]["wlo_cancel_flow"] = [_abgelehnt("upstream_error",
                                                                outcome_open=True)]
    antwort = asyncio.run(vorgang_aktion.loeschen(
        _S(), _req(action=vorgang_aktion.AKTION_LOESCHEN, action_params={"bestaetigt": True}),
        state))
    assert ueber_mcp.mcp["gerufen"][-1] == ("wlo_cancel_flow", {"jobId": JOB})
    assert antwort.content == (bot_text("de", "action.vorgang.geloescht") + " "
                               + bot_text("de", "action.vorgang.auftragUnklar"))
