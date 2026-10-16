"""Der Verbindungs-Pool je Replik ist einstellbar (Paket 10, Audit 2026-10-10 M-8).

Ein Zug hält seine Datenbank-Sitzung über die ganze Laufzeit, die LLM-Aufrufe
eingeschlossen; die LLM-Parallelität liegt bei 20. Mit den festen
SQLAlchemy-Vorgaben (5 + 10) warteten ab etwa 15 parallelen Zügen weitere auf eine
Verbindung. Die Vorgaben bleiben, damit sich ohne Eintrag nichts ändert.
"""

from __future__ import annotations

from boerdi.db.session import make_engine
from boerdi.settings import Settings

_URL = "postgresql+asyncpg://u:p@127.0.0.1:5432/x"


def _pool(**werte):
    return make_engine(Settings(_env_file=None, database_url=_URL, **werte)).sync_engine.pool


def test_ohne_eintrag_gelten_die_bisherigen_werte() -> None:
    pool = _pool()
    assert (pool.size(), pool._max_overflow) == (5, 10)


def test_groesse_und_ueberlauf_sind_einstellbar() -> None:
    pool = _pool(db_pool_size=20, db_max_overflow=5)
    assert (pool.size(), pool._max_overflow) == (20, 5)


def test_die_umgebung_setzt_den_pool(monkeypatch) -> None:
    monkeypatch.setenv("DB_POOL_SIZE", "12")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    pool = make_engine(Settings(_env_file=None, database_url=_URL)).sync_engine.pool
    assert (pool.size(), pool._max_overflow) == (12, 0)
