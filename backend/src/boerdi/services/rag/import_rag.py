"""Migrate ALT sqlite ``rag_chunks`` -> NEU pg (``rag_documents`` + ``rag_chunks``).

Spec §9.2 (RAG-Re-Ingest): read the ALT rows' TEXT only and re-embed via LiteLLM.
The ALT float32 embedding BLOBs are deliberately NOT carried over — NEU's embedding
model/dimension may differ, so a binary copy would land vectors the pgvector column
rejects (or silently mis-scores). Re-embedding is the price of the model swap.

Read-only on the source: the sqlite is opened ``mode=ro`` and only ever SELECTed,
so the ALT DB (a *copy* per the runbook) is never mutated. The CLI requires an
explicit ``--sqlite`` path — there is no default pointing at the real ALT DB.

ALT stored flat rows (title/source duplicated per chunk); NEU is normalised, so
chunks are regrouped into one ``rag_documents`` row per ``(area, source, title)``
with their ``chunk_index`` order preserved. The whole import runs in one
transaction: a mid-run embed failure rolls everything back, leaving no partial
migration to clean up before a re-run.

**Zwei Quellen, ein Schreibweg** (2026-08-19). Die sqlite war die einmalige
Bruecke aus ALT; der Dauerzustand ist ein **Seed im Repositorium**
(``backend/seeds/rag/*.jsonl``), damit eine frische Anlage ihren Wissensbestand
mitbringt, statt ihn per Datei-Transfer nachgereicht zu bekommen. Beide Quellen
liefern dieselbe Zeilenform und gehen durch dasselbe :func:`_ingest_rows` —
getauscht wird nur der Leser.

Bewusst KEINE Alembic-Migration: Migrationen tragen Schema, nicht Inhalt. Inhalt
darin waere einmalig, nicht editierbar und liefe auch dort mit, wo jemand einen
Bereich absichtlich geleert hat.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import RagChunk, RagDocument
from boerdi.services.rag.admin import delete_area
from boerdi.services.rag.embed import embed_text

logger = logging.getLogger(__name__)


def _read_alt_chunks(sqlite_path: Path) -> list[dict]:
    """ALT ``rag_chunks`` rows (text columns only) read-only, in document order.

    The ``embedding`` BLOB is never selected — it is re-embedded downstream. Opened
    ``mode=ro`` so a mistaken path to the real ALT DB still cannot be written.
    """
    uri = f"{sqlite_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT area, title, source, chunk_index, content FROM rag_chunks "
            "ORDER BY area, source, title, chunk_index"
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _read_seed_chunks(seed_dir: Path) -> list[dict]:
    """Seed-Zeilen aus ``<seed_dir>/*.jsonl`` — dieselbe Form wie der sqlite-Leser.

    **Der Bereich steht IN der Zeile, nicht im Dateinamen.** Ein Dateiname muss
    fuers Dateisystem entschaerft werden, und eine Entschaerfung, die einen
    Bereich stillschweigend umbenennt, verschoebe genau das, was der Chatbot
    durchsucht. Der Dateiname dient nur der Lesbarkeit.

    Sortiert wie :func:`_read_alt_chunks` (area, source, title, chunk_index),
    damit beide Quellen dieselbe Dokument-Gruppierung ergeben — sonst haengt die
    Aufteilung in ``rag_documents`` davon ab, woher die Zeilen kamen.

    Eine kaputte Zeile bricht ab statt sie zu ueberspringen: ein halb
    eingelesener Wissensbestand ist schlimmer als ein Abbruch mit Fundstelle.
    """
    zeilen: list[dict] = []
    for datei in sorted(seed_dir.glob("*.jsonl")):
        for nr, roh in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if not roh.strip():
                continue
            try:
                satz = json.loads(roh)
            except json.JSONDecodeError as fehler:
                raise ValueError(f"{datei.name}:{nr} ist kein JSON: {fehler}") from fehler
            fehlt = [f for f in ("area", "content") if not str(satz.get(f) or "").strip()]
            if fehlt:
                raise ValueError(f"{datei.name}:{nr} ohne {', '.join(fehlt)}")
            zeilen.append({
                "area": satz["area"],
                "title": satz.get("title") or "",
                "source": satz.get("source") or "",
                "chunk_index": int(satz.get("chunk_index") or 0),
                "content": satz["content"],
            })
    zeilen.sort(key=lambda z: (z["area"], z["source"], z["title"], z["chunk_index"]))
    return zeilen


def _group_into_documents(
    rows: list[dict],
) -> list[tuple[tuple[str, str, str], list[dict]]]:
    """Regroup flat ALT chunks into (``(area, source, title)``, chunks) documents.

    Insertion order is preserved (so the read's document ordering carries through),
    and within a group the chunks keep their read order (= ``chunk_index``).
    """
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for r in rows:
        key = (r["area"], r["source"] or "", r["title"] or "")
        groups.setdefault(key, []).append(r)
    return list(groups.items())


async def _ingest_rows(
    session: AsyncSession, rows: list[dict], quelle: str
) -> dict[str, int]:
    """Zeilen gruppieren, neu einbetten, schreiben. Returns ``{"documents", "chunks"}``.

    Der gemeinsame Schreibweg beider Quellen (sqlite und Seed): eine
    ``rag_documents``-Zeile + N neu eingebettete ``rag_chunks`` je Gruppe.
    """
    docs = 0
    chunks = 0
    for (area, source, title), members in _group_into_documents(rows):
        doc = RagDocument(area=area, title=title, source=source)
        session.add(doc)
        await session.flush()  # assigns doc.id for the FK
        for m in members:
            emb = await embed_text(m["content"], kind="passage")
            session.add(RagChunk(
                document_id=doc.id, area=area,
                chunk_index=m["chunk_index"], content=m["content"], embedding=emb,
            ))
        docs += 1
        chunks += len(members)
    # simplify: one transaction across all (network) embed calls — atomic and fine
    # for a one-time migration; for a very large ALT DB, batch the embeds or commit
    # per document to avoid holding a single transaction open for the whole run.
    await session.commit()
    logger.info("import-rag: %d chunks in %d documents from %s", chunks, docs, quelle)
    return {"documents": docs, "chunks": chunks}


async def import_rag_from_sqlite(session: AsyncSession, sqlite_path: Path) -> dict[str, int]:
    """Re-ingest ALT ``rag_chunks`` into pg. Returns ``{"documents", "chunks"}``.

    One ``rag_documents`` row + N re-embedded ``rag_chunks`` per group, all in a
    single transaction (see module docstring).
    """
    return await _ingest_rows(session, _read_alt_chunks(sqlite_path), str(sqlite_path))


async def import_rag_from_seed(
    session: AsyncSession, seed_dir: Path, *, force: bool = False
) -> dict[str, int]:
    """Den Seed-Baum einlesen — den Werkszustand des Wissensbestands.

    **Belegte Bereiche bleiben unberuehrt** (Vorgabe). Ein Seed soll eine leere
    Anlage fuellen, nicht eine gepflegte ueberschreiben: wer im Studio Dokumente
    ergaenzt oder entfernt hat, verloere sie sonst beim naechsten Deployment.
    Damit ist der Aufruf gefahrlos wiederholbar und taugt als Schritt im Runbook.

    ``force=True`` leert die betroffenen Bereiche vorher — die ausdrueckliche
    Ansage „stelle den Werkszustand wieder her". Das Leeren committet fuer sich
    (``admin.delete_area``), der Einlesevorgang danach ebenfalls: zwei
    Transaktionen statt einer. Fuer einen vom Betreiber angestossenen Vorgang ist
    das vertretbar; bricht der zweite Teil ab, ist der Bereich leer und der
    Aufruf schlicht zu wiederholen.

    ``skipped`` nennt die uebersprungenen Bereiche — stumm zu ueberspringen sieht
    aus wie ein Einlesen, das nichts gefunden hat.
    """
    zeilen = _read_seed_chunks(seed_dir)
    belegt = set((await session.execute(select(RagChunk.area).distinct())).scalars())
    im_seed = {z["area"] for z in zeilen}
    betroffen = sorted(im_seed & belegt)
    if betroffen and force:
        for name in betroffen:
            await delete_area(session, name)
        logger.info("import-rag --seed --force: %d Bereiche geleert (%s)",
                    len(betroffen), ", ".join(betroffen))
        betroffen = []
    elif betroffen:
        zeilen = [z for z in zeilen if z["area"] not in belegt]
        logger.info("import-rag --seed: %d Bereiche uebersprungen, weil belegt (%s)",
                    len(betroffen), ", ".join(betroffen))
    stats = await _ingest_rows(session, zeilen, str(seed_dir))
    stats["skipped"] = betroffen
    return stats
