"""RAG ingest/query/administration (studio). Implemented in P6
(SSRF guard + size caps are iron rule 9).
"""

import logging
import os
import tempfile
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Security, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.api.deps import Lang, get_session, require_studio_key
from boerdi.api.schemas import RagQuery, RagResult
from boerdi.i18n import msg
from boerdi.services.rag.admin import (
    delete_area,
    delete_document,
    get_document_chunks,
    list_areas,
)
from boerdi.services.rag.ingest import (
    convert_to_markdown,
    convert_url_to_markdown,
    embed_missing_chunks,
    get_rag_chunks,
    ingest_document,
)
from boerdi.services.rag.retrieval import query_rag
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/rag", tags=["rag"],
    dependencies=[Security(require_studio_key)],
)


@router.post("/ingest/file")
async def ingest_file(
    file: Annotated[UploadFile, File()],
    session: Annotated[AsyncSession, Depends(get_session)],
    lang: Lang,
    area: Annotated[str, Form()] = "general",
    title: Annotated[str, Form()] = "",
):
    """Upload and ingest a document (PDF, DOCX, PPTX, etc.) via markitdown."""
    if not title:
        title = file.filename or "Unbenannt"

    # Hard cap on upload size — markitdown loads the entire file plus its
    # rendered content (images, tables) into RAM. On a 2 GB vserver a
    # PDF > ~15 MB regularly OOM-kills the Python process; result is a
    # cryptic "Fehler beim Konvertieren" instead of a clean error. Honour
    # ``BOERDI_MAX_INGEST_MB`` (env, default 25 MB) to keep the failure
    # mode explicit. Unlimited uploads are still possible on hosts with
    # plenty of RAM by setting BOERDI_MAX_INGEST_MB=0.
    _max_mb = get_settings().max_ingest_mb
    if _max_mb > 0:
        # Try to size-check before reading the body fully — avoids buffering
        # the whole file just to reject it. ``UploadFile.size`` is set by
        # FastAPI when ``Content-Length`` is present (which it always is
        # for multipart/form-data uploads).
        cl = getattr(file, "size", None)
        if isinstance(cl, int) and cl > _max_mb * 1024 * 1024:
            raise HTTPException(
                413,
                msg(lang, "ingest.tooLarge", size=f"{cl / 1024 / 1024:.1f}", max=_max_mb)
                + " "
                + msg(lang, "ingest.raiseLimit"),
            )

    # Save to temp file
    suffix = os.path.splitext(file.filename or "")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Re-check after read in case ``size`` was unset (some edge cases)
    if _max_mb > 0:
        on_disk = len(content)
        if on_disk > _max_mb * 1024 * 1024:
            try:
                os.unlink(tmp_path)
            except Exception:
                logger.debug("temp file cleanup failed", exc_info=True)
            raise HTTPException(
                413,
                msg(lang, "ingest.tooLarge", size=f"{on_disk / 1024 / 1024:.1f}", max=_max_mb),
            )

    try:
        markdown = await convert_to_markdown(tmp_path)
        if markdown.startswith("Fehler"):
            raise HTTPException(status_code=400, detail=markdown)

        chunks = await ingest_document(session, area, title, file.filename or "", markdown)
        return {"status": "ok", "title": title, "area": area, "chunks": chunks,
                "preview": markdown[:500]}
    finally:
        os.unlink(tmp_path)


@router.post("/ingest/url")
async def ingest_url(
    url: Annotated[str, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
    area: Annotated[str, Form()] = "general",
    title: Annotated[str, Form()] = "",
):
    """Ingest a web page into a knowledge area via markitdown."""
    if not title:
        title = url

    markdown = await convert_url_to_markdown(url)
    if markdown.startswith("Fehler"):
        raise HTTPException(status_code=400, detail=markdown)

    chunks = await ingest_document(session, area, title, url, markdown)
    return {"status": "ok", "title": title, "area": area, "chunks": chunks,
            "preview": markdown[:500]}


@router.post("/ingest/text")
async def ingest_text(
    content: Annotated[str, Form()],
    session: Annotated[AsyncSession, Depends(get_session)],
    area: Annotated[str, Form()] = "general",
    title: Annotated[str, Form()] = "",
    source: Annotated[str, Form()] = "manual",
):
    """Ingest raw markdown/text into a knowledge area."""
    chunks = await ingest_document(session, area, title or "Manueller Eintrag", source, content)
    return {"status": "ok", "title": title, "area": area, "chunks": chunks}


@router.post("/query", response_model=list[RagResult])
async def rag_query(req: RagQuery, session: Annotated[AsyncSession, Depends(get_session)]):
    """Query the RAG knowledge base."""
    results = await query_rag(session, req.query, req.area, req.top_k)
    return [RagResult(**r) for r in results]


@router.post("/embed")
async def rag_embed(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """Generate embeddings for all chunks that don't have one yet.

    A backfill for chunks that reached the DB without a vector (restored dump,
    manual insert) — the ingest endpoints always embed inline. ALT additionally
    ran this at startup after its seed import; NEU has no RAG seed importer, so
    there is no such caller.

    Returns the number of chunks that were embedded.
    """
    embedded, total = await embed_missing_chunks(session)
    if not total:
        return {"status": "ok", "embedded": 0,
                "message": "All chunks already have embeddings"}
    return {"status": "ok", "embedded": embedded, "total": total}


@router.get("/areas")
async def list_rag_areas(session: Annotated[AsyncSession, Depends(get_session)]):
    """List all knowledge areas with chunk counts."""
    return await list_areas(session)


@router.get("/area/{area}")
async def get_rag_area(area: str, session: Annotated[AsyncSession, Depends(get_session)]):
    """List documents in a knowledge area.

    Documents are grouped by the compound key ``(title, source)`` so that
    e.g. two uploads with the same filename from different folders, or two
    manual entries with the same title, remain distinguishable.
    """
    chunks = await get_rag_chunks(session, area)
    docs: dict[tuple[str, str], Any] = {}
    for c in chunks:
        key = (c.get("title") or "", c.get("source") or "")
        if key not in docs:
            docs[key] = {
                "title": key[0],
                "source": key[1],
                "chunks": 0,
                "preview": "",
            }
        docs[key]["chunks"] += 1
        if not docs[key]["preview"]:
            docs[key]["preview"] = (c.get("content") or "")[:200]
    return list(docs.values())


@router.delete("/area/{area}")
async def delete_rag_area(area: str, session: Annotated[AsyncSession, Depends(get_session)]):
    """Delete all chunks in a knowledge area, and its document rows.

    ALT swept the sqlite-vec index here too, because embeddings lived in a
    separate table whose rows could outlive their chunk. pgvector keeps the
    embedding as a column on ``rag_chunks``, so the vector dies with the chunk
    and there is nothing left to sweep (see services/rag/admin.py).
    """
    await delete_area(session, area)
    return {"status": "deleted", "area": area}


@router.get("/area/{area}/doc")
async def get_rag_doc(
    area: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    title: str = "",
    source: str = "",
):
    """Return all chunks of a single document, ordered by chunk_index.

    Identified by ``(area, title, source)`` exactly like the delete
    endpoint. Use when the Studio wants to preview the full content
    of a RAG document instead of just the 200-char preview.

    Returns ``{title, source, area, chunks: [{index, content, created_at}]}``.
    """
    rows = await get_document_chunks(session, area, title, source)
    return {
        "area": area,
        "title": title,
        "source": source,
        "chunk_count": len(rows),
        "total_chars": sum(len(r.get("content") or "") for r in rows),
        "chunks": [
            {
                "index": r.get("chunk_index", 0),
                "content": r.get("content") or "",
                "created_at": r.get("created_at") or "",
            }
            for r in rows
        ],
    }


@router.delete("/area/{area}/doc")
async def delete_rag_doc(
    area: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    title: str = "",
    source: str = "",
):
    """Delete a single document (all its chunks) from a knowledge area.

    Query params ``title`` and ``source`` together identify the document
    — they must match the values returned by ``GET /area/{area}``. Empty
    strings are valid (the match is exact).
    """
    deleted = await delete_document(session, area, title, source)
    if not deleted:
        return {
            "status": "noop",
            "area": area,
            "title": title,
            "source": source,
            "deleted": 0,
        }
    return {
        "status": "deleted",
        "area": area,
        "title": title,
        "source": source,
        "deleted": deleted,
    }
