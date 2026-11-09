"""Paket S4 (2026-11-08): ein Plan (W2/W3, Sammlungsbaum, Massen-Aufnahme) als Freigabe-Schritt.

- Vorgelegt und eingelöst wie jeder Freigabe-Schritt (``freigabe_zug``).
- Ist der Plan nach dem ersten Abschnitt noch offen, trägt er die Marke des Laufs; der Lauf wartet,
  unter den Antworten steht „Plan fortsetzen“.
- Wird er mit „Plan fortsetzen“ fertig, geht der Lauf weiter (Ergebnis → Teil ``schreibt``).
- Läuft er ab oder gilt nicht mehr, wartet der Lauf mit „Vorschau erneut zeigen“.
- „Ablauf abbrechen“ verwirft auch den offenen Plan; was er schon erledigt hat, bleibt.
"""

from __future__ import annotations

import asyncio
import copy
import time

import pytest

from boerdi.i18n.bot_text import bot_text
from boerdi.services import plan_fortsetzen
from boerdi.services.ablauf import ausloeser, freigabe_zug, treiber
from boerdi.services.mcp.client import McpAntwort
from tests.test_ablauf_zug import _S
from tests.test_paket_s import _FREIGABE
from tests.test_paket_s_zug import (  # noqa: F401
    _SCHLUESSEL,
    _SITZUNG,
    _ja,
    _lauf,
    _req,
    _teile,
    im_zug,
)

W2 = "wlo_attach_fulltexts"
_PLAN = "Plan-0123456789abcdef"
_SCHRITTE = [
    {"id": "anhaengen", "typ": "werkzeug", "werkzeug": W2, "freigabe": _FREIGABE,
     "argumente": {"items": [{"nodeId": "n-1", "markdown": "# A", "source": "manual"},
                             {"nodeId": "n-2", "markdown": "# B", "source": "manual"}]},
     "schreibt": "angehaengt", "bei_fehler": "schade"},
    {"id": "fertig", "typ": "ende", "text": {"de": "Alle angehängt."}},
    {"id": "schade", "typ": "ende", "text": {"de": "Nicht angehängt."}},
]


def _plan(complete: bool, done: int) -> McpAntwort:
    sc = {"complete": complete, "progress": {"done": done, "total": 2},
          "items": [{"nodeId": "n-1", "status": "attached"}]}
    text = f"{done} von 2 Volltexten angehängt."
    if not complete:
        sc |= {"continuationToken": _PLAN, "expiresAt": "2099-01-01T00:00:00Z"}
        text += f"\n\nNoch nicht fertig. Derselbe Aufruf mit continuationToken: {_PLAN} setzt fort."
    return McpAntwort(text, strukturiert=sc)


@pytest.fixture
def plan_zug(im_zug, monkeypatch):  # noqa: F811
    katalog = {"ablaeufe": [{"id": "anhaengen", "titel": {"de": "Anhängen"}, "aktiv": True,
                             "ausloeser": [{"art": "knopf"}], "voraussetzungen": ["anmeldung"],
                             "schritte": copy.deepcopy(_SCHRITTE)}]}
    monkeypatch.setattr(ausloeser, "area", lambda key: katalog if key == ausloeser.BEREICH else {})

    async def nichts(*_a, **_k):
        return None

    for name in ("update_session", "save_message"):
        monkeypatch.setattr(plan_fortsetzen, name, nichts)
    monkeypatch.setattr(plan_fortsetzen, "schreiben_erlaubt", lambda: True)
    monkeypatch.setattr(plan_fortsetzen, "aufrufer_kennung", lambda: "person-a")
    fortgesetzt: list = []
    weitere: list = []

    async def mcp(tool, args, **_k):
        fortgesetzt.append((tool, dict(args)))
        return weitere.pop(0)

    monkeypatch.setattr(plan_fortsetzen, "call_mcp_tool_antwort", mcp)
    im_zug.fortgesetzt, im_zug.weitere = fortgesetzt, weitere
    return im_zug


def _starte(state):
    from boerdi.services.ablauf import zug

    return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION,
                                              action_params={"ablauf": "anhaengen"}), state))


def _fortsetzen(state):
    async def lauf():
        vorher = state["entities"].get(plan_fortsetzen.KEY)
        anfrage = _req(action=plan_fortsetzen.AKTION)
        antwort = await plan_fortsetzen.weiter(_S(), anfrage, state)
        return await freigabe_zug.nach_plan(_S(), anfrage, state, vorher, antwort)

    return asyncio.run(lauf())


def test_s4_ein_plan_laeuft_ueber_plan_fortsetzen_zu_ende(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    plan_zug.antworten.append(_plan(False, 1))
    antwort = _ja(state)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    offen = state["entities"][plan_fortsetzen.KEY]
    assert offen["token"] == _PLAN and offen[freigabe_zug.MARKE]["ablauf"] == "anhaengen"
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE
    assert freigabe_zug.weiter_knopf(_SITZUNG, state, "de") == plan_fortsetzen.knopf("de")
    plan_zug.weitere.append(_plan(True, 2))
    antwort = _fortsetzen(state)
    [(tool, args)] = plan_zug.fortgesetzt
    assert tool == W2 and args["continuationToken"] == _PLAN
    assert "2 von 2" in antwort.content and "Alle angehängt." in antwort.content
    assert _lauf(state)["status"] == "fertig"
    assert _teile(plan_zug)["angehaengt"]["wert"]["complete"] is True
    assert plan_fortsetzen.KEY not in state["entities"]


def test_s4_die_marke_reist_von_abschnitt_zu_abschnitt(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    plan_zug.antworten.append(_plan(False, 1))
    _ja(state)
    plan_zug.weitere.append(_plan(False, 1))
    antwort = _fortsetzen(state)
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    assert state["entities"][plan_fortsetzen.KEY][freigabe_zug.MARKE]["schritt"] == "anhaengen"
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE


def test_s4_ein_abgelaufener_plan_bietet_die_vorschau_neu(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    plan_zug.antworten.append(_plan(False, 1))
    _ja(state)
    plan_zug.weitere.append(McpAntwort("MCP error [plan_expired]: weg", "tool", "plan_expired",
                                       {"code": "plan_expired", "message": "weg"}))
    antwort = _fortsetzen(state)
    assert antwort.content.startswith(bot_text("de", "write.planExpired"))
    assert antwort.quick_replies[0].split("|")[2] == freigabe_zug.AKTION_ERNEUT
    assert _lauf(state)["status"] == treiber.WARTET_FREIGABE


def test_s4_abbrechen_verwirft_den_offenen_plan(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    plan_zug.antworten.append(_plan(False, 1))
    _ja(state)
    antwort = asyncio.run(freigabe_zug.abbrechen(_S(), _req(
        action=freigabe_zug.AKTION_ABBRECHEN, action_params={"ablauf": "anhaengen"}), state))
    assert antwort.content == bot_text("de", "action.ablauf.freigabeAbgebrochenPlan")
    assert plan_fortsetzen.KEY not in state["entities"] and _lauf(state)["status"] == "abgebrochen"


def test_s4_ein_plan_im_ersten_abschnitt_fertig_geht_gleich_weiter(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    plan_zug.antworten.append(_plan(True, 2))
    antwort = _ja(state)
    assert "Alle angehängt." in antwort.content and _lauf(state)["status"] == "fertig"


def test_s4_ein_plan_ohne_marke_bleibt_wie_er_war(plan_zug):
    """Ein Plan aus dem Chat (ohne Lauf) — der Nachlauf ändert nichts."""
    state: dict = {"entities": {plan_fortsetzen.KEY: {
        "tool": W2, "args": {"items": []}, "token": _PLAN, "caller": "person-a",
        "minted_at": time.time()}}}
    plan_zug.weitere.append(_plan(True, 2))
    antwort = _fortsetzen(state)
    assert "2 von 2" in antwort.content and not antwort.quick_replies
    assert _SCHLUESSEL not in antwort.content


# ── Review S4 ─────────────────────────────────────────────────────────────────────────────────

def _offen(state, plan_zug):
    _starte(state)
    plan_zug.antworten.append(_plan(False, 1))
    _ja(state)


def test_review_s4_keine_neue_vorschau_solange_der_plan_laeuft(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    antwort = asyncio.run(freigabe_zug.erneut(_S(), _req(
        action=freigabe_zug.AKTION_ERNEUT, action_params={"ablauf": "anhaengen"}), state))
    assert antwort.content == bot_text("de", "write.planStillOpen")
    assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
    assert len(plan_zug.vorgelegt) == 1                  # nicht noch einmal vorgelegt


def test_review_s4_abbrechen_nach_abgelaufenem_plan_sagt_dass_er_schrieb(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    state["entities"].pop(plan_fortsetzen.KEY)           # abgelaufen
    antwort = asyncio.run(freigabe_zug.abbrechen(_S(), _req(
        action=freigabe_zug.AKTION_ABBRECHEN, action_params={"ablauf": "anhaengen"}), state))
    assert antwort.content == bot_text("de", "action.ablauf.freigabeAbgebrochenPlan")


def test_review_s4_eine_ablehnung_mitten_im_plan_geht_zu_bei_fehler(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    plan_zug.weitere.append(McpAntwort("MCP error [refused]: nein", "tool", "refused",
                                       {"code": "refused", "message": "nein"}))
    antwort = _fortsetzen(state)
    assert "Nicht angehängt." in antwort.content and _lauf(state)["status"] == "fertig"


def test_review_s4_ausgelastet_beim_fortsetzen_laesst_warten(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    for antwort_mcp in (McpAntwort("MCP error: voll", "busy"),
                        McpAntwort("MCP error: keine Antwort", "timeout")):
        plan_zug.weitere.append(antwort_mcp)
        antwort = _fortsetzen(state)
        assert antwort.quick_replies == [plan_fortsetzen.knopf("de")]
        assert plan_fortsetzen.KEY in state["entities"]
        assert _lauf(state)["status"] == treiber.WARTET_FREIGABE


def test_review_s4_alle_eintraege_gescheitert_geht_zu_bei_fehler(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    gescheitert = _plan(True, 2)
    gescheitert.strukturiert["items"] = [{"nodeId": "n-1", "status": "failed"},
                                         {"nodeId": "n-2", "status": "failed"}]
    plan_zug.weitere.append(gescheitert)
    antwort = _fortsetzen(state)
    assert "Nicht angehängt." in antwort.content


def test_review_s4_zu_zugbeginn_abgelaufen_bietet_die_vorschau(plan_zug):
    state: dict = {"entities": {}}
    _offen(state, plan_zug)
    state["entities"].pop(plan_fortsetzen.KEY)           # ``abgelaufen_weg`` in ``setup``
    antwort = _fortsetzen(state)
    assert antwort.content == bot_text("de", "write.planNone")
    assert antwort.quick_replies[0].split("|")[2] == freigabe_zug.AKTION_ERNEUT


def test_review_s4_ein_fremder_plan_gilt_nicht_als_der_des_laufs(plan_zug):
    state: dict = {"entities": {}}
    _starte(state)
    state["entities"][plan_fortsetzen.KEY] = {
        "tool": W2, "args": {}, "token": "Plan-fremd-0123456789", "caller": "person-b",
        "minted_at": time.time()}
    plan_zug.antworten.append(_plan(True, 2))
    antwort = _ja(state)
    assert "Alle angehängt." in antwort.content and _lauf(state)["status"] == "fertig"

