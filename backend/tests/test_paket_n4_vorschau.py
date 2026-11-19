"""Paket N4 (Plan 2026-11-19): Vorschau und Bestätigung des MCP getrennt (``mcp_vorschau``).

Drahtform von ``wlo-mcp-server-sc`` ``src/tools/bapi-flows.ts``: die Vorschau trägt
``confirm.token``/``expiresAt``/``preview.items`` (``nodeId „Titel“``); ein Datensatz mit Problem
lässt die GANZE Vorschau scheitern (``bad_inputs`` mit ``problems``), nur ungeprüfte →
``upstream_error``. Die Bestätigung kennt ``confirm_expired``/``confirm_mismatch`` (nichts
geschrieben, neue Vorschau) und ``replayed: true`` (dieselbe jobId).
"""

from __future__ import annotations

import asyncio
import logging
import time

import pytest

from boerdi.services.auftraege import client, mcp_starter, mcp_vorschau
from tests.test_paket_k_mcp_starter import FLOW, GESTARTET, JOB, TOKEN, _abgelehnt, _ok


def _vorschau(items: list[str], *, token: str = TOKEN, laeuft_ab: str = "2099-01-01T00:00:00Z"):
    return _ok({"status": "preview", "confirm": {
        "token": token, "expiresAt": laeuft_ab,
        "preview": {"action": "change", "statement": "Startet …", "items": items, "fields": []}}},
        text=f"Bitte prüfen … confirmToken: {token}")


@pytest.fixture
def mcp(monkeypatch):
    gerufen: list = []
    antworten: list = []

    async def call_tool(name, args, **_k):
        gerufen.append((name, args))
        return antworten.pop(0)

    monkeypatch.setattr(mcp_starter.transport, "call_tool", call_tool)
    monkeypatch.setattr(mcp_starter, "has_personal_auth", lambda: True)
    monkeypatch.setattr(mcp_starter, "_zug_block", lambda: "wlo2.block")
    monkeypatch.setattr(client, "freigegebene_flows", lambda: frozenset({FLOW}))
    return {"gerufen": gerufen, "antworten": antworten}


def test_vorschau_liest_schluessel_frist_und_eintraege(mcp):
    mcp["antworten"].append(_vorschau(["n-1 „Bruchrechnung“", "n-2 „Quiz 'A'“", "kaputt"]))
    v = asyncio.run(mcp_vorschau.vorschau(FLOW, {"node_ids": ["n-1", "n-2"], "language": "de"}))
    assert v.token == TOKEN
    assert v.titel == {"n-1": "Bruchrechnung", "n-2": "Quiz 'A'"}
    assert v.laeuft_ab <= time.time() + 600 + 1          # nie länger als die eigene Frist
    assert mcp["gerufen"] == [("wlo_start_flow", {"flow": FLOW, "inputs": {
        "node_ids": ["n-1", "n-2"], "language": "de"}})]


def test_frist_in_der_vergangenheit_gilt_als_uhrenversatz(mcp):
    """Eine Frist des MCP, die schon beim Holen vorbei ist, wäre nie einlösbar — dann die eigene."""
    mcp["antworten"].append(_vorschau(["n-1 „A“"], laeuft_ab="2001-01-01T00:00:00Z"))
    v = asyncio.run(mcp_vorschau.vorschau(FLOW, {"node_ids": ["n-1"]}))
    assert v.laeuft_ab > time.time() + 500


def test_probleme_der_vorschau_kommen_mit(mcp):
    mcp["antworten"].append(_abgelehnt("bad_inputs", problems=[
        {"nodeId": "n-2", "problem": "not_writable"}, {"nodeId": "n-3", "problem": "erfunden"}]))
    with pytest.raises(mcp_vorschau.VorschauFehler) as f:
        asyncio.run(mcp_vorschau.vorschau(FLOW, {"node_ids": ["n-1", "n-2", "n-3"]}))
    assert f.value.grund == "eingaben"
    assert f.value.probleme == [("n-2", "not_writable"), ("n-3", "unbekannt")]


def test_vorschau_ohne_schluessel_ist_ein_fehler(mcp):
    mcp["antworten"].append(_ok({"status": "preview"}))
    with pytest.raises(client.AuftragFehler) as f:
        asyncio.run(mcp_vorschau.vorschau(FLOW, {"node_ids": ["n-1"]}))
    assert f.value.grund == "fehler"


def test_bestaetigen_startet_mit_dem_schluessel(mcp, caplog):
    mcp["antworten"].append(GESTARTET)
    with caplog.at_level(logging.DEBUG):
        kennung = asyncio.run(mcp_vorschau.bestaetigen(FLOW, {"node_ids": ["n-1"]}, TOKEN))
    assert kennung == mcp_starter.PRAEFIX + JOB
    assert mcp["gerufen"][0][1]["confirmToken"] == TOKEN
    assert TOKEN not in caplog.text and JOB not in caplog.text


def test_wiederholung_liefert_dieselbe_kennung(mcp):
    """Doppelklick bis zum MCP: ``replayed: true`` ist derselbe Job, kein zweiter."""
    mcp["antworten"].append(_ok({"status": "started", "jobId": JOB, "flow": FLOW,
                                 "replayed": True}))
    assert asyncio.run(mcp_vorschau.bestaetigen(FLOW, {"node_ids": ["n-1"]}, TOKEN)) == (
        mcp_starter.PRAEFIX + JOB)


@pytest.mark.parametrize("code", ["confirm_expired", "confirm_mismatch"])
def test_abgelaufener_schluessel_braucht_eine_neue_vorschau(mcp, code):
    mcp["antworten"].append(_abgelehnt(code, outcome_open=False))
    with pytest.raises(client.AuftragFehler) as f:
        asyncio.run(mcp_vorschau.bestaetigen(FLOW, {"node_ids": ["n-1"]}, TOKEN))
    assert f.value.grund == "abgelaufen"


def test_unbekannter_schluessel_ist_offen(mcp):
    mcp["antworten"].append(_abgelehnt("confirm_unknown", outcome_open=True))
    with pytest.raises(client.AuftragFehler) as f:
        asyncio.run(mcp_vorschau.bestaetigen(FLOW, {"node_ids": ["n-1"]}, TOKEN))
    assert f.value.grund == "offen"


def test_starten_bleibt_vorschau_und_bestaetigung_in_einem(mcp):
    mcp["antworten"].extend([_vorschau(["n-1 „A“"]), GESTARTET])
    assert asyncio.run(mcp_starter.starten(FLOW, {"node_ids": ["n-1"]})) == (
        mcp_starter.PRAEFIX + JOB)
    assert [a.get("confirmToken") for _n, a in mcp["gerufen"]] == [None, TOKEN]
