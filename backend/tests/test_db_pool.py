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


# ── Paket 19 (Audit 2026-10-31, H-5/M-10) ─────────────────────────────────────

def test_eine_engine_mit_eigenem_kleinen_pool() -> None:
    engine = make_engine(Settings(_env_file=None, database_url=_URL),
                         pool_size=2, max_overflow=2, pool_timeout=7.0)
    pool = engine.sync_engine.pool
    assert (pool.size(), pool._max_overflow, pool._timeout) == (2, 2, 7.0)


def test_im_startpaket_nur_die_clientfrist() -> None:
    """Review 19-4 (HOCH): Server-Fristen als ``server_settings`` gehen ins Startpaket —
    PgBouncer (Session-Modus, Cluster-Checkliste) weist sie als „unsupported startup
    parameter“ ab, und kein Pod startet. Ins Startpaket nur noch ``command_timeout``
    (clientseitig); die Server-Fristen setzt ``SET`` nach dem Verbindungsaufbau."""
    from boerdi.db.session import verbindungs_fristen

    cfg = Settings(_env_file=None, database_url=_URL, db_statement_timeout_s=60,
                   db_command_timeout_s=90, db_idle_in_transaction_timeout_s=300,
                   db_lock_timeout_s=0)
    assert verbindungs_fristen(cfg) == {"command_timeout": 90.0}


def test_die_server_fristen_als_set_anweisungen() -> None:
    from boerdi.db.session import fristen_anweisungen

    cfg = Settings(_env_file=None, database_url=_URL, db_statement_timeout_s=60,
                   db_command_timeout_s=90, db_idle_in_transaction_timeout_s=300,
                   db_lock_timeout_s=0)
    assert fristen_anweisungen(cfg) == [
        "SET statement_timeout = 60000",
        "SET idle_in_transaction_session_timeout = 300000",
    ]


def test_null_schaltet_eine_frist_ab() -> None:
    from boerdi.db.session import fristen_anweisungen, verbindungs_fristen

    cfg = Settings(_env_file=None, database_url=_URL, db_statement_timeout_s=0,
                   db_command_timeout_s=0, db_idle_in_transaction_timeout_s=0,
                   db_lock_timeout_s=0)
    assert verbindungs_fristen(cfg) == {}
    assert fristen_anweisungen(cfg) == []


def test_vorgaben_der_fristen() -> None:
    cfg = Settings(_env_file=None, database_url=_URL)
    assert (cfg.db_statement_timeout_s, cfg.db_command_timeout_s,
            cfg.db_idle_in_transaction_timeout_s, cfg.db_lock_timeout_s) == (60, 90, 300, 30)
