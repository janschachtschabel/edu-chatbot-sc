"""Der RAG-Seed: Werkszustand des Wissensbestands im Repositorium.

Ergaenzt ``test_import_rag`` um den zweiten Leser. Der Schreibweg ist derselbe
(``_ingest_rows``) und dort schon gepinnt — hier geht es um das, was neu ist:
das Lesen der ``*.jsonl``, die Gleichheit beider Quellen und die Regel, dass ein
belegter Bereich unberuehrt bleibt.

Warum die Gleichheit ein eigener Test ist: beide Leser fuettern dieselbe
Gruppierung nach ``(area, source, title)``. Weicht die Reihenfolge ab, entstehen
andere ``rag_documents`` — dieselben Texte, andere Dokumentgrenzen, und niemand
saehe es an den Zahlen.

Offline laeuft alles ausser den zwei Einlese-Pfaden; die sind pg-gated und
bemessen ihre falschen Vektoren aus ``get_embed_dim()``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from boerdi.services.rag import import_rag
from tests import pg_utils

_ALT_ROWS = [
    ("erdkunde", "Klima", "klima.md", 0, "Eiszeit"),
    ("erdkunde", "Klima", "klima.md", 1, "Gletscher"),
    ("mathe", "Bruch", "bruch.md", 0, "Zaehler"),
    ("erdkunde", "", "", 0, "Ohne Titel"),
]


def _alt_sqlite(path: Path) -> Path:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE rag_chunks ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL,"
            " title TEXT DEFAULT '', source TEXT DEFAULT '', chunk_index INTEGER DEFAULT 0,"
            " content TEXT NOT NULL, embedding BLOB, created_at TEXT)"
        )
        conn.executemany(
            "INSERT INTO rag_chunks (area, title, source, chunk_index, content, created_at)"
            " VALUES (?, ?, ?, ?, ?, '2026-01-01T00:00:00')",
            _ALT_ROWS,
        )
        conn.commit()
    finally:
        conn.close()
    return path


def _seed(dir_: Path, zeilen: list[dict], name: str = "bereich.jsonl") -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / name).write_text(
        "".join(json.dumps(z, ensure_ascii=False) + "\n" for z in zeilen),
        encoding="utf-8",
    )
    return dir_


# ── Der Leser ──────────────────────────────────────────────────────────────

def test_export_und_leser_ergeben_dieselben_zeilen_wie_die_sqlite(tmp_path) -> None:
    """Die Rundreise sqlite -> Seed -> Leser aendert nichts.

    Der schaerfste Test des Pakets: nur wenn beide Leser Zeile fuer Zeile
    dasselbe liefern, entstehen aus beiden Quellen dieselben Dokumente.
    """
    from scripts.export_rag_seed import main as export_main

    quelle = _alt_sqlite(tmp_path / "alt.db")
    ziel = tmp_path / "seed"
    assert export_main(["--sqlite", str(quelle), "--to", str(ziel)]) == 0

    aus_sqlite = import_rag._read_alt_chunks(quelle)
    aus_seed = import_rag._read_seed_chunks(ziel)
    assert aus_seed == aus_sqlite


def test_der_bereich_kommt_aus_der_zeile_nicht_aus_dem_dateinamen(tmp_path) -> None:
    """Ein entschaerfter Dateiname darf den Bereich nicht umbenennen."""
    ziel = _seed(tmp_path / "seed", [
        {"area": "Edu-Sharing/Netz", "title": "T", "source": "s.md",
         "chunk_index": 0, "content": "Inhalt"},
    ], name="Edu-Sharing-Netz.jsonl")
    assert import_rag._read_seed_chunks(ziel)[0]["area"] == "Edu-Sharing/Netz"


def test_fehlende_felder_werden_zu_leerstrings(tmp_path) -> None:
    ziel = _seed(tmp_path / "seed", [{"area": "a", "content": "nur das Noetige"}])
    zeile = import_rag._read_seed_chunks(ziel)[0]
    assert (zeile["title"], zeile["source"], zeile["chunk_index"]) == ("", "", 0)


def test_leerzeilen_werden_uebergangen(tmp_path) -> None:
    ziel = tmp_path / "seed"
    ziel.mkdir()
    (ziel / "a.jsonl").write_text(
        '{"area":"a","content":"eins"}\n\n   \n{"area":"a","content":"zwei"}\n',
        encoding="utf-8")
    assert len(import_rag._read_seed_chunks(ziel)) == 2


def test_kaputte_zeile_bricht_ab_und_nennt_die_fundstelle(tmp_path) -> None:
    """Abbruch statt Ueberspringen: ein halber Wissensbestand ist schlimmer."""
    ziel = tmp_path / "seed"
    ziel.mkdir()
    (ziel / "a.jsonl").write_text('{"area":"a","content":"gut"}\n{kaputt\n', encoding="utf-8")
    with pytest.raises(ValueError, match=r"a\.jsonl:2"):
        import_rag._read_seed_chunks(ziel)


@pytest.mark.parametrize("satz", [
    {"content": "ohne Bereich"},
    {"area": "a"},
    {"area": "   ", "content": "leerer Bereich"},
])
def test_pflichtfelder_fehlen_bricht_ab(tmp_path, satz) -> None:
    ziel = _seed(tmp_path / "seed", [satz])
    with pytest.raises(ValueError):
        import_rag._read_seed_chunks(ziel)


def test_die_reihenfolge_ist_unabhaengig_von_datei_und_zeilenfolge(tmp_path) -> None:
    ziel = tmp_path / "seed"
    _seed(ziel, [{"area": "b", "source": "s", "title": "t", "chunk_index": 1,
                  "content": "spaeter"}], name="zweite.jsonl")
    _seed(ziel, [{"area": "b", "source": "s", "title": "t", "chunk_index": 0,
                  "content": "frueher"}], name="erste.jsonl")
    assert [z["content"] for z in import_rag._read_seed_chunks(ziel)] == ["frueher", "spaeter"]


# ── Der ausgelieferte Seed ─────────────────────────────────────────────────

def test_der_ausgelieferte_seed_ist_lesbar_und_nicht_leer() -> None:
    """Waechter gegen einen kaputten Seed im Repositorium.

    Er faellt beim Einlesen sonst erst auf dem Server auf — also hier, wo es
    nichts kostet.
    """
    seed = Path(__file__).resolve().parents[1] / "seeds" / "rag"
    if not seed.is_dir():
        pytest.skip("kein RAG-Seed im Baum")
    zeilen = import_rag._read_seed_chunks(seed)
    assert zeilen, "Seed-Baum vorhanden, aber ohne Zeilen"
    assert all(z["content"].strip() for z in zeilen)
    # Gruppierung muss aufgehen: jede Gruppe hat mindestens einen Abschnitt.
    gruppen = import_rag._group_into_documents(zeilen)
    assert gruppen and all(mitglieder for _, mitglieder in gruppen)


# ── CLI ────────────────────────────────────────────────────────────────────

def test_cli_lehnt_seed_und_sqlite_zusammen_ab(tmp_path, capsys) -> None:
    from boerdi.cli import main

    rc = main(["import-rag", "--seed", str(tmp_path), "--sqlite", str(tmp_path / "x.db")])
    assert rc == 2
    assert "mutually exclusive" in capsys.readouterr().err


def test_cli_meldet_fehlenden_seed_baum(tmp_path, capsys) -> None:
    from boerdi.cli import main

    rc = main(["import-rag", "--seed", str(tmp_path / "gibt-es-nicht")])
    assert rc == 2
    assert "seed tree not found" in capsys.readouterr().err


# ── pg: Ueberspringen und Ersetzen ─────────────────────────────────────────

_DB = "boerdi_ragseed_test"


@pytest.fixture(scope="module")
def test_db():
    if not pg_utils.pg_available():
        pytest.skip(pg_utils.SKIP_REASON)
    pg_utils.create_migrated_db(_DB)
    yield _DB
    pg_utils.drop_db(_DB)


def _dim() -> int:
    from boerdi.services.llm_models import get_embed_dim
    return get_embed_dim()


async def _fake_embed(text: str, *, kind: str = "query") -> list[float]:
    return [0.1] * _dim()


def _engine(db: str):
    from boerdi.db.session import make_engine
    from boerdi.settings import Settings
    return make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))


@pytest.mark.pg
def test_belegter_bereich_bleibt_unberuehrt_und_wird_gemeldet(
    tmp_path, monkeypatch, test_db,
) -> None:
    """Ein zweiter Lauf darf einen gepflegten Bestand nicht ueberschreiben."""
    import asyncio

    from sqlalchemy import select

    from boerdi.db.models import RagChunk
    from boerdi.db.session import make_session_factory

    monkeypatch.setattr(import_rag, "embed_text", _fake_embed)
    ziel = _seed(tmp_path / "seed", [
        {"area": "alpha", "title": "T", "source": "s.md", "chunk_index": 0, "content": "eins"},
    ])

    async def lauf():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                erst = await import_rag.import_rag_from_seed(s, ziel)
            async with factory() as s:
                zweit = await import_rag.import_rag_from_seed(s, ziel)
            async with factory() as s:
                anzahl = len((await s.execute(
                    select(RagChunk).where(RagChunk.area == "alpha"))).scalars().all())
            return erst, zweit, anzahl
        finally:
            await engine.dispose()

    erst, zweit, anzahl = asyncio.run(lauf())
    assert erst["chunks"] == 1 and erst["skipped"] == []
    assert zweit["chunks"] == 0 and zweit["skipped"] == ["alpha"]
    assert anzahl == 1, "der zweite Lauf hat verdoppelt statt uebersprungen"


@pytest.mark.pg
def test_force_stellt_den_werkszustand_wieder_her(tmp_path, monkeypatch, test_db) -> None:
    """``--force`` ersetzt den Bereich, statt daneben zu schreiben."""
    import asyncio

    from sqlalchemy import select

    from boerdi.db.models import RagChunk
    from boerdi.db.session import make_session_factory

    monkeypatch.setattr(import_rag, "embed_text", _fake_embed)
    alt = _seed(tmp_path / "alt", [
        {"area": "beta", "title": "T", "source": "s.md", "chunk_index": 0, "content": "alt"},
    ])
    neu = _seed(tmp_path / "neu", [
        {"area": "beta", "title": "T", "source": "s.md", "chunk_index": 0, "content": "neu"},
        {"area": "beta", "title": "T", "source": "s.md", "chunk_index": 1, "content": "auch neu"},
    ])

    async def lauf():
        engine = _engine(test_db)
        try:
            factory = make_session_factory(engine)
            async with factory() as s:
                await import_rag.import_rag_from_seed(s, alt)
            async with factory() as s:
                stats = await import_rag.import_rag_from_seed(s, neu, force=True)
            async with factory() as s:
                inhalte = sorted((await s.execute(
                    select(RagChunk.content).where(RagChunk.area == "beta"))).scalars().all())
            return stats, inhalte
        finally:
            await engine.dispose()

    stats, inhalte = asyncio.run(lauf())
    assert stats["chunks"] == 2 and stats["skipped"] == []
    assert inhalte == ["auch neu", "neu"], "der alte Stand steht noch daneben"
