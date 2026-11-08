"""Kleine offene Punkte nach K2c/K2d (2026-11-08).

- Der Knopf eines Plans heißt werkzeugneutral „Plan fortsetzen“ (W2/W3 legen nichts an).
- „WLO ist ausgelastet“ nennt die Wartezeit, die der Server bei ``upstream_busy`` angibt.
- W2/W3 laufen als Plan durch Einlösen und „Plan fortsetzen“ (wie M5).
- ``bei_fehler`` nur, wo der Treiber ihn nimmt; ``weiter`` als Liste an einem anderen Schritt als
  einer Verzweigung gilt im Treiber wie kein ``weiter`` (nicht als ``bei_fehler``).
"""

from __future__ import annotations

import asyncio
import re
import time

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.write_confirm import remember_pending
from boerdi.i18n.bot_text import bot_text
from boerdi.services import plan_fortsetzen
from boerdi.services import write_approval as wa_mod
from boerdi.services.ablauf import treiber
from boerdi.services.ablauf.pruefung import nachfolger, pruefe
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.mcp.wiederholung import genannte_wartezeit
from boerdi.services.write_approval import redeem_write_approval
from tests.test_mcp_client import mcp_state  # noqa: F401 — Fixture
from tests.test_mcp_vertrag_m5 import _Antworten, _rand  # noqa: F401 — Fixture
from tests.test_write_approval import _SESSION, _req

_PLAN = "Plan-0123456789abcdef"


def test_der_knopf_ist_werkzeugneutral():
    assert bot_text("de", "action.plan.weiterKnopf") == "Plan fortsetzen"
    assert "Plan fortsetzen" in plan_fortsetzen.knopf("de")
    for schluessel in ("write.planOpen", "write.planStillOpen", "write.planBusy",
                       "write.planUnclear", "write.planUnclearStart", "write.planExpired",
                       "write.planTooLarge"):
        assert not re.search(r"anleg|angelegt", bot_text("de", schluessel)), schluessel


def test_die_genannte_wartezeit():
    assert genannte_wartezeit({"code": "upstream_busy", "retryAfter": 60}) == 60
    assert genannte_wartezeit({"retryAfter": 0.4}) == 1
    for unsinn in (None, {}, {"retryAfter": True}, {"retryAfter": -3}, {"retryAfter": 0},
                   {"retryAfter": "60"}, {"retryAfter": 86_400}):
        assert genannte_wartezeit(unsinn) is None, unsinn


def _busy(retry_after=None) -> McpAntwort:
    fehler = {"code": "upstream_busy", "message": "voll",
              **({"retryAfter": retry_after} if retry_after is not None else {})}
    return McpAntwort("MCP error [upstream_busy]: voll", "busy", "upstream_busy", fehler,
                      warte_s=genannte_wartezeit(fehler))


@pytest.mark.parametrize(("fehler", "warte"), [
    ({"kind": "busy", "grund": "rate_limited", "retry_after": 90}, 90),        # 429 Retry-After
    ({"kind": "tool", "structured": {"error": {"code": "upstream_busy", "retryAfter": 60}}}, 60),
    ({"kind": "busy", "grund": "budget"}, None),
])
def test_die_wartezeit_kommt_aus_beiden_quellen_an(mcp_state, monkeypatch, fehler, warte):  # noqa: F811
    from boerdi.services.mcp import client
    from tests.test_mcp_client import _wire_tool_url, _wire_transport

    _wire_tool_url(monkeypatch)
    _wire_transport(monkeypatch, [{"error": dict(fehler, message="voll")}])
    antwort = asyncio.run(client.call_mcp_tool_antwort("unknown_probe_tool", {"q": "x"}))
    assert antwort.art == "busy" and antwort.warte_s == warte
    if warte is not None:
        assert f"etwa {warte} Sekunden" in antwort.text      # auch das Modell liest sie


def _zustand(tool, args):
    return {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        tool, args, "Schluessel-0123456789abcd", now=time.time(), caller="person-a")}}


_W2 = ("wlo_attach_fulltexts",
       {"items": [{"nodeId": "n-1", "markdown": "# A", "source": "manual"}]})
_W3 = ("wlo_update_contents", {"items": [{"nodeId": "n-1", "title": "Optik"}]})


@pytest.mark.asyncio
async def test_ausgelastet_nennt_die_wartezeit_des_servers(_rand, monkeypatch):  # noqa: F811
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(_busy(60)))
    zustand = _zustand(*_W2)
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.content.startswith(bot_text("de", "write.busy"))
    assert "60 Sekunden" in antwort.content and "_pending_write" in zustand["entities"]
    # ohne Angabe bleibt der Satz, wie er war
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(_busy()))
    antwort = await redeem_write_approval(_SESSION, _req(), _zustand(*_W2))
    assert antwort.content == bot_text("de", "write.busy")


def _plan_antwort(complete: bool) -> McpAntwort:
    sc = {"complete": complete, "progress": {"done": 1 if not complete else 2, "total": 2},
          "items": [{"nodeId": "n-1", "status": "updated"}]}
    text = "1 von 2 erledigt." if not complete else "2 von 2 erledigt."
    if not complete:
        sc |= {"continuationToken": _PLAN, "expiresAt": "2026-11-08T23:00:00Z"}
        text += f"\n\nNoch nicht fertig. Derselbe Aufruf mit continuationToken: {_PLAN} setzt fort."
    return McpAntwort(text, strukturiert=sc)


@pytest.mark.asyncio
@pytest.mark.parametrize(("tool", "args"), [_W2, _W3])
async def test_w2_w3_laufen_als_plan_durch(_rand, monkeypatch, tool, args):  # noqa: F811
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(_plan_antwort(False)))
    zustand = _zustand(tool, args)
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")] and _PLAN not in antwort.content
    offen = zustand["entities"][plan_fortsetzen.KEY]
    assert offen["tool"] == tool and offen["args"] == args and offen["token"] == _PLAN
    # „Plan fortsetzen“: dieselben Angaben mit dem Schlüssel des Plans, ohne neue Bestätigung
    mcp = _Antworten(_plan_antwort(True))
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    [(gerufen, gesendet)] = mcp.calls
    assert gerufen == tool and gesendet == {**args, "continuationToken": _PLAN}
    assert "2 von 2" in antwort.content and plan_fortsetzen.KEY not in zustand["entities"]


@pytest.mark.asyncio
async def test_fortsetzen_ausgelastet_nennt_die_wartezeit(_rand, monkeypatch):  # noqa: F811
    zustand = {"persona_id": "P-AND", "entities": {plan_fortsetzen.KEY: {
        "tool": _W2[0], "args": _W2[1], "token": _PLAN, "caller": "person-a",
        "minted_at": time.time()}}}
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", _Antworten(_busy(45)))
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert "45 Sekunden" in antwort.content and plan_fortsetzen.KEY in zustand["entities"]


def _ablauf(schritte):
    return AblaufArea.model_validate({"id": "probe", "titel": {"de": "Probe"},
                                      "voraussetzungen": ["anmeldung"], "schritte": schritte})


def test_bei_fehler_nur_wo_der_treiber_ihn_nimmt():
    ablauf = _ablauf([
        {"id": "n", "typ": "nachricht", "text": {"de": "x"}, "bei_fehler": "rest"},
        {"id": "e", "typ": "ende"},
        {"id": "rest", "typ": "ende"}])
    assert nachfolger(ablauf, 0) == ["e"]
    # ein Tippfehler im Ziel zeigt sich trotzdem
    tippfehler = _ablauf([{"id": "n", "typ": "nachricht", "text": {"de": "x"}, "bei_fehler": "rst"},
                          {"id": "e", "typ": "ende"}])
    assert any("'rst'" in b for b in pruefe(tippfehler))
    befunde = pruefe(ablauf)
    assert any("bei_fehler wirkt" in b and "nachricht" in b for b in befunde)
    # „rest“ ist damit unerreichbar — auch das sagt die Prüfung
    assert any("rest" in b and "erreichbar" in b for b in befunde)


def test_weiter_als_liste_ausserhalb_einer_verzweigung_ist_nicht_bei_fehler():
    from tests.test_ablauf_treiber import _umgebung

    ablauf = _ablauf([
        {"id": "w", "typ": "werkzeug", "werkzeug": "strukturentwurf_aus_ordnern",
         "argumente": {"struktur": {"$teil": "structure"}}, "schreibt": "draft", "weiter": [],
         "bei_fehler": "schlecht"},
        {"id": "gut", "typ": "ende", "text": {"de": "gut"}},
        {"id": "schlecht", "typ": "ende", "text": {"de": "schlecht"}}])
    assert nachfolger(ablauf, 0) == ["gut", "schlecht"]
    from tests.test_ablauf_treiber import _STRUKTUR

    aus = asyncio.run(treiber.starten(ablauf, _umgebung(teile={"structure": _STRUKTUR})))
    assert aus.lauf["schritt"] == "gut" and aus.lauf["status"] == "fertig"


def test_agent_ausgelastet_ohne_aufruf_behaelt_die_freigabe():
    """Offener Punkt (Review kleine Punkte): ``WriteGate.prepare`` verbrauchte die Freigabe auch,
    wenn der Aufruf nie hinausging (ausgelastet ohne Code)."""
    from boerdi.services.agent_write import WriteGate
    from boerdi.services.mcp import client

    gate = WriteGate("execute")
    args = {"nodeId": "n-1", "title": "Optik"}
    gate.observe("wlo_update_content", args, "Vorschau … confirmToken: Schluessel-0123456789abcd")
    mit = gate.prepare("wlo_update_content", dict(args))
    assert mit["confirmToken"] == "Schluessel-0123456789abcd" and gate.offene_abnahme() is None
    gate.observe("wlo_update_content", mit, f"MCP error: {client._AUSGELASTET_STANDARD}")
    assert gate.offene_abnahme() is not None                       # bleibt
    # mit Code (upstream_busy) ist der Ausgang offen — dann bleibt sie verbraucht
    mit = gate.prepare("wlo_update_content", dict(args))
    gate.observe("wlo_update_content", mit, "MCP error [upstream_busy]: voll")
    assert gate.offene_abnahme() is None
    assert not client.ausgelastet_ohne_aufruf("MCP error [upstream_busy]: voll")
    assert not client.ausgelastet_ohne_aufruf("alles gut")


def test_gesamt_upload_quittung_sagt_was_nicht_geht(monkeypatch):
    """Gesamt-Review U3/M1/U4/U5, Befund 5: die KI erfährt, was im Auswahlfeld nicht geht."""
    from boerdi.ui_module import dienst_upload

    monkeypatch.setattr(dienst_upload, "has_personal_auth", lambda: False)
    satz = dienst_upload._was_geht({"dokument_im_chat": False, "ablage_in_wlo": False})
    assert "lesen lassen geht hier nicht ohne WLO-Anmeldung" in satz
    assert "Übertragen nach WLO geht hier nicht ohne WLO-Anmeldung" in satz
    assert dienst_upload._was_geht({"dokument_im_chat": True, "ablage_in_wlo": True}) == ""

