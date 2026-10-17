"""Die Wissensbasis in den Vektorraum des eingestellten Einbettungsmodells überführen (Paket 11, D).

Ein Modellwechsel ist kein Schalter: ``rag_chunks.embedding`` hat die Dimension, die die erste
Migration festschrieb, und Vektoren verschiedener Modelle lassen sich nicht vergleichen — auch
nicht bei gleicher Länge. Die Reihenfolge hier:

1. Mit einem Probeaufruf die Dimension des eingestellten Modells **messen**. Sie muss zu
   ``EMBED_DIM`` bzw. der Modelltabelle passen (``expected_dim``), sonst wiese der Import später
   jeden Abschnitt ab.
2. Über 2000 Dimensionen abbrechen: so weit reicht der HNSW-Index von pgvector für ``vector``.
3. Index weg, Spalte auf ``vector(<dim>)``, alle Vektoren leer — eine Transaktion.
4. Alle Abschnitte neu einbetten (``ingest.embed_missing_chunks``: Seed und Studio-Uploads
   gleich).
5. Index wieder anlegen.

``fortsetzen`` überspringt Schritt 3 und holt nur, was nach einem abgebrochenen Lauf noch fehlt.
Während des Laufs findet die Wissenssuche nur bereits neu eingebettete Abschnitte.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.db.session import make_session_factory
from boerdi.services.rag import ingest
from boerdi.services.rag.embed import embed_text, expected_dim

logger = logging.getLogger(__name__)

#: Höchste Dimension, die pgvector für ``vector`` mit einem HNSW-Index trägt.
HNSW_GRENZE = 2000

_INDEX = "idx_rag_embedding"
_SPALTENTYP = text(
    "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
    "WHERE attrelid = 'rag_chunks'::regclass AND attname = 'embedding'")


class Abbruch(Exception):
    """Der Wechsel endet vor jeder Änderung — die Meldung sagt, was zu tun ist."""


@dataclass(frozen=True)
class Bericht:
    spalte_vorher: int | None
    dimension: int
    abschnitte: int
    #: Abschnitte ohne Vektor — vor dem Lauf (Probe) bzw. danach.
    fehlend: int
    eingebettet: int = 0


def _dimension_aus(typ: str) -> int | None:
    """``vector(1536)`` → 1536; ohne Angabe ``None``."""
    if "(" not in typ:
        return None
    return int(typ.split("(", 1)[1].rstrip(")"))


async def _zaehlen(engine: AsyncEngine) -> tuple[int | None, int, int]:
    async with engine.connect() as conn:
        typ = (await conn.execute(_SPALTENTYP)).scalar_one()
        gesamt, ohne = (await conn.execute(text(
            "SELECT count(*), count(*) FILTER (WHERE embedding IS NULL) FROM rag_chunks"))).one()
    return _dimension_aus(typ), gesamt, ohne


async def _gemessene_dimension() -> int:
    dim = len(await embed_text("Probe für die Dimension", kind="passage", kanal="ingest"))
    if dim != expected_dim():
        raise Abbruch(
            f"Das Modell liefert {dim} Dimensionen, eingestellt sind {expected_dim()}: "
            f"EMBED_DIM={dim} setzen (Backend und dieser Lauf), dann erneut.")
    if dim > HNSW_GRENZE:
        raise Abbruch(
            f"{dim} Dimensionen: der Suchindex von pgvector trägt höchstens {HNSW_GRENZE}. "
            "Ein Modell mit kleinerer Dimension wählen.")
    return dim


async def wechseln(
    engine: AsyncEngine, *, probe: bool = False, fortsetzen: bool = False,
) -> Bericht:
    """Siehe Modulkopf. ``probe`` misst und zählt nur."""
    dim = await _gemessene_dimension()
    spalte, gesamt, ohne = await _zaehlen(engine)
    if probe:
        return Bericht(spalte_vorher=spalte, dimension=dim, abschnitte=gesamt, fehlend=ohne)
    if fortsetzen and spalte != dim:
        raise Abbruch(f"Die Spalte hat {spalte} Dimensionen, das Modell {dim} — ohne "
                      "--fortsetzen starten.")
    if not fortsetzen:
        async with engine.begin() as conn:
            await conn.execute(text(f"DROP INDEX IF EXISTS {_INDEX}"))
            await conn.execute(text(
                f"ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector({dim}) USING NULL"))
        logger.info("Einbettungswechsel: Spalte vector(%s) → vector(%d), %d Abschnitte geleert",
                    spalte, dim, gesamt)
    async with make_session_factory(engine)() as session:
        eingebettet, _offen = await ingest.embed_missing_chunks(session)
    async with engine.begin() as conn:
        await conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS {_INDEX} ON rag_chunks "
            "USING hnsw (embedding vector_cosine_ops)"))
    _spalte, gesamt, ohne = await _zaehlen(engine)
    return Bericht(spalte_vorher=spalte, dimension=dim, abschnitte=gesamt, fehlend=ohne,
                   eingebettet=eingebettet)
