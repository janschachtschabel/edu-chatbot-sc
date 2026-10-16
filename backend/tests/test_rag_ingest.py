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
    # Die Attrappe liefert zwei Dimensionen; seit Paket 4 (C2) prüft der Import
    # die Länge gegen die Spalte.
    monkeypatch.setattr(ri, "expected_dim", lambda: 2)
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
    assert n == ri.ImportZahlen(chunks=2, embedded=2)
    assert len(docs) == 1 and len(chunks) == 2
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


# ── Kein Textverlust, wenn Vektoren fehlen (Paket 4, C2; externes Audit F06) ──

_ZWEI_ABSCHNITTE = "# A\n\n" + "x" * 600 + "\n\n# B\n\n" + "y" * 600


def _import_mit(monkeypatch, einbetter, dim=2):
    monkeypatch.setattr(ri, "embed_many", _als_many(einbetter))
    monkeypatch.setattr(ri, "expected_dim", lambda: dim)
    sess = _FakeSession()
    zahlen = asyncio.run(ri.ingest_document(sess, "a", "t", "s", _ZWEI_ABSCHNITTE))
    return zahlen, [o for o in sess.added if isinstance(o, RagChunk)]


def test_ein_fehlgeschlagener_vektor_verliert_keinen_text(monkeypatch):
    """Probe: zwei Abschnitte gemeldet, einer gespeichert — der Text des
    anderen fehlte danach, und das Nachholen fand ihn nicht, weil es nur
    vorhandene Zeilen ohne Vektor sucht."""
    aufrufe = {"n": 0}

    async def wackelig(text, *, kind="query"):
        aufrufe["n"] += 1
        if aufrufe["n"] == 2:
            raise RuntimeError("Anbieter weg")
        return [0.1, 0.2]

    zahlen, chunks = _import_mit(monkeypatch, wackelig)
    assert [c.chunk_index for c in chunks] == [0, 1]   # beide Texte gespeichert
    assert chunks[0].embedding == [0.1, 0.2]
    assert chunks[1].embedding is None                 # nachholbar
    assert (zahlen.chunks, zahlen.embedded, zahlen.missing) == (2, 1, 1)


def test_fallen_alle_vektoren_aus_bleiben_alle_texte(monkeypatch):
    async def weg(text, *, kind="query"):
        raise RuntimeError("Anbieter weg")

    zahlen, chunks = _import_mit(monkeypatch, weg)
    assert len(chunks) == 2 and all(c.embedding is None for c in chunks)
    assert (zahlen.embedded, zahlen.missing) == (0, 2)


def test_ein_vektor_falscher_laenge_wird_nicht_gespeichert(monkeypatch, caplog):
    """C5(d): ``expected_dim`` hatte keinen Leser. Ein Vektor, der nicht zur
    Spalte passt, ließe den ganzen Import scheitern; jetzt bleibt der Text
    ohne Vektor stehen, und das Protokoll nennt die Ursache."""
    async def zu_lang(text, *, kind="query"):
        return [0.1, 0.2, 0.3]

    with caplog.at_level(logging.WARNING, logger="boerdi.services.rag.ingest"):
        zahlen, chunks = _import_mit(monkeypatch, zu_lang, dim=2)
    assert all(c.embedding is None for c in chunks)
    assert zahlen.missing == 2
    assert any("EMBED_DIM" in r.getMessage() for r in caplog.records)


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
