"""The MCP registry's write and egress endpoints: PUT /mcp-servers and
POST /mcp-servers/discover.

Both carry an SSRF gate (ALT audit T8, 2026-07-05). PUT is *stored* SSRF: a studio
write must not persist an internal/private URL, since the backend POSTs to every
enabled server on each chat turn -- a stored ``http://169.254.169.254`` would turn
the bot into an SSRF proxy that fires once per conversation. Discover is *immediate*
SSRF: it handshakes whatever URL it is handed, so the guard must sit in front of the
egress rather than behind it.

Ports ALT tests/test_config_mcp_servers.py (the PUT cases + discover-rejects-internal)
and the three discover cases from ALT tests/test_config_router.py (url required, tools
on success, failure -> 502) -- they lived over there only because ALT's config router
was still one monolith.

Offline and deterministic exactly as ALT's: numeric IPs mean ``assert_public_url``
resolves without a real DNS round-trip, and both boundaries -- ``save_mcp_servers``
and ``transport.discover_server_tools`` -- are spied, so neither a store write nor a
socket is attempted (TestClient without ``with`` -> no lifespan -> no DB). The
cleaning logic behind the save spy (meta strip, primary restore) is pinned in the P2
loader tests; what is under test here is the endpoints' own gates.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.mcp import transport
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    return TestClient(create_app())  # no context manager -> lifespan not run


@pytest.fixture()
def saved(monkeypatch) -> list[list]:
    """Spy on the persistence boundary; returns the list of payloads written."""
    calls: list[list] = []

    async def _save(servers):
        calls.append(servers)

    monkeypatch.setattr(config_loader, "save_mcp_servers", _save)
    return calls


@pytest.fixture()
def discovered(monkeypatch) -> list[str]:
    """Spy on the MCP network boundary; returns the URLs a handshake was tried against."""
    calls: list[str] = []

    async def _discover(url: str) -> list[dict[str, str]]:
        calls.append(url)
        return [{"name": "t1", "description": "d"}]

    monkeypatch.setattr(transport, "discover_server_tools", _discover)
    return calls


def _body(url: str, server_id: str = "extra") -> dict:
    return {"servers": [{
        "id": server_id, "name": "X", "url": url, "enabled": True, "tools": [],
    }]}


def test_put_rejects_internal_url(client, saved) -> None:
    r = client.put("/api/config/mcp-servers", headers=_AUTH,
                   json=_body("http://169.254.169.254/mcp"))  # cloud metadata
    assert r.status_code == 400
    assert saved == []  # the rejection must happen BEFORE the write


def test_put_rejects_private_url(client, saved) -> None:
    r = client.put("/api/config/mcp-servers", headers=_AUTH,
                   json=_body("http://10.1.2.3/mcp"))
    assert r.status_code == 400
    assert saved == []


def test_put_names_the_offending_server_in_the_error(client, saved) -> None:
    r = client.put("/api/config/mcp-servers", headers=_AUTH,
                   json=_body("http://10.1.2.3/mcp", server_id="kaputt"))
    assert "kaputt" in r.json()["detail"]


def test_put_accepts_public_url_and_hands_the_payload_over_verbatim(client, saved) -> None:
    body = _body("http://8.8.8.8/mcp")
    r = client.put("/api/config/mcp-servers", headers=_AUTH, json=body)
    assert r.status_code == 200
    assert r.json() == {"status": "saved", "count": 1}
    # The router only validates. Stripping meta fields and restoring the primary
    # is the loader's job, so it must receive the payload untouched.
    assert saved == [body["servers"]]


def test_put_skips_primary_url_validation(client, saved) -> None:
    # The primary's URL comes from MCP_SERVER_URL and may deliberately point
    # inside the network; save_mcp_servers drops it anyway, so an internal value
    # must not block the write.
    r = client.put("/api/config/mcp-servers", headers=_AUTH,
                   json=_body("http://127.0.0.1:8000/mcp", server_id="wlo-mcp"))
    assert r.status_code == 200
    assert len(saved) == 1


def test_put_ignores_servers_without_a_url(client, saved) -> None:
    r = client.put("/api/config/mcp-servers", headers=_AUTH, json=_body(""))
    assert r.status_code == 200
    assert len(saved) == 1


def test_put_requires_the_studio_key(client, saved) -> None:
    r = client.put("/api/config/mcp-servers", json=_body("http://8.8.8.8/mcp"))
    assert r.status_code == 401
    assert saved == []


def test_put_rejects_a_non_dict_server_entry(client, saved) -> None:
    """``list[dict]`` is the type gate, so a non-dict never reaches the handler
    (which is why the handler's own isinstance branch is unreachable)."""
    r = client.put("/api/config/mcp-servers", headers=_AUTH,
                   json={"servers": ["kein-dict"]})
    assert r.status_code == 422
    assert saved == []


# ── POST /mcp-servers/discover: a one-off handshake with the SSRF guard in front ──


def test_discover_requires_a_url(client, discovered) -> None:
    r = client.post("/api/config/mcp-servers/discover", headers=_AUTH)
    assert r.status_code == 400
    # C1-e3: die Meldung folgt `Accept-Language`; ohne Header ist Deutsch die
    # Vorgabe. Gepinnt werden BEIDE Sprachen — der Katalog-Test allein belegt
    # nicht, dass die Wahl den Endpunkt erreicht.
    assert r.json()["detail"] == "Bitte eine Server-URL angeben."
    assert discovered == []  # no URL -> nothing is handshaked


def test_discover_url_message_follows_accept_language(client, discovered) -> None:
    r = client.post(
        "/api/config/mcp-servers/discover",
        headers={**_AUTH, "Accept-Language": "en-GB"},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Please provide a server URL."


def test_discover_rejects_an_internal_url(client, discovered) -> None:
    r = client.post("/api/config/mcp-servers/discover", headers=_AUTH,
                    params={"url": "http://10.0.0.5/mcp"})
    assert r.status_code == 400
    assert discovered == []  # the guard blocks BEFORE the egress, not after


def test_discover_returns_the_tools_on_success(client, discovered) -> None:
    r = client.post("/api/config/mcp-servers/discover", headers=_AUTH,
                    params={"url": "http://8.8.8.8/mcp"})
    assert r.status_code == 200
    assert r.json() == {"url": "http://8.8.8.8/mcp",
                        "tools": [{"name": "t1", "description": "d"}]}
    assert discovered == ["http://8.8.8.8/mcp"]  # handshaked exactly the given URL


def test_discover_maps_a_connection_failure_to_502(client, monkeypatch) -> None:
    async def _boom(url: str) -> list[dict[str, str]]:
        raise RuntimeError("kaputt")

    monkeypatch.setattr(transport, "discover_server_tools", _boom)
    r = client.post("/api/config/mcp-servers/discover", headers=_AUTH,
                    params={"url": "http://8.8.8.8/mcp"})
    assert r.status_code == 502
    assert "Verbindung fehlgeschlagen" in r.json()["detail"]


# ── the OTHER two write paths into the same document ────────────────────────
# The registry lives in the config area ``05-knowledge/mcp-servers``, and two
# generic endpoints can write any area: ``PUT /config/data/{area}`` (the 9-3
# schema form) and ``PUT /config/file`` (its raw-text tab). Both reach the same
# stored URLs the backend POSTs to on every chat turn, so the gate above is only
# a gate if it also covers them -- otherwise an editor just uses the other tab.


@pytest.fixture()
def area_written(monkeypatch) -> list[tuple]:
    """Spy on the generic area write boundary."""
    calls: list[tuple] = []

    async def _write(area_key, data, updated_by="studio"):
        calls.append((area_key, data))
        return 1

    monkeypatch.setattr(config_loader, "write_area", _write)
    return calls


@pytest.fixture()
def file_written(monkeypatch) -> list[tuple]:
    """Spy on the raw-text write boundary."""
    calls: list[tuple] = []

    async def _write(rel_path, content):
        calls.append((rel_path, content))

    monkeypatch.setattr(config_loader, "write_config_file", _write)
    return calls


def _doc(url: str, server_id: str = "extra") -> dict:
    return {"servers": [{"id": server_id, "name": "X", "url": url, "enabled": True}]}


def test_generic_area_put_rejects_internal_url(client, area_written) -> None:
    r = client.put("/api/config/data/05-knowledge/mcp-servers", headers=_AUTH,
                   json={"data": _doc("http://169.254.169.254/mcp")})
    assert r.status_code == 400
    assert "extra" in r.json()["detail"]
    assert area_written == []


def test_generic_area_put_accepts_public_url(client, area_written) -> None:
    r = client.put("/api/config/data/05-knowledge/mcp-servers", headers=_AUTH,
                   json={"data": _doc("http://8.8.8.8/mcp")})
    assert r.status_code == 200
    assert len(area_written) == 1


def test_generic_area_put_skips_primary_url_validation(client, area_written) -> None:
    r = client.put("/api/config/data/05-knowledge/mcp-servers", headers=_AUTH,
                   json={"data": _doc("http://127.0.0.1:8000/mcp", server_id="wlo-mcp")})
    assert r.status_code == 200
    assert len(area_written) == 1


def test_generic_area_put_leaves_other_areas_alone(client, area_written) -> None:
    # The check is per area, not a global "no private URL anywhere": a display
    # rule or a tour step may legitimately carry any string at all.
    r = client.put("/api/config/data/01-base/device-config", headers=_AUTH,
                   json={"data": {"url": "http://10.1.2.3/x"}})
    assert r.status_code == 200
    assert len(area_written) == 1


def test_raw_file_put_rejects_internal_url(client, file_written) -> None:
    r = client.put("/api/config/file", headers=_AUTH, json={
        "path": "05-knowledge/mcp-servers.yaml",
        "content": "servers:\n  - id: extra\n    url: http://169.254.169.254/mcp\n",
    })
    assert r.status_code == 400
    assert file_written == []


def test_raw_file_put_accepts_public_url(client, file_written) -> None:
    r = client.put("/api/config/file", headers=_AUTH, json={
        "path": "05-knowledge/mcp-servers.yaml",
        "content": "servers:\n  - id: extra\n    url: http://8.8.8.8/mcp\n",
    })
    assert r.status_code == 200
    assert len(file_written) == 1
