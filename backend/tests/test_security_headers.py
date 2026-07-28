"""P1-3: security response headers + CORS semantics — port of ALT
tests/test_security_headers.py (+ CORS credentials rule from ALT main.py:188-195).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from boerdi.main import create_app


def test_security_headers_present(monkeypatch):
    client = TestClient(create_app())
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "SAMEORIGIN"
    assert "referrer-policy" in r.headers


def test_cors_wildcard_disables_credentials(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)  # default "*"
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "https://embedder.example"})
    assert r.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in r.headers


def test_cors_explicit_origin_enables_credentials(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://embedder.example,https://two.example")
    client = TestClient(create_app())
    r = client.get("/health", headers={"Origin": "https://embedder.example"})
    assert r.headers.get("access-control-allow-origin") == "https://embedder.example"
    assert r.headers.get("access-control-allow-credentials") == "true"
