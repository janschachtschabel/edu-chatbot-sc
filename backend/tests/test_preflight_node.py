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
import time

import pytest

from boerdi.api.schemas import ChatRequest, ChatResponse, Environment, SafetyDecision
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes import setup as setup_mod
from boerdi.graph.nodes.preflight import preflight
from boerdi.graph.nodes.setup import setup
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


def _liegengelassene_abnahme(monkeypatch):
    """Ein offener Vorgang aus einem früheren Zug, echte Einlösung dahinter.

    Gepatcht sind nur die Außenkanten von ``services/write_approval`` — das
    Zusammenspiel beider Vorlauf-Schritte (Verwerfen, dann Einlösen) läuft echt.
    """
    from boerdi.domain.write_confirm import remember_pending
    from boerdi.services import write_approval as wa_mod

    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    monkeypatch.setattr(pf_mod, "_log_early_quality", _Spy())
    schreiben = _Spy(("Der Datensatz wurde angelegt.", ""))
    monkeypatch.setattr(wa_mod, "call_mcp_tool_status", schreiben)
    monkeypatch.setattr(wa_mod, "update_session", _Spy())
    monkeypatch.setattr(wa_mod, "save_message", _Spy())
    # Eine angemeldete Person: seit Paket 7 (S4) die Bedingung jeder Einlösung.
    monkeypatch.setattr(wa_mod, "schreiben_erlaubt", lambda: True)
    zustand = {"persona_id": "P-AND", "entities": {"_pending_write": remember_pending(
        "wlo_create_content", {"title": "Arbeitsblatt Bruchrechnung"},
        "Ax9-_QmZ2kLpWvRt7NbYcE4s", now=time.time())}}

    # ``setup`` lädt die Sitzung je Zug neu — hier immer dieselben ``entities``,
    # damit ein Verwerfen im ersten Zug auch im zweiten gilt (wie in der DB).
    async def _sitzung(*_a, **_k):
        return {"persona_id": "P-AND", "entities": zustand["entities"]}

    async def _kein_verlauf(*_a, **_k):
        return []

    monkeypatch.setattr(setup_mod, "get_or_create_session", _sitzung)
    monkeypatch.setattr(setup_mod, "get_messages", _kein_verlauf)
    return schreiben, zustand


def _zug(ctx) -> state_mod.TurnContext:
    """Ein Zug in Graph-Reihenfolge: ``setup`` verwirft einen Vorgang, den dieser
    Zug nicht bestätigen kann (vor Tour und Kontext-Gruß), dann der Vorlauf."""
    ctx = asyncio.run(setup(ctx, _SESSION, peer_ip="1.2.3.4"))
    return asyncio.run(preflight(ctx, _SESSION))


def test_ein_spaeteres_ja_loest_einen_liegengelassenen_vorgang_nicht_aus(monkeypatch):
    """Audit 2026-09-29. Die Vorschau stand, die Person ging zu etwas anderem
    über — und ein späterer Chip „Ja, zeig mir mehr Videos" war eine glatte
    Zustimmung (kurz, ohne Vorbehalt). Bis hier überdauerte der Vorgang die
    Zwischenzüge (Frist zehn Minuten) und wurde von diesem „ja" ausgeführt:
    eine Änderung, der niemand zugestimmt hat. Bestätigen kann ihn nur die
    Antwort direkt auf die Vorschau. Seit Review Paket 9 zählt jener Satz nicht
    mehr als Zustimmung; der Test nimmt deshalb einen, der es bleibt."""
    from boerdi.domain.zustimmung import is_affirmation

    schreiben, zustand = _liegengelassene_abnahme(monkeypatch)

    _zug(_ctx(None, message="Zeig mir erst Videos zu Brüchen", session_state=zustand))
    assert is_affirmation("Ja, gerne"), "sonst prüfte der Test nichts"
    out = _zug(_ctx(None, message="Ja, gerne", session_state=zustand))

    assert schreiben.calls == [], "Ein liegengelassener Vorgang wurde ausgeführt"
    assert out.early_response is None


def test_eine_direktaktion_dazwischen_laesst_den_vorgang_verfallen(monkeypatch):
    """Dasselbe über einen Knopf: ein Klick auf „Sammlung ansehen" ist ein
    anderer Auftrag. Danach darf ein „ja" die alte Vorschau nicht mehr
    bestätigen."""
    schreiben, zustand = _liegengelassene_abnahme(monkeypatch)

    _zug(_ctx("browse_collection", message="", session_state=zustand, collection_id="c1"))
    _zug(_ctx(None, message="ja", session_state=zustand))

    assert schreiben.calls == []


def test_die_antwort_direkt_auf_die_vorschau_bestaetigt_weiterhin(monkeypatch):
    """Gegenprobe: die unmittelbare Zustimmung löst den Vorgang wie bisher ein."""
    schreiben, zustand = _liegengelassene_abnahme(monkeypatch)

    out = _zug(_ctx(None, message="Ja, so ausführen", session_state=zustand))

    assert len(schreiben.calls) == 1
    assert out.early_response is not None


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


# ── Paket 18A: geschlossener Schalter, Moderation fehlt ─────────

def _moderation_fehlt(monkeypatch, schalter: str):
    from types import SimpleNamespace

    from boerdi.services.safety import service

    monkeypatch.setattr(service, "get_settings",
                        lambda: SimpleNamespace(moderation_failure_mode=schalter))
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low",
                                              reasons=["moderation_unavailable"]))


def test_geschlossen_beantwortet_eine_direktaktion_ohne_moderation_nicht(monkeypatch):
    browse, _lp, _curate = _patch_handlers(monkeypatch)
    log, save = _patch_db(monkeypatch)
    auswertung = _Spy()
    monkeypatch.setattr(pf_mod, "log_turn_quality", auswertung)
    _moderation_fehlt(monkeypatch, "closed")

    out = asyncio.run(preflight(_ctx("browse_collection", collection_id="c1"), _SESSION))

    assert "nicht prüfen" in out.early_response.content
    assert out.early_response.debug.pattern == "SAFETY: moderation_unavailable"
    assert browse.calls == []
    assert log.calls == []          # kein Sicherheitsereignis: die Person tat nichts
    assert len(save.calls) == 1
    assert len(auswertung.calls) == 1   # aber eine Zeile in der Auswertung (Review 18)


def test_offen_fuehrt_eine_direktaktion_ohne_moderation_aus(monkeypatch):
    browse, _lp, _curate = _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _moderation_fehlt(monkeypatch, "open")

    out = asyncio.run(preflight(_ctx("browse_collection", collection_id="c1"), _SESSION))

    assert out.early_response.content == "BROWSE-OK"
    assert len(browse.calls) == 1


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


def test_ein_ja_ohne_die_anmeldung_der_vorschau_bekommt_einen_hinweis(monkeypatch):
    """Paket 10 (Kurzaudit S-1/S-3/S-4/S-9): die Vorschau entstand unter einer
    Anmeldung, die in diesem Zug nicht gilt — neuer Tab, abgelaufen, Ticket noch
    nicht getauscht. Bis hier ging das „ja“ ohne Zusammenhang an das Modell, und es
    kam eine neue Vorschau: die gemeldete Schleife. Jetzt ein fester Satz samt
    Anmelde-Chip, und geschrieben wird nichts."""
    from boerdi.domain.auth_qr import AUTH_QR_MARKER
    from boerdi.i18n.bot_text import bot_text
    from boerdi.services import abnahme_hinweis

    monkeypatch.setattr(abnahme_hinweis, "save_message", _Spy())
    schreiben, zustand = _liegengelassene_abnahme(monkeypatch)
    zustand["entities"]["_pending_write"]["caller"] = "p:andere-anmeldung"

    out = _zug(_ctx(None, message="Ja, so ausführen", session_state=zustand))

    assert schreiben.calls == []
    assert out.early_response is not None
    assert out.early_response.content == bot_text("de", "write.callerChanged")
    assert AUTH_QR_MARKER in out.early_response.quick_replies


def test_ein_anderes_anliegen_bekommt_keinen_hinweis(monkeypatch):
    """Gegenprobe: wer zu etwas anderem übergeht, meint die Vorschau nicht."""
    from boerdi.services import abnahme_hinweis

    monkeypatch.setattr(abnahme_hinweis, "save_message", _Spy())
    _schreiben, zustand = _liegengelassene_abnahme(monkeypatch)
    zustand["entities"]["_pending_write"]["caller"] = "p:andere-anmeldung"

    out = _zug(_ctx(None, message="Zeig mir Videos zu Brüchen", session_state=zustand))

    assert out.early_response is None


# ── Paket U3-1b: „Ordnerstruktur als Entwurf“ aus ui_upload ────────────────

def _ordner_ctx(aktion: str = "ordner_als_entwurf") -> state_mod.TurnContext:
    ctx = _ctx(None, message="Ordnerstruktur „Physik“ als Themenbaum-Entwurf übernehmen")
    ctx.ui_antwort = {"block_id": "b0000001", "modul": "ui_upload", "frage": "Ordner erfassen",
                      "labels": [], "daten": {"aktion": aktion, "struktur": {
                          "name": "Physik", "dateien": 0, "alle_dateien": 1,
                          "kinder": [{"name": "Böses <Ordner>", "dateien": 1, "alle_dateien": 1,
                                      "kinder": []}]}}}
    return ctx


def test_ordner_als_entwurf_wird_geprueft_und_ohne_llm_beantwortet(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    handler = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", handler)
    uebernommen: list = []

    async def uebernehmen(session, session_id, entities, geprueft):
        uebernommen.append(geprueft)

    gespeichert: list = []

    async def update_session(session, session_id, **felder):
        gespeichert.append(felder)

    monkeypatch.setattr(pf_mod.arbeitsstand, "uebernehmen", uebernehmen)
    monkeypatch.setattr(pf_mod, "update_session", update_session)
    ctx = _ordner_ctx()
    out = asyncio.run(preflight(ctx, _SESSION))
    assert out.early_response.content == "ORDNER-OK"
    # Paket V1: die Ordner werden Teil des Vorgangs (dieser Zug erreicht ``persist`` nie), und der
    # Verweis geht sofort fest (Review V1, Befund 7)
    assert uebernommen == [ctx.ui_antwort] and "entities" in gespeichert[0]
    # die Sicherheitsprüfung las die Ordnernamen (nicht nur die Blase)
    assert "Böses <Ordner>" in safety.calls[0]["args"][0]
    assert handler.calls[0]["args"][3] is ctx.ui_antwort


def test_ordner_als_entwurf_wird_bei_hohem_risiko_nicht_gebaut(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))
    handler = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", handler)
    out = asyncio.run(preflight(_ordner_ctx(), _SESSION))
    assert out.early_response.content != "ORDNER-OK" and handler.calls == []


def test_nur_der_befund_geht_den_gewoehnlichen_weg(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    handler = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", handler)
    out = asyncio.run(preflight(_ordner_ctx("erfasst"), _SESSION))
    assert out.early_response is None and handler.calls == [] and safety.calls == []


def test_ordner_als_entwurf_ohne_moderation_wird_nicht_gebaut(monkeypatch):
    """Review U3-1, Befund 10: ``MODERATION_FAILURE_MODE=closed`` gilt auch hier."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    monkeypatch.setattr(pf_mod, "sperrt_ohne_moderation", lambda _d: True)
    handler = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", handler)
    out = asyncio.run(preflight(_ordner_ctx(), _SESSION))
    assert out.early_response is not None and out.early_response.content != "ORDNER-OK"
    assert handler.calls == []


# ── Paket A1 (Review, Befund 1/2/13): Abläufe im Preflight ─────────────────────────────────

def _lauf_spione(monkeypatch, wartet=True):
    gerufen: dict[str, list] = {"starten": [], "fortsetzen": []}

    async def wartet_auf(session, sid, state, geprueft):
        return wartet

    async def starten(session, req, state, **k):
        gerufen["starten"].append(k)
        return ChatResponse(session_id="bb-1", content="ABLAUF-START")

    async def fortsetzen(session, req, state, geprueft, **k):
        gerufen["fortsetzen"].append((geprueft, k))
        return ChatResponse(session_id="bb-1", content="ABLAUF-WEITER")

    monkeypatch.setattr(pf_mod.ablauf_zug, "wartet_auf", wartet_auf)
    monkeypatch.setattr(pf_mod.ablauf_zug, "starten", starten)
    monkeypatch.setattr(pf_mod.ablauf_zug, "fortsetzen", fortsetzen)
    return gerufen


def test_der_ordner_knopf_im_lauf_setzt_den_ablauf_fort(monkeypatch):
    """Befund 1: ``ordner_als_entwurf`` auf den offenen Block eines Laufs gehört dem Treiber."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="medium",
                                                       blocked_tools=["search_wlo_all"]))
    ordner = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", ordner)
    gerufen = _lauf_spione(monkeypatch)
    ctx = _ordner_ctx()
    out = asyncio.run(preflight(ctx, _SESSION))
    assert out.early_response.content == "ABLAUF-WEITER" and ordner.calls == []
    [(geprueft, k)] = gerufen["fortsetzen"]
    assert geprueft is ctx.ui_antwort and k["blocked_tools"] == ["search_wlo_all"]
    # die Ordnernamen gingen durch die Sicherheitsprüfung
    assert "Böses <Ordner>" in safety.calls[0]["args"][0]


def test_ohne_lauf_bleibt_der_ordner_knopf_beim_ordner_weg(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    ordner = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", ordner)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(pf_mod.arbeitsstand, "uebernehmen", nichts)
    monkeypatch.setattr(pf_mod, "update_session", nichts)
    gerufen = _lauf_spione(monkeypatch, wartet=False)
    out = asyncio.run(preflight(_ordner_ctx(), _SESSION))
    assert out.early_response.content == "ORDNER-OK" and gerufen["fortsetzen"] == []


def test_ablauf_starten_gibt_die_werkzeugsperren_weiter(monkeypatch):
    """Befund 2: eine mittlere Einstufung sperrt Werkzeuge auch für die Schritte."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="medium",
                                              blocked_tools=["search_wlo_all"]))
    gerufen = _lauf_spione(monkeypatch)
    ctx = _ctx("ablauf_starten", ablauf="sammlungsstruktur")
    out = asyncio.run(preflight(ctx, _SESSION))
    assert out.early_response.content == "ABLAUF-START"
    assert gerufen["starten"] == [{"blocked_tools": ["search_wlo_all"]}]


def test_ablauf_starten_bei_hohem_risiko_startet_nicht(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))
    gerufen = _lauf_spione(monkeypatch)
    out = asyncio.run(preflight(_ctx("ablauf_starten", ablauf="x"), _SESSION))
    assert out.early_response.content != "ABLAUF-START" and gerufen["starten"] == []


# ── Paket A2a: Auslöser Wendung und Modul-Antwort im Preflight ───────────────────────────────

def _ausloeser_spione(monkeypatch, *, text=None, modul=None):
    gerufen: dict[str, list] = {"text": [], "modul": []}
    monkeypatch.setattr(pf_mod.ablauf_zug, "text_ausloeser", lambda nachricht: text)
    monkeypatch.setattr(pf_mod.ablauf_zug, "modul_ausloeser", lambda geprueft: modul)

    async def starten_mit(session, req, state, ablauf, **k):
        gerufen["text"].append((ablauf, k))
        return ChatResponse(session_id="bb-1", content="ABLAUF-TEXT")

    async def per_modul_starten(session, req, state, geprueft, treffer, **k):
        gerufen["modul"].append((treffer, k))
        return ChatResponse(session_id="bb-1", content="ABLAUF-MODUL")

    monkeypatch.setattr(pf_mod.ablauf_zug, "starten_mit", starten_mit)
    monkeypatch.setattr(pf_mod.ablauf_zug, "per_modul_starten", per_modul_starten)
    return gerufen


def test_eine_wendung_startet_den_ablauf_nach_der_sicherheitspruefung(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="medium",
                                                       blocked_tools=["search_wlo_all"]))
    gerufen = _ausloeser_spione(monkeypatch, text="ABLAUF")
    out = asyncio.run(preflight(_ctx(None, message="Themenbaum aus meinem Ordner"), _SESSION))
    assert out.early_response.content == "ABLAUF-TEXT"
    assert gerufen["text"] == [("ABLAUF", {"blocked_tools": ["search_wlo_all"]})]
    assert "Themenbaum aus meinem Ordner" in safety.calls[0]["args"][0]


def test_eine_wendung_bei_hohem_risiko_geht_den_gewoehnlichen_weg(monkeypatch):
    """Review A2a, Befund 2: keine Abweisung als Direktaktion — der gewöhnliche Weg antwortet
    (bei einer Krise mit M01), und er protokolliert selbst."""
    _patch_handlers(monkeypatch)
    log, _save = _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))
    gerufen = _ausloeser_spione(monkeypatch, text="ABLAUF")
    out = asyncio.run(preflight(_ctx(None, message="Themenbaum aus meinem Ordner"), _SESSION))
    assert out.early_response is None and gerufen["text"] == [] and log.calls == []


def test_eine_wendung_waehrend_eines_wartenden_laufs_ersetzt_ihn_nicht(monkeypatch):
    """Review A2a, Befund 1: getippter Text im Lauf ist ein gewöhnlicher Zug (F1)."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    gerufen = _ausloeser_spione(monkeypatch, text="ABLAUF")
    monkeypatch.setattr(pf_mod.ablauf_zug, "lauf_wartet", lambda sid, state: True)
    out = asyncio.run(preflight(_ctx(None, message="Themenbaum aus meinem Ordner"), _SESSION))
    assert out.early_response is None and gerufen["text"] == [] and safety.calls == []


def test_ohne_wendung_geht_der_zug_den_gewoehnlichen_weg(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    _ausloeser_spione(monkeypatch)
    out = asyncio.run(preflight(_ctx(None, message="Hallo"), _SESSION))
    assert out.early_response is None and safety.calls == []


def test_ein_modul_ausloeser_geht_vor_der_ordner_aktion(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    ordner = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", ordner)
    _lauf_spione(monkeypatch, wartet=False)
    gerufen = _ausloeser_spione(monkeypatch, modul=("ABLAUF", 1))
    out = asyncio.run(preflight(_ordner_ctx(), _SESSION))
    assert out.early_response.content == "ABLAUF-MODUL" and ordner.calls == []
    assert gerufen["modul"] == [(("ABLAUF", 1), {"blocked_tools": []})]
    assert "Böses <Ordner>" in safety.calls[0]["args"][0]


def test_ablauf_weiter_ist_eine_direktaktion_hinter_der_pruefung(monkeypatch):
    """Paket A2b: „Weiter im Ablauf“ — mit den Werkzeugsperren dieser Prüfung."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low", blocked_tools=["x"]))
    gerufen: list = []

    async def weiter_nach_ki(session, req, state, **k):
        gerufen.append(k)
        return ChatResponse(session_id="bb-1", content="WEITER")

    monkeypatch.setattr(pf_mod.ablauf_zug, "weiter_nach_ki", weiter_nach_ki)
    out = asyncio.run(preflight(_ctx("ablauf_weiter", ablauf="baum"), _SESSION))
    assert out.early_response.content == "WEITER" and gerufen == [{"blocked_tools": ["x"]}]



def test_eine_modul_antwort_im_wartenden_lauf_startet_keinen_neuen(monkeypatch):
    """Review A2b, Befund 2: am agent-Schritt zeigt die KI Module — ihre Antwort ersetzt den Lauf
    nicht."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    ordner = _Spy(ChatResponse(session_id="bb-1", content="ORDNER-OK"))
    monkeypatch.setattr(pf_mod, "handle_folders_as_draft", ordner)
    _lauf_spione(monkeypatch, wartet=False)
    gerufen = _ausloeser_spione(monkeypatch, modul=("ABLAUF", 1))
    monkeypatch.setattr(pf_mod.ablauf_zug, "lauf_wartet", lambda sid, state: True)

    async def nichts(*_a, **_k):
        return None

    monkeypatch.setattr(pf_mod.arbeitsstand, "uebernehmen", nichts)
    monkeypatch.setattr(pf_mod, "update_session", nichts)
    asyncio.run(preflight(_ordner_ctx(), _SESSION))
    assert gerufen["modul"] == []


# ── Querschnitts-Review 2026-11-06 (Q2) ─────────────────────────────────────────────────────

def test_m4_eine_wendung_prueft_die_ganze_nachricht(monkeypatch):
    """Vorher nur die ersten 500 Zeichen: eine Krise dahinter blieb ungesehen, der Ablauf
    startete."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    safety = _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    _ausloeser_spione(monkeypatch, text="ABLAUF")
    lang = "Themenbaum aus meinem Ordner " + "x" * 700 + " ich will nicht mehr leben"
    asyncio.run(preflight(_ctx(None, message=lang), _SESSION))
    assert "nicht mehr leben" in safety.calls[0]["args"][0]


def _pruef_spion(monkeypatch):
    gerufen: list[dict] = []

    async def pruefen(session, req, state, **k):
        gerufen.append(k)
        return ChatResponse(session_id="bb-1", content="STAND")

    monkeypatch.setattr(pf_mod.auftrag_zug, "pruefen", pruefen)
    return gerufen


def test_stand_pruefen_geht_durch_die_sicherheitspruefung_mit_sperren(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="medium",
                                              blocked_tools=["search_wlo_all"]))
    gerufen = _pruef_spion(monkeypatch)
    out = asyncio.run(preflight(_ctx("ablauf_auftrag_pruefen", ablauf="lesen"), _SESSION))
    assert out.early_response.content == "STAND"
    assert gerufen == [{"blocked_tools": ["search_wlo_all"]}]


def test_stand_pruefen_bei_hohem_risiko_nicht(monkeypatch):
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))
    gerufen = _pruef_spion(monkeypatch)
    out = asyncio.run(preflight(_ctx("ablauf_auftrag_pruefen", ablauf="lesen"), _SESSION))
    assert out.early_response.content != "STAND" and gerufen == []


def test_der_verweis_wird_vor_den_ablauf_pruefungen_aufgefrischt(monkeypatch):
    """Review Q3, Befund 10: ``lauf_wartet`` und die Auslöser lesen nur den Verweis — er muss
    vorher dem Vorgang gefolgt sein."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    _ausloeser_spione(monkeypatch)
    reihe: list[str] = []

    async def auffrischen(session, sid, entities):
        reihe.append("auffrischen")

    def wartet(sid, state):
        reihe.append("lauf_wartet")
        return False

    monkeypatch.setattr(pf_mod.arbeitsstand, "auffrischen", auffrischen)
    monkeypatch.setattr(pf_mod.ablauf_zug, "lauf_wartet", wartet)
    asyncio.run(preflight(_ctx(None, message="Hallo"), _SESSION))
    assert reihe[:2] == ["auffrischen", "lauf_wartet"]


def test_neues_vorhaben_und_loeschen_gehen_durch_die_sicherheitspruefung(monkeypatch):
    """Querschnitts-Review 2026-11-06 (Q3): die neuen Direktaktionen wie jede andere."""
    _patch_handlers(monkeypatch)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low"))
    gerufen: list[str] = []

    async def neu(session, req, state):
        gerufen.append("neu")
        return ChatResponse(session_id="bb-1", content="NEU")

    async def loeschen(session, req, state):
        gerufen.append("loeschen")
        return ChatResponse(session_id="bb-1", content="WEG")

    monkeypatch.setattr(pf_mod.vorgang_aktion, "neu", neu)
    monkeypatch.setattr(pf_mod.vorgang_aktion, "loeschen", loeschen)
    assert asyncio.run(preflight(_ctx("vorgang_neu"), _SESSION)).early_response.content == "NEU"
    weg = asyncio.run(preflight(_ctx("vorgang_loeschen"), _SESSION))
    assert weg.early_response.content == "WEG"
    _patch_safety(monkeypatch, SafetyDecision(risk_level="high"))
    assert asyncio.run(preflight(_ctx("vorgang_neu"), _SESSION)).early_response.content != "NEU"
    assert gerufen == ["neu", "loeschen"]
