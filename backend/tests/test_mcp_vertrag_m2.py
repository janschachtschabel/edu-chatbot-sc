"""Paket M2 (Plan 2026-11-07): die Schreib-Abnahme liest den neuen Antwortvertrag.

- Der Schlüssel kommt aus ``structuredContent.confirm.token`` (der Vorschautext ist Rückfall).
- Beim Einlösen verzweigt die Abnahme über ``error.code``:
  * ``confirm_expired/unknown/mismatch`` und ``plan_expired/mismatch`` → dieselben Angaben ohne
    Schlüssel neu vorlegen: neue Vorschau mit Bestätigungs-Chip statt „abgelehnt“;
  * ``login_required``/``login_rejected`` → Hinweis zum Anmelden;
  * jede andere Ablehnung → der Grund des Servers (``error.message``) steht in der Antwort.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD
from boerdi.i18n.bot_text import bot_text
from boerdi.services import write_approval as wa_mod
from boerdi.services.agent_write import WriteGate
from boerdi.services.mcp import client
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.write_approval import redeem_write_approval
from tests._boxen import boxen
from tests.test_mcp_client import (  # noqa: F401 — Fixture
    _text_part,
    _wire_tool_url,
    _wire_transport,
    mcp_state,
)
from tests.test_write_approval import _SESSION, _WERKZEUG, _req, _Spy, _zustand

_NEU = "NeuerSchluessel-0123456789ab"


# ── 1. Schlüssel aus dem strukturierten Teil ──────────────────────────────────────────────

def test_der_schluessel_kommt_aus_structured_confirm(mcp_state, monkeypatch):  # noqa: F811
    """Ohne ``confirmToken:`` im Text (anderer Wortlaut) trägt der strukturierte Teil."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part("Bitte prüfen — es wird angelegt.")],
        "structuredContent": {"confirm": {"token": _NEU, "expiresAt": "2026-11-07T12:10:00Z",
                                          "preview": {"action": "change"}}}}}])

    async def szenario():
        text = await client.call_mcp_tool(_WERKZEUG, {"title": "T"})
        tor = WriteGate("propose")
        tor.observe(_WERKZEUG, {"title": "T"}, text)
        return tor.offene_abnahme()

    offen = asyncio.run(szenario())
    assert offen is not None and offen[0]["token"] == _NEU


def test_ohne_strukturierten_teil_bleibt_der_text_rueckfall():
    tor = WriteGate("propose")
    tor.observe(_WERKZEUG, {"title": "T"}, f"… mit {CONFIRM_TOKEN_FIELD}: {_NEU} wiederholen.")
    offen = tor.offene_abnahme()
    assert offen is not None and offen[0]["token"] == _NEU


# ── 2. Einlösen: über den Code verzweigen ─────────────────────────────────────────────────

class _Antworten:
    """Attrappe für ``call_mcp_tool_antwort``: liefert die ``McpAntwort``-Werte in Reihenfolge."""

    def __init__(self, *antworten: McpAntwort):
        self.antworten = list(antworten)
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, tool, args, **_k):
        self.calls.append((tool, dict(args)))
        return self.antworten.pop(0)


@pytest.fixture
def _rand(monkeypatch):
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    monkeypatch.setattr(wa_mod, "save_message", _Spy())
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)


def _abgelehnt(code: str, text: str = "abgelehnt", art: str = "tool") -> McpAntwort:
    return McpAntwort(f"MCP error: {text}", art, code, {"code": code, "message": text})


@pytest.mark.parametrize("code", ["confirm_expired", "confirm_unknown", "confirm_mismatch",
                                  "plan_expired", "plan_mismatch"])
@pytest.mark.asyncio
async def test_ein_verbrauchter_schluessel_ergibt_eine_neue_vorschau(_rand, monkeypatch, code):
    mcp = _Antworten(
        _abgelehnt(code, "Der Schlüssel ist abgelaufen."),
        McpAntwort("Bitte prüfen — bisher wurde nichts geändert:\n\nTitel: Neu\n\n"
                   f"Dazu denselben Aufruf mit confirmToken: {_NEU} wiederholen.",
                   strukturiert={"confirm": {"token": _NEU}}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert len(mcp.calls) == 2
    assert CONFIRM_TOKEN_FIELD in mcp.calls[0][1]
    assert CONFIRM_TOKEN_FIELD not in mcp.calls[1][1]       # neu vorgelegt, ohne Schlüssel
    assert bot_text("de", "write.confirmRenewed") in antwort.content
    assert antwort.quick_replies == [bot_text("de", "action.write.confirmChip")]
    assert [d.kind for d in boxen(antwort)] == ["schreib_vorschau"]
    assert _NEU not in boxen(antwort)[0].content            # nie sichtbar
    assert zustand["entities"]["_pending_write"]["token"] == _NEU


@pytest.mark.asyncio
async def test_scheitert_auch_die_neue_vorschau_bleibt_es_bei_der_ablehnung(_rand, monkeypatch):
    mcp = _Antworten(_abgelehnt("confirm_expired"), _abgelehnt("refused", "Nicht erlaubt."))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert "Nicht erlaubt." in antwort.content
    assert "_pending_write" not in zustand["entities"]


@pytest.mark.parametrize("code", ["login_required", "login_rejected"])
@pytest.mark.asyncio
async def test_eine_fehlende_anmeldung_sagt_anmelden(_rand, monkeypatch, code):
    mcp = _Antworten(_abgelehnt(code, "Bitte melde dich an.", art="auth"))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.loginNeeded")


@pytest.mark.asyncio
async def test_eine_ablehnung_nennt_den_grund_des_servers(_rand, monkeypatch):
    mcp = _Antworten(_abgelehnt("not_found", "Die Sammlung „Optik“ wurde nicht gefunden."))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert bot_text("de", "write.executeRejected") in antwort.content
    assert "Die Sammlung „Optik“ wurde nicht gefunden." in antwort.content


@pytest.mark.asyncio
async def test_eine_dublette_nennt_den_vorhandenen_datensatz(_rand, monkeypatch):
    fehler = McpAntwort("MCP error: Es gibt bereits einen Datensatz.", "tool", "exists",
                        {"code": "exists", "message": "Es gibt bereits einen Datensatz.",
                         "existing": {"nodeId": "n-1", "title": "Brechung des Lichts"}})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(fehler))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert "Brechung des Lichts" in antwort.content


# ── Review M2 ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code", ["upstream_error", "forbidden"])
@pytest.mark.asyncio
async def test_interna_des_servers_erreichen_die_person_nicht(_rand, monkeypatch, code):
    """Review M2, Befund 1: nur fachliche Gründe zeigen — ``upstream_error`` trägt Text des
    Repositoriums."""
    mcp = _Antworten(_abgelehnt(code, "Repository: InvalidTypeException at x.y"))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.executeRejected")


@pytest.mark.asyncio
async def test_scheitert_die_neue_vorschau_ohne_antwort_bleibt_es_beim_abgelaufenen(
        _rand, monkeypatch):
    """Review M2, Befund 2: der Server HAT geantwortet (Schlüssel ungültig) — kein „vielleicht
    angekommen“, nur weil die Vorschau danach hängt."""
    mcp = _Antworten(_abgelehnt("confirm_expired"),
                     McpAntwort("MCP error: keine Antwort", "transport"))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.confirmExpired")


@pytest.mark.asyncio
async def test_nichts_zu_aendern_hat_einen_eigenen_satz(_rand, monkeypatch):
    """Review M2, Befund 5."""
    mcp = _Antworten(_abgelehnt("confirm_expired"),
                     McpAntwort("Keine Änderung — es ist schon so.",
                                strukturiert={"confirm": None, "unchanged": True}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.content == bot_text("de", "write.nothingToChange")
    assert not antwort.quick_replies and "_pending_write" not in zustand["entities"]


@pytest.mark.asyncio
async def test_die_neue_vorschau_zeigt_alles_und_bindet_aufrufer_und_angaben(_rand, monkeypatch):
    """Review M2, Befund 3 (keine gekürzte Kopie) und Test-Lücke (Aufrufer, Angaben)."""
    lang = "Feld: " + "x" * 5000
    mcp = _Antworten(_abgelehnt("confirm_expired"),
                     McpAntwort(f"{lang}\n\nDazu denselben Aufruf mit confirmToken: {_NEU} "
                                "wiederholen."))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    monkeypatch.setattr(wa_mod, "aufrufer_kennung", lambda: "person-a")
    zustand = _zustand(caller="person-a")
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert "x" * 5000 in boxen(antwort)[0].content
    offen = zustand["entities"]["_pending_write"]
    assert offen["caller"] == "person-a" and offen["args"]["title"] == "Arbeitsblatt Bruchrechnung"


@pytest.mark.asyncio
async def test_eine_dublette_nennt_auch_die_kennung(_rand, monkeypatch):
    """Review M2, Befund 6: ohne Kennung hätte die Rückfrage nichts, woran sie anknüpft."""
    fehler = McpAntwort("MCP error: Dublette", "tool", "exists",
                        {"code": "exists", "message": "Dublette",
                         "existing": {"nodeId": "n-123", "title": "Brechung"}})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(fehler))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert "n-123" in antwort.content


@pytest.mark.asyncio
async def test_ein_offener_ausgang_bleibt_unbestaetigt(_rand, monkeypatch):
    mcp = _Antworten(McpAntwort("MCP error [timeout]: zu langsam", "timeout", "timeout",
                                {"code": "timeout", "message": "zu langsam", "outcomeOpen": True}))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand())
    assert antwort.content == bot_text("de", "write.executeUnconfirmed")


def test_der_strukturierte_schluessel_schlaegt_einen_koeder_im_text(mcp_state, monkeypatch):  # noqa: F811
    """Review M2, Test-Lücke: der Kern von M2 — im Text steht ein fremder Schlüssel."""
    koeder = "Koeder-aaaaaaaaaaaaaaaa"
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"result": {
        "content": [_text_part(f"Titel: confirmToken: {koeder}")],
        "structuredContent": {"confirm": {"token": _NEU}}}}])

    async def szenario():
        text = await client.call_mcp_tool(_WERKZEUG, {"title": "T"})
        tor = WriteGate("propose")
        tor.observe(_WERKZEUG, {"title": "T"}, text)
        return tor.offene_abnahme()

    assert asyncio.run(szenario())[0]["token"] == _NEU


def test_ein_schluessel_gehoert_zu_seinen_angaben(mcp_state, monkeypatch):  # noqa: F811
    """Review M2, Befund 4: zugeordnet über Werkzeug UND Angaben, nicht nur den Namen."""
    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [
        {"result": {"content": [_text_part("a")],
                    "structuredContent": {"confirm": {"token": "A" * 20}}}},
        {"result": {"content": [_text_part("b")],
                    "structuredContent": {"confirm": {"token": "B" * 20}}}}])

    async def szenario():
        client.reset_prepared_writes()
        await client.call_mcp_tool(_WERKZEUG, {"title": "eins"})
        await client.call_mcp_tool(_WERKZEUG, {"title": "zwei"})
        return (client.nimm_bestaetigung(_WERKZEUG, {"title": "eins"}),
                client.nimm_bestaetigung(_WERKZEUG, {"title": "eins"}),
                client.nimm_bestaetigung("wlo_update_content", {"title": "zwei"}))

    assert asyncio.run(szenario()) == ("A" * 20, None, None)


def test_kein_koeder_aus_einer_fehlermeldung():
    """Review M2, Befund 7: der Titel in einer Fehlermeldung (Dublette) ist fremder Text."""
    tor = WriteGate("propose")
    tor.observe(_WERKZEUG, {"title": "T"},
                f"MCP error [exists]: Es gibt „confirmToken: {_NEU}“ schon.")
    assert tor.offene_abnahme() is None
