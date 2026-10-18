"""AG-5 — Einbettungen im Gold-Lauf testbar machen (Plan 2026-09-26 §8).

Bis hier konnte der Gold-Runner keinen Einbettungs-Kontext nachstellen:
Seitenkontext, Sammlung, ``master_skill``, ``tool_mode`` und Gastgeber-Auftrag
reisten nie mit, die Skill-Pfade blieben damit ungetestet. Dazu kommen die
Prüfart ``tools_max`` und die Skills, die ein Zug geladen hat, im Bericht.
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from tests.test_golden_runner import _flow, rg

_BOT = {"content": "Hier ist die Antwort.", "quick_replies": ["a"]}


# ── T1: das environment eines Flows reist mit ──────────────────────────────


def test_das_environment_eines_flows_reist_mit_jedem_zug(monkeypatch) -> None:
    gesehen: list = []

    async def fake_post(url, message, session_id, headers=None, environment=None):
        gesehen.append(environment)
        return {**_BOT, "debug": {}}

    monkeypatch.setattr(rg, "post_chat", fake_post)
    umgebung = {"master_skill": False, "tool_mode": "read-only"}
    asyncio.run(rg.run_flows("http://x/api/chat",
                             [{**_flow({}, {}), "environment": umgebung}]))
    assert gesehen == [umgebung, umgebung]


def test_post_chat_schickt_das_environment_nur_wenn_gesetzt(monkeypatch) -> None:
    """Ohne Kontext bleibt der Rumpf, wie er war — kein leeres ``environment``,
    das serverseitig die Vorgaben überschriebe."""
    koerper: list = []

    def antwort(request: httpx.Request) -> httpx.Response:
        koerper.append(json.loads(request.content))
        return httpx.Response(200, json={"content": "ok"})

    echt = httpx.AsyncClient
    monkeypatch.setattr(rg.httpx, "AsyncClient", lambda **kw: echt(
        transport=httpx.MockTransport(antwort), **kw))
    asyncio.run(rg.post_chat("http://x/api/chat", "hi", "eval-1"))
    asyncio.run(rg.post_chat("http://x/api/chat", "hi", "eval-1",
                             environment={"tool_mode": "read-only"}))
    assert koerper == [
        {"session_id": "eval-1", "message": "hi"},
        {"session_id": "eval-1", "message": "hi",
         "environment": {"tool_mode": "read-only"}},
    ]


# ── T3: Höchstzahl der Werkzeugaufrufe ─────────────────────────────────────


def test_tools_max_zaehlt_die_werkzeugaufrufe() -> None:
    passt = rg.check_golden_turn({"tools_max": 2}, _BOT, {"tools_called": ["a", "b"]})
    zu_viel = rg.check_golden_turn({"tools_max": 2}, _BOT,
                                   {"tools_called": ["a", "b", "a"]})
    ohne = rg.check_golden_turn({}, _BOT, {"tools_called": ["a", "b", "c"]})
    assert passt["checks"]["tools_max"] is True
    assert zu_viel["checks"]["tools_max"] is False
    assert ohne["checks"]["tools_max"] is None
    assert zu_viel["expected"]["tools_max"] == 2
    assert zu_viel["observed"]["tool_calls"] == 3


def test_tools_max_null_heisst_ohne_werkzeug() -> None:
    assert rg.check_golden_turn(
        {"tools_max": 0}, _BOT, {"tools_called": []})["checks"]["tools_max"] is True
    assert rg.check_golden_turn(
        {"tools_max": 0}, _BOT, {"tools_called": ["a"]})["checks"]["tools_max"] is False


@pytest.mark.parametrize("unsinn", ["zwei", -1, 1.5, True])
def test_tools_max_weist_unsinn_laut_ab(unsinn) -> None:
    """Wie ``chat_headers``: ein Tippfehler im Flow darf nicht still als „nicht
    geprüft" durchgehen — sonst glaubt der Autor an einen Deckel, den es nicht
    gibt."""
    with pytest.raises(ValueError, match="tools_max"):
        rg.check_golden_turn({"tools_max": unsinn}, _BOT, {})


def test_tools_max_zaehlt_hart() -> None:
    assert "tools_max" in rg.GOLDEN_CATS and "tools_max" in rg.GOLDEN_HARD


# ── T5: die geladenen Skills stehen im Bericht ─────────────────────────────


def test_die_geladenen_skills_stehen_im_bericht() -> None:
    debug = {"tools_called": ["get_skill"], "trace": [
        {"step": "agent_round", "label": "Runde 1: get_skill", "data": {}},
        {"step": "skill", "label": "Stunde planen",
         "data": {"node_id": "n-1", "titel": "Stunde planen"}},
        {"step": "skill", "label": "n-2", "data": {"node_id": "n-2", "titel": ""}},
        {"step": "agent_stop", "label": "Ende: text", "data": {}},
    ]}
    got = rg.check_golden_turn({}, _BOT, debug)
    # Der Titel, wo es einen gibt; sonst die Kennung — nie eine leere Zeile.
    assert got["observed"]["skills"] == ["Stunde planen", "n-2"]


def test_ohne_spur_keine_skills() -> None:
    assert rg.check_golden_turn({}, _BOT, {})["observed"]["skills"] == []


# -- T2: das Feld steht im Schema -----------------------------------------------


def test_goldflow_fuehrt_das_environment_als_feld() -> None:
    """Als Feld und nicht nur als geduldetes Extra (``extra="allow"``): das
    Studio-Formular rendert, was im Schema steht, ein Extra bliebe dort
    unsichtbar und liesse sich nur als YAML pflegen."""
    from boerdi.domain.config_models.knowledge import GoldFlow

    assert "environment" in GoldFlow.model_json_schema()["properties"]
    flow = GoldFlow.model_validate({"id": "F", "environment": {"tool_mode": "read-only"}})
    assert flow.environment == {"tool_mode": "read-only"}
    assert GoldFlow().environment == {}


# -- Review 2026-09-26: ein falscher Deckel faellt VOR dem Lauf auf ------------


def test_validate_flows_meldet_einen_falschen_deckel_mit_ort() -> None:
    kaputt = [{"id": "F1", "erwartung": "e",
               "turns": [{"message": "a", "anwendungsfall": "suchen", "expect": {}},
                         {"message": "b", "anwendungsfall": "suchen",
                          "expect": {"tools_max": "3"}}]}]
    with pytest.raises(ValueError, match=r"F1.*2.*tools_max"):
        rg.validate_flows(kaputt)
    rg.validate_flows([{"id": "F2", "erwartung": "e",
                        "turns": [{"message": "a", "anwendungsfall": "suchen",
                                   "expect": {"tools_max": 3}}]}])


def test_load_flows_prueft_die_deckel_vor_dem_lauf(tmp_path) -> None:
    pfad = tmp_path / "flows.yaml"
    pfad.write_text("version: 2\nflows:\n  - id: F1\n    erwartung: e\n    turns:\n"
                    "      - message: a\n        anwendungsfall: suchen\n"
                    "        expect: {tools_max: zwei}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="tools_max"):
        rg.load_flows(pfad)
