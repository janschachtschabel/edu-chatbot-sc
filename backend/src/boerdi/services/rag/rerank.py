"""V13 in-proc reranker seam (P6 decision, resolved 2026-07-17).

ALT ran an ONNX cross-encoder here (``rag_service.py``: ``_OnnxReranker`` +
``run_in_rerank_pool`` + the ``RERANK_*`` CPU knobs) and fell back to
embedding-only ranking when the model asset was missing or
``RAG_RERANKER_ENABLED=false``. The V13 options were: bi-encoder-cosine
(sharing the 6-1 embedder) / CE ALT parity / lexical / off.

**Decision (verified):** the pgvector retrieval (``rag/retrieval.search_rag_chunks``)
already orders by cosine over the shared 6-1 embedder — a bi-encoder-cosine
rerank with that same embedder reproduces exactly that order, at the cost of N
extra embedding API calls. So the default backend IS the embedding order:
``_get_reranker()`` returns None and ``rerank_results`` (ALT-verbatim) takes its
fallback branch (score-sort + truncate). A CE backend (new deps: onnxruntime +
tokenizers + ~130 MB asset) can slot into ``_get_reranker`` later without
touching any caller; the capped rerank thread pool returns with it.
``_reranker_enabled_via_env`` keeps the documented ops knob ALT-verbatim.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_RERANK_CANDIDATES = 25   # top-N from embedding retrieval fed into rerank


def _reranker_enabled_via_env() -> bool:
    """Return False wenn ``RAG_RERANKER_ENABLED`` per ENV explizit
    abgeschaltet wurde. Akzeptierte „false"-Werte: ``false``, ``0``,
    ``no``, ``off`` (case-insensitive, mit whitespace-Stripping).
    Alles andere (auch fehlende Variable) → True = Reranker aktiv.

    Use-Case: kleine RAM-Deployments (≤ 2 GB), in denen der ONNX-
    Reranker (~150-300 MB resident) zu OOM-Crashes führt. Embedding-
    only-Ranking ist die Fallback-Strategie — RAG-Antworten sind
    weiterhin nutzbar, nur die Top-1-Sortierung wird etwas weniger
    präzise als mit Cross-Encoder-Reranking.
    """
    import os as _os
    raw = (_os.getenv("RAG_RERANKER_ENABLED") or "").strip().lower()
    if not raw:
        return True
    return raw not in ("false", "0", "no", "off")


def _get_reranker():
    """V13 seam: the in-proc rerank backend, or None = embedding-order ranking.

    Today there is deliberately no backend (see module docstring) — the
    pgvector cosine order already is the bi-encoder ranking of the shared
    6-1 embedder. A CE implementation plugs in here (``predict(pairs)``).
    """
    if not _reranker_enabled_via_env():
        return None
    return None  # no in-proc backend built — embedding order is the ranking


def rerank_results(query: str, results: list[dict], top_n: int) -> list[dict]:
    """Rerank retrieval results with a cross-encoder. Falls back to
    embedding-score sort if the reranker is unavailable.
    """
    if not results or top_n <= 0:
        return results[:top_n] if results else []
    rr = _get_reranker()
    if rr is None:
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return results[:top_n]
    pairs = [(query, r.get("chunk") or "") for r in results]
    try:
        scores = rr.predict(pairs)
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning("Reranker predict failed: %s", e)
        results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return results[:top_n]
    for r, s in zip(results, scores):  # noqa: B905 (verbatim ALT)
        r["rerank_score"] = float(s)
    results.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
    return results[:top_n]
