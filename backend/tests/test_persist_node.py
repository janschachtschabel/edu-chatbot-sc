"""graph.nodes.persist — the persist node adapter (R4a Sub-Slice 3).

Thin adapter that chains the three verbatim turn-persist functions and maps every
argument off ``ctx``:
  build_debug_and_update_session (P25-26) → _finalize_links_and_metas (P27-28, #82)
  → persist_and_build_response (P29-33).
These pins verify the wiring only (the three functions have their own suites); the
node's own job is the ctx→arg mapping, the winner-id shim, the no-op tracer, and
storing the finished ChatResponse on ``ctx.response``.
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import (
    ChatRequest,
    ClassificationResult,
    Environment,
    SafetyDecision,
)
from boerdi.graph.nodes import persist as persist_mod
from boerdi.graph.nodes.persist import _ProgressTracer, persist
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import TurnProgress

_SESSION = object()


def _ctx() -> TurnContext:
    ctx = TurnContext(
        req=ChatRequest(
            session_id="bb-1", message="hi",
            environment=Environment(page="/p", device="mobile"),
        ),
        env={"page": "/p", "device": "mobile"},
        session_state={"persona_id": "P-AND", "state_id": "S2", "entities": {}, "turn_count": 3},
        classification=ClassificationResult(intent_id="I03"),
        safety=SafetyDecision(risk_level="low"),
        usage={"calls": 1},
        winner_id="M09", winner_label="Lernpfad",
        pattern_output={"format_follow_up": "quick_replies"},
        scores={"M09": 1.0}, eliminated=[], trans_check={"plausible": True},
        signals=["s1"], signal_history=["s1", "s0"], state_id="S3",
        effective_pattern_id="M09", effective_pattern_label="Lernpfad",
        tools_called=["search_wlo_content"], spec_query="Bruch",
        qr_mode="llm", qr_max=None,
        cards=[], quick_replies=["A"], page_action=None, pagination=None,
        response_text="RT",
    )
    ctx.debug.outcomes = ["OUT"]
    ctx.debug.confidence = 0.7
    return ctx


def _patch(monkeypatch):
    class _Calls:
        bd = fin = pbr = None

    c = _Calls()

    async def _fake_bd(*a, **k):
        c.bd = (a, k)
        return "DEBUG_SENTINEL"

    async def _fake_fin(*a, **k):
        c.fin = (a, k)
        return (["CARD"], "RT2", "FINAL", ["WL"], ["META"], ["QME"], "TF")

    async def _fake_pbr(*a, **k):
        c.pbr = (a, k)
        return "RESPONSE_SENTINEL"

    monkeypatch.setattr(persist_mod, "build_debug_and_update_session", _fake_bd)
    monkeypatch.setattr(persist_mod, "_finalize_links_and_metas", _fake_fin)
    monkeypatch.setattr(persist_mod, "persist_and_build_response", _fake_pbr)
    return c


def _run(monkeypatch):
    c = _patch(monkeypatch)
    ctx = _ctx()
    result = asyncio.run(persist(ctx, _SESSION))
    return result, ctx, c


def test_persist_wires_build_debug_from_ctx(monkeypatch):
    _, _, c = _run(monkeypatch)
    args, kwargs = c.bd
    assert args[0] is _SESSION                       # session injected first
    assert kwargs["new_state"] == "S3"               # ctx.state_id
    assert kwargs["response_outcomes"] == ["OUT"]     # ctx.debug.outcomes
    assert kwargs["final_confidence"] == 0.7          # ctx.debug.confidence
    assert kwargs["winner_id"] == "M09"
    assert kwargs["_effective_pattern_id"] == "M09"


def test_persist_wires_finalize_with_shim_and_null_tracer(monkeypatch):
    _, _, c = _run(monkeypatch)
    args, kwargs = c.fin
    assert kwargs["classification_dict"] == ClassificationResult(intent_id="I03").model_dump()
    assert kwargs["winner"].id == "M09"              # SimpleNamespace(id=ctx.winner_id)
    assert isinstance(kwargs["tracer"], _ProgressTracer)  # forwards to the SSE seam
    assert kwargs["cards"] == []                      # ctx.cards
    assert kwargs["response_text"] == "RT"            # ctx.response_text (pre-finalize)


def test_persist_feeds_finalize_output_into_response_builder(monkeypatch):
    _, _, c = _run(monkeypatch)
    args, kwargs = c.pbr
    assert args[0] is _SESSION                       # session injected first
    assert kwargs["debug"] == "DEBUG_SENTINEL"        # from build_debug
    # the finalize-returned 7-tuple threads through, NOT the raw ctx values
    assert kwargs["cards"] == ["CARD"]
    assert kwargs["response_text"] == "RT2"
    assert kwargs["_final_text"] == "FINAL"
    assert kwargs["_web_links"] == ["WL"]
    assert kwargs["_raw_metas"] == ["META"]
    assert kwargs["_query_meta_entries"] == ["QME"]
    assert kwargs["_type_focus_label"] == "TF"
    # and the ctx-sourced params
    assert kwargs["env"] == {"page": "/p", "device": "mobile"}
    assert kwargs["spec_query"] == "Bruch"
    assert kwargs["new_state"] == "S3"
    assert kwargs["quick_replies"] == ["A"]


def test_persist_stores_response_and_returns_same_ctx(monkeypatch):
    result, ctx, _ = _run(monkeypatch)
    assert result is ctx                              # mutate-and-return idiom
    assert ctx.response == "RESPONSE_SENTINEL"


# ── Gelieferte Boxen: zwei Zuflüsse, eine Naht (D3) ──────────────────

_BOX = {"kind": "stundenplanung", "title": "T", "content": "C",
        "meta": {"source": "tool"}}


def test_die_boxen_der_schleife_gehen_an_den_antwortbau(monkeypatch):
    c = _patch(monkeypatch)
    ctx = _ctx()
    ctx.gelieferte_dokumente = [dict(_BOX)]
    asyncio.run(persist(ctx, _SESSION))
    assert c.pbr[1]["gelieferte_dokumente"] == [_BOX]


def test_die_boxen_des_musterwegs_kommen_aus_dem_session_state(monkeypatch):
    """Der Tool-Loop kennt kein ``ctx`` — er legt sie nach seiner eigenen
    Konvention im ``session_state`` ab (wie ``_selected_card_ids``). Hier
    laufen beide Wege zusammen, damit ``turn_persist`` eine Quelle sieht."""
    c = _patch(monkeypatch)
    ctx = _ctx()
    ctx.session_state["_gelieferte_dokumente"] = [dict(_BOX)]
    asyncio.run(persist(ctx, _SESSION))
    assert c.pbr[1]["gelieferte_dokumente"] == [_BOX]


def test_der_merker_gehoert_diesem_zug(monkeypatch):
    """Bliebe er im ``session_state`` stehen, zeigte der nächste Zug dieselbe
    Box noch einmal — dieselbe Begründung wie bei ``_write_preview``."""
    _patch(monkeypatch)
    ctx = _ctx()
    ctx.session_state["_gelieferte_dokumente"] = [dict(_BOX)]
    asyncio.run(persist(ctx, _SESSION))
    assert "_gelieferte_dokumente" not in ctx.session_state


def test_progress_tracer_swallows_the_duration_alt_passes():
    """ALT ``Tracer.record`` nimmt ein viertes ``duration_ms`` — der Fortschritt
    kennt es nicht. Der Adapter muss den Aufruf trotzdem annehmen, sonst bricht
    ein Verbatim-Port, sobald er es mitgibt."""
    seen: list[dict] = []
    _ProgressTracer(TurnProgress(seen.append)).record("query_meta", "x", {"a": 1}, 42)
    assert seen == [{"kind": "record", "step": "query_meta",
                     "label": "x", "data": {"a": 1}}]


# ── C9: Fortschritts-Meldung ────────────────────────────────────────

def test_persist_forwards_query_meta_from_the_verbatim_port(monkeypatch):
    """``_finalize_links_and_metas`` ist ein Verbatim-Port und ruft darin
    ``tracer.record("query_meta", …)``. Bis C9 bekam er einen No-op-Tracer, der
    den Aufruf verschluckte. Jetzt muss der übergebene Tracer die Meldung an die
    Fortschritts-Naht weiterreichen — sonst ist der Port-Aufruf weiter tot."""
    c = _patch(monkeypatch)
    seen: list[dict] = []
    asyncio.run(persist(_ctx(), _SESSION, progress=TurnProgress(seen.append)))

    tracer = c.fin[1]["tracer"]
    tracer.record("query_meta", "MCP search queries", {"queries": 2})
    assert seen == [{
        "kind": "record", "step": "query_meta",
        "label": "MCP search queries", "data": {"queries": 2},
    }]


# ── Strukturiertes Ergebnis durchreichen (Nutzer-Entscheid 2026-08-14) ──

def _mit_echter_antwort(monkeypatch):
    """Wie ``_patch``, aber der Antwort-Bauer liefert eine ECHTE ChatResponse.

    Die Sentinel-Zeichenkette der Nachbartests genügt hier nicht: geprüft wird
    genau, dass die zwei Felder AN DER ANTWORT ankommen — und an einer
    Zeichenkette kann man nichts setzen. Genau diese Naht (etwas wird gesetzt,
    aber nie weitergereicht) hat am selben Tag schon einmal ein Feld
    verschluckt.
    """
    from boerdi.api.schemas import ChatResponse

    async def _fake_bd(*a, **k):
        return "DEBUG_SENTINEL"

    async def _fake_fin(*a, **k):
        return (["CARD"], "RT2", "FINAL", ["WL"], ["META"], ["QME"], "TF")

    async def _fake_pbr(*a, **k):
        return ChatResponse(session_id="s1", content="FINAL")

    monkeypatch.setattr(persist_mod, "build_debug_and_update_session", _fake_bd)
    monkeypatch.setattr(persist_mod, "_finalize_links_and_metas", _fake_fin)
    monkeypatch.setattr(persist_mod, "persist_and_build_response", _fake_pbr)


def test_ergebnis_und_ende_grund_erreichen_die_antwort(monkeypatch):
    _mit_echter_antwort(monkeypatch)
    ctx = _ctx()
    ctx.result = {"taxon_id": "…/discipline/460"}
    ctx.result_stop_reason = "submit"
    asyncio.run(persist(ctx, _SESSION))
    assert ctx.response.result == {"taxon_id": "…/discipline/460"}
    assert ctx.response.result_stop_reason == "submit"


def test_ohne_ergebnis_bleibt_die_antwort_unberuehrt(monkeypatch):
    # Der Normalfall — ein Chat ohne erklärtes Schema. Kein leeres Feldpaar in
    # jeder Antwort.
    _mit_echter_antwort(monkeypatch)
    ctx = _ctx()
    asyncio.run(persist(ctx, _SESSION))
    assert ctx.response.result is None
    assert ctx.response.result_stop_reason == ""


def test_ein_ende_ohne_ergebnis_wird_trotzdem_gemeldet(monkeypatch):
    # „Hallo" bei erklärtem Schema: kein Ergebnis, aber die Gastseite soll
    # erkennen können, warum.
    _mit_echter_antwort(monkeypatch)
    ctx = _ctx()
    ctx.result_stop_reason = "text"
    asyncio.run(persist(ctx, _SESSION))
    assert ctx.response.result is None
    assert ctx.response.result_stop_reason == "text"
