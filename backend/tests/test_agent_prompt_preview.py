"""ST-8d: die Vorschau des Prompt-Anfangs der Agent-Schleife, für das Studio.

Die Vorschau taugt nur, wenn sie zeigt, was das Modell wirklich bekommt. Der
erste Test lässt deshalb ``respond_agent`` mit denselben Quellen laufen und
vergleicht Kopf und Master-Skill-Block Wort für Wort; der letzte Test tut dasselbe
für die Reihenfolge der Blöcke, die je Zug folgen.
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    PolicyDecision,
    SafetyDecision,
)
from boerdi.domain.config_models.engine import EngineArea
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import respond_agent as agent_mod
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.i18n.prompt_language import language_name
from boerdi.services import agent_prompt_preview as pv
from boerdi.services import agent_tools, agent_write
from boerdi.services.agent_knowledge import WISSENS_REGEL, wissen_werkzeug
from boerdi.services.agent_kopf import kopf
from boerdi.services.agent_loop import AgentRun

_RAG = {"Plattformwissen": {"description": "Was WLO ist"}}
_BLOCK = "## Master-Skill\nRahmen der Anlage\n\nText der Redaktion"


def _engine() -> EngineArea:
    return EngineArea(mode="agent")


def _zustand(**abweichung) -> dict:
    return {"enabled": True, "node_id": "k-1", "cached": True, "fetched_at": None,
            "length": 18, "sha256": "ab" * 32, "last_error": None, "ttl_seconds": 300,
            **abweichung}


@pytest.fixture()
def quellen(monkeypatch):
    """Dieselben Quellen für Vorschau und Zug; der Master-Skill ist an."""
    async def block(_ueberschreibung=None):
        return _BLOCK

    monkeypatch.setattr(pv, "load_engine", _engine)
    monkeypatch.setattr(pv, "load_rag_config", lambda: _RAG)
    # ``pv.master_skill`` ist dasselbe Modul wie ``agent_mod.master_skill``.
    monkeypatch.setattr(pv.master_skill, "prompt_block", block)
    monkeypatch.setattr(pv.master_skill, "zustand", _zustand)
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)


async def test_kopf_und_master_skill_sind_wortgleich_mit_dem_zug(quellen, monkeypatch):
    gesehen: dict = {}

    # Die ECHTE Signatur von ``run_agent_loop`` (A4b-Regel für Attrappen).
    async def _loop(*, messages, tools, limits, usage_acc=None, progress=None,
                    clock=None, on_tool_result=None, wissen=None, on_offene_abnahme=None,
                    on_token=None, start=None):
        gesehen["messages"] = [dict(m) for m in messages]
        return AgentRun(text="ok", stop_reason="text", iterations=1)

    monkeypatch.setattr(agent_mod, "run_agent_loop", _loop)
    monkeypatch.setattr(agent_mod, "load_engine", _engine)
    monkeypatch.setattr(agent_write, "has_personal_auth", lambda: False)
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message="hallo"))
    ctx.env = ctx.req.environment.model_dump()
    ctx.history = []
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.policy = PolicyDecision()
    ctx.classification = ClassificationResult()
    ctx.session_state = {"persona_id": "P-AND", "entities": {}}
    ctx.rag_config = _RAG

    await respond_agent(ctx)
    kette = (await pv.prompt_vorschau("de"))["chain"]

    assert kette[0]["text"] == gesehen["messages"][0]["content"]
    assert kette[1]["text"] == gesehen["messages"][1]["content"]
    assert WISSENS_REGEL in kette[0]["text"]


async def test_ohne_wissensbereiche_steht_keine_wissensregel_im_kopf(quellen, monkeypatch):
    monkeypatch.setattr(pv, "load_rag_config", lambda: {})
    kopf_block = (await pv.prompt_vorschau("de"))["chain"][0]
    assert kopf_block == {"id": "head", "text": kopf(_engine().agent_rolle, "de"),
                          "chars": len(kopf(_engine().agent_rolle, "de"))}


async def test_die_sprache_der_vorschau_ist_die_des_widgets(quellen):
    deutsch = (await pv.prompt_vorschau("de"))["chain"][0]["text"]
    englisch = (await pv.prompt_vorschau("en"))["chain"][0]["text"]
    assert language_name("en") in englisch
    assert deutsch != englisch


@pytest.mark.parametrize(("block", "zustand", "erwartet"), [
    (_BLOCK, _zustand(), {"state": "on", "chars": len(_BLOCK), "error": None}),
    (None, _zustand(enabled=False), {"state": "off", "chars": 0, "error": None}),
    (None, _zustand(node_id=""), {"state": "no_node", "chars": 0, "error": None}),
    (None, _zustand(last_error="Server lehnte ab: timeout"),
     {"state": "failed", "chars": 0, "error": "Server lehnte ab: timeout"}),
])
async def test_der_master_skill_sagt_warum_er_fehlt(quellen, monkeypatch, block, zustand, erwartet):
    async def fake(_ueberschreibung=None):
        return block

    monkeypatch.setattr(pv.master_skill, "prompt_block", fake)
    monkeypatch.setattr(pv.master_skill, "zustand", lambda: zustand)
    eintrag = (await pv.prompt_vorschau("de"))["chain"][1]
    assert eintrag["id"] == "master_skill"
    assert {k: eintrag[k] for k in erwartet} == erwartet
    assert eintrag["text"] == block
    assert eintrag["node_id"] == zustand["node_id"]


async def test_was_je_zug_folgt_steht_in_der_reihenfolge_des_zugs_ohne_text(quellen):
    folgend = (await pv.prompt_vorschau("de"))["chain"][2:]
    assert [b["id"] for b in folgend] == [
        "result_schema", "host_capabilities", "page_rules", "host_instruction",
        "skill_hints", "page_data", "prefetch", "history", "last_shown", "message",
    ]
    assert all(set(b) == {"id"} for b in folgend)


async def test_nennt_zahl_und_umfang_der_werkzeug_beschreibungen(quellen):
    werkzeuge = (await pv.prompt_vorschau("de"))["tools"]
    im_zug = agent_tools.build_agent_tools(
        include_submit=False, include_dokument=True, wissen_tool=wissen_werkzeug(_RAG))
    assert werkzeuge["count"] == len(im_zug)
    assert werkzeuge["chars"] > 1000


async def test_zaehlt_die_werkzeuge_einer_person_ohne_anmeldung(quellen, monkeypatch):
    # Paket 9 (Review Paket 7, NIT): mit dem Dienstkonto der Anlage zählte die
    # Vorschau die kuratierenden Werkzeuge mit — ein Zug ohne Anmeldung bekommt sie
    # nur, wenn das Studio das Gastkonto erlaubt (``schreibrecht``).
    from boerdi.services import schreibrecht

    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: True)
    monkeypatch.setattr(schreibrecht, "has_personal_auth", lambda: False)
    monkeypatch.setattr(schreibrecht.betriebsschalter, "gastkonto_schreibt", lambda: False)
    wissen = wissen_werkzeug(_RAG)
    ohne, mit = (agent_tools.build_agent_tools(
        allow_curation=kuratieren, include_submit=False, include_dokument=True,
        wissen_tool=wissen) for kuratieren in (False, True))
    assert len(mit) > len(ohne)  # sonst prüfte der Test nichts
    assert (await pv.prompt_vorschau("de"))["tools"]["count"] == len(ohne)


async def test_die_bloecke_je_zug_stehen_in_der_reihenfolge_des_echten_zugs(quellen, monkeypatch):
    """Review-Befund 2026-09-27: ``JE_ZUG`` ist eine Abschrift der Reihenfolge in
    ``respond_agent``. Dieser Test lässt einen Zug mit JEDEM Block laufen und
    vergleicht — ändert jemand die Kette, wird die Vorschau hier rot statt still
    falsch."""
    marken = {
        "host_capabilities": "<GRENZEN>", "page_rules": "<SEITENREGELN>",
        "page_data": "<SEITE>",
        "host_instruction": "<AUFTRAG>", "skill_hints": "<ANLEITUNGEN>",
        "history": "<VERLAUF>", "prefetch": "<VORABRUF>", "last_shown": "<ZULETZT>",
        "message": "<NACHRICHT>",
    }
    # Paket C: was die Person zuletzt gesehen hat — direkt vor ihrer Nachricht.
    monkeypatch.setattr(agent_mod, "zuletzt_gezeigt", lambda *_a, **_kw: marken["last_shown"])
    monkeypatch.setattr(agent_mod.host_capabilities, "prompt_block",
                        lambda **_kw: marken["host_capabilities"])
    # Paket B: feste Regeln im Systemteil, die Daten gerahmt vor dem Verlauf.
    monkeypatch.setattr(agent_mod.seitenkontext_prompt, "SEITEN_REGELN", marken["page_rules"])
    monkeypatch.setattr(agent_mod.seitenkontext_prompt, "seiten_daten",
                        lambda *_a, **_kw: marken["page_data"])
    monkeypatch.setattr(agent_mod.host_instruction, "prompt_block",
                        lambda *_a, **_kw: marken["host_instruction"])
    monkeypatch.setattr(agent_mod, "anleitungs_hinweis", lambda *_a, **_kw: marken["skill_hints"])

    async def _vorabruf(messages, _aufrufe, **_kw):
        messages.append({"role": "system", "content": marken["prefetch"]})

    monkeypatch.setattr(agent_mod, "resolve_prefetch", _vorabruf)
    gesehen: dict = {}

    async def _loop(*, messages, tools, limits, usage_acc=None, progress=None,
                    clock=None, on_tool_result=None, wissen=None, on_offene_abnahme=None,
                    on_token=None, start=None):
        gesehen["messages"] = [dict(m) for m in messages]
        return AgentRun(text="ok", stop_reason="text", iterations=1)

    monkeypatch.setattr(agent_mod, "run_agent_loop", _loop)
    monkeypatch.setattr(agent_mod, "load_engine", _engine)
    monkeypatch.setattr(agent_write, "has_personal_auth", lambda: False)
    ctx = state_mod.TurnContext(req=ChatRequest(
        session_id="s1", message=marken["message"],
        environment=Environment(result_schema={"type": "object"})))
    ctx.env = ctx.req.environment.model_dump()
    ctx.history = [{"role": "user", "content": marken["history"]}]
    ctx.safety = SafetyDecision(risk_level="low")
    ctx.policy = PolicyDecision()
    ctx.classification = ClassificationResult()
    ctx.session_state = {"persona_id": "P-AND", "entities": {}}
    ctx.rag_config = {}

    await respond_agent(ctx)
    kette = gesehen["messages"]
    namen = {marke: name for name, marke in marken.items()}
    # Der Satz zum Ergebnis-Schema ist kein eigener Block: er hängt am Kopf.
    assert "liefere_ergebnis" in kette[0]["content"]
    assert kette[1]["content"] == _BLOCK
    # Paket C (Review 2026-09-29): „zuletzt gezeigt“ steht am Anfang der Nachricht
    # der Person, im selben Beitrag — die Reihenfolge gilt dort im Text.
    assert kette[-1]["role"] == "user"
    reihe = [namen[teil] for m in kette[2:] for teil in m["content"].split("\n\n")]
    assert reihe == [kennung for kennung in pv.JE_ZUG if kennung != "result_schema"]
