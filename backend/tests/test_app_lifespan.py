"""P2: app lifespan wires engine + ConfigStore (NOTIFY listener) onto
app.state. Needs the migrated Compose dev DB (settings default URL).
"""

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]


def test_lifespan_provides_config_store_and_warm_loaders() -> None:
    app = create_app()
    with TestClient(app) as client:  # context manager runs the lifespan
        from boerdi.services import config_loader as cl
        from boerdi.services.config_store import ConfigStore

        store = app.state.config_store
        assert isinstance(store, ConfigStore)
        # P6-2a: request-scoped sessions come from ONE factory built here —
        # api.deps.get_session reads it off app.state per request.
        assert app.state.session_factory is not None
        assert app.state.session_factory.kw["bind"] is app.state.engine
        assert client.get("/health").json() == {"status": "ok"}
        # dev DB is seeded (P2-4 CLI import) => facade reads real content
        welcome = cl.load_welcome_config()
        assert welcome["greeting"]
        assert cl.load_intents(), "intents area should be preloaded"
    # after shutdown the facade is unbound and the engine disposed


def test_lifespan_sweeps_orphaned_loadtests(monkeypatch) -> None:
    # The lifespan runs the V9 orphan-sweep so a crashed ``running`` row can't
    # permanently 409-block new loadtest runs (main.py). Patch the sweep at its
    # source (the lifespan lazy-imports it) and assert startup invokes it once
    # with a DB session.
    from sqlalchemy.ext.asyncio import AsyncSession

    seen: list = []

    async def _spy(session):
        seen.append(session)
        return 0

    monkeypatch.setattr("boerdi.services.loadtest.sweep_orphaned_loadtests", _spy)
    app = create_app()
    with TestClient(app):  # context manager runs the lifespan
        pass
    assert len(seen) == 1
    assert isinstance(seen[0], AsyncSession)
