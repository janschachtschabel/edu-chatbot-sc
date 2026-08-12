"""Behavior pins for services/rag/ingest — file/URL→markdown conversion
(ALT-verbatim) + the pg store path (schema-driven rewrite: 1 RagDocument + N
RagChunks, float embeddings, one transaction). Boundaries faked: markitdown
(parser/fetcher), llm.embedding (network), AsyncSession (DB). chunk_markdown and
the url_safety guard run real — numerische IPs braucht kein echtes DNS, die
URL-Tests sind damit offline und deterministisch.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from sqlalchemy import Update
from sqlalchemy.dialects import postgresql

import boerdi.services.rag.ingest as ri
from boerdi.db.models import RagChunk, RagDocument


def _als_many(einzeln):
    """Eine Einzel-Attrappe an die neue Sammel-Grenze anschliessen (W10).

    `ingest` ruft seit W10 `embed_many`; die Tests beschreiben aber weiterhin
    das Verhalten PRO Chunk (Reihenfolge, Fehler-Isolation). Diese Huelle
    bewahrt beides: dieselbe Attrappe, neue Grenze.
    """
    async def viele(texte, *, kind="passage"):
        aus = []
        for t in texte:
            try:
                aus.append(await einzeln(t, kind=kind))
            except Exception:
                aus.append(None)
        return aus
    return viele



# ── convert_to_markdown (verbatim ALT) ───────────────────────────────────
class _FakeMid:
    def __init__(self, text="# MD", raise_exc=None):
        self.text, self.raise_exc = text, raise_exc

    def convert(self, path):
        if self.raise_exc:
            raise self.raise_exc
        from types import SimpleNamespace
        return SimpleNamespace(text_content=self.text)


def test_convert_returns_text_content(monkeypatch, tmp_path):
    f = tmp_path / "doc.txt"
    f.write_text("hallo", encoding="utf-8")
    monkeypatch.setattr("markitdown.MarkItDown", lambda: _FakeMid("# Ergebnis"))
    assert asyncio.run(ri.convert_to_markdown(str(f))) == "# Ergebnis"


def test_convert_error_becomes_fehler_string_not_raise(monkeypatch):
    monkeypatch.setattr(
        "markitdown.MarkItDown", lambda: _FakeMid(raise_exc=RuntimeError("kaputt")))
    out = asyncio.run(ri.convert_to_markdown("fehlt.pdf"))
    assert out == "Fehler beim Konvertieren: RuntimeError: kaputt"


# ── convert_url_to_markdown (verbatim ALT; SSRF-Guard via url_safety) ────
class _FakeUrlMid:
    def __init__(self, requests_session, text, raise_exc):
        self.requests_session = requests_session
        self.text, self.raise_exc = text, raise_exc

    def convert_url(self, url):
        if self.raise_exc:
            raise self.raise_exc
        from types import SimpleNamespace
        return SimpleNamespace(text_content=self.text)


def _wire_url_markitdown(monkeypatch, text="# Seite", raise_exc=None):
    """Patch the markitdown boundary; return the list of constructed fakes
    (empty = never constructed = no fetch was attempted)."""
    built: list[_FakeUrlMid] = []

    def _factory(requests_session=None):
        built.append(_FakeUrlMid(requests_session, text, raise_exc))
        return built[-1]

    monkeypatch.setattr("markitdown.MarkItDown", _factory)
    return built


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/x",         # Loopback
        "http://localhost/x",         # interner Name
        "http://169.254.169.254/l",   # Cloud-Metadaten (link-local)
        "ftp://8.8.8.8/x",            # Nicht-http(s)-Schema
        "http://",                    # fehlender Host
    ],
)
def test_convert_url_guard_blocks_internal_and_bad_scheme(url):
    assert asyncio.run(ri.convert_url_to_markdown(url)).startswith("Fehler")


def test_convert_url_guard_returns_before_any_fetch(monkeypatch):
    built = _wire_url_markitdown(monkeypatch)
    out = asyncio.run(ri.convert_url_to_markdown("http://169.254.169.254/latest"))
    # Die exakte Meldung (statt nur des "Fehler"-Präfixes) beweist den frühen
    # Return: der markitdown-Pfad liefert "Fehler beim Konvertieren: …".
    assert out == "Fehler: Internal network URLs not allowed"
    assert built == []  # markitdown nie konstruiert → kein Netz-Fetch versucht


def test_convert_url_returns_text_content_via_guarded_session(monkeypatch):
    built = _wire_url_markitdown(monkeypatch, text="# Wikipedia")
    out = asyncio.run(ri.convert_url_to_markdown("http://8.8.8.8/seite"))
    assert out == "# Wikipedia"
    # N-2: die Guard-Session MUSS durchgereicht werden — sonst folgt markitdown
    # einem 302 auf ein internes Ziel ungeprüft.
    adapter = built[0].requests_session.get_adapter("http://8.8.8.8/")
    assert type(adapter).__name__ == "_SsrfGuardAdapter"


def test_convert_url_error_becomes_fehler_string_not_raise(monkeypatch):
    _wire_url_markitdown(monkeypatch, raise_exc=RuntimeError("timeout"))
    out = asyncio.run(ri.convert_url_to_markdown("http://8.8.8.8/seite"))
    # ALT-Asymmetrie verbatim erhalten: der URL-Pfad formatiert OHNE
    # type(e).__name__ (der Datei-Pfad oben MIT).
    assert out == "Fehler beim Konvertieren: timeout"


def test_real_markitdown_honours_requests_session_kwarg():
    """Integrations-Pin gegen das ECHTE markitdown (kein Fetch, nur Konstruktion).

    ``MarkItDown.__init__`` nimmt ``requests_session`` nur über ``**kwargs``
    (0.1.6: ``(*, enable_builtins, enable_plugins, **kwargs)``) — ein Rename in
    einer künftigen Version würde das Kwarg STILL ignorieren und damit den
    N-2-Redirect-Guard lautlos abschalten, ohne dass die Fakes oben es merken.
    Der Griff auf das private ``_requests_session`` ist hier Absicht: genau
    dieser Durchstich ist die zu schützende Eigenschaft.
    """
    from markitdown import MarkItDown

    from boerdi.services.url_safety import make_ssrf_guarded_session
    guard = make_ssrf_guarded_session()
    mid = MarkItDown(requests_session=guard)
    assert mid._requests_session is guard
    assert type(guard.get_adapter("https://example.org/")).__name__ == "_SsrfGuardAdapter"


# ── fakes for the DB store path ──────────────────────────────────────────
class _FakeSession:
    def __init__(self, rows=()):
        self.added: list = []
        self.flushed = 0
        self.commits = 0
        self.rows = list(rows)
        self.stmts: list = []

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushed += 1
        for o in self.added:
            if isinstance(o, RagDocument) and o.id is None:
                o.id = 77

    async def commit(self):
        self.commits += 1

    async def execute(self, stmt):
        self.stmts.append(stmt)

        class _R:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows
        return _R(self.rows)


def _wire_embedding(monkeypatch):
    calls: list[str] = []

    async def fake_embedding(text, *, kind="query"):
        calls.append(text)
        return [0.1, float(len(calls))]

    monkeypatch.setattr(ri, "embed_many", _als_many(fake_embedding))
    return calls


# ── ingest_document (pg rewrite) ─────────────────────────────────────────
def test_ingest_creates_document_and_linked_chunks(monkeypatch):
    calls = _wire_embedding(monkeypatch)
    sess = _FakeSession()
    # Two heading sections too large to merge (600+600+2 > max_chunk 1000)
    # -> the real chunker yields exactly 2 chunks.
    md = "# A\n\n" + "x" * 600 + "\n\n# B\n\n" + "y" * 600
    from boerdi.domain.rag_chunking import chunk_markdown
    assert len(chunk_markdown(md)) == 2  # fixture guard
    n = asyncio.run(ri.ingest_document(sess, "erdkunde", "Klima", "klima.md", md))
    docs = [o for o in sess.added if isinstance(o, RagDocument)]
    chunks = [o for o in sess.added if isinstance(o, RagChunk)]
    assert n == 2 and len(docs) == 1 and len(chunks) == 2
    assert (docs[0].area, docs[0].title, docs[0].source) == ("erdkunde", "Klima", "klima.md")
    assert all(c.document_id == 77 and c.area == "erdkunde" for c in chunks)
    assert [c.chunk_index for c in chunks] == [0, 1]
    assert calls == [chunks[0].content, chunks[1].content]  # embeds each chunk
    assert chunks[0].embedding == [0.1, 1.0]  # float list, no BLOB packing


def test_ingest_commits_once_transactional(monkeypatch):
    _wire_embedding(monkeypatch)
    sess = _FakeSession()
    asyncio.run(ri.ingest_document(sess, "a", "t", "s", "Eins.\n\nZwei.\n\nDrei."))
    assert sess.commits == 1  # ALT committed per chunk; NEU: all-or-nothing


# ── get_rag_chunks (pg rewrite) ──────────────────────────────────────────
def test_get_rag_chunks_query_and_contract():
    from types import SimpleNamespace
    row = SimpleNamespace(id=5, area="a", title="T", source="s.md",
                          chunk_index=0, content="Text")
    sess = _FakeSession(rows=[row])
    out = asyncio.run(ri.get_rag_chunks(sess, "a"))
    assert out == [{"id": 5, "area": "a", "title": "T", "source": "s.md",
                    "chunk_index": 0, "content": "Text"}]
    sql = str(sess.stmts[0].compile(dialect=postgresql.dialect()))
    assert "LEFT OUTER JOIN rag_documents" in sql
    assert "rag_chunks.area = " in sql and "ORDER BY rag_chunks.id" in sql


# ── embed_missing_chunks (pg rewrite, ALT routers/rag.py:310-354) ─────────
def _updated_id(stmt):
    """The chunk id an UPDATE targets — None for any other statement."""
    if not isinstance(stmt, Update):
        return None
    return stmt.compile(dialect=postgresql.dialect()).params.get("id_1")


def _null_row(cid, content):
    from types import SimpleNamespace
    return SimpleNamespace(id=cid, content=content)


class _Savepoint:
    def __init__(self, sess):
        self.sess = sess

    async def __aenter__(self):
        self.sess.savepoints += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self.sess.savepoint_rollbacks += 1
        return False  # never swallow — the caller's except owns the policy


class _EmbedSession:
    """DB boundary for the backfill loop.

    ``fail_update_ids`` makes the UPDATE of those chunks raise — the Postgres
    case ALT never had: there a failed statement aborts the whole transaction,
    which is what the per-chunk SAVEPOINT is for.
    """

    def __init__(self, rows=(), fail_update_ids=()):
        self.rows = list(rows)
        self.fail_update_ids = set(fail_update_ids)
        self.stmts: list = []
        self.commits = 0
        self.savepoints = 0
        self.savepoint_rollbacks = 0

    async def execute(self, stmt):
        self.stmts.append(stmt)
        cid = _updated_id(stmt)
        if cid is not None and cid in self.fail_update_ids:
            raise RuntimeError(f"expected 1536 dimensions, not 2 (chunk {cid})")

        class _R:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows
        return _R(self.rows)

    async def commit(self):
        self.commits += 1

    def begin_nested(self):
        return _Savepoint(self)


def test_embed_missing_returns_zero_when_no_chunk_lacks_an_embedding(monkeypatch):
    calls = _wire_embedding(monkeypatch)
    sess = _EmbedSession(rows=[])
    assert asyncio.run(ri.embed_missing_chunks(sess)) == (0, 0)
    assert calls == []  # ALT returned before it opened the write path
    assert sess.commits == 0


def test_embed_missing_selects_null_embeddings_across_every_area():
    sess = _EmbedSession(rows=[])
    asyncio.run(ri.embed_missing_chunks(sess))
    sql = str(sess.stmts[0].compile(dialect=postgresql.dialect()))
    assert "FROM rag_chunks" in sql
    assert "embedding IS NULL" in sql
    assert "area" not in sql  # ALT backfilled every area in one pass


def test_embed_missing_embeds_each_chunk_and_updates_it_by_id(monkeypatch):
    calls = _wire_embedding(monkeypatch)
    sess = _EmbedSession(rows=[_null_row(1, "eins"), _null_row(2, "zwei")])
    assert asyncio.run(ri.embed_missing_chunks(sess)) == (2, 2)
    assert calls == ["eins", "zwei"]
    updates = [s for s in sess.stmts if isinstance(s, Update)]
    assert [_updated_id(s) for s in updates] == [1, 2]
    # float list straight into the pgvector column — no struct.pack, no BLOB
    assert updates[0].compile(dialect=postgresql.dialect()).params["embedding"] == [0.1, 1.0]


def test_embed_missing_skips_a_chunk_whose_embedding_call_fails(monkeypatch, caplog):
    async def flaky(text, *, kind="query"):
        if text == "kaputt":
            raise RuntimeError("rate limited")
        return [0.5, 0.5]

    monkeypatch.setattr(ri, "embed_many", _als_many(flaky))
    sess = _EmbedSession(rows=[_null_row(1, "kaputt"), _null_row(2, "ok")])
    with caplog.at_level(logging.WARNING):
        assert asyncio.run(ri.embed_missing_chunks(sess)) == (1, 2)
    assert [_updated_id(s) for s in sess.stmts if isinstance(s, Update)] == [2]
    assert "Embedding failed for chunk 1" in caplog.text
    assert sess.commits == 1  # ALT committed the survivors


def test_embed_missing_isolates_a_failing_db_write_in_a_savepoint(monkeypatch):
    _wire_embedding(monkeypatch)
    sess = _EmbedSession(rows=[_null_row(1, "a"), _null_row(2, "b")], fail_update_ids={1})
    # Without the savepoint Postgres would poison the transaction and take
    # chunk 2 and the commit down with it; ALT's sqlite simply carried on.
    assert asyncio.run(ri.embed_missing_chunks(sess)) == (1, 2)
    assert sess.savepoint_rollbacks == 1
    assert [_updated_id(s) for s in sess.stmts if isinstance(s, Update)] == [1, 2]
    assert sess.commits == 1


def test_embed_missing_commits_once_after_the_loop(monkeypatch):
    _wire_embedding(monkeypatch)
    sess = _EmbedSession(rows=[_null_row(1, "a"), _null_row(2, "b")])
    asyncio.run(ri.embed_missing_chunks(sess))
    assert sess.commits == 1
