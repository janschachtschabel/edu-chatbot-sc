"""Coverage + Verhaltens-Pins für card_reranker (Port aus ALT test_card_reranker).

Reine Env-/Threshold-/Doc-Helfer + ``rerank_gate_envelope`` (Cross-Encoder via
gemocktem ``rag_service._get_reranker`` → Fake mit ``.predict()``). Kein echtes
Modell nötig. Deckt: Fallback ohne CE, CE-Rank+Gate, Soft-Gate, CE-Error, leere
Query, nicht-parsebares Envelope.

Test-Anpassung ggü. ALT: ALT patchte ``app.services.rag_service``. Der V13-Seam
ist seit P6 real gebaut (``boerdi.services.rag.rerank._get_reranker``, Entscheid
2026-07-17) — der Fake-Scorer wird direkt dort angehängt statt wie zuvor als
Fake-Modul unter dem nie gebauten ALT-Namenspfad registriert.
"""

from __future__ import annotations

import json

from boerdi.services import card_reranker as cr


# ── Env-/Threshold-/Doc-Helfer (rein) ──────────────────────────────
def test_env_float(monkeypatch):
    monkeypatch.delenv("CE_X", raising=False)
    assert cr._env_float("CE_X", 1.5) == 1.5
    monkeypatch.setenv("CE_X", "2.5")
    assert cr._env_float("CE_X", 1.5) == 2.5
    monkeypatch.setenv("CE_X", "keine zahl")
    assert cr._env_float("CE_X", 1.5) == 1.5


def test_env_int(monkeypatch):
    monkeypatch.delenv("CE_N", raising=False)
    assert cr._env_int("CE_N", 3) == 3
    monkeypatch.setenv("CE_N", "5")
    assert cr._env_int("CE_N", 3) == 5
    monkeypatch.setenv("CE_N", "x")
    assert cr._env_int("CE_N", 3) == 3


def test_threshold_for_tool(monkeypatch):
    monkeypatch.delenv("CARD_CE_GATE_COLLECTION", raising=False)
    monkeypatch.delenv("CARD_CE_GATE_CONTENT", raising=False)
    assert cr.threshold_for_tool("search_wlo_collections") == 0.0
    assert cr.threshold_for_tool("search_wlo_topic_pages") == 0.0
    assert cr.threshold_for_tool("search_wlo_content") == -1.5
    assert cr.threshold_for_tool("get_node_details") == -1.5


def test_doc_text():
    item = {"title": "Bruch", "description": "Ein Bruch", "keywords": ["mathe", "klasse5"]}
    assert cr._doc_text(item) == "Bruch. Ein Bruch mathe klasse5"
    assert cr._doc_text("kein dict") == ""


# ── rerank_gate_envelope ───────────────────────────────────────────
class _FakeRR:
    def __init__(self, scores):
        self._scores = scores

    def predict(self, pairs):
        return self._scores[:len(pairs)]


def _mock_rr(monkeypatch, rr):
    """Hängt den Fake-Scorer an den echten V13-Seam (``rag/rerank._get_reranker``)."""
    import boerdi.services.rag.rerank as rk

    monkeypatch.setattr(rk, "_get_reranker", lambda: rr)


def _envelope(*items, **extra):
    return json.dumps({"total": 99, "count": len(items), "results": list(items), **extra})


def test_rerank_empty_text_unchanged():
    out, dbg = cr.rerank_gate_envelope("q", "", tool_name="search_wlo_content")
    assert out == "" and dbg is None


def test_rerank_non_envelope_unchanged():
    out, dbg = cr.rerank_gate_envelope("q", "kein json", tool_name="search_wlo_content")
    assert out == "kein json" and dbg is None


def test_rerank_fallback_no_reranker(monkeypatch):
    _mock_rr(monkeypatch, None)
    env = _envelope({"nodeId": "1"}, {"nodeId": "2"}, {"nodeId": "3"}, {"nodeId": "4"})
    out, dbg = cr.rerank_gate_envelope("q", env, tool_name="search_wlo_content", top_n=2)
    parsed = json.loads(out)
    assert dbg["mode"] == "fallback-no-ce"
    assert len(parsed["results"]) == 2       # Top-N nach MCP-Reihenfolge
    assert parsed["count"] == 2
    assert parsed["total"] == 99             # total unangetastet


def test_rerank_ce_ranks_and_gates(monkeypatch):
    _mock_rr(monkeypatch, _FakeRR([2.0, -3.0, 1.0]))
    env = _envelope({"nodeId": "1", "title": "relevant"},
                    {"nodeId": "2", "title": "offtopic"},
                    {"nodeId": "3", "title": "ok"})
    # Content-Gate -1.5: item2 (-3.0) fällt raus; sortiert nach Score desc.
    out, dbg = cr.rerank_gate_envelope("Klimawandel", env, tool_name="search_wlo_content", top_n=5)
    parsed = json.loads(out)
    assert [r["nodeId"] for r in parsed["results"]] == ["1", "3"]
    assert dbg["dropped_by_gate"] == 1
    assert dbg["out"] == 2


def test_rerank_soft_gate_keeps_all_ranked(monkeypatch):
    _mock_rr(monkeypatch, _FakeRR([-2.0, -4.0]))
    env = _envelope({"nodeId": "1"}, {"nodeId": "2"}, _global_fallback=True)
    out, dbg = cr.rerank_gate_envelope("q", env, tool_name="search_wlo_topic_pages",
                                       top_n=5, allow_soft_fallback=True)
    parsed = json.loads(out)
    assert dbg["soft_gate"] is True
    assert dbg["dropped_by_gate"] == 0
    assert [r["nodeId"] for r in parsed["results"]] == ["1", "2"]  # nur gerankt, nichts gegated


def test_rerank_ce_predict_error_falls_back(monkeypatch):
    class _BoomRR:
        def predict(self, pairs):
            raise RuntimeError("ce boom")

    _mock_rr(monkeypatch, _BoomRR())
    env = _envelope({"nodeId": "1"}, {"nodeId": "2"})
    out, dbg = cr.rerank_gate_envelope("q", env, tool_name="search_wlo_content", top_n=1)
    assert dbg["mode"] == "fallback-ce-error"
    assert len(json.loads(out)["results"]) == 1


def test_rerank_empty_query_uses_fallback(monkeypatch):
    _mock_rr(monkeypatch, _FakeRR([5.0, 5.0]))
    env = _envelope({"nodeId": "1"}, {"nodeId": "2"})
    out, dbg = cr.rerank_gate_envelope("", env, tool_name="search_wlo_content", top_n=1)
    assert dbg["mode"] == "fallback-no-ce"   # leere Query → kein CE


def test_card_gate_has_its_own_switch(monkeypatch):
    """W9: der billige Pfad darf nicht am teuren hängen.

    Das Karten-Gate kostet ein Achtel des RAG-Reranks (227 ms gegen 1853 ms bei
    3 Threads, je 25 Elemente) und liefert das sichtbarste Stück Qualität — das
    Wegwerfen thematisch verfehlter Treffer. Wer den RAG-Rerank abschaltet, soll
    dieses Gate nicht STILL mitverlieren; und umgekehrt.
    """
    import json as _json

    from boerdi.services.card_reranker import rerank_gate_envelope
    from boerdi.settings import get_settings

    class _Backend:
        def predict(self, pairs):
            return [-9.0] * len(pairs)  # alles off-topic → Gate wirft weg

    monkeypatch.setattr(
        "boerdi.services.rag.rerank._get_reranker", lambda: _Backend(),
    )
    envelope = _json.dumps({
        "total": 2, "count": 2,
        "results": [{"title": "A", "description": "x"}, {"title": "B", "description": "y"}],
    })

    monkeypatch.setenv("CARD_RERANKER_ENABLED", "true")
    get_settings.cache_clear()
    text, debug = rerank_gate_envelope("Klimawandel", envelope, tool_name="t")
    # Der aktive Pfad setzt kein `mode` — er meldet Schwelle und Verworfene.
    assert "mode" not in debug and debug["dropped_by_gate"] == 2
    assert _json.loads(text)["count"] == 0  # gegatet

    monkeypatch.setenv("CARD_RERANKER_ENABLED", "false")
    get_settings.cache_clear()
    text, debug = rerank_gate_envelope("Klimawandel", envelope, tool_name="t")
    assert debug["mode"] == "fallback-no-ce"
    assert _json.loads(text)["count"] == 2  # ungegatet durchgereicht
