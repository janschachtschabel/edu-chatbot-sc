"""The studio MCP-registry enrichment: services/mcp/tool_descriptions.py.

GET /api/config/mcp-servers enriches every enabled server that has a url and a
tool list with a ``{tool_name: description}`` map, so the studio can render
hover-tooltips that disambiguate near-identical tool names (``get_node_details``
single vs ``get_nodes_details`` bulk). The descriptions come from a one-off MCP
handshake, cached per URL for 5 min so the studio's GET doesn't pay the round-trip
on every render.

Ports ALT's three ``_fetch_tool_descriptions`` unit cases (normalize, cache-per-url,
failure-not-cached / A7) plus the enrichment-rule case from ALT
tests/test_config_router.py. In ALT this logic sat in the config router; here it is
a service (spec §4: I/O out of the api layer), so the unit tests drive the service
directly and one thin HTTP test pins the GET wiring.

Offline: the network boundary ``transport.discover_server_tools`` is spied (ALT
mocked the internal ``_fetch_tool_descriptions`` instead; spying the true boundary
exercises the real cache + normalize + loop). The per-process TTL cache — which
Eiserne Regel 3 explicitly permits ("MCP-TTL-Cache pro Prozess erlaubt, da nur
Performance") — is reset per test so one test's write can't leak into the next.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.mcp import tool_descriptions, transport
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture(autouse=True)
def _fresh_cache(monkeypatch) -> None:
    """Start each test with an empty TTL cache so writes don't bleed across tests."""
    monkeypatch.setattr(tool_descriptions, "_TOOL_DESC_CACHE", {})


@pytest.fixture()
def handshakes(monkeypatch) -> list[str]:
    """Spy the MCP network boundary; returns the URLs a handshake was tried against."""
    calls: list[str] = []

    async def _discover(url):
        calls.append(url)
        return [{"name": "a", "description": "d"}]

    monkeypatch.setattr(transport, "discover_server_tools", _discover)
    return calls


async def test_fetch_normalizes_entries(monkeypatch) -> None:
    async def _discover(url):
        return [{"name": "a", "description": "  d  "}, {"name": "b"},
                {"ohne_name": 1}, "kein-dict"]

    monkeypatch.setattr(transport, "discover_server_tools", _discover)
    out = await tool_descriptions._fetch_tool_descriptions("http://u")
    # trimmed; missing description -> ""; nameless dict + non-dict entry dropped.
    assert out == {"a": "d", "b": ""}


async def test_fetch_caches_per_url(handshakes) -> None:
    await tool_descriptions._fetch_tool_descriptions("http://u")
    await tool_descriptions._fetch_tool_descriptions("http://u")
    await tool_descriptions._fetch_tool_descriptions("http://v")
    assert handshakes == ["http://u", "http://v"]  # the second u came from the cache


async def test_fetch_failure_is_not_cached(monkeypatch) -> None:
    # A7 (ALT fix 2026-07-10): a failure is NOT cached. The cache write happens only
    # on success, so the next call retries the server instead of blocking for 5 min.
    calls: list[str] = []

    async def _boom(url):
        calls.append(url)
        raise RuntimeError("down")

    monkeypatch.setattr(transport, "discover_server_tools", _boom)
    assert await tool_descriptions._fetch_tool_descriptions("http://u") == {}
    assert await tool_descriptions._fetch_tool_descriptions("http://u") == {}
    assert calls == ["http://u", "http://u"]  # retried, not served from a negative cache


async def test_enriches_only_enabled_with_url_and_tools(monkeypatch, handshakes) -> None:
    servers = [
        {"id": "a", "enabled": True, "url": "http://x", "tools": ["t"]},
        {"id": "b", "enabled": False, "url": "http://y", "tools": ["t"]},
        {"id": "c", "enabled": True, "url": "http://z", "tools": []},
    ]
    monkeypatch.setattr(config_loader, "load_mcp_servers",
                        lambda: [dict(s) for s in servers])
    out = await tool_descriptions.load_mcp_servers_with_descriptions()
    assert handshakes == ["http://x"]  # only the enabled server with a url and tools
    assert out[0]["tool_descriptions"] == {"a": "d"}
    assert "tool_descriptions" not in out[1]  # disabled
    assert "tool_descriptions" not in out[2]  # no tools


def test_get_endpoint_returns_the_enriched_list(monkeypatch) -> None:
    """The GET endpoint is a one-liner over the service — pin that it awaits the
    service and serialises its result (offline: the service is spied)."""
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()

    async def _enriched():
        return [{"id": "a", "tool_descriptions": {"t": "d"}}]

    monkeypatch.setattr(tool_descriptions, "load_mcp_servers_with_descriptions", _enriched)
    client = TestClient(create_app())  # no context manager -> lifespan not run
    r = client.get("/api/config/mcp-servers", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == [{"id": "a", "tool_descriptions": {"t": "d"}}]
