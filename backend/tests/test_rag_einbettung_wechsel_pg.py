"""Die Wissensbasis in einen anderen Vektorraum überführen (Paket 11, D) — gegen echtes Postgres.

Nutzer 2026-10-15: ein Einbettungsmodell der AcademicCloud soll machbar und angebbar sein.
Angeben geht schon (``LLM_EMBED_MODEL``); es fehlte der Wechsel: die Spalte
``rag_chunks.embedding`` hat die Dimension der ersten Migration, und ``import-rag --force``
bettet nur die Seed-Bereiche neu ein — Studio-Uploads blieben im alten Raum. Das Kommando misst
die Dimension des eingestellten Modells, stellt die Spalte um, bettet ALLE Abschnitte neu ein
und legt den Index wieder an. Gefälscht ist nur das Einbetten (Netz).
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p11_einbettung_test"


def _basis() -> int:
    from boerdi.services.llm_models import get_embed_dim

    return get_embed_dim()


@pytest.fixture(scope="module")
def test_db():
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _engine():
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings

    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)))


async def _zuruecksetzen(engine, *, spalte: int, null_zeilen: int = 1) -> None:
    """Spalte in ``vector(spalte)``, drei Abschnitte, davon ``null_zeilen`` ohne Vektor."""
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE rag_chunks, rag_documents RESTART IDENTITY CASCADE"))
        await conn.execute(text("DROP INDEX IF EXISTS idx_rag_embedding"))
        await conn.execute(text(
            f"ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector({spalte}) USING NULL"))
        await conn.execute(text(
            "CREATE INDEX idx_rag_embedding ON rag_chunks "
            "USING hnsw (embedding vector_cosine_ops)"))
        await conn.execute(text(
            "INSERT INTO rag_documents (id, area, title, source) "
            "VALUES (1, 'bio', 'Zelle', 'z.md')"))
        vektor = "[" + ",".join(["0.5"] * spalte) + "]"
        for i in range(3):
            ohne = i < null_zeilen
            await conn.execute(
                text("INSERT INTO rag_chunks (document_id, area, chunk_index, content, embedding) "
                     "VALUES (1, 'bio', :i, :c, CAST(:v AS vector))"),
                {"i": i, "c": f"Zelle Teil {i}", "v": None if ohne else vektor})


async def _abfrage(engine, sql: str):
    async with engine.connect() as conn:
        return (await conn.execute(text(sql))).all()


def _modell(monkeypatch, dim: int, *, eingestellt: int | None = None) -> list[str]:
    """Das Modell liefert ``dim``-lange Vektoren; ``eingestellt`` ist ``EMBED_DIM``."""
    from boerdi.services.rag import einbettung_wechsel as ew
    from boerdi.services.rag import ingest as ri

    eingebettet: list[str] = []

    async def einzeln(text_, *, kind="query", kanal="live"):
        return [0.25] * dim

    async def viele(texte, *, kind="passage"):
        eingebettet.extend(texte)
        return [[0.25] * dim for _ in texte]

    monkeypatch.setattr(ew, "embed_text", einzeln)
    monkeypatch.setattr(ew, "expected_dim", lambda: eingestellt or dim)
    monkeypatch.setattr(ri, "embed_many", viele)
    monkeypatch.setattr(ri, "expected_dim", lambda: eingestellt or dim)
    return eingebettet


def _lauf(test_db, monkeypatch, *, spalte, dim, eingestellt=None, null_zeilen=1, **kw):
    from boerdi.services.rag.einbettung_wechsel import wechseln

    eingebettet = _modell(monkeypatch, dim, eingestellt=eingestellt)

    async def szenario():
        engine = _engine()
        try:
            await _zuruecksetzen(engine, spalte=spalte, null_zeilen=null_zeilen)
            try:
                bericht = await wechseln(engine, **kw)
            except Exception as fehler:  # noqa: BLE001 — der Test prüft den Abbruch
                bericht = fehler
            typ = await _abfrage(engine, "SELECT format_type(atttypid, atttypmod) "
                                         "FROM pg_attribute WHERE attrelid = "
                                         "'rag_chunks'::regclass AND attname = 'embedding'")
            dims = await _abfrage(engine, "SELECT vector_dims(embedding), embedding IS NULL "
                                          "FROM rag_chunks ORDER BY id")
            index = await _abfrage(engine, "SELECT indexname FROM pg_indexes "
                                           "WHERE indexname = 'idx_rag_embedding'")
            return bericht, typ[0][0], dims, bool(index)
        finally:
            await engine.dispose()

    return (*asyncio.run(szenario()), eingebettet)


def test_wechsel_auf_neue_dimension_bettet_alles_neu_ein(test_db, monkeypatch):
    basis = _basis()
    bericht, typ, dims, index, eingebettet = _lauf(test_db, monkeypatch, spalte=basis, dim=1024)
    assert typ == "vector(1024)"
    assert [d for d, _null in dims] == [1024, 1024, 1024]
    assert index, "der HNSW-Index muss wieder stehen"
    assert len(eingebettet) == 3, "auch die schon eingebetteten Abschnitte (Studio-Uploads)"
    assert (bericht.spalte_vorher, bericht.dimension, bericht.eingebettet, bericht.abschnitte) == (
        basis, 1024, 3, 3)


def test_gleiche_dimension_bettet_trotzdem_alles_neu_ein(test_db, monkeypatch):
    """Anderes Modell, gleiche Länge (etwa ada-002 → 3-small): die alten Vektoren liegen in einem
    anderen Raum und müssen trotzdem weg."""
    basis = _basis()
    bericht, typ, _dims, _index, eingebettet = _lauf(test_db, monkeypatch, spalte=basis, dim=basis)
    assert typ == f"vector({basis})"
    assert len(eingebettet) == 3 and bericht.eingebettet == 3


def test_probe_aendert_nichts(test_db, monkeypatch):
    basis = _basis()
    bericht, typ, dims, index, eingebettet = _lauf(
        test_db, monkeypatch, spalte=basis, dim=1024, probe=True)
    assert typ == f"vector({basis})"
    assert [null for _d, null in dims] == [True, False, False]
    assert index and eingebettet == []
    assert (bericht.spalte_vorher, bericht.dimension, bericht.abschnitte, bericht.fehlend) == (
        basis, 1024, 3, 1)


def test_gemessene_dimension_muss_zur_einstellung_passen(test_db, monkeypatch):
    from boerdi.services.rag.einbettung_wechsel import Abbruch

    basis = _basis()
    fehler, typ, _dims, _index, eingebettet = _lauf(
        test_db, monkeypatch, spalte=basis, dim=1024, eingestellt=basis)
    assert isinstance(fehler, Abbruch) and "EMBED_DIM=1024" in str(fehler)
    assert typ == f"vector({basis})" and eingebettet == []


def test_ueber_2000_dimensionen_bricht_ab(test_db, monkeypatch):
    from boerdi.services.rag.einbettung_wechsel import Abbruch

    basis = _basis()
    fehler, typ, _dims, _index, eingebettet = _lauf(test_db, monkeypatch, spalte=basis, dim=3072)
    assert isinstance(fehler, Abbruch) and "2000" in str(fehler)
    assert typ == f"vector({basis})" and eingebettet == []


def test_fortsetzen_holt_nur_die_fehlenden(test_db, monkeypatch):
    """Nach einem unterbrochenen Lauf: Spalte schon umgestellt, ein Abschnitt noch ohne Vektor."""
    bericht, typ, dims, index, eingebettet = _lauf(
        test_db, monkeypatch, spalte=1024, dim=1024, fortsetzen=True)
    assert typ == "vector(1024)" and index
    assert eingebettet == ["Zelle Teil 0"]
    assert all(not null for _d, null in dims)
    assert (bericht.eingebettet, bericht.fehlend) == (1, 0)


def test_fortsetzen_mit_falscher_spalte_bricht_ab(test_db, monkeypatch):
    from boerdi.services.rag.einbettung_wechsel import Abbruch

    basis = _basis()
    fehler, typ, _dims, _index, eingebettet = _lauf(
        test_db, monkeypatch, spalte=basis, dim=1024, fortsetzen=True)
    assert isinstance(fehler, Abbruch) and eingebettet == []
    assert typ == f"vector({basis})"
