"""Paket K7 (Plan 2026-11-17, E16/E17): „Später weitermachen“ am gesperrten Auftragsschritt.

- Neben „Stand prüfen“ und „Auftrag abbrechen“ ein dritter Knopf — nur, solange die Eingabe
  gesperrt ist (``warten: gesperrt``).
- Der Lauf bleibt ``wartet_auftrag`` im Vorgang, der Auftrag läuft weiter (keine Abfrage, kein
  Abbruch). Die Sperre fällt für diese Sitzung — gemerkt in ``entities`` (die überleben den Zug).
- Der Satz nennt „Stand prüfen“ als Weg zurück und die Frist: die frühere von Aufbewahrung des
  Vorgangs (``verfaellt_am``) und 30 Tagen des Jobs bei der b-api (Review B2: nicht „Meine
  Vorgänge“, dort stehen nur andere Gespräche).
- Review B1: ein gewöhnlicher Start-Knopf beendet den wartenden Lauf nicht still — erst die
  Rückfrage (wie bei der Gastseite).
- Zurück über „Stand prüfen“ (auch „Fortsetzen“ schickt es): die Sperre greift wieder, solange der
  Job läuft — auch über den MCP; ``unknown_job`` geht weiter zu ``lesen``.
- Die jobId steht nirgends in der Antwort.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest

from boerdi.api import chat
from boerdi.domain.wahl_knopf import ist_steuer_knopf
from boerdi.graph.nodes import preflight, preflight_ablauf
from boerdi.i18n import bot_text
from boerdi.services.ablauf import auftrag_spaeter, auftrag_zug, treiber, zug, zug_basis
from boerdi.services.auftraege import client
from tests.test_ablauf_auftrag import _pruefe, _starte, freigeschaltet, im_zug  # noqa: F401
from tests.test_ablauf_auftrag_abbruch import _SID, _aktionen, _gesperrt_katalog, _preflight
from tests.test_ablauf_zug import _S, _req
from tests.test_paket_k_mcp_starter import JOB, _abgelehnt, _ok
from tests.test_paket_k_zug import _gestartet, ueber_mcp  # noqa: F401

_DREI = [auftrag_zug.AKTION, auftrag_zug.AKTION_SPAETER, auftrag_zug.AKTION_ABBRECHEN]
_ZWEI = [auftrag_zug.AKTION, auftrag_zug.AKTION_ABBRECHEN]


def _spaeter(state, ablauf="lesen"):
    anfrage = _req(action=auftrag_zug.AKTION_SPAETER, action_params={"ablauf": ablauf})
    return asyncio.run(auftrag_spaeter.spaeter(_S(), anfrage, state))


def _gesperrt_gestartet(im_zug, monkeypatch) -> dict:  # noqa: F811
    _gesperrt_katalog(monkeypatch)
    state: dict = {"entities": {}}
    _starte(state)
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"
    return state


# ── Knöpfe ───────────────────────────────────────────────────────────────────────────────────────

def test_der_dritte_knopf_nur_bei_gesperrter_eingabe(im_zug, monkeypatch):  # noqa: F811
    frei: dict = {"entities": {}}
    _starte(frei)
    assert [a for a, _p in _aktionen(auftrag_zug.pruefen_knoepfe(_SID, frei, "de"))] == _ZWEI
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    assert [a for a, _p in _aktionen(auftrag_zug.pruefen_knoepfe(_SID, state, "de"))] == _DREI
    im_zug.staende.append(client.Stand("laeuft"))
    assert [a for a, _p in _aktionen(_pruefe(state))] == _DREI
    getippt, antwort = _preflight(state, message="Was gibt es zu Optik?")
    assert [a for a, _p in _aktionen(antwort.antwort)] == _DREI
    knopf = auftrag_zug.pruefen_knoepfe(_SID, state, "de")[1]
    assert knopf.split("|")[1] == bot_text("de", "action.ablauf.auftragSpaeterKnopf")
    assert auftrag_zug.ist_knopf(knopf) and ist_steuer_knopf(knopf)


def test_spaeter_ist_eine_steuer_aktion_im_gesperrten_lauf():
    assert not preflight_ablauf.abgewiesen(auftrag_zug.AKTION_SPAETER, "lesen")
    assert auftrag_zug.AKTION_SPAETER in preflight._DIRECT_ACTIONS
    assert auftrag_zug.AKTION_SPAETER in preflight._STEUER_OHNE_TEXT


# ── Später weitermachen ──────────────────────────────────────────────────────────────────────────

def test_spaeter_laesst_den_lauf_wartend_und_hebt_die_sperre(im_zug, monkeypatch):  # noqa: F811
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    antwort = _spaeter(state)
    [v] = im_zug.speicher.v.values()
    frist = auftrag_spaeter.datum(v.verfaellt_am, "de")
    assert antwort.content == bot_text("de", "action.ablauf.auftragSpaeter", datum=frist)
    assert "Stand prüfen" in antwort.content
    assert v.akte["lauf"]["status"] == treiber.WARTET_AUFTRAG
    assert im_zug.ablage.auftraege[0].status == "laeuft" and im_zug.staende == []
    assert auftrag_zug.gesperrt(_SID, state) is None
    # „Stand prüfen“ bleibt der Weg zurück; „Später“ und der Abbruch stehen nicht mehr darunter
    assert [a for a, _p in _aktionen(antwort)] == [auftrag_zug.AKTION]
    assert chat._anmeldestand(antwort, _req(), {"session_state": state}).eingabe_gesperrt is False
    # getippter Text geht danach den gewöhnlichen Weg (kein Hinweis „gesperrt“)
    a, frei = _preflight(state, message="Was gibt es zu Optik?")
    assert a.gesperrt is None and frei is None
    assert "job-1" not in json.dumps(antwort.model_dump(mode="json"), ensure_ascii=False)


def test_die_marke_liegt_in_den_entities(im_zug, monkeypatch):  # noqa: F811
    """Die Sitzung lädt je Zug nur ``entities`` neu — die Marke muss dort liegen und gespeichert
    werden, sonst wäre die Sperre im nächsten Zug zurück."""
    gespeichert: list[dict] = []

    async def merke(_s, _sid, **felder):
        gespeichert.append(json.loads(json.dumps(felder.get("entities"))))

    monkeypatch.setattr(zug_basis, "update_session", merke)
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    _spaeter(state)
    neu = {"entities": gespeichert[-1]}                 # der nächste Zug: frisch aus der Sitzung
    assert auftrag_zug.gesperrt(_SID, neu) is None


def test_die_frist_ist_die_fruehere_der_beiden_grenzen():
    jetzt = datetime(2026, 11, 19, 12, tzinfo=UTC)
    vorgang = jetzt + timedelta(days=8)
    assert auftrag_spaeter.rueckkehr_frist(vorgang, jetzt) == vorgang
    erstellt = jetzt - timedelta(days=25)
    assert auftrag_spaeter.rueckkehr_frist(vorgang, erstellt) == erstellt + timedelta(days=30)
    assert auftrag_spaeter.rueckkehr_frist(vorgang, None) == vorgang
    assert auftrag_spaeter.datum(datetime(2026, 12, 3, 9, tzinfo=UTC), "de") == "02.12.2026"
    assert auftrag_spaeter.datum(datetime(2026, 12, 3, 9, tzinfo=UTC), "en") == "2 Dec 2026"


def test_die_frist_des_jobs_kommt_aus_dem_auftrag(im_zug, monkeypatch):  # noqa: F811
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    erstellt = datetime.now(UTC) - timedelta(days=29)
    im_zug.ablage.auftraege[0].erstellt = erstellt
    antwort = _spaeter(state)
    erwartet = auftrag_spaeter.datum(erstellt + timedelta(days=30), "de")
    assert antwort.content == bot_text("de", "action.ablauf.auftragSpaeter", datum=erwartet)


def test_spaeter_ohne_wartenden_auftrag(im_zug):  # noqa: F811
    state: dict = {"entities": {}}
    antwort = _spaeter(state)
    assert antwort.content == bot_text("de", "action.ablauf.auftragSchonBeendet")


def test_der_preflight_fuehrt_spaeter_aus(im_zug, monkeypatch):  # noqa: F811
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    _a, antwort = _preflight(state, action=auftrag_zug.AKTION_SPAETER,
                             action_params={"ablauf": "lesen"})
    assert "Stand prüfen" in antwort.antwort.content
    assert auftrag_zug.gesperrt(_SID, state) is None


# ── Rückkehr ─────────────────────────────────────────────────────────────────────────────────────

def test_stand_pruefen_sperrt_wieder_solange_der_job_laeuft(im_zug, monkeypatch):  # noqa: F811
    gespeichert: list[dict] = []

    async def merke(_s, _sid, **felder):
        gespeichert.append(json.loads(json.dumps(felder.get("entities"))))

    monkeypatch.setattr(zug_basis, "update_session", merke)
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    _spaeter(state)
    im_zug.staende.append(client.Stand("laeuft"))
    antwort = _pruefe(state)
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"
    assert auftrag_zug.gesperrt(_SID, {"entities": gespeichert[-1]}) == "lesen"
    assert [a for a, _p in _aktionen(antwort)] == _DREI
    assert chat._anmeldestand(antwort, _req(), {"session_state": state}).eingabe_gesperrt is True


def test_ein_fertiger_job_setzt_nach_spaeter_fort(im_zug, monkeypatch):  # noqa: F811
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    _spaeter(state)
    im_zug.staende.append(client.Stand("fertig", {"markdown": "# T"}, []))
    _pruefe(state)
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == "fertig"
    assert auftrag_zug.gesperrt(_SID, state) is None
    assert auftrag_zug.SPAETER not in state["entities"]


def test_ueber_den_mcp_sperrt_die_rueckkehr_wieder(ueber_mcp, monkeypatch):  # noqa: F811
    _gesperrt_katalog(monkeypatch)
    state = _gestartet(ueber_mcp)
    antwort = _spaeter(state)
    assert JOB not in antwort.content and auftrag_zug.gesperrt(_SID, state) is None
    assert [n for n, _a in ueber_mcp.mcp["gerufen"]] == ["wlo_start_flow"] * 2   # keine Abfrage
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [
        _ok({"status": "running", "progress": {"started": 40, "running": 28, "succeeded": 12,
                                               "warning": 0, "failed": 0}})]
    laeuft = _pruefe(state)
    assert laeuft.content == bot_text("de", "action.ablauf.auftragLaeuftFortschritt",
                                      fertig=12, gesamt=40)
    assert [a for a, _p in _aktionen(laeuft)] == _DREI
    assert auftrag_zug.gesperrt(_SID, state) == "lesen"


def test_unknown_job_nach_spaeter_geht_weiter_zu_lesen(ueber_mcp, monkeypatch):  # noqa: F811
    _gesperrt_katalog(monkeypatch)
    state = _gestartet(ueber_mcp)
    _spaeter(state)
    ueber_mcp.mcp["antworten"]["wlo_flow_status"] = [_abgelehnt("unknown_job")]
    antwort = _pruefe(state)
    assert antwort.content.startswith(bot_text("de", "action.ablauf.auftragStandWeg"))
    assert auftrag_zug.gesperrt(_SID, state) is None
    assert JOB not in antwort.content


@pytest.mark.parametrize("lang", ["de", "en"])
def test_die_saetze_gibt_es_in_beiden_sprachen(lang):
    satz = bot_text(lang, "action.ablauf.auftragSpaeter", datum="X")
    assert "X" in satz and "{" not in satz
    assert bot_text(lang, "action.ablauf.auftragSpaeterKnopf")


# ── Review B1: ein Start-Knopf beendet den wartenden Lauf nicht still ────────────────────────────

def _start_knopf(state):
    return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                              action_params={"ablauf": "lesen"}), state))


def test_nach_spaeter_fragt_ein_start_knopf_erst_nach(im_zug, monkeypatch):  # noqa: F811
    state = _gesperrt_gestartet(im_zug, monkeypatch)
    _spaeter(state)
    antwort = _start_knopf(state)
    assert antwort.content == bot_text("de", "action.ablauf.ersetzen")
    assert [a for a, _p in _aktionen(antwort)] == [zug.AKTION, auftrag_zug.AKTION]
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_AUFTRAG
    assert im_zug.ablage.auftraege[0].status == "laeuft" and len(im_zug.gestartet) == 1


def test_bei_freiem_warten_fragt_ein_start_knopf_erst_nach(im_zug, monkeypatch):  # noqa: F811
    _gesperrt_katalog(monkeypatch, warten="frei")
    state: dict = {"entities": {}}
    _starte(state)
    antwort = _start_knopf(state)
    assert antwort.content == bot_text("de", "action.ablauf.ersetzen")
    [v] = im_zug.speicher.v.values()
    assert v.akte["lauf"]["status"] == treiber.WARTET_AUFTRAG
    assert im_zug.ablage.auftraege[0].status == "laeuft" and len(im_zug.gestartet) == 1
