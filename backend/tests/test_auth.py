"""P1-3: Studio-API-Key-Auth — port of ALT tests/test_auth.py.

Fail-closed (ALT Audit T1): no configured key => 503 unless the explicit
dev opt-in BOERDI_ALLOW_OPEN_ADMIN is set; configured key => timing-safe
compare, header-only (never query params).
"""

from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from boerdi.api import deps


def _call(header=None):
    return asyncio.run(deps.require_studio_key(x_studio_key=header))


def test_no_key_configured_fails_closed(monkeypatch):
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _call(header=None)
    assert exc.value.status_code == 503


def test_no_key_with_dev_optin_is_noop(monkeypatch):
    monkeypatch.delenv("STUDIO_API_KEY", raising=False)
    monkeypatch.setenv("BOERDI_ALLOW_OPEN_ADMIN", "1")
    assert _call(header=None) is None


def test_change_me_placeholder_fails_closed(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "CHANGE_ME")
    monkeypatch.delenv("BOERDI_ALLOW_OPEN_ADMIN", raising=False)
    with pytest.raises(HTTPException) as exc:
        _call(header="CHANGE_ME")
    assert exc.value.status_code == 503


def test_correct_key_in_header_passes(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    assert _call(header="s3cr3t") is None


def test_query_key_not_accepted(monkeypatch):
    # key is header-only (never query params -> proxy/Referer logs)
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    assert "key" not in inspect.signature(deps.require_studio_key).parameters


def test_wrong_key_raises_401(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    with pytest.raises(HTTPException) as exc:
        _call(header="falsch")
    assert exc.value.status_code == 401


def test_missing_key_when_configured_raises_401(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    with pytest.raises(HTTPException):
        _call(header=None)


def test_key_is_stripped(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "  s3cr3t  ")
    assert _call(header="s3cr3t") is None


def test_http_matrix_on_studio_route(monkeypatch):
    """401/403-Matrix (spec P1-3) over a real studio-gated route. Post-P7 all the
    studio ROUTERS are implemented; the remaining studio-gated 501 stub is
    GET /api/debug/mcp-test (P5-1)."""
    from fastapi.testclient import TestClient

    from boerdi.main import create_app

    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t")
    client = TestClient(create_app())
    assert client.get("/api/debug/mcp-test").status_code == 401
    assert client.get("/api/debug/mcp-test", headers={"X-Studio-Key": "falsch"}).status_code == 401
    # correct key reaches the stub (501 until P5-1)
    assert client.get("/api/debug/mcp-test", headers={"X-Studio-Key": "s3cr3t"}).status_code == 501
    # A public route stays open: no key, and the request still reaches its
    # handler. The 503 is that handler talking — no widget bundle exists in the
    # test environment. A gated route would have answered 401 long before.
    assert client.get("/widget/boerdi-widget.js").status_code == 503
