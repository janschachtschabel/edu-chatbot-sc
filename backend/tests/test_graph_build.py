"""graph.build — the LangGraph turn-graph assembly (R4e).

These pins verify WIRING only (each node has its own suite): the node order, the
three ``early_response`` short-circuits (tour, context_greeting, preflight), the
``functools.partial`` seam binding (session / peer_ip / on_token / memory_fetch), and
the two inline glue steps — the user-message persist (between context_greeting and
preflight) and the config-gated main safety-log (between assess and merge).

Strategy: replace the nine node functions on the build module with a single
union-signature spy that records its name + the seams it received, then invoke the
compiled graph and assert on the recorded call order and on the terminal result
dict (``.ainvoke`` returns a dict; None-default fields are omitted). The two glue
steps run for real with their DB/config boundaries patched, so their order and
behaviour are exercised in the same pass.
"""

from __future__ import annotations

import asyncio
import functools

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment, SafetyDecision
from boerdi.graph import build as build_mod
from boerdi.graph.build import build_turn_graph
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import TurnProgress

_NODE_NAMES = [
    "setup", "tour", "page_context_enrich", "context_greeting", "preflight", "assess",
    "merge", "route", "respond", "assemble", "persist",
]


def _spy(name, calls, *, sets=None):
    """A stand-in node: records (name, seams) and optionally sets ctx attrs.

    The signature is the UNION of every real node's keyword seams (all defaulted),
    so the same spy stands in for any node — build binds seams by keyword, and the
    absence of a ``config``/``**kwargs`` param keeps LangGraph from injecting one.
    """

    async def _node(ctx, session=None, peer_ip="", memory_fetch=None, on_token=None,
                    progress=None, engine="pattern"):
        calls.append(
            (name, {"session": session, "peer_ip": peer_ip,
                    "memory_fetch": memory_fetch, "on_token": on_token,
                    "progress": progress, "engine": engine})
        )
        for key, val in (sets or {}).items():
            setattr(ctx, key, val)
        return ctx

    return _node


def _patch(monkeypatch, calls, *, tour_early=None, context_greeting_early=None,
           preflight_early=None, safety_cfg=None):
    sets_by = {
        "tour": {"early_response": tour_early} if tour_early is not None else None,
        "context_greeting": (
            {"early_response": context_greeting_early}
            if context_greeting_early is not None else None
        ),
        "preflight": {"early_response": preflight_early} if preflight_early is not None else None,
        "persist": {"response": ChatResponse(session_id="bb-1", content="DONE")},
    }
    for name in _NODE_NAMES:
        monkeypatch.setattr(build_mod, name, _spy(name, calls, sets=sets_by.get(name)))

    async def _save(session, session_id, role, content, **k):
        calls.append(("persist_user", {"session": session, "session_id": session_id,
                                        "role": role, "content": content}))

    async def _logsafe(session, session_id, message, decision, ip="", **k):
        calls.append(("safety_log", {"session": session, "session_id": session_id,
                                     "decision": decision, "ip": ip}))

    async def _getmem(session, session_id, *a, **k):
        calls.append(("get_memory", {"session": session, "session_id": session_id}))
        return []

    monkeypatch.setattr(build_mod, "save_message", _save)
    monkeypatch.setattr(build_mod, "log_safety_event", _logsafe)
    monkeypatch.setattr(build_mod, "get_memory", _getmem)
    monkeypatch.setattr(
        build_mod, "load_safety_config",
        lambda: safety_cfg if safety_cfg is not None
        else {"logging": {"enabled": True, "log_all_turns": True}},
    )


def _ctx(*, risk="high"):
    ctx = TurnContext(
        req=ChatRequest(session_id="bb-1", message="hallo", environment=Environment()),
    )
    ctx.safety = SafetyDecision(risk_level=risk)
    ctx.client_ip = "1.2.3.4"
    return ctx


def _run(monkeypatch, *, ctx=None, session=None, peer_ip="9.9.9.9", on_token=None, **patch_kw):
    calls: list = []
    session = session if session is not None else object()
    on_token = on_token if on_token is not None else object()
    _patch(monkeypatch, calls, **patch_kw)
    graph = build_turn_graph(session=session, peer_ip=peer_ip, on_token=on_token)
    result = asyncio.run(graph.ainvoke(ctx if ctx is not None else _ctx()))
    return result, calls, session, on_token


def _order(calls):
    return [name for name, _ in calls]


@pytest.mark.parametrize("knoten", ["assess", "route", "respond", "persist"])
def test_die_engine_naht_erreicht_ihre_knoten(monkeypatch, knoten):
    """A4b/A4c: ``engine`` darf nicht der neunte Fall „dokumentiert ohne
    Konsumenten" werden. Der Wächter prüft beide Richtungen — die Vorgabe kommt
    als ``pattern`` an, ein gesetzter Wert unverändert — und alle Knoten, die
    ihn auswerten: ``assess`` (ohne Klassifikator), ``route`` (ohne
    Musterwahl und ohne Schnellwege), ``respond`` (reicht an
    ``respond_agent`` weiter) und ``persist`` (schreibt ihn in den
    Debug-Block, AG-1)."""
    calls: list = []
    _patch(monkeypatch, calls)
    graph = build_turn_graph(session=object(), engine="agent")
    asyncio.run(graph.ainvoke(_ctx()))
    assert dict(calls)[knoten]["engine"] == "agent"

    calls2: list = []
    _patch(monkeypatch, calls2)
    asyncio.run(build_turn_graph(session=object()).ainvoke(_ctx()))
    assert dict(calls2)[knoten]["engine"] == "pattern"


# ── Topology ──────────────────────────────────────────────────────────────

def test_normal_path_runs_every_node_in_order(monkeypatch):
    result, calls, _, _ = _run(monkeypatch)
    assert _order(calls) == [
        "setup", "tour", "page_context_enrich", "context_greeting", "persist_user",
        "preflight", "assess", "safety_log", "merge", "route", "respond", "assemble", "persist",
    ]
    # terminal ChatResponse flows to the output dict (R4f reads result["response"])
    assert result["response"].content == "DONE"
    assert result.get("early_response") is None


def test_jeder_knoten_bucht_seine_dauer_in_den_zug(monkeypatch):
    """Plan 2026-09-30 (T8): der Debug-Block zeigt, wo ein Zug seine Zeit lässt —
    je Knoten, in der Reihenfolge der Kette."""
    result, _calls, _, _ = _run(monkeypatch)
    zeiten = result["usage"]["zeiten_ms"]
    assert list(zeiten) == [
        "setup", "tour", "page_context_enrich", "context_greeting", "persist_user",
        "preflight", "assess", "safety_log", "merge", "route", "respond", "assemble", "persist",
    ]
    assert all(isinstance(ms, int) and ms >= 0 for ms in zeiten.values())


def test_tour_early_exit_skips_rest_and_does_not_persist_user(monkeypatch):
    tour_resp = ChatResponse(session_id="bb-1", content="TOUR")
    result, calls, _, _ = _run(monkeypatch, tour_early=tour_resp)
    assert _order(calls) == ["setup", "tour"]
    assert "persist_user" not in _order(calls)  # tour persists its own user turn
    assert result["early_response"].content == "TOUR"
    assert "response" not in result  # persist never ran


def test_context_greeting_early_exit_stops_before_persist_user(monkeypatch):
    ctx_resp = ChatResponse(session_id="bb-1", content="CTX")
    result, calls, _, _ = _run(monkeypatch, context_greeting_early=ctx_resp)
    assert _order(calls) == ["setup", "tour", "page_context_enrich", "context_greeting"]
    assert "persist_user" not in _order(calls)  # a context_open ping is never persisted
    assert result["early_response"].content == "CTX"
    assert "response" not in result


def test_preflight_early_exit_stops_before_assess(monkeypatch):
    pre_resp = ChatResponse(session_id="bb-1", content="DIRECT")
    result, calls, _, _ = _run(monkeypatch, preflight_early=pre_resp)
    assert _order(calls) == [
        "setup", "tour", "page_context_enrich", "context_greeting", "persist_user", "preflight",
    ]
    assert result["early_response"].content == "DIRECT"
    assert "response" not in result


# ── Seam binding (functools.partial) ────────────────────────────────────────

def test_setup_gets_session_and_peer_ip(monkeypatch):
    _, calls, session, _ = _run(monkeypatch)
    seams = dict(calls)["setup"]
    assert seams["session"] is session
    assert seams["peer_ip"] == "9.9.9.9"


def test_respond_gets_session_and_on_token(monkeypatch):
    _, calls, session, on_token = _run(monkeypatch)
    seams = dict(calls)["respond"]
    assert seams["session"] is session
    assert seams["on_token"] is on_token


def test_persist_gets_session(monkeypatch):
    _, calls, session, _ = _run(monkeypatch)
    assert dict(calls)["persist"]["session"] is session


def test_assess_memory_fetch_delegates_to_get_memory_with_session(monkeypatch):
    _, calls, session, _ = _run(monkeypatch)
    mf = dict(calls)["assess"]["memory_fetch"]
    assert isinstance(mf, functools.partial)
    # calling the seam delegates to the bound get_memory(session, session_id)
    asyncio.run(mf("bb-42"))
    getmem = dict(calls)["get_memory"]
    assert getmem["session"] is session
    assert getmem["session_id"] == "bb-42"


# ── Glue: user-message persist ──────────────────────────────────────────────

def test_user_message_persisted_between_tour_and_preflight(monkeypatch):
    _, calls, session, _ = _run(monkeypatch)
    persisted = dict(calls)["persist_user"]
    assert persisted["session"] is session
    assert persisted["session_id"] == "bb-1"
    assert persisted["role"] == "user"
    assert persisted["content"] == "hallo"


# ── Glue: main safety-log (ALT chat_turn_setup:202-212) ─────────────────────

def test_safety_log_fires_after_assess_with_session_and_ip(monkeypatch):
    _, calls, session, _ = _run(monkeypatch)
    order = _order(calls)
    assert order.index("safety_log") == order.index("assess") + 1
    logged = dict(calls)["safety_log"]
    assert logged["session"] is session
    assert logged["ip"] == "1.2.3.4"
    assert isinstance(logged["decision"], SafetyDecision)


def test_safety_log_skipped_when_logging_disabled(monkeypatch):
    _, calls, _, _ = _run(monkeypatch, safety_cfg={"logging": {"enabled": False}})
    assert "safety_log" not in _order(calls)
    assert "merge" in _order(calls)  # chain still continues


def test_safety_log_skipped_when_low_risk_and_not_log_all_turns(monkeypatch):
    _, calls, _, _ = _run(
        monkeypatch,
        ctx=_ctx(risk="low"),
        safety_cfg={"logging": {"enabled": True, "log_all_turns": False}},
    )
    assert "safety_log" not in _order(calls)
    assert "merge" in _order(calls)


def test_safety_log_fires_for_low_risk_when_log_all_turns(monkeypatch):
    _, calls, _, _ = _run(
        monkeypatch,
        ctx=_ctx(risk="low"),
        safety_cfg={"logging": {"enabled": True, "log_all_turns": True}},
    )
    assert "safety_log" in _order(calls)


# ── Real-node compile (no patching, no DB/LLM — structure only) ──────────────

def test_real_graph_compiles_with_all_expected_nodes():
    """Compiles with the REAL (unpatched) nodes — proves their signatures are
    LangGraph-compatible without the DB/LLM boundaries an e2e invoke needs."""
    graph = build_turn_graph(session=object())
    nodes = set(graph.get_graph().nodes)
    assert {
        "setup", "tour", "page_context_enrich", "context_greeting", "persist_user",
        "preflight", "assess", "safety_log", "merge", "route", "respond", "assemble", "persist",
    } <= nodes


# ── C9: Fortschritts-Naht ───────────────────────────────────────────

def _run_with_progress(monkeypatch, progress=None):
    calls: list = []
    _patch(monkeypatch, calls)
    kw = {} if progress is None else {"progress": progress}
    graph = build_turn_graph(session=object(), **kw)
    asyncio.run(graph.ainvoke(_ctx()))
    return calls


REPORTING_NODES = {"assess", "route", "respond", "persist"}


def test_progress_reaches_exactly_the_reporting_nodes(monkeypatch):
    """Die vier Knoten mit einem SSE-Schritt bekommen das Fortschritts-Objekt;
    die übrigen nicht — so ist am Graph-Bau ablesbar, wer überhaupt meldet."""
    progress = TurnProgress(lambda _e: None)
    calls = _run_with_progress(monkeypatch, progress)
    # ``.get``: persist_user/safety_log/get_memory werden von eigenen Attrappen
    # ohne Seam-Dict protokolliert.
    assert {n for n, s in calls if s.get("progress") is progress} == REPORTING_NODES


def test_progress_defaults_to_the_no_op_when_not_streaming(monkeypatch):
    """POST /api/chat baut denselben Graphen ohne Sink — die meldenden Knoten
    dürfen dann kein ``None`` bekommen, sonst müsste jeder Aufruf abgesichert
    werden."""
    calls = _run_with_progress(monkeypatch)
    for name, seams in calls:
        if name in REPORTING_NODES:
            assert isinstance(seams.get("progress"), TurnProgress)


# ── Zug-Sammler über Knotengrenzen (Audit 2026-09-29) ─────────────────────

def _sammler_knoten(gesehen):
    """``respond`` bucht wie ``call_mcp_tool`` und der Vokabular-Abgleich;
    ``persist`` liest wie ``turn_links``/``turn_persist``. Die Signatur ist die
    der Spione oben — ohne ``**kwargs``, sonst injizierte LangGraph ``config``."""
    from boerdi.domain.prepared_write import PreparedWrite
    from boerdi.obs.usage import add_usage, current_turn_usage
    from boerdi.services.mcp import client

    async def _respond(ctx, session=None, peer_ip="", memory_fetch=None, on_token=None,
                       progress=None, engine="pattern"):
        metas = client._query_metas.get([])
        metas.append({"queryType": "content"})
        client._query_metas.set(metas)
        offene = client._prepared_writes.get([])
        offene.append(PreparedWrite(method="POST", path="/edu-sharing/rest/x",
                                    body=None, done_message="erledigt"))
        client._prepared_writes.set(offene)
        add_usage(current_turn_usage(),
                  {"prompt": 100, "completion": 10, "model": "vocab-model"}, phase="vocab")
        return ctx

    async def _persist(ctx, session=None, peer_ip="", memory_fetch=None, on_token=None,
                       progress=None, engine="pattern"):
        gesehen["metas"] = client.get_query_metas()
        gesehen["writes"] = client.get_prepared_writes()
        gesehen["calls"] = ctx.usage["calls"]
        ctx.response = ChatResponse(session_id="bb-1", content="DONE")
        return ctx

    return _respond, _persist


def test_zug_sammler_erreichen_den_persist_knoten(monkeypatch):
    """LangGraph startet jeden Knoten in einer KOPIE des Kontexts: was ein Knoten
    in einen ContextVar setzt, sieht der nächste nicht. Die Zug-Sammler wurden
    im ``setup``-Knoten gebunden — Query-Metas und vorbereitete
    Schreibzugriffe aus ``respond`` kamen deshalb in ``persist`` nie an, und
    Buchungen über den Merkposten (Vokabular-Abgleich) verfielen. Gebunden wird
    jetzt vor dem Graphen (``run_turn``); geprüft wird am echten Graphen."""
    calls: list = []
    _patch(monkeypatch, calls)
    gesehen: dict = {}
    _respond, _persist = _sammler_knoten(gesehen)
    monkeypatch.setattr(build_mod, "respond", _respond)
    monkeypatch.setattr(build_mod, "persist", _persist)

    graph = build_turn_graph(session=object())
    result = asyncio.run(build_mod.run_turn(graph, _ctx()))

    assert gesehen["metas"] == [{"queryType": "content"}]
    assert len(gesehen["writes"]) == 1
    assert gesehen["calls"] == 1
    assert result["usage"]["calls"] == 1


def test_begin_turn_startet_mit_leeren_sammlern_und_bindet_den_merkposten():
    """Ein Zug darf nie an den Sammlern des vorigen hängen — auch nicht, wenn
    der Kontext noch Werte trägt."""
    from boerdi.domain.prepared_write import PreparedWrite
    from boerdi.obs.usage import current_turn_usage
    from boerdi.services.mcp import client

    async def zug():
        client._query_metas.set([{"queryType": "alt"}])
        client._prepared_writes.set([PreparedWrite(
            method="POST", path="/alt", body=None, done_message="alt")])
        ctx = _ctx()
        build_mod.begin_turn(ctx)
        return (client.get_query_metas(), client.get_prepared_writes(),
                current_turn_usage() is ctx.usage)

    assert asyncio.run(zug()) == ([], [], True)


def test_der_zugbeginn_bindet_den_merkposten_und_ein_blatt_bucht_hinein(monkeypatch):
    """Die Verbindung, nicht die beiden Enden (K1e, aus ``test_setup_node``
    hierher gezogen).

    Der Vokabular-Abgleich sitzt hinter ``TOOL_PREPROCESSORS`` und
    ``call_mcp_tool`` — er bekommt den Merkposten nicht als Parameter, sondern
    aus dem ContextVar. Bis 2026-09-29 band ihn der ``setup``-Knoten, und dieser
    Test fuhr ``setup`` und das Blatt in EINER Task-Kette — im Graphen laufen
    sie in zwei Kontext-Kopien, dort kam die Buchung nie an. Gebunden wird jetzt
    in ``begin_turn``; dass die Bindung über die Knotengrenzen trägt, prüft
    ``test_zug_sammler_erreichen_den_persist_knoten`` am echten Graphen.

    ``asyncio.run`` kopiert den Kontext, also muss die Prüfung INNERHALB des
    Laufs stehen — ein Binden im Task ist draußen nicht sichtbar.
    """
    from types import SimpleNamespace

    from boerdi.services import llm
    from boerdi.services.mcp import arg_resolvers as ar

    async def fake_acompletion(**kwargs):
        return SimpleNamespace(
            model="gpt-5.6-luna",
            choices=[SimpleNamespace(
                message=SimpleNamespace(content="http://x/im"))],
            usage=SimpleNamespace(
                prompt_tokens=10, completion_tokens=5,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0)),
        )

    monkeypatch.setattr(llm, "_acompletion", fake_acompletion)
    ar._label_to_uri_cache["lrt"]["interaktiv"] = "http://x/im"
    ctx = _ctx()

    async def zug():
        build_mod.begin_turn(ctx)
        return await ar._llm_vocab_match("lrt", "Simulation")

    try:
        assert asyncio.run(zug()) == "http://x/im"
    finally:
        ar._label_to_uri_cache["lrt"].clear()
        ar._llm_vocab_cache.clear()

    # Die Token stehen im Merkposten DIESES Zuges — dort liest turn_persist.
    assert ctx.usage["calls"] == 1
    assert ctx.usage["per_phase"]["vocab_match"]["prompt"] == 10
