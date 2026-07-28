"""P2-6 (V3): GET /api/config/schema/{area} — JSON schema per area for the
generic studio form renderer. All 35 logical areas + grouped file keys
resolve; unknown areas 404. Studio-gated like the other config endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from boerdi.domain.config_models import AREA_MODELS
from boerdi.main import create_app
from boerdi.settings import get_settings


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "s3cr3t-test")
    get_settings.cache_clear()
    return TestClient(create_app()), {"X-Studio-Key": "s3cr3t-test"}


def test_all_35_logical_areas_return_valid_schema(client) -> None:
    c, auth = client
    for area in AREA_MODELS:
        resp = c.get(f"/api/config/schema/{area}", headers=auth)
        assert resp.status_code == 200, area
        schema = resp.json()
        assert "properties" in schema or schema.get("type") == "object", area


def test_grouped_file_key_resolves(client) -> None:
    c, auth = client
    resp = c.get("/api/config/schema/03-patterns/m01-krisen-empathie", headers=auth)
    assert resp.status_code == 200
    assert resp.json() == c.get("/api/config/schema/03-patterns", headers=auth).json()


def test_unknown_area_404(client) -> None:
    c, auth = client
    assert c.get("/api/config/schema/does/not-exist", headers=auth).status_code == 404


def test_schema_endpoint_requires_studio_key(client) -> None:
    c, _ = client
    assert c.get("/api/config/schema/01-base/welcome-config").status_code == 401
