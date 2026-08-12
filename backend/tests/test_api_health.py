"""P1-6: /api/health provider status (shape like ALT main.py:275-292, no
secrets) + root redirect to /api/health (ALT main.py:269-272).
"""

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for name in ("LLM_PROVIDER", "LLM_CHAT_MODEL", "OPENAI_MODEL", "LLM_EMBED_MODEL",
                 "LLM_VERBOSITY", "LLM_REASONING_EFFORT", "OPENAI_API_KEY", "B_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    return monkeypatch


def test_api_health_shape_gpt5(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-value")
    get_settings.cache_clear()
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["provider"] == "openai"
    assert body["chat_model"] == "gpt-5.6-luna"
    assert body["embed_model"] == "text-embedding-3-small"
    assert body["gpt5_params_active"] is True
    assert body["verbosity"] == "low"  # W12
    assert body["reasoning_effort"] == "low"
    assert "sk-super-secret-value" not in r.text  # never leak key material


def test_api_health_non_gpt5_omits_params(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "b-api-academiccloud")
    get_settings.cache_clear()
    body = TestClient(create_app()).get("/api/health").json()
    assert body["gpt5_params_active"] is False
    assert "verbosity" not in body and "reasoning_effort" not in body


def test_root_redirects_to_api_health():
    client = TestClient(create_app())
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/api/health"
