"""graph.nodes.preflight — Direct-Action safety-dispatch (P4-2b, R2).

Port of the direct-action half of ALT ``chat_pipeline_phases._run_preflight_guards``.
The rate-limit half does NOT live here: NEU rate-limits at the slowapi HTTP layer
(``api/ratelimit.py``, P1-4), so the node only screens + dispatches the three
direct actions and sets ``ctx.early_response`` on a block/dispatch.

Tested with fakes: ``session`` is an injected sentinel (the DB writes + the R5
handlers are patched on the node module — ALT convention); ``regex_gate`` runs
for real (pure) as the safety-assess fallback.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes.preflight import preflight
from boerdi.services.rate_limits import RateVerdict

_SESSION = object()  # sentinel — every DB boundary is patched


@pytest.fixture(autouse=True)
def _allow_rate(monkeypatch):
    """C6 put a config-driven throttle in front of the dispatch. It reads the
    safety config (DB-backed), so the direct-action tests neutralise it; the
    throttle's own behaviour is pinned in ``test_rate_limits_config.py`` and in
    the two wiring tests at the end of this file."""
    monkeypatch.setattr(pf_mod, "check_rate_limit", _Spy(RateVerdict(allowed=True)))


def _ctx(action, message="los", session_state=None, locale=None,
         **params) -> state_mod.TurnContext:
    _env = {"environment": Environment(locale=locale)} if locale else {}
    ctx = state_mod.TurnContext(
        req=ChatRequest(session_id="bb-1", message=message, action=action,
                        action_params=params, **_env)
    )
    ctx.session_state = session_state if session_state is not None else {"persona_id": "P-AND"}
    ctx.client_ip = "1.2.3.4"
    return ctx


class _Spy:
    def __init__(self, ret=None):
        self.calls = []
        self.ret = ret

    async def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.ret


def _patch_handlers(monkeypatch, *, browse=None, lp=None, curate=None, text=None):
    browse = browse or _Spy(ChatResponse(session_id="bb-1", content="BROWSE-OK"))
    lp = lp or _Spy(ChatResponse(session_id="bb-1", content="LP-OK"))
    curate = curate or _Spy(ChatResponse(session_id="bb-1", content="CURATE-OK"))
    text = text or _Spy(ChatResponse(session_id="bb-1", content="TEXT-OK"))
    monkeypatch.setattr(pf_mod, "_handle_browse_collection", browse)
    monkeypatch.setattr(pf_mod, "_handle_curate_collection", curate)
    monkeypatch.setattr(pf_mod, "_handle_generate_learning_path", lp)
    monkeypatch.setattr(pf_mod, "_handle_show_content_text", text)
    return browse, lp, curate


def _patch_db(monkeypatch):
    log = _Spy()
    save = _Spy()
    monkeypatch.setattr(pf_mod, "log_safety_event", log)
    monkeypatch.setattr(pf_mod, "save_message", save)
    return log, save


def _patch_safety(monkeypatch, decision):
    spy = _Spy(decision)
    monkeypatch.setattr(pf_mod, "assess_safety", spy)
    return spy


# ── pass-through (not a direct action) ──────────────────────────

def test_no_action_passes_through(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    out = asyncio.run(preflight(_ctx(None, message="wie geht photosynthese?"), _SESSION))

    assert out.early_response is None  # regular path continues
    assert safety.calls == [] and browse.calls == [] and log.calls == []


def test_unknown_action_passes_through(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    out = asyncio.run(preflight(_ctx("canvas_create", collection_id="c1"), _SESSION))

    assert out.early_response is None
    assert safety.calls == [] and browse.calls == []


# ── dispatch (safe) ─────────────────────────────────────────────

def test_browse_action_screens_then_dispatches(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    ctx = _ctx("browse_collection", message="zeig mir Bio", collection_id="c1", title="Bio")
    out = asyncio.run(preflight(ctx, _SESSION))

    assert out.early_response.content == "BROWSE-OK"
    # safety was screened on the concatenated action text (not skipped)
    assert len(safety.calls) == 1
    assert "zeig mir Bio" in safety.calls[0]["args"][0]
    # handler got the injected session + req + session_state
    assert browse.calls[0]["args"][0] is _SESSION
    assert browse.calls[0]["args"][1] is ctx.req
    assert browse.calls[0]["args"][2] is ctx.session_state
    # safe path → no block log, no block persist
    assert log.calls == [] and save.calls == []
    assert lp.calls == [] and curate.calls == []


def test_direktaktion_bekommt_den_zug_merkposten(monkeypatch):
    """K1b: Direkt-Aktionen rufen dieselben LLM-Generatoren wie der Hauptweg.
    Ohne den Merkposten aus dem Zug bucht dort niemand — und der Zug endet hier,
    also gibt es keine zweite Gelegenheit."""
    browse, lp, curate = _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    ctx = _ctx("generate_learning_path", collection_id="c1")
    asyncio.run(preflight(ctx, _SESSION))
    assert lp.calls[0]["kwargs"]["usage_acc"] is ctx.usage

    ctx2 = _ctx("curate_collection", collection_id="c1")
    asyncio.run(preflight(ctx2, _SESSION))
    assert curate.calls[0]["kwargs"]["usage_acc"] is ctx2.usage

    # Auch das Blättern: es ruft den QR-Generator (echter LLM-Aufruf).
    ctx3 = _ctx("browse_collection", collection_id="c1")
    asyncio.run(preflight(ctx3, _SESSION))
    assert browse.calls[0]["kwargs"]["usage_acc"] is ctx3.usage


def test_direktaktions_sicherheitspruefung_bucht_mit(monkeypatch):
    """K1d: ``assess_safety`` läuft auch HIER — vor dem assess-Knoten und mit
    eigener Rechtsprüfung. Der Plan nannte nur den assess-Knoten; gemessen sind
    es zwei Aufrufer."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    ctx = _ctx("generate_learning_path", collection_id="c1")
    asyncio.run(preflight(ctx, _SESSION))

    assert safety.calls[0]["kwargs"]["usage_acc"] is ctx.usage


def test_learning_path_and_curate_dispatch(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    out_lp = asyncio.run(preflight(_ctx("generate_learning_path", collection_id="c1"), _SESSION))
    assert out_lp.early_response.content == "LP-OK"
    assert len(lp.calls) == 1 and browse.calls == []

    out_cur = asyncio.run(preflight(_ctx("curate_collection", collection_id="c1"), _SESSION))
    assert out_cur.early_response.content == "CURATE-OK"
    assert len(curate.calls) == 1


def test_show_content_text_dispatches_und_geht_durch_das_safety_gate(monkeypatch):
    # M17: die Volltext-Aktion ist eine Direkt-Aktion wie die anderen drei —
    # sie überspringt die Pattern-Engine und MUSS deshalb dasselbe
    # Sicherheits-Gate passieren, sonst wäre sie ein Weg daran vorbei.
    text = _Spy(ChatResponse(session_id="bb-1", content="TEXT-OK"))
    _patch_handlers(monkeypatch, text=text)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))

    out = asyncio.run(preflight(_ctx("show_content_text", node_id="abc-123"), _SESSION))

    assert out.early_response.content == "TEXT-OK"
    assert len(text.calls) == 1


def test_show_content_text_wird_bei_high_risk_geblockt(monkeypatch):
    text = _Spy(ChatResponse(session_id="bb-1", content="TEXT-OK"))
    _patch_handlers(monkeypatch, text=text)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))

    out = asyncio.run(preflight(_ctx("show_content_text", node_id="abc-123"), _SESSION))

    assert text.calls == []
    assert out.early_response.debug.pattern == "SAFETY: blocked_direct_action"


# ── high-risk block ─────────────────────────────────────────────

def test_high_risk_blocks_logs_and_persists(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)
    decision = SafetyDecision(risk_level="high", reasons=["crisis"], enforced_pattern="M02")
    _patch_safety(monkeypatch, decision)

    ctx = _ctx("browse_collection", message="etwas boeses", collection_id="c1")
    out = asyncio.run(preflight(ctx, _SESSION))

    # blocked → friendly bubble, direct-action handler NOT run
    assert out.early_response.content.startswith("Diese Anfrage konnte ich nicht bearbeiten")
    assert "verletzt Sicherheits" in out.early_response.content
    assert out.early_response.debug.pattern == "SAFETY: blocked_direct_action"
    assert out.early_response.debug.safety.risk_level == "high"
    assert out.early_response.debug.entities == {"action": "browse_collection"}
    assert browse.calls == []
    # safety event logged with the SafetyDecision object (R3b _field reads it) + ip
    assert len(log.calls) == 1
    assert log.calls[0]["args"][0] is _SESSION
    assert log.calls[0]["kwargs"].get("decision") is decision or decision in log.calls[0]["args"]
    # blocked message persisted as an assistant turn
    assert len(save.calls) == 1
    assert save.calls[0]["args"][0] is _SESSION


# ── safety-assess failure falls back to regex_gate ──────────────

def test_safety_assess_failure_falls_back_to_regex_gate(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)

    async def _boom(*a, **k):
        raise RuntimeError("moderation upstream 500")

    monkeypatch.setattr(pf_mod, "assess_safety", _boom)

    # benign action text → regex_gate returns low → dispatch proceeds
    ctx = _ctx("browse_collection", message="zeig Sammlung Bio", collection_id="c1", title="Bio")
    out = asyncio.run(preflight(ctx, _SESSION))

    assert out.early_response.content == "BROWSE-OK"  # recovered, dispatched
    assert len(browse.calls) == 1
    assert log.calls == []  # not high-risk → no block log


# ── C6: config-driven throttle, ALT's first preflight guard ─────

def test_rate_limited_turn_answers_with_the_editors_text_and_logs_it(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    monkeypatch.setattr(pf_mod, "check_rate_limit", _Spy(
        RateVerdict(allowed=False, reason="session_minute", blocked_message="Kurz durchatmen."),
    ))

    # A PLAIN turn (no direct action): ALT checks the limit for every request,
    # not only for actions — so the guard must sit before the action filter.
    out = asyncio.run(preflight(_ctx(None, message="und noch eine frage"), _SESSION))

    assert out.early_response.content == "Kurz durchatmen."
    assert out.early_response.quick_replies == []
    # the turn is stopped before anything expensive runs
    assert safety.calls == [] and browse.calls == [] and save.calls == []
    # …and it is the ONE event that can move the `rate_limited` counter
    assert len(log.calls) == 1
    assert log.calls[0]["kwargs"]["rate_limited"] is True
    assert log.calls[0]["kwargs"]["ip"] == "1.2.3.4"
    assert "session_minute" in str(log.calls[0]["kwargs"]["decision"])


def test_rate_limit_is_checked_before_a_direct_action_dispatches(monkeypatch):
    browse, lp, curate = _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    monkeypatch.setattr(pf_mod, "check_rate_limit", _Spy(
        RateVerdict(allowed=False, reason="ip_minute", blocked_message="Zu viele Anfragen."),
    ))

    out = asyncio.run(preflight(_ctx("browse_collection", collection_id="c1"), _SESSION))

    assert out.early_response.content == "Zu viele Anfragen."
    assert browse.calls == []  # a direct action does not slip past the brake


# ── C1-f2b6b: die Abweisung folgt der Widget-Sprache ─────────────

def test_high_risk_block_message_english(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high", reasons=["crisis"]))

    ctx = _ctx("browse_collection", message="something bad",
               locale="en-GB", collection_id="c1")
    out = asyncio.run(preflight(ctx, _SESSION))

    assert out.early_response.content == (
        "I could not process this request — it breaks our safety or content "
        "rules. Please try rephrasing it."
    )
