"""Paket M5 (Plan 2026-11-07): Pläne — Sammlungsbaum und Massen-Aufnahme unter EINER Bestätigung.

``wlo_create_collection_tree`` und ``wlo_add_to_collections`` legen eine Vorschau für den ganzen
Plan vor; nach dem „ja“ arbeitet der Server in Abschnitten von etwa 40 s und antwortet mit
``complete``, ``progress`` und — solange etwas offen ist — ``continuationToken``. Fortgesetzt wird
OHNE neue Bestätigung (der Plan ist an die Freigabe gebunden), aber nur von derselben Person und
mit denselben Angaben: über den Knopf „Weiter anlegen“ (Direktaktion ``plan_weiter``).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import pytest

from boerdi.domain.write_confirm import CONFIRMABLE_TOOLS, CURATION_TOOLS, remember_pending
from boerdi.i18n.bot_text import bot_text
from boerdi.services import plan_fortsetzen
from boerdi.services import write_approval as wa_mod
from boerdi.services.mcp.client import McpAntwort
from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS
from boerdi.services.write_approval import redeem_write_approval
from tests.test_write_approval import _SESSION, _req, _Spy

_BAUM = "wlo_create_collection_tree"
_ANGABEN = {"parentCollectionId": "c-physik",
            "tree": [{"title": "Optik", "children": [{"title": "Linsen"}]}]}
_PLAN = "Plan-0123456789abcdef"


def _plan_antwort(complete: bool, done: int = 1, total: int = 2) -> McpAntwort:
    text = (f"Sammlungsbaum: {done} von {total} Schritten erledigt.\n- Optik: angelegt (n-1)"
            + ("" if complete else f"\n\nNoch nicht fertig. Derselbe Aufruf mit "
               f"continuationToken: {_PLAN} setzt fort — ohne neue Bestätigung, bis 2026-11-07."))
    sc = {"complete": complete, "progress": {"done": done, "total": total},
          "nodes": [{"path": "Optik", "status": "created", "nodeId": "n-1"}]}
    if not complete:
        sc |= {"continuationToken": _PLAN, "expiresAt": "2026-11-07T13:00:00Z"}
    return McpAntwort(text, strukturiert=sc)


class _Antworten:
    def __init__(self, *antworten):
        self.antworten, self.calls = list(antworten), []

    async def __call__(self, tool, args, **_k):
        self.calls.append((tool, dict(args)))
        return self.antworten.pop(0)


@pytest.fixture
def _rand(monkeypatch):
    for modul in (wa_mod, plan_fortsetzen):
        monkeypatch.setattr(modul, "update_session", _Spy())
        monkeypatch.setattr(modul, "save_message", _Spy())
        monkeypatch.setattr(modul, "schreiben_erlaubt", lambda: True)
        monkeypatch.setattr(modul, "aufrufer_kennung", lambda: "person-a")


def _zustand():
    return {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        _BAUM, _ANGABEN, "Schluessel-0123456789abcd", now=time.time(), caller="person-a")}}


# ── Werkzeuge ─────────────────────────────────────────────────────────────────────────────

def test_die_plan_werkzeuge_sind_kuratierend_und_zweistufig():
    for name in (_BAUM, "wlo_add_to_collections"):
        assert name in CURATION_TOOLS and name in CONFIRMABLE_TOOLS, name
        assert any(d["function"]["name"] == name for d in CURATION_TOOL_DEFINITIONS), name
    out = validate_tool_args(_BAUM, {**_ANGABEN, "onExisting": "merge"})
    assert out["tree"] == _ANGABEN["tree"] and out["onExisting"] == "merge"
    out = validate_tool_args("wlo_add_to_collections",
                             {"pairs": [{"nodeId": "m-1", "collectionId": "c-1"}]})
    assert out["pairs"] == [{"nodeId": "m-1", "collectionId": "c-1"}]


# ── Einlösen ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ein_unfertiger_plan_zeigt_den_stand_und_den_knopf_weiter(_rand, monkeypatch):
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(_plan_antwort(False)))
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert "1 von 2" in antwort.content and _PLAN not in antwort.content
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    offen = zustand["entities"][plan_fortsetzen.KEY]
    assert offen["token"] == _PLAN and offen["tool"] == _BAUM and offen["caller"] == "person-a"
    assert offen["args"] == _ANGABEN


@pytest.mark.asyncio
async def test_ein_fertiger_plan_braucht_keinen_knopf(_rand, monkeypatch):
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(_plan_antwort(True, 2, 2)))
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert "2 von 2" in antwort.content and not antwort.quick_replies
    assert plan_fortsetzen.KEY not in zustand["entities"]


@pytest.mark.asyncio
async def test_zu_viele_plaene_verbraucht_die_freigabe(_rand, monkeypatch):
    """``too_many_plans`` — nichts geschrieben. Review M5, Befund 2: der Merkposten bleibt
    verbraucht (jeder Folgezug verwürfe ihn), der Text kündigt eine neue Vorschau an."""
    fehler = McpAntwort("MCP error [too_many_plans]: fünf offen", "tool", "too_many_plans",
                        {"code": "too_many_plans", "message": "fünf offen"})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(fehler))
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.content == bot_text("de", "write.tooManyPlans")
    assert "_pending_write" not in zustand["entities"] and not antwort.quick_replies


# ── Weiter ────────────────────────────────────────────────────────────────────────────────

def _mit_plan():
    return {"persona_id": "P-AND", "entities": {plan_fortsetzen.KEY: {
        "tool": _BAUM, "args": _ANGABEN, "token": _PLAN, "caller": "person-a",
        "minted_at": time.time()}}}


@pytest.mark.asyncio
async def test_weiter_setzt_mit_dem_schluessel_des_plans_fort(_rand, monkeypatch):
    mcp = _Antworten(_plan_antwort(True, 2, 2))
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    zustand = _mit_plan()
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    [(tool, args)] = mcp.calls
    assert tool == _BAUM and args == {**_ANGABEN, "continuationToken": _PLAN}
    assert "2 von 2" in antwort.content and plan_fortsetzen.KEY not in zustand["entities"]


@pytest.mark.asyncio
async def test_weiter_nur_fuer_dieselbe_person(_rand, monkeypatch):
    mcp = _Antworten()
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    monkeypatch.setattr(plan_fortsetzen, "aufrufer_kennung", lambda: "person-b")
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION),
                                           _mit_plan())
    assert mcp.calls == [] and antwort.content == bot_text("de", "write.planNone")


@pytest.mark.asyncio
async def test_weiter_nur_mit_schreibrecht(_rand, monkeypatch):
    mcp = _Antworten()
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    monkeypatch.setattr(plan_fortsetzen, "schreiben_erlaubt", lambda: False)
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION),
                                           _mit_plan())
    assert mcp.calls == [] and antwort.content == bot_text("de", "write.loginNeeded")


@pytest.mark.asyncio
async def test_ein_abgelaufener_plan_wird_gesagt(_rand, monkeypatch):
    fehler = McpAntwort("MCP error [plan_expired]: weg", "tool", "plan_expired",
                        {"code": "plan_expired", "message": "weg"})
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", _Antworten(fehler))
    zustand = _mit_plan()
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert antwort.content == bot_text("de", "write.planExpired")
    assert plan_fortsetzen.KEY not in zustand["entities"]


def test_weiter_ist_eine_direktaktion_hinter_der_pruefung():
    from boerdi.graph.nodes.preflight import _DIRECT_ACTIONS

    assert plan_fortsetzen.AKTION in _DIRECT_ACTIONS


# ── Review M5 ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_weiter_prueft_wie_das_einloesen(_rand, monkeypatch):
    """Befund 1: ein im Studio verborgenes Werkzeug wird nicht fortgesetzt — und nie mehr."""
    mcp = _Antworten()
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    monkeypatch.setattr(wa_mod, "verborgene_werkzeuge", lambda: frozenset({_BAUM}))
    zustand = _mit_plan()
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert mcp.calls == [] and antwort.content == bot_text("de", "write.planBlocked")
    assert plan_fortsetzen.KEY not in zustand["entities"] and antwort.debug.tools_called == []


@pytest.mark.asyncio
async def test_zu_viele_plaene_zeigt_den_eigenen_offenen_plan(_rand, monkeypatch):
    fehler = McpAntwort("MCP error [too_many_plans]: fünf offen", "tool", "too_many_plans",
                        {"code": "too_many_plans", "message": "fünf offen"})
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", _Antworten(fehler))
    zustand = _zustand()
    zustand["entities"][plan_fortsetzen.KEY] = _mit_plan()["entities"][plan_fortsetzen.KEY]
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]


@pytest.mark.asyncio
@pytest.mark.parametrize("art", ["timeout", "transport"])
async def test_ohne_antwort_beim_einloesen_bleibt_der_plan_fortsetzbar(_rand, monkeypatch, art):
    """Befund 3: der Bestätigungsschlüssel setzt einen Plan fort, dessen Antwort verloren ging."""
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort",
                        _Antworten(McpAntwort("MCP error: zu langsam", art)))
    zustand = _zustand()
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert antwort.content == bot_text("de", "write.planUnclearStart")
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    offen = zustand["entities"][plan_fortsetzen.KEY]
    assert offen["token"] == "Schluessel-0123456789abcd" and offen["args"] == _ANGABEN


@pytest.mark.asyncio
async def test_weiter_ohne_antwort_behaelt_den_plan(_rand, monkeypatch):
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort",
                        _Antworten(McpAntwort("MCP error: zu langsam", "timeout")))
    zustand = _mit_plan()
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    assert zustand["entities"][plan_fortsetzen.KEY]["token"] == _PLAN


@pytest.mark.asyncio
async def test_weiter_waehrend_ein_anderer_aufruf_arbeitet(_rand, monkeypatch):
    laeuft = _plan_antwort(False)
    laeuft.strukturiert["inProgress"] = True
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", _Antworten(laeuft))
    zustand = _mit_plan()
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    assert plan_fortsetzen.KEY in zustand["entities"]


@pytest.mark.asyncio
async def test_weiter_nach_der_frist_nicht_mehr(_rand, monkeypatch):
    mcp = _Antworten()
    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    zustand = _mit_plan()
    zustand["entities"][plan_fortsetzen.KEY]["minted_at"] -= plan_fortsetzen.PLAN_TTL_SECONDS + 1
    antwort = await plan_fortsetzen.weiter(_SESSION, _req(action=plan_fortsetzen.AKTION), zustand)
    assert mcp.calls == [] and antwort.content == bot_text("de", "write.planNone")
    assert plan_fortsetzen.KEY not in zustand["entities"]


def test_ein_fertiger_plan_raeumt_keinen_anderen_ab():
    """Befund 4."""
    anderer = {"tool": "wlo_add_to_collections", "args": {"pairs": []}, "token": "t",
               "caller": "a", "minted_at": time.time()}
    entities = {plan_fortsetzen.KEY: dict(anderer)}
    assert not plan_fortsetzen.merke(entities, _BAUM, _ANGABEN, _plan_antwort(True, 2, 2),
                                     caller="a", now=time.time())
    assert entities[plan_fortsetzen.KEY] == anderer


def test_die_frist_kommt_vom_server():
    entities: dict = {}
    plan_fortsetzen.merke(entities, _BAUM, _ANGABEN, _plan_antwort(False), caller="a",
                          now=time.time())
    assert entities[plan_fortsetzen.KEY]["expires_at"] == datetime(
        2026, 11, 7, 13, 0, tzinfo=UTC).timestamp()


def test_das_modell_setzt_nie_selbst_fort():
    """Befund 5: der Fortsetzungs-Schlüssel geht wie der Bestätigungsschlüssel nur von uns aus."""
    from boerdi.domain.write_confirm import strip_confirm_token

    assert strip_confirm_token(_BAUM, {**_ANGABEN, "continuationToken": _PLAN}) == _ANGABEN
    assert not any("continuationToken" in d["function"]["parameters"]["properties"]
                   for d in CURATION_TOOL_DEFINITIONS)


def test_die_studio_ansicht_zeigt_keinen_plan_schluessel():
    """Befund 6."""
    from boerdi.domain.write_anzeige import entities_for_display

    gezeigt = entities_for_display(_mit_plan()["entities"])
    assert gezeigt[plan_fortsetzen.KEY]["token"] != _PLAN


def test_ein_abgelaufener_plan_faellt_zu_zugbeginn_weg():
    """Befund 7."""
    entities = _mit_plan()["entities"]
    plan_fortsetzen.abgelaufen_weg(entities, time.time())
    assert plan_fortsetzen.KEY in entities
    plan_fortsetzen.abgelaufen_weg(entities, time.time() + plan_fortsetzen.PLAN_TTL_SECONDS + 1)
    assert plan_fortsetzen.KEY not in entities


def test_einen_plan_loest_nur_der_vorlauf_ein():
    """Re-Review, Befund 1: die Agent-Schleife (``execute``) setzt für einen Plan keinen Schlüssel
    ein — sonst liefe er ohne Merkposten und ohne „Weiter anlegen“."""
    from boerdi.services.agent_write import WriteGate

    gate = WriteGate("execute")
    gate.observe(_BAUM, _ANGABEN,
                 "Vorschau … mit confirmToken: Schluessel-0123456789abcd wiederholen.")
    assert gate.offene_abnahme() is not None                 # die Vorschau ist gemerkt …
    assert "confirmToken" not in gate.prepare(_BAUM, dict(_ANGABEN))   # … eingelöst wird nicht


@pytest.mark.parametrize(("tool", "angaben", "eingesetzt"), [
    (_BAUM, _ANGABEN, False),
    ("wlo_rename_collection", {"nodeId": "c-1", "title": "Optik"}, True),   # Gegenprobe
])
def test_die_werkzeug_schleife_loest_keinen_plan_ein(monkeypatch, tool, angaben, eingesetzt):
    """Review M6 (Befund 8): der Fingerabdruck-Weg setzt für einen Plan keinen Schlüssel ein."""
    import json

    from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

    mcp = _OutcomeFake()
    zustand = {"turn_count": 3, "entities": {"_pending_write": remember_pending(
        tool, angaben, "Schluessel-0123456789abcd", now=time.time(), caller="")}}
    _run_loop(monkeypatch, [_resp_tools([("c1", tool, json.dumps(angaben))]), _resp_text("ok")],
              outcome=mcp, session_state=zustand, message="Ja, so ausführen")
    [(name, args)] = mcp.calls
    assert name == tool and ("confirmToken" in args) is eingesetzt


@pytest.mark.asyncio
async def test_ein_zu_grosser_plan_wird_nicht_wortlos_neu_vorgelegt(_rand, monkeypatch):
    """Review M6 (Befund 6): ohne gemerkte Angaben kein stilles Wiedervorlegen."""
    mcp = _Antworten()
    monkeypatch.setattr(wa_mod, "call_mcp_tool_antwort", mcp)
    zustand = _zustand()
    zustand["entities"]["_pending_write"].pop("args")
    antwort = await redeem_write_approval(_SESSION, _req(), zustand)
    assert mcp.calls == [] and antwort.content == bot_text("de", "write.planTooLarge")
    assert "_pending_write" not in zustand["entities"]
