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


# ── S5: die offene Schreib-Abnahme ──────────────────────────────

def _mit_abnahme(monkeypatch, ret):
    """Die Einlösung als Attrappe — ihr Inneres prüft ``test_write_approval``."""
    spy = _Spy(ret)
    monkeypatch.setattr(pf_mod, "redeem_write_approval", spy)
    return spy


def test_offene_abnahme_beendet_den_zug_vor_dem_klassifikator(monkeypatch):
    """DER FIX. Vor S5 lief ein „ja" in den normalen Weg: der Klassifikator
    musste M18 treffen (nur dieses Muster nennt die schreibenden Werkzeuge) und
    das Modell die nie gesehenen Argumente rekonstruieren. Jedes Scheitern war
    eine neue Vorschau — die Schleife. Jetzt endet der Zug hier."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    einloesung = _mit_abnahme(
        monkeypatch, ChatResponse(session_id="bb-1", content="ANGELEGT"))

    ctx = _ctx(None, message="Ja, so ausführen")
    out = asyncio.run(preflight(ctx, _SESSION))

    assert out.early_response.content == "ANGELEGT"
    assert einloesung.calls[0]["args"][0] is _SESSION
    assert einloesung.calls[0]["args"][2] is ctx.session_state
    assert safety.calls == []


def test_ohne_offene_abnahme_laeuft_der_zug_normal_weiter(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    einloesung = _mit_abnahme(monkeypatch, None)

    out = asyncio.run(preflight(_ctx(None, message="Ja, gerne"), _SESSION))

    assert out.early_response is None, "Ohne Vorgang gehört der Zug dem Klassifikator"
    assert len(einloesung.calls) == 1


def test_eine_direktaktion_loest_keine_abnahme_ein(monkeypatch):
    """Ein Zug mit ``action`` beauftragt etwas anderes. Würde ein „ja" daneben
    als Abnahme gelesen, führte ein Klick auf „Sammlung ansehen" eine fremde
    Änderung aus."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    einloesung = _mit_abnahme(
        monkeypatch, ChatResponse(session_id="bb-1", content="ANGELEGT"))

    out = asyncio.run(preflight(
        _ctx("browse_collection", message="ja", collection_id="c1"), _SESSION))

    assert einloesung.calls == []
    assert out.early_response.content == "BROWSE-OK"


def test_die_drosselung_kommt_vor_der_abnahme(monkeypatch):
    """Sonst liefe der einzige schreibende Weg an der Bremse vorbei."""
    monkeypatch.setattr(pf_mod, "check_rate_limit", _Spy(
        RateVerdict(allowed=False, reason="session", blocked_message="Moment bitte")))
    _patch_db(monkeypatch)
    einloesung = _mit_abnahme(
        monkeypatch, ChatResponse(session_id="bb-1", content="ANGELEGT"))

    out = asyncio.run(preflight(_ctx(None, message="Ja, so ausführen"), _SESSION))

    assert out.early_response.content == "Moment bitte"
    assert einloesung.calls == []


# ── Die Auswertungs-Zeile für früh endende Züge (2026-08-15) ────

def _mit_qualitaet(monkeypatch):
    spy = _Spy()
    monkeypatch.setattr(pf_mod, "log_turn_quality", spy)
    return spy


def test_eine_direktaktion_hinterlaesst_eine_auswertungszeile(monkeypatch):
    """Diese Züge erreichen den ``persist``-Knoten nie — dort steht der einzige
    andere Aufruf. Ohne diese Naht waren ausgerechnet die Knopfdruck-Züge in
    der Auswertung unsichtbar."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    qual = _mit_qualitaet(monkeypatch)

    ctx = _ctx("browse_collection", message="zeig mir Bio", collection_id="c1")
    asyncio.run(preflight(ctx, _SESSION))

    assert len(qual.calls) == 1
    assert qual.calls[0]["args"][1] is ctx.req


def test_eine_eingeloeste_abnahme_hinterlaesst_eine_auswertungszeile(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    _mit_abnahme(monkeypatch, ChatResponse(session_id="bb-1", content="ANGELEGT"))
    qual = _mit_qualitaet(monkeypatch)

    asyncio.run(preflight(_ctx(None, message="Ja, so ausführen"), _SESSION))

    assert len(qual.calls) == 1


def test_ein_gedrosselter_zug_schreibt_keine_auswertungszeile(monkeypatch):
    """Drosselung und Sicherheits-Block führen ihr eigenes Sicherheits-Ereignis.
    Ein zweiter Datensatz daneben machte die Zählung mehrdeutig."""
    monkeypatch.setattr(pf_mod, "check_rate_limit", _Spy(
        RateVerdict(allowed=False, reason="session", blocked_message="Moment")))
    _patch_db(monkeypatch)
    qual = _mit_qualitaet(monkeypatch)

    asyncio.run(preflight(_ctx(None, message="hallo"), _SESSION))

    assert qual.calls == []


def test_ein_normaler_zug_schreibt_hier_nichts(monkeypatch):
    """Gegenprobe: wer weiterläuft, wird im ``persist``-Knoten gezählt — hier
    zusätzlich zu buchen wäre eine Doppelzählung."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    _mit_abnahme(monkeypatch, None)
    qual = _mit_qualitaet(monkeypatch)

    out = asyncio.run(preflight(_ctx(None, message="wie geht photosynthese?"), _SESSION))

    assert out.early_response is None
    assert qual.calls == []


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
