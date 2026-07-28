"""RAG retrieval (P6-1): config resolution + pgvector similarity search.

Ports ALT ``rag_service.py`` / ``db_rag.py``:
* ``get_retrieval_settings`` + ``_parse_float_env`` / ``_parse_int_env`` + ``_RAG_DEFAULTS``
  resolve the 3 retrieval params (``top_k``, ``min_score`` 0-1, ``max_chars_per_area``
  0 = uncapped) from ENV > yaml-area > defaults;
* ``search_rag_chunks`` / ``query_rag`` do the per-area similarity search;
* ``get_rag_context`` / ``get_always_on_rag_context`` merge areas, apply the
  ``min_score`` floor, run the V13 rerank seam (``rag/rerank`` — decision resolved
  2026-07-17: embedding-order default, see there) and render the ``[Quelle: …]``
  prompt block. Deviations vs ALT: session DI, ``embedding`` transport, and the
  ``run_in_rerank_pool`` wrapper dropped (sync seam call — no CPU-bound backend;
  the capped pool returns together with a CE backend). Bodies otherwise verbatim.

**NEU-Portierung:**
* The two ``_parse_*_env`` helpers are byte-for-byte ALT. In ``get_retrieval_settings``
  the single yaml read is the sanctioned config-backend swap (P2: ALT read files via
  ``config_loader._load_yaml``; NEU reads the Postgres-backed config_store via
  ``area()``) — ``_load_yaml("01-base/rag-retrieval.yaml")`` ->
  ``area("01-base/rag-retrieval")`` (same ``.yaml``-suffix-stripping mapping as the
  sibling ``config_loader/rag.py``; ``area()`` returns ``{}`` on a missing area, matching
  ALT's ``_load_yaml`` default, so the yaml tier stays a graceful optional override).
  Everything else in the fn is byte-for-byte ALT.
* ``search_rag_chunks`` is a **rewrite, not a port**: ALT ran sqlite-vec (vec0 KNN on a
  virtual table, **L2** distance, ``score = 1/(1+distance)``, over-fetching ``top_k*5``
  because vec0's KNN cannot filter by area, then filtering in a wrapping query). NEU runs
  **pgvector cosine** (``<=>``, matching the ``hnsw vector_cosine_ops`` index) with the
  area filter INSIDE the query — the over-fetch hack is gone — and scores
  ``1 - cosine_distance``. Ranking therefore differs from ALT **by design** (spec risk
  row "pgvector-Ranking != sqlite-vec-Ranking": compare via Ragas/samples in P6;
  ``RAG_MIN_SCORE`` is the config-side adjuster, not code). ``title``/``source`` come from
  ``rag_documents`` via LEFT JOIN (NEU normalised ALT's flat table; ``document_id`` is
  nullable, so orphan chunks yield ``None``). Chunks without an embedding are skipped —
  ALT's vec0 table only ever held embedded rows. The result dict contract
  ``{chunk, score, source, area, title}`` is ALT-identical.
* The ``AsyncSession`` is passed in (spec rule 3: no module-global engine) instead of
  ALT's global ``_connect_vec()``.
"""

from __future__ import annotations

import asyncio
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import RagChunk, RagDocument
from boerdi.services.config_loader._store import area
from boerdi.services.llm import embedding
from boerdi.services.rag.rerank import _RERANK_CANDIDATES, rerank_results

_RAG_DEFAULTS = {
    "top_k": 15,
    "min_score": 0.30,
    "max_chars_per_area": 3000,  # cap per-area text injected into prompt
}


def _parse_float_env(name: str) -> float | None:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _parse_int_env(name: str) -> int | None:
    raw = (os.getenv(name) or "").strip()
    if not raw.isdigit():
        return None
    return int(raw)


def get_retrieval_settings() -> dict:
    """Resolve retrieval params from ENV > yaml > defaults.

    Keys: ``top_k`` (int), ``min_score`` (float 0-1),
    ``max_chars_per_area`` (int, 0 = no cap).
    """
    settings = dict(_RAG_DEFAULTS)
    # YAML tier (optional)
    try:
        cfg = area("01-base/rag-retrieval") or {}
        r = cfg.get("retrieval") if isinstance(cfg, dict) else None
        if isinstance(r, dict):
            if isinstance(r.get("top_k"), int) and r["top_k"] > 0:
                settings["top_k"] = r["top_k"]
            if isinstance(r.get("min_score"), (int, float)) and 0 <= r["min_score"] <= 1:
                settings["min_score"] = float(r["min_score"])
            if isinstance(r.get("max_chars_per_area"), int) and r["max_chars_per_area"] >= 0:
                settings["max_chars_per_area"] = r["max_chars_per_area"]
    except Exception:
        pass
    # ENV tier (wins)
    env_top_k = _parse_int_env("RAG_TOP_K")
    if env_top_k and env_top_k > 0:
        settings["top_k"] = env_top_k
    env_score = _parse_float_env("RAG_MIN_SCORE")
    if env_score is not None and 0 <= env_score <= 1:
        settings["min_score"] = env_score
    env_cap = _parse_int_env("RAG_MAX_CHARS_PER_AREA")
    if env_cap is not None and env_cap >= 0:
        settings["max_chars_per_area"] = env_cap
    return settings


async def search_rag_chunks(
    session: AsyncSession, area: str, query_embedding: list[float], top_k: int = 3
) -> list[dict]:
    """Similarity search over one knowledge area (pgvector cosine).

    Returns ALT's dict shape ``{chunk, score, source, area, title}``, best match
    first. ``score`` is cosine similarity (``1 - <=>``, so 1.0 = identical). The
    ``area`` parameter shadows the config-store ``area()`` import on purpose — it is
    ALT's name and the DB column's name, and this fn never reads config.
    """
    distance = RagChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(
            RagChunk.content,
            RagChunk.area,
            RagDocument.title,
            RagDocument.source,
            distance.label("distance"),
        )
        .select_from(RagChunk)
        .outerjoin(RagDocument, RagChunk.document_id == RagDocument.id)
        .where(RagChunk.area == area, RagChunk.embedding.is_not(None))
        .order_by(distance)
        .limit(top_k)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "chunk": r.content,
            "score": 1.0 - float(r.distance),
            "source": r.source,
            "area": r.area,
            "title": r.title,
        }
        for r in rows
    ]


async def query_rag(
    session: AsyncSession,
    query: str,
    area: str = "general",
    top_k: int = 3,
    query_emb: list[float] | None = None,
) -> list[dict]:
    """Search RAG knowledge base by semantic similarity.

    ``query_emb`` lets multi-area callers embed the query ONCE and reuse it
    (avoids one embedding round-trip per area). None → embed here, as before.
    """
    if query_emb is None:
        query_emb = await embedding(query)
    results = await search_rag_chunks(session, area, query_emb, top_k)
    return results


async def get_rag_context(session: AsyncSession, query: str,
                          areas: list[str] | None = None, top_k: int = 3,
                          min_score: float = 0.25,
                          max_chars_per_area: int = 0,
                          out_sources: list[str] | None = None) -> str:
    """Get RAG context string for injection into LLM prompt.

    Queries all given areas, merges results, filters by relevance threshold,
    and returns the top-k chunks sorted by score. Because all areas share the
    same embedding model and distance metric, scores are directly comparable
    across areas — no per-area guarantees needed.

    Args:
        query: Search query.
        areas: List of knowledge areas to search.
        top_k: Maximum total chunks to return.
        min_score: Minimum similarity score (0-1). Chunks below this threshold
                   are dropped even if top_k is not yet reached. This prevents
                   irrelevant chunks from diluting the context.
        max_chars_per_area: Optional per-area character cap applied AFTER
                            relevance ranking. 0 = unlimited (default).
                            Protects against prompt bloat when many areas
                            each contribute large chunks.
    """
    if not areas:
        areas = ["general"]

    # Embed the query ONCE and search all areas concurrently — previously each
    # area re-embedded the same query and ran serially (N embed round-trips +
    # serial searches per RAG turn, T-7). Scores are re-sorted globally below,
    # so the concurrent completion order does not affect the result.
    query_emb = await embedding(query)
    per_area = await asyncio.gather(
        *(query_rag(session, query, area, top_k, query_emb=query_emb) for area in areas)
    )
    all_results = []
    for results in per_area:
        all_results.extend(results)

    if not all_results:
        return ""

    # Sort by embedding score globally across all areas.
    all_results.sort(key=lambda x: x["score"], reverse=True)

    # Embedding score acts as a safety floor — anything below min_score is
    # almost certainly irrelevant, so drop it before (optional) rerank.
    # This also prevents the cross-encoder from wasting cycles on noise.
    plausible = [r for r in all_results if r["score"] >= min_score]

    if not plausible:
        return ""

    # Cross-encoder rerank is always on (ONNX int8). If the model file
    # is missing, rerank_results transparently falls back to score-sort.
    # A5 (2026-06-10): der ONNX-Predict ist CPU-bound (~600 ms) und lief
    # synchron im Event-Loop — währenddessen standen ALLE parallelen
    # Requests. In den Default-ThreadPool auslagern (onnxruntime gibt das
    # GIL während der Inferenz frei, echte Parallelität).
    candidates = plausible[:max(_RERANK_CANDIDATES, top_k)]
    # Gedeckelter Rerank-Pool statt Default-Executor (2026-06-15): so
    # konkurrieren RAG-Rerank und Card-CE-Gate um dieselben max_workers
    # und überbuchen die CPU nicht.
    top = rerank_results(query, candidates, top_k)

    if not top:
        return ""

    # Optional per-area cap: greedily take highest-scored chunks per area
    # until the char budget is spent. Prevents a single area from monopolising
    # the context window when multiple areas have good matches.
    if max_chars_per_area and max_chars_per_area > 0:
        per_area_used: dict[str, int] = {}
        filtered = []
        for r in top:
            a = r.get("area", "")
            used = per_area_used.get(a, 0)
            chunk = r.get("chunk") or ""
            # Keep the whole chunk if it fits; otherwise truncate the last
            # chunk that crosses the budget and drop subsequent ones for
            # that area.
            if used >= max_chars_per_area:
                continue
            remaining = max_chars_per_area - used
            if len(chunk) > remaining:
                r = dict(r)
                r["chunk"] = chunk[:remaining].rstrip() + "…"
                per_area_used[a] = max_chars_per_area
            else:
                per_area_used[a] = used + len(chunk)
            filtered.append(r)
        top = filtered

    parts = []
    for r in top:
        # Expose rerank score (if present) so prompt/debug shows the effective
        # ordering criterion. Embedding score is kept as "Relevanz".
        tag = f"[Quelle: {r.get('title', r.get('source', 'unbekannt'))} | " \
              f"Bereich: {r['area']} | Relevanz: {r['score']:.2f}"
        if "rerank_score" in r:
            tag += f" | Rerank: {r['rerank_score']:.2f}"
        tag += "]"
        parts.append(f"{tag}\n{r['chunk']}")

    # Side-channel for callers that want to know which source filenames
    # contributed to the prompt — used by the Webseiten-Lotsen-Modus to
    # surface a precise "Bring mich hin"-URL via ``rag_url_index``.
    # Filled in rank-order; caller decides what to do with it.
    if out_sources is not None:
        for r in top:
            src = r.get("source")
            if isinstance(src, str) and src and src not in out_sources:
                out_sources.append(src)

    return "\n\n---\n\n".join(parts)


async def get_always_on_rag_context(session: AsyncSession, query: str, top_k: int = 3) -> str:
    """Get RAG context from areas configured as 'always' available.

    These areas are included in every request regardless of pattern config.
    """
    from boerdi.services.config_loader import get_always_on_rag_areas

    always_areas = get_always_on_rag_areas()
    if not always_areas:
        return ""

    return await get_rag_context(session, query, areas=always_areas, top_k=top_k)
