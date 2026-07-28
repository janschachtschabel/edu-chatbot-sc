"""Behavior pins for services/rag/rerank — the V13 in-proc reranker seam.

Decision record (Nutzer 2026-07-17, verified this session): the pgvector
retrieval already orders by cosine over the shared 6-1 embedder, so a
bi-encoder-cosine rerank with that same embedder is a mathematical no-op.
The seam therefore defaults to embedding-order ranking (= ALT's documented
missing-model fallback); a CE backend can slot into ``_get_reranker`` later.
``_reranker_enabled_via_env`` and ``rerank_results`` are ALT-verbatim ports.
"""

from __future__ import annotations

import boerdi.services.rag.rerank as rk
from boerdi.services.rag.rerank import (
    _get_reranker,
    _reranker_enabled_via_env,
    rerank_results,
)


# ── _reranker_enabled_via_env (ALT-verbatim) ─────────────────────────────
def test_enabled_by_default(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    assert _reranker_enabled_via_env() is True


def test_disabled_values_case_and_whitespace_insensitive(monkeypatch):
    for raw in ("false", "0", "no", "off", " FALSE ", "Off"):
        monkeypatch.setenv("RAG_RERANKER_ENABLED", raw)
        assert _reranker_enabled_via_env() is False, raw


def test_other_values_stay_enabled(monkeypatch):
    for raw in ("true", "1", "yes", "banana"):
        monkeypatch.setenv("RAG_RERANKER_ENABLED", raw)
        assert _reranker_enabled_via_env() is True, raw


# ── _get_reranker: the V13 seam ──────────────────────────────────────────
def test_seam_has_no_backend_today(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    assert _get_reranker() is None


def test_seam_none_when_disabled(monkeypatch):
    monkeypatch.setenv("RAG_RERANKER_ENABLED", "false")
    assert _get_reranker() is None


# ── rerank_results (ALT-verbatim) ────────────────────────────────────────
def _r(chunk, score):
    return {"chunk": chunk, "score": score}


def test_empty_results_and_nonpositive_top_n():
    assert rerank_results("q", [], 3) == []
    assert rerank_results("q", [_r("a", 0.9)], 0) == []


def test_fallback_sorts_by_embedding_score_and_truncates(monkeypatch):
    monkeypatch.delenv("RAG_RERANKER_ENABLED", raising=False)
    out = rerank_results("q", [_r("low", 0.1), _r("high", 0.9), _r("mid", 0.5)], 2)
    assert [r["chunk"] for r in out] == ["high", "mid"]
    assert all("rerank_score" not in r for r in out)


class _FakeBackend:
    """predict() scores the pairs; here: reverse of embedding order."""

    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def predict(self, pairs):
        self.pairs = pairs
        return self.scores[: len(pairs)]


def test_backend_reorders_by_rerank_score(monkeypatch):
    fake = _FakeBackend([0.1, 0.9])  # first input scores low, second high
    monkeypatch.setattr(rk, "_get_reranker", lambda: fake)
    out = rerank_results("q", [_r("emb-best", 0.9), _r("emb-worst", 0.2)], 2)
    assert [r["chunk"] for r in out] == ["emb-worst", "emb-best"]  # CE wins
    assert out[0]["rerank_score"] == 0.9
    assert fake.pairs == [("q", "emb-best"), ("q", "emb-worst")]


def test_backend_predict_error_falls_back_to_score_sort(monkeypatch):
    class _Boom:
        def predict(self, pairs):
            raise RuntimeError("onnx down")

    monkeypatch.setattr(rk, "_get_reranker", lambda: _Boom())
    out = rerank_results("q", [_r("low", 0.1), _r("high", 0.9)], 2)
    assert [r["chunk"] for r in out] == ["high", "low"]
