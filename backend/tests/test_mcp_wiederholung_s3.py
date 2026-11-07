"""Plan 2026-11-07, Paket N1 (CB-6 und Einlösen): der Chatbot nutzt S2/S3 des MCP-Servers.

* Ein bestätigter Schreibaufruf ohne Antwort holt seine Antwort mit demselben Schlüssel nach
  (``replayed``, ``inProgress``); kennt der Server den Schlüssel nicht mehr, bleibt der Ausgang
  offen — nie „nichts geändert“.
* ``outcomeOpen: true`` heißt bei jedem Code „Ausgang offen“ (S3: ``upstream_error`` nach der
  Einlösung).
* ``requiresNewPreview`` ohne offenen Ausgang → dieselben Angaben neu vorlegen.
* ``busy`` beim Einlösen → die Abnahme bleibt liegen, der Chip löst sie gleich noch einmal ein.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD
from boerdi.i18n.bot_text import bot_text
from boerdi.services import plan_fortsetzen
from boerdi.services import write_approval as wa_mod
from boerdi.services.mcp import client, wiederholung
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.write_approval import redeem_write_approval
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)
from tests.test_mcp_vertrag_m2 import _Antworten, _rand  # noqa: F401 — Fixture
from tests.test_write_approval import _SESSION, _req, _zustand

_ARGS = {"title": "Brechung", CONFIRM_TOKEN_FIELD: "T" * 24}
_OHNE_ANTWORT = {"error": {"message": "read timeout", "kind": "transport"}}


@pytest.fixture
def _ohne_warten(monkeypatch):
    async def _sofort(_s):
        return None

    monkeypatch.setattr(wiederholung.asyncio, "sleep", _sofort)


def _replay(text: str = "Angelegt: Brechung") -> dict:
    hinweis = "Dieser Bestätigungsschlüssel wurde schon eingelöst — hier die Antwort von damals."
    return {"result": {"content": [_text_part(hinweis), _text_part(text)],
                       "structuredContent": {"nodeId": "n-1", "replayed": True}}}


def test_eine_verlorene_antwort_wird_nachgeholt(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_OHNE_ANTWORT, _replay()])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert (antwort.text, antwort.art) == ("Angelegt: Brechung", "")
    assert antwort.strukturiert == {"nodeId": "n-1", "replayed": True}
    assert calls[1]["arguments"] == calls[0]["arguments"]   # derselbe Schlüssel


def test_eine_laufende_einloesung_wird_abgewartet(mcp_state, monkeypatch, _ohne_warten):  # noqa: F811
    _wire_tool_url(monkeypatch)
    laeuft = {"result": {"content": [_text_part("läuft")],
                         "structuredContent": {"inProgress": True}}}
    calls = _wire_transport(monkeypatch, [_OHNE_ANTWORT, laeuft, laeuft, _replay()])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert antwort.text == "Angelegt: Brechung"
    assert len(calls) == 4


def test_bleibt_sie_laufend_bleibt_der_ausgang_offen(mcp_state, monkeypatch, _ohne_warten):  # noqa: F811
    _wire_tool_url(monkeypatch)
    laeuft = {"result": {"content": [], "structuredContent": {"inProgress": True}}}
    _wire_transport(monkeypatch, [_OHNE_ANTWORT] + [laeuft] * wiederholung.NACHFRAGEN)
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert antwort.art == "transport"


@pytest.mark.parametrize("code", ["confirm_unknown", "confirm_mismatch", "login_rejected"])
def test_vergisst_der_server_den_schluessel_bleibt_der_ausgang_offen(
        mcp_state, monkeypatch, code):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_OHNE_ANTWORT, {"error": {
        "message": "unbekannt", "kind": "tool", "structured": {"error": {"code": code}}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert antwort.art == "transport"


def test_der_fehler_des_ersten_aufrufs_kommt_beim_nachholen(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [_OHNE_ANTWORT, {"error": {
        "message": "Dublette", "kind": "tool", "structured": {"error": {
            "code": "exists", "requiresNewPreview": True}}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert (antwort.art, antwort.code) == ("tool", "exists")


def test_plaene_holen_nicht_nach(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_OHNE_ANTWORT, _replay()])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_collection_tree",
                                                       dict(_ARGS)))
    assert antwort.art == "transport" and len(calls) == 1


def test_ein_lesender_aufruf_wiederholt_wie_bisher(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    calls = _wire_transport(monkeypatch, [_OHNE_ANTWORT, {"result": {"content": [
        _text_part("Treffer")]}}])
    text, art = asyncio.run(client.call_mcp_tool_status("search_wlo_all", {"query": "Optik"},
                                                        use_cache=False))
    assert (text, art) == ("Treffer", "") and len(calls) == 2


def test_outcome_open_heisst_bei_jedem_code_offen(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"message": "abgebrochen", "kind": "tool",
                                             "structured": {"error": {
                                                 "code": "upstream_error", "outcomeOpen": True,
                                                 "requiresNewPreview": True}}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", {"title": "T"}))
    assert antwort.art == "timeout"


# ── Einlösen ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ausgelastet_beim_einloesen_laesst_die_abnahme_liegen(_rand, monkeypatch):  # noqa: F811
    mcp = _Antworten(McpAntwort("MCP error: WLO ist gerade ausgelastet.", "busy"))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    gemerkt = dict(zustand["entities"]["_pending_write"])
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.content == bot_text("de", "write.busy")
    assert antwort.quick_replies == [bot_text("de", "action.write.confirmChip")]
    assert zustand["entities"]["_pending_write"] == gemerkt


@pytest.mark.asyncio
async def test_requires_new_preview_mit_ausdruecklich_nichts_geschehen_legt_neu_vor(
        _rand, monkeypatch):  # noqa: F811
    neu = "NeuerSchluessel-0123456789ab"
    mcp = _Antworten(
        McpAntwort("MCP error [refused]: belegt", "tool", "refused",
                   {"code": "refused", "requiresNewPreview": True, "outcomeOpen": False}),
        McpAntwort(f"Bitte prüfen:\n\nTitel: Neu\n\nconfirmToken: {neu}",
                   strukturiert={"confirm": {"token": neu}}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert CONFIRM_TOKEN_FIELD not in mcp.calls[1][1]
    assert bot_text("de", "write.confirmRenewed") in antwort.content
    assert zustand["entities"]["_pending_write"]["token"] == neu


@pytest.mark.parametrize(("antwort", "text"), [
    # Review 2026-11-07, Befund 1: „angenommen, aber nicht nachweisbar“ — nie „nichts geändert“.
    (McpAntwort("MCP error [not_visible]: fehlt", "timeout", "not_visible",
                {"code": "not_visible", "requiresNewPreview": True}), "write.executeUnconfirmed"),
    (McpAntwort("MCP error [unverified]: offen", "timeout", "unverified",
                {"code": "unverified", "requiresNewPreview": True}), "write.executeUnconfirmed"),
], ids=["not_visible", "unverified"])
@pytest.mark.asyncio
async def test_ein_unbelegter_ausgang_nach_der_einloesung_wird_nicht_neu_vorgelegt(
        _rand, monkeypatch, antwort, text):  # noqa: F811
    mcp = _Antworten(antwort)
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort_chat = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort_chat.content == bot_text("de", text)
    assert len(mcp.calls) == 1


@pytest.mark.asyncio
async def test_eine_ablehnung_nach_der_einloesung_nennt_den_grund(_rand, monkeypatch):  # noqa: F811
    mcp = _Antworten(McpAntwort("MCP error [exists]: Dublette", "tool", "exists",
                                {"code": "exists", "message": "Gibt es schon.",
                                 "requiresNewPreview": True}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert len(mcp.calls) == 1
    assert bot_text("de", "write.confirmRenewed") not in antwort.content


def test_ausgelastet_nach_der_einloesung_ohne_wirkung_ist_eine_ablehnung(
        mcp_state, monkeypatch):  # noqa: F811
    """Zweite Antwort des MCP-Teams: ``outcomeOpen: false`` = nachweislich nichts geschrieben."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"message": "belegt", "kind": "tool", "structured": {
        "error": {"code": "upstream_busy", "requiresNewPreview": True, "outcomeOpen": False}}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert (antwort.art, antwort.code) == ("tool", "upstream_busy")


@pytest.mark.asyncio
async def test_eine_dublette_nach_der_einloesung_wird_nicht_neu_vorgelegt(
        _rand, monkeypatch):  # noqa: F811
    mcp = _Antworten(McpAntwort("MCP error [exists]: Dublette", "tool", "exists",
                                {"code": "exists", "requiresNewPreview": True,
                                 "outcomeOpen": False,
                                 "existing": {"nodeId": "n-9", "title": "Brechung"}}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert len(mcp.calls) == 1
    assert "n-9" in antwort.content


@pytest.mark.asyncio
async def test_nichts_gespeichert_nach_der_einloesung_legt_neu_vor(_rand, monkeypatch):  # noqa: F811
    neu = "NeuerSchluessel-0123456789ab"
    mcp = _Antworten(
        McpAntwort("MCP error [not_stored]: nichts angekommen", "tool", "not_stored",
                   {"code": "not_stored", "requiresNewPreview": True, "outcomeOpen": False}),
        McpAntwort(f"Bitte prüfen:\n\nTitel: Neu\n\nconfirmToken: {neu}",
                   strukturiert={"confirm": {"token": neu}}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert bot_text("de", "write.confirmRenewed") in antwort.content


def test_ausgelastet_nach_der_einloesung_heisst_offen(mcp_state, monkeypatch):  # noqa: F811
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": {"message": "belegt", "kind": "tool", "structured": {
        "error": {"code": "upstream_busy", "requiresNewPreview": True}}}}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("wlo_create_content", dict(_ARGS)))
    assert antwort.art == "timeout"


@pytest.mark.asyncio
async def test_ungepruefte_anmeldung_und_unklare_zustimmung_lassen_liegen(
        _rand, monkeypatch):  # noqa: F811
    """Review 2026-11-07, Befund 2: auch bei unklarer Zustimmung endet der Zug hier — sonst fände
    der Fingerabdruck-Weg der Werkzeug-Schleife den Schlüssel ohne ein Ja."""
    from boerdi.services import zustimmung_pruefen
    from boerdi.services.mcp import auth

    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: False)
    mcp = _Antworten()
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    auth.set_turn_auth_block("wlo2.persoenlich-ungeprueft")
    auth.merke_anmeldung_unklar()
    zustand = _zustand(caller="p:0123456789abcdef")
    zustand[zustimmung_pruefen.UNKLAR_MERKER] = True
    antwort = await redeem_write_approval(_SESSION, _req("vielleicht"), zustand)
    auth.set_turn_auth_block(None)
    assert antwort.content == bot_text("de", "write.authUnclear")
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_ein_plan_bleibt_bei_auslastung_bestehen(monkeypatch):
    gespeichert = []

    async def _antwort(session, req, entities, text, debug, *, knoepfe=None):
        gespeichert.append((text, knoepfe, dict(entities)))

    monkeypatch.setattr(plan_fortsetzen, "_antwort", _antwort)
    entities = {plan_fortsetzen.KEY: {"tool": "wlo_add_to_collections"}}
    from boerdi.api.schemas import DebugInfo
    await plan_fortsetzen._fehler(None, _req(), entities, "de", McpAntwort("x", "busy"),
                                  DebugInfo(pattern="p"))
    text, knoepfe, gemerkt = gespeichert[0]
    assert text == bot_text("de", "write.planBusy")
    assert knoepfe == [plan_fortsetzen.knopf("de")]
    assert plan_fortsetzen.KEY in gemerkt


@pytest.mark.asyncio
async def test_eine_ungepruefte_anmeldung_laesst_die_abnahme_liegen(_rand, monkeypatch):  # noqa: F811
    """CB-4: der Server konnte die Anmeldung nicht prüfen und es gab keine frühere Bestätigung
    (etwa nach einem Neustart) — kein Schreibrecht, aber auch kein Grund zu verwerfen."""
    from boerdi.services.mcp import auth

    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: False)
    mcp = _Antworten()
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    auth.set_turn_auth_block("wlo2.persoenlich-ungeprueft")
    auth.merke_anmeldung_unklar()
    zustand = _zustand(caller="p:0123456789abcdef")
    gemerkt = dict(zustand["entities"]["_pending_write"])
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    auth.set_turn_auth_block(None)
    assert antwort.content == bot_text("de", "write.authUnclear")
    assert zustand["entities"]["_pending_write"] == gemerkt
    assert mcp.calls == []


@pytest.mark.asyncio
async def test_ohne_unklare_pruefung_bleibt_es_beim_verwerfen(_rand, monkeypatch):  # noqa: F811
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: False)
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten())
    zustand = _zustand()
    assert await redeem_write_approval(_SESSION, _req(), zustand) is None
    assert "_pending_write" not in zustand["entities"]
