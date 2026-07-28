"""alembic/env.py must not silence the application's loggers.

env.py calls ``logging.config.fileConfig`` at import, and that function's default
is ``disable_existing_loggers=True``: it disables every logger that already
exists. Alembic normally runs as its own process, where that is harmless — but
``tests/pg_utils.create_migrated_db`` runs ``command.upgrade`` IN-PROCESS, so the
first pg test to migrate would disable every ``logging.getLogger(__name__)`` the
app created at import time.

The damage is silent and order-dependent: later tests still call the code that
logs, ``caplog`` just captures nothing, so assertions about warnings quietly stop
testing anything. Found when Postgres came up and test_rag_ingest's
"embedding failure is logged" pin started failing in the suite while passing
alone.

Offline mode (``sql=True``) executes env.py without needing a DBAPI, so this pins
the real file on the real path without a database.
"""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND = Path(__file__).resolve().parents[1]


def test_running_a_migration_keeps_existing_app_loggers_alive(capsys) -> None:
    canary = logging.getLogger("boerdi.canary.alembic_logging")
    assert not canary.disabled, "precondition: a fresh logger is enabled"

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", "postgresql+psycopg://u:p@localhost/none")
    command.upgrade(cfg, "head", sql=True)  # offline: runs env.py, connects to nothing
    capsys.readouterr()  # swallow the emitted DDL

    assert not canary.disabled, (
        "alembic/env.py disabled an existing logger — pass "
        "disable_existing_loggers=False to fileConfig"
    )
