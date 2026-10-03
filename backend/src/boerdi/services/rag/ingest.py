"""RAG ingestion (P6): file/URL→markdown conversion + chunk/embed/store.

``convert_to_markdown`` and ``convert_url_to_markdown`` are ALT-verbatim
(``rag_service.py``; markitdown parses synchronously → ``asyncio.to_thread``
keeps the event loop free; errors come back as ``Fehler…``-strings, the router
translates them — never raises). The URL path is guarded by ``url_safety``
(``assert_public_url`` before any fetch + the redirect-checking
``make_ssrf_guarded_session`` handed to markitdown, Audit T8/T9/N-2).

``ingest_document`` / ``get_rag_chunks`` are schema-driven **rewrites, not
ports**: ALT stored flat sqlite rows (title/source duplicated per chunk, BLOB
embeddings via ``embedding_to_bytes``/``struct.pack``, one commit PER chunk).
NEU writes the normalised pair — ONE ``rag_documents`` row + N ``rag_chunks``
(``document_id`` FK, pgvector float lists) — in ONE transaction. A chunk whose
embedding failed keeps its text with ``embedding = NULL`` (Paket 4, C2): the
search skips it, ``embed_missing_chunks`` fills it later, and the import reports
how many are missing. Until then such chunks were dropped, and the text was
gone. ``embedding_to_bytes`` is dropped (sqlite artifact). Session via DI (spec
rule 3).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import RagChunk, RagDocument
from boerdi.domain.rag_chunking import chunk_markdown
from boerdi.services.rag.embed import embed_many, expected_dim
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)


class ImportZahlen(NamedTuple):
    """Ergebnis eines Imports: Abschnitte gesamt und davon eingebettet."""

    chunks: int
    embedded: int

    @property
    def missing(self) -> int:
        """Abschnitte ohne Vektor — die Suche findet sie erst nach dem Nachholen."""
        return self.chunks - self.embedded


async def convert_to_markdown(file_path: str) -> str:
    """Convert any document to markdown using markitdown."""
    try:
        size = os.path.getsize(file_path) if os.path.exists(file_path) else -1
    except Exception:
        size = -1
    try:
        from markitdown import MarkItDown
        mid = MarkItDown()
        # markitdown parst synchron (PDF/DOCX = Sekunden); ohne to_thread
        # würde der Event-Loop blockieren und alle Chat-/SSE-Requests
        # einfrieren, solange die Konvertierung läuft.
        result = await asyncio.to_thread(mid.convert, file_path)
        return result.text_content
    except ImportError as e:
        logger.exception(
            "markitdown ImportError — auf dem Server fehlt eine Python-/"
            "OS-Dependency. Häufige Ursachen: pip install markitdown nicht "
            "ausgeführt; libmagic1 / poppler-utils / tesseract-ocr fehlen "
            "im Container. Datei: %s (%d bytes)", file_path, size,
        )
        return f"Fehler beim Konvertieren (ImportError): {e}"
    except Exception as e:
        if _format_nicht_lesbar(e):
            # Keine kaputte Datei, sondern ein Format, das dieses Image nicht
            # liest (Paket 4, C5): ohne markitdown-Extras scheitern DOCX, PDF,
            # PPTX und XLSX. Der Router macht daraus 415 mit klarem Satz.
            logger.warning("markitdown liest das Format von %s nicht: %s",
                           file_path, type(e).__name__)
            return f"{FORMAT_NICHT_LESBAR}: {type(e).__name__}"
        # Volltext-Trace ins Backend-Log — die HTTP-Antwort kürzt nur die
        # Top-Zeile mit, daher hier explizit logger.exception aufrufen.
        logger.exception(
            "markitdown convert failed für %s (%d bytes): %s",
            file_path, size, e,
        )
        return f"Fehler beim Konvertieren: {type(e).__name__}: {e}"


#: Vorsilbe für „dieses Format liest der Server nicht“. Beginnt mit „Fehler“,
#: damit jeder Aufrufer, der nur darauf prüft, es weiter als Fehler sieht.
FORMAT_NICHT_LESBAR = "Fehler (Format nicht lesbar)"

#: Gesamtfrist eines URL-Abrufs in Sekunden (Paket 4, C5).
URL_FRIST_S = 60.0


def _format_nicht_lesbar(fehler: Exception) -> bool:
    """Scheiterte markitdown am Format statt an der Datei?

    ``UnsupportedFormatException``: kein Wandler für das Format.
    ``MissingDependencyException``: der Wandler fehlt im Image; markitdown hüllt
    sie in eine ``FileConversionException`` und nennt sie in ``attempts``.
    """
    from markitdown._exceptions import (
        FileConversionException,
        MissingDependencyException,
        UnsupportedFormatException,
    )

    if isinstance(fehler, (UnsupportedFormatException, MissingDependencyException)):
        return True
    if isinstance(fehler, FileConversionException):
        return any(
            versuch.exc_info and issubclass(versuch.exc_info[0], MissingDependencyException)
            for versuch in fehler.attempts or ())
    return False


async def convert_url_to_markdown(url: str) -> str:
    """Fetch a URL and convert to markdown using markitdown.

    SSRF-Schutz via ``url_safety.assert_public_url`` (zentraler Choke-Point,
    Audit T8/T9): blockt Nicht-http(s)-Schemata und private/interne Netzbereiche
    (Loopback, link-local inkl. Cloud-Metadaten 169.254.169.254, private Ranges).
    Bei einem Verstoß wird KEIN Netz-Fetch versucht — die Funktion kehrt (wie bei
    anderen Fehlern) mit einem "Fehler:"-String zurück, den der Router in 400
    übersetzt.

    Seit Paket 4 (C5, externes Audit F17) holt ``url_safety.hole_begrenzt`` den
    Rumpf — mit Frist und Bytedeckel, über dieselbe SSRF-Sitzung —, und
    markitdown wandelt nur noch um. Vorher holte markitdown selbst, ohne Frist
    und mit dem ganzen Rumpf im Speicher. Auch die DNS-Prüfung läuft jetzt im
    Thread: ``getaddrinfo`` blockierte den Event-Loop.
    """
    import io

    from markitdown import MarkItDown, StreamInfo

    from boerdi.services import url_safety

    try:
        await asyncio.to_thread(url_safety.assert_public_url, url)
    except url_safety.UnsafeUrlError as e:
        return f"Fehler: {e}"
    max_mb = get_settings().max_ingest_mb
    try:
        rumpf, typ = await asyncio.to_thread(
            url_safety.hole_begrenzt, url,
            max_bytes=max_mb * 1024 * 1024, frist_s=URL_FRIST_S)
    except url_safety.DownloadAbgebrochen as e:
        return f"Fehler: {e}"
    except Exception as e:
        return f"Fehler beim Konvertieren: {e}"
    try:
        # N-2 (Audit 2026-07-10): Guard-Session prüft AUCH Redirect-Ziele.
        # markitdown holt bei manchen Formaten selbst nach (etwa Transkripte);
        # auch dort darf kein 302 auf eine interne Adresse durchgehen.
        mid = MarkItDown(requests_session=url_safety.make_ssrf_guarded_session())
        mime, _, rest = typ.partition(";")
        charset = rest.split("charset=", 1)[1].strip() if "charset=" in rest else None
        info = StreamInfo(url=url, mimetype=mime.strip() or None, charset=charset)
        result = await asyncio.to_thread(mid.convert_stream, io.BytesIO(rumpf),
                                         stream_info=info)
        return result.text_content
    except Exception as e:
        if _format_nicht_lesbar(e):
            # Wie beim Datei-Upload (C5): ein Link auf ein PDF ist keine kaputte
            # Seite, sondern ein Format ohne Wandler im Image (Prüfer 2026-10-04).
            logger.warning("markitdown liest das Format einer URL nicht: %s",
                           type(e).__name__)
            return f"{FORMAT_NICHT_LESBAR}: {type(e).__name__}"
        return f"Fehler beim Konvertieren: {e}"


async def ingest_document(
    session: AsyncSession,
    area: str,
    title: str,
    source: str,
    markdown_content: str,
) -> ImportZahlen:
    """Chunk, embed, and store a markdown document. Returns the counts.

    One ``rag_documents`` row + N ``rag_chunks`` in a single transaction
    (ALT committed per chunk — a mid-ingest failure left partial documents).
    Every chunk's text is stored; one without a usable vector keeps
    ``embedding = NULL`` for ``embed_missing_chunks`` (Paket 4, C2).
    """
    chunks = chunk_markdown(markdown_content)

    doc = RagDocument(area=area, title=title, source=source)
    session.add(doc)
    await session.flush()  # assigns doc.id for the FK

    # W10: gedeckelt nebenlaeufig statt streng seriell. Vorher wartete jeder
    # Chunk auf den Netz-Roundtrip des vorigen; bei 906 Chunks sind das 906
    # Wartezeiten hintereinander. `embed_many` haelt die Reihenfolge (gather)
    # und laeuft im eigenen Kanal, damit der Import den Chat nicht belegt.
    vektoren = await embed_many(chunks, kind="passage")
    dim = expected_dim()
    eingebettet = 0
    for i, (chunk, emb) in enumerate(zip(chunks, vektoren, strict=True)):
        if emb is not None and len(emb) != dim:
            # Passt nicht zur Spalte ``vector(dim)``: geschrieben liesse er den
            # ganzen Import scheitern (Paket 4, C5d — ``expected_dim`` hatte
            # bis dahin keinen Leser).
            logger.warning(
                "Vektor mit %d statt %d Dimensionen verworfen (Abschnitt %d) — "
                "EMBED_DIM und Embedding-Modell pruefen", len(emb), dim, i)
            emb = None
        if emb is not None:
            eingebettet += 1
        session.add(RagChunk(
            document_id=doc.id, area=area, chunk_index=i,
            content=chunk, embedding=emb,
        ))
    await session.commit()
    if eingebettet < len(chunks):
        logger.warning(
            "Import in %s: %d von %d Abschnitten ohne Vektor — POST /api/rag/embed "
            "holt sie nach", area, len(chunks) - eingebettet, len(chunks))
    return ImportZahlen(chunks=len(chunks), embedded=eingebettet)


async def get_rag_chunks(session: AsyncSession, area: str) -> list[dict]:
    """All chunks of one area, insertion order — ALT's dict contract
    ``{id, area, title, source, chunk_index, content}`` (title/source via
    LEFT JOIN from ``rag_documents``; orphan chunks yield ``None``)."""
    stmt = (
        select(RagChunk.id, RagChunk.area, RagDocument.title,
               RagDocument.source, RagChunk.chunk_index, RagChunk.content)
        .select_from(RagChunk)
        .outerjoin(RagDocument, RagChunk.document_id == RagDocument.id)
        .where(RagChunk.area == area)
        .order_by(RagChunk.id)
    )
    rows = (await session.execute(stmt)).all()
    return [
        {"id": r.id, "area": r.area, "title": r.title, "source": r.source,
         "chunk_index": r.chunk_index, "content": r.content}
        for r in rows
    ]


async def embed_missing_chunks(session: AsyncSession) -> tuple[int, int]:
    """Backfill every chunk that has no embedding yet. Returns ``(embedded, total)``.

    Port of ALT ``routers/rag.py::embed_missing`` (Z. 310-354) with the DB half
    moved out of the router (spec rule 4); the router keeps ALT's two response
    shapes. The scan is deliberately area-wide, as ALT's was.

    Since Paket 4 (C2), ``ingest_document`` itself produces ``embedding IS
    NULL``: a chunk whose embedding failed keeps its text, and this backfill
    fills it (the Studio offers it right after such an import). ALT's producer
    was the seed importer (``db_init.py`` Z. 437-448 inserts NULL and logs
    "embeddings will be generated in background"). Rows can also arrive some
    other way: a restored dump or a manual insert.

    sqlite-vec artifacts dropped: ``embedding_to_bytes``/``struct.pack`` (pgvector
    takes the float list), and the ``INSERT OR REPLACE INTO rag_vec`` mirror with
    its ``len(emb_bytes) == EMBED_DIM * 4`` guard (the vector is a column here).
    That also removes an ALT trap: a wrong-dimension embedding was written to
    ``rag_chunks`` *before* the guard was checked, so the chunk went non-NULL
    (never retried) but never reached ``rag_vec`` (never searchable) — broken,
    silently, forever. Here the single write either lands or raises.

    The per-chunk SAVEPOINT is the one addition, and it is what preserves ALT's
    semantics rather than changing them: ALT's ``except`` could swallow a failed
    write because sqlite leaves the transaction usable, but Postgres aborts the
    whole transaction on any failed statement. Without the savepoint a single
    dimension mismatch — the realistic failure, since the column is
    ``vector(dim)`` — would fail every later chunk and the final commit (500),
    where ALT answered 200.
    """
    rows = (await session.execute(
        select(RagChunk.id, RagChunk.content).where(RagChunk.embedding.is_(None))
    )).all()
    if not rows:
        return 0, 0

    # W10: erst nebenlaeufig einbetten (Netz), dann seriell schreiben (DB).
    # Die Trennung ist Absicht: die Savepoint-Isolation je Zeile bleibt exakt
    # wie vorher, nur die Wartezeit auf den Anbieter faellt zusammen.
    vektoren = await embed_many([r.content for r in rows], kind="passage")
    embedded = 0
    for row, emb in zip(rows, vektoren, strict=True):
        if emb is None:
            # `embed_many` hat den GRUND geloggt, kennt aber die Zeile nicht.
            # Ohne diese Zeile verlöre der Betrieb die ID — also genau die
            # Angabe, mit der man den kaputten Chunk findet.
            logger.warning("Embedding failed for chunk %d", row.id)
            continue
        try:
            async with session.begin_nested():
                await session.execute(
                    update(RagChunk).where(RagChunk.id == row.id).values(embedding=emb)
                )
            embedded += 1
        except Exception as e:
            logger.warning("Embedding write failed for chunk %d: %s", row.id, e)
    await session.commit()
    return embedded, len(rows)
