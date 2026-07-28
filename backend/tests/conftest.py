"""Shared fixtures.

Settings are lru-cached (boerdi.settings.get_settings). Tests that monkeypatch
env vars need a fresh Settings read — clear the cache around EVERY test so no
test can leak env-dependent state into the next.
"""

import pytest

from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _fresh_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _no_startup_warmups(monkeypatch):
    """Start-Vorwärmung (W1) in Tests stilllegen.

    ``spawn_startup_warmups`` startet echte MCP-/LLM-Round-Trips. Jeder Test, der
    den Lifespan fährt (``with TestClient(app)``), löste sie sonst mit aus — 16
    SDK-Deprecation-Warnungen und Netz-I/O in einer Unit-Suite.

    Der EINE Test, der die Verdrahtung prüfen muss
    (``test_startup_warmup.test_lifespan_actually_spawns_the_warmups``), patcht
    dasselbe Attribut selbst und gewinnt damit — die Naht bleibt also bewiesen.
    """
    import boerdi.main as main_mod
    monkeypatch.setattr(main_mod, "spawn_startup_warmups", lambda: None)
