"""Paket U1-e (E-6): Direktaktion ``show_collection_tree`` — „Unterthemen öffnen“ im Themenbaum.

Ein Knopf im Baum fragt einen neuen Baum ab einem Knoten an. Der Zug läuft ohne KI durch
Drosselung und Sicherheitsprüfung (``preflight``) wie ``browse_collection``; die Antwort trägt
einen neuen ``ui_themenbaum``-Block, der auch im Verlauf steht. Gespeichert wird nur der
Begleitsatz — die Knoten gehen auch über den Verlauf nicht an die KI.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.publikum import ui_aus_gespeichert
from boerdi.api.schemas import ChatRequest, ChatResponse, Environment, SafetyDecision
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes.preflight import preflight
from boerdi.services import themenbaum_aktion
from boerdi.ui_module import datenquelle
from tests.test_preflight_node import (
    _SESSION,
    _ctx,
    _patch_db,
    _patch_handlers,
    _patch_safety,
    _Spy,
)
from tests.test_ui_themenbaum import ALLE_KNOTEN, THEMENBAUM, WERKZEUG, _payload, _Rufer


class _SaveSpy:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def __call__(self, session, session_id, role, content, cards=None, debug=None):
        self.calls.append({"role": role, "content": content, "debug": debug})


def _req(locale=None, **params) -> ChatRequest:
    env = {"environment": Environment(locale=locale)} if locale else {}
    return ChatRequest(session_id="bb-1", message="Unterthemen von Algebra",
                       action="show_collection_tree", action_params=params, **env)


@pytest.fixture
def save(monkeypatch):
    spy = _SaveSpy()
    monkeypatch.setattr(themenbaum_aktion, "save_message", spy)
    return spy


def _laufen(req) -> ChatResponse:
    return asyncio.run(themenbaum_aktion.handle_show_collection_tree(
        _SESSION, req, {}, blocked_tools=[]))


def test_die_aktion_liefert_einen_neuen_baum_ab_dem_knoten(monkeypatch, save):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)

    resp = _laufen(_req(collection_id="bbbb-2222", title="Algebra"))

    assert rufer.calls == [(WERKZEUG, {"nodeId": "bbbb-2222", "depth": 2, "maxResults": 31})]
    [block] = resp.ui.ui_bloecke
    assert block.modul == THEMENBAUM and block.daten["titel"] == "Algebra"
    assert resp.content == "Hier sind die Unterthemen:"   # Titel im Block (Review U1-e, 11)
    assert resp.debug.pattern == "ACTION: show_collection_tree"
    assert resp.debug.tools_called == [WERKZEUG]


def test_der_block_steht_im_verlauf_der_text_ohne_knoten(monkeypatch, save):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    resp = _laufen(_req(collection_id="bbbb-2222", title="Algebra"))

    [gespeichert] = save.calls
    [block] = resp.ui.ui_bloecke
    assert gespeichert["role"] == "assistant"
    wieder = ui_aus_gespeichert(gespeichert["debug"]).ui_bloecke
    assert [(b.block_id, b.modul, b.daten) for b in wieder] == [
        (block.block_id, block.modul, block.daten)]
    # Der Text der Nachricht ist das, was ein Folgezug als Verlauf liest.
    for teil in ALLE_KNOTEN[1:]:          # „Algebra“ ist der Titel der Aktion selbst
        assert teil not in gespeichert["content"]


@pytest.mark.parametrize("kennung", ["", None, "bad id", "x" * 200, 42])
def test_eine_unbrauchbare_kennung_ruft_nichts(monkeypatch, save, kennung):
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    resp = _laufen(_req(collection_id=kennung, title="Algebra"))
    assert rufer.calls == [] and resp.ui.ui_bloecke == []
    assert resp.content


def test_ein_fehler_des_werkzeugs_ergibt_einen_hinweis_mit_wiederholen(monkeypatch, save):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer("MCP error: weg", "transport"))
    resp = _laufen(_req(collection_id="bbbb-2222", title="Algebra"))
    assert resp.ui.ui_bloecke == []
    assert "Algebra" in resp.content
    assert any(q.startswith("__action__|") and "show_collection_tree" in q
               for q in resp.quick_replies)


def test_englisch_und_ohne_titel(monkeypatch, save):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer(json.dumps(_payload(results=[]))))
    resp = _laufen(_req(locale="en", collection_id="bbbb-2222"))
    [block] = resp.ui.ui_bloecke
    assert "titel" not in block.daten or block.daten["titel"]
    assert resp.content == "Here are the subtopics:"


# ── Verteiler (preflight) ─────────────────────────────────────────────────


def test_der_verteiler_kennt_die_aktion_und_prueft_sie_wie_die_anderen(monkeypatch):
    _patch_handlers(monkeypatch)
    baum = _Spy(ChatResponse(session_id="bb-1", content="BAUM-OK"))
    monkeypatch.setattr(pf_mod, "handle_show_collection_tree", baum)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    out = asyncio.run(preflight(_ctx("show_collection_tree", collection_id="bbbb-2222",
                                     title="Algebra"), _SESSION))

    assert out.early_response.content == "BAUM-OK"
    assert len(baum.calls) == 1 and len(safety.calls) == 1


def test_bei_hohem_risiko_wird_die_aktion_geblockt(monkeypatch):
    _patch_handlers(monkeypatch)
    baum = _Spy(ChatResponse(session_id="bb-1", content="BAUM-OK"))
    monkeypatch.setattr(pf_mod, "handle_show_collection_tree", baum)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))

    out = asyncio.run(preflight(_ctx("show_collection_tree", collection_id="bbbb-2222"), _SESSION))
    assert baum.calls == []
    assert out.early_response.debug.pattern == "SAFETY: blocked_direct_action"
