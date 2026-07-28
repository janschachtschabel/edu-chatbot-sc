"""Behavior pins for services/rag/retrieval (port of ALT rag_service.py
get_retrieval_settings + _parse_float_env + _parse_int_env). ENV > yaml-area >
defaults. The yaml tier is read via the NEU config_store ``area()`` (sanctioned
swap of ALT ``_load_yaml``); tests patch ``area`` and control the 3 RAG_* env vars.
Every expected value is traced against the ALT resolution logic.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

import boerdi.services.rag.retrieval as rr
from boerdi.services.rag.retrieval import (
    _parse_float_env,
    _parse_int_env,
    get_retrieval_settings,
)

_ENV_VARS = ("RAG_TOP_K", "RAG_MIN_SCORE", "RAG_MAX_CHARS_PER_AREA")


def _clear_env(monkeypatch):
    for name in _ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def _no_yaml(monkeypatch):
    # area() returns {} when the config area is unbound/missing (ALT _load_yaml default).
    monkeypatch.setattr(rr, "area", lambda key: {})


# ── get_retrieval_settings: ENV > yaml > defaults ────────────────────────
def test_defaults_when_no_env_and_no_yaml(monkeypatch):
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    assert get_retrieval_settings() == {
        "top_k": 15,
        "min_score": 0.30,
        "max_chars_per_area": 3000,
    }


def test_env_overrides_defaults(monkeypatch):
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    monkeypatch.setenv("RAG_TOP_K", "7")
    monkeypatch.setenv("RAG_MIN_SCORE", "0.5")
    monkeypatch.setenv("RAG_MAX_CHARS_PER_AREA", "500")
    assert get_retrieval_settings() == {
        "top_k": 7,
        "min_score": 0.5,
        "max_chars_per_area": 500,
    }


def test_env_max_chars_zero_is_allowed(monkeypatch):
    # 0 = "no cap" — passes the >= 0 guard.
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    monkeypatch.setenv("RAG_MAX_CHARS_PER_AREA", "0")
    assert get_retrieval_settings()["max_chars_per_area"] == 0


def test_env_out_of_range_min_score_is_ignored(monkeypatch):
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    monkeypatch.setenv("RAG_MIN_SCORE", "1.5")  # > 1 → rejected
    assert get_retrieval_settings()["min_score"] == 0.30


def test_env_zero_top_k_is_ignored(monkeypatch):
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    monkeypatch.setenv("RAG_TOP_K", "0")  # not > 0 → rejected
    assert get_retrieval_settings()["top_k"] == 15


def test_yaml_tier_applies_when_no_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(
        rr, "area",
        lambda key: {"retrieval": {"top_k": 20, "min_score": 0.4, "max_chars_per_area": 1000}},
    )
    assert get_retrieval_settings() == {
        "top_k": 20,
        "min_score": 0.4,
        "max_chars_per_area": 1000,
    }


def test_env_wins_over_yaml(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(rr, "area", lambda key: {"retrieval": {"top_k": 20}})
    monkeypatch.setenv("RAG_TOP_K", "9")
    assert get_retrieval_settings()["top_k"] == 9


def test_returns_fresh_copy_not_the_defaults(monkeypatch):
    _clear_env(monkeypatch)
    _no_yaml(monkeypatch)
    out = get_retrieval_settings()
    out["top_k"] = 999
    assert rr._RAG_DEFAULTS["top_k"] == 15


# ── _parse_int_env / _parse_float_env ────────────────────────────────────
def test_parse_int_env(monkeypatch):
    monkeypatch.setenv("X", "42")
    assert _parse_int_env("X") == 42
    monkeypatch.setenv("X", "-5")  # isdigit() False → None
    assert _parse_int_env("X") is None
    monkeypatch.setenv("X", "abc")
    assert _parse_int_env("X") is None
    monkeypatch.setenv("X", "  ")
    assert _parse_int_env("X") is None
    monkeypatch.delenv("X", raising=False)
    assert _parse_int_env("X") is None


def test_parse_float_env(monkeypatch):
    monkeypatch.setenv("Y", "0.75")
    assert _parse_float_env("Y") == 0.75
    monkeypatch.setenv("Y", "nope")
    assert _parse_float_env("Y") is None
    monkeypatch.setenv("Y", "")
    assert _parse_float_env("Y") is None
    monkeypatch.delenv("Y", raising=False)
    assert _parse_float_env("Y") is None


# ── search_rag_chunks: pgvector cosine (the DB is the faked boundary) ─────
class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _FakeSession:
    """Captures the executed statement and returns canned rows. The real query
    against pgvector is covered by the pg-gated tests/test_rag_search_pg.py."""

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.stmts: list = []

    async def execute(self, stmt):
        self.stmts.append(stmt)
        return _FakeResult(self.rows)


def _row(content, area="general", title="T", source="s.md", distance=0.1):
    return SimpleNamespace(
        content=content, area=area, title=title, source=source, distance=distance
    )


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def test_search_builds_cosine_query_with_left_join_and_area_filter():
    sess = _FakeSession()
    asyncio.run(rr.search_rag_chunks(sess, "erdkunde", [0.1, 0.2], top_k=5))
    sql = _sql(sess.stmts[0])
    assert "<=>" in sql  # cosine distance — matches the hnsw vector_cosine_ops index
    assert "LEFT OUTER JOIN rag_documents" in sql  # title/source live on the document
    assert "rag_chunks.area = " in sql  # filtered IN the query (no ALT over-fetch hack)
    assert "embedding IS NOT NULL" in sql
    assert "ORDER BY" in sql and "LIMIT" in sql


def test_search_maps_rows_to_the_alt_contract():
    sess = _FakeSession([
        _row("Eiszeit-Text", area="erdkunde", title="Klima", source="klima.md", distance=0.25)
    ])
    out = asyncio.run(rr.search_rag_chunks(sess, "erdkunde", [0.1]))
    assert out == [{
        "chunk": "Eiszeit-Text", "score": 0.75, "source": "klima.md",
        "area": "erdkunde", "title": "Klima",
    }]


def test_search_score_is_cosine_similarity():
    # NEU scores 1 - cosine_distance (ALT: 1/(1+L2) on sqlite-vec) — ranking
    # differs from ALT by design; RAG_MIN_SCORE is the config-side adjuster.
    sess = _FakeSession([_row("a", distance=0.0), _row("b", distance=1.0)])
    out = asyncio.run(rr.search_rag_chunks(sess, "general", [0.1]))
    assert [r["score"] for r in out] == [1.0, 0.0]


def test_search_tolerates_chunk_without_document():
    # document_id is nullable -> LEFT JOIN yields NULL title/source
    sess = _FakeSession([_row("orphan", title=None, source=None)])
    out = asyncio.run(rr.search_rag_chunks(sess, "general", [0.1]))
    assert out[0]["title"] is None and out[0]["source"] is None


def test_search_empty_returns_empty_list():
    assert asyncio.run(rr.search_rag_chunks(_FakeSession(), "general", [0.1])) == []


def test_search_top_k_becomes_the_sql_limit():
    sess = _FakeSession()
    asyncio.run(rr.search_rag_chunks(sess, "general", [0.1], top_k=7))
    compiled = sess.stmts[0].compile(dialect=postgresql.dialect())
    assert 7 in compiled.params.values()


# ── query_rag ────────────────────────────────────────────────────────────
def test_query_rag_embeds_when_no_vector_given(monkeypatch):
    seen: list[str] = []

    async def fake_embedding(text):
        seen.append(text)
        return [0.9]

    monkeypatch.setattr(rr, "embedding", fake_embedding)
    out = asyncio.run(rr.query_rag(_FakeSession([_row("x")]), "Eiszeit", "erdkunde"))
    assert seen == ["Eiszeit"] and out[0]["chunk"] == "x"


def test_query_rag_reuses_given_vector_without_re_embedding(monkeypatch):
    async def boom(text):
        raise AssertionError("must not re-embed when query_emb is passed")

    monkeypatch.setattr(rr, "embedding", boom)
    out = asyncio.run(
        rr.query_rag(_FakeSession([_row("y")]), "Eiszeit", "erdkunde", query_emb=[0.5])
    )
    assert out[0]["chunk"] == "y"


# ── get_rag_context (multi-area merge + rerank seam + format) ────────────
def _chunk(text, score, area="a", title="T", source="s.md", **extra):
    return {"chunk": text, "score": score, "source": source, "area": area,
            "title": title, **extra}


def _wire(monkeypatch, per_area, emb=(0.1,)):
    """Fake the two boundaries: embedding (network) + search_rag_chunks (DB).
    Returns (embed_calls, search_calls)."""
    embed_calls: list[str] = []
    search_calls: list[tuple] = []

    async def fake_embedding(text):
        embed_calls.append(text)
        return list(emb)

    async def fake_search(session, area, query_embedding, top_k=3):
        search_calls.append((session, area, tuple(query_embedding), top_k))
        return [dict(r) for r in per_area.get(area, [])]

    monkeypatch.setattr(rr, "embedding", fake_embedding)
    monkeypatch.setattr(rr, "search_rag_chunks", fake_search)
    return embed_calls, search_calls


def test_ctx_embeds_once_and_searches_every_area(monkeypatch):
    embeds, searches = _wire(monkeypatch, {
        "a": [_chunk("A", 0.9, area="a")], "b": [_chunk("B", 0.8, area="b")],
    })
    out = asyncio.run(rr.get_rag_context("sess", "Eiszeit", areas=["a", "b"]))
    assert embeds == ["Eiszeit"]  # embedded ONCE for both areas (T-7)
    assert [(c[1], c[2]) for c in searches] == [("a", (0.1,)), ("b", (0.1,))]
    assert "A" in out and "B" in out


def test_ctx_merges_and_sorts_globally_across_areas(monkeypatch):
    _wire(monkeypatch, {
        "a": [_chunk("weak", 0.5, area="a")], "b": [_chunk("strong", 0.9, area="b")],
    })
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a", "b"]))
    assert out.index("strong") < out.index("weak")


def test_ctx_min_score_floor_drops_and_empties(monkeypatch):
    _wire(monkeypatch, {"a": [_chunk("keep", 0.9), _chunk("drop", 0.2)]})
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a"]))
    assert "keep" in out and "drop" not in out  # default min_score=0.25
    _wire(monkeypatch, {"a": [_chunk("drop", 0.1)]})
    assert asyncio.run(rr.get_rag_context("s", "q", areas=["a"])) == ""


def test_ctx_no_results_returns_empty(monkeypatch):
    _wire(monkeypatch, {})
    assert asyncio.run(rr.get_rag_context("s", "q", areas=["a", "b"])) == ""


def test_ctx_defaults_to_general_area(monkeypatch):
    _, searches = _wire(monkeypatch, {})
    asyncio.run(rr.get_rag_context("s", "q"))
    assert [c[1] for c in searches] == ["general"]


def test_ctx_format_tag_and_separator(monkeypatch):
    _wire(monkeypatch, {"a": [
        _chunk("Text eins", 0.9, area="a", title="Klima"),
        _chunk("Text zwei", 0.8, area="a", title="Wetter"),
    ]})
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a"]))
    assert "[Quelle: Klima | Bereich: a | Relevanz: 0.90]\nText eins" in out
    assert "\n\n---\n\n" in out


def test_ctx_title_falls_back_to_source_then_unbekannt(monkeypatch):
    no_title = {"chunk": "x", "score": 0.9, "area": "a", "source": "s.md"}
    bare = {"chunk": "y", "score": 0.8, "area": "a"}
    _wire(monkeypatch, {"a": [no_title, bare]})
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a"]))
    assert "[Quelle: s.md | Bereich: a" in out
    assert "[Quelle: unbekannt | Bereich: a" in out


def test_ctx_backend_rerank_reorders_and_tags(monkeypatch):
    import boerdi.services.rag.rerank as rk

    class _Backend:
        def predict(self, pairs):
            # score the embedding-weaker chunk higher
            return [0.1 if "emb-best" in p[1] else 0.9 for p in pairs]

    monkeypatch.setattr(rk, "_get_reranker", lambda: _Backend())
    _wire(monkeypatch, {"a": [
        _chunk("emb-best", 0.9, area="a"), _chunk("emb-worst", 0.3, area="a"),
    ]})
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a"]))
    assert out.index("emb-worst") < out.index("emb-best")  # CE decides
    assert "| Rerank: 0.90]" in out


def test_ctx_per_area_char_cap_truncates_and_drops(monkeypatch):
    _wire(monkeypatch, {
        "a": [_chunk("A" * 30, 0.9, area="a"), _chunk("gone", 0.8, area="a")],
        "b": [_chunk("B-bleibt", 0.7, area="b")],
    })
    out = asyncio.run(rr.get_rag_context(
        "s", "q", areas=["a", "b"], max_chars_per_area=10))
    assert "A" * 10 + "…" in out       # truncated at the area budget
    assert "gone" not in out            # same-area follow-up dropped
    assert "B-bleibt" in out            # other area has its own budget


def test_ctx_out_sources_rank_order_dedup(monkeypatch):
    _wire(monkeypatch, {"a": [
        _chunk("one", 0.9, area="a", source="x.md"),
        _chunk("two", 0.8, area="a", source="y.md"),
        _chunk("three", 0.7, area="a", source="x.md"),   # dupe
        {"chunk": "four", "score": 0.6, "area": "a", "title": "t", "source": None},
    ]})
    sources: list[str] = []
    asyncio.run(rr.get_rag_context("s", "q", areas=["a"], top_k=10,
                                   out_sources=sources))
    assert sources == ["x.md", "y.md"]


def test_ctx_top_k_caps_total(monkeypatch):
    _wire(monkeypatch, {"a": [_chunk(f"c{i}", 0.9 - i / 100, area="a") for i in range(6)]})
    out = asyncio.run(rr.get_rag_context("s", "q", areas=["a"], top_k=2))
    assert out.count("\n\n---\n\n") == 1  # exactly 2 entries


# ── get_always_on_rag_context ────────────────────────────────────────────
def test_always_on_empty_areas_short_circuits(monkeypatch):
    _, searches = _wire(monkeypatch, {})
    monkeypatch.setattr(
        "boerdi.services.config_loader.get_always_on_rag_areas", lambda: [])
    out = asyncio.run(rr.get_always_on_rag_context("s", "q"))
    assert out == "" and searches == []


def test_always_on_delegates_with_configured_areas(monkeypatch):
    _, searches = _wire(monkeypatch, {"faq": [_chunk("Antwort", 0.9, area="faq")]})
    monkeypatch.setattr(
        "boerdi.services.config_loader.get_always_on_rag_areas", lambda: ["faq"])
    out = asyncio.run(rr.get_always_on_rag_context("s", "q", top_k=5))
    assert "Antwort" in out
    assert [(c[1], c[3]) for c in searches] == [("faq", 5)]
