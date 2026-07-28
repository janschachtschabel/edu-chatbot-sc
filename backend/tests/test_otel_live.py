"""P1-5 live check (spec: '/health-Trace in Jaeger sichtbar') — automated via
the Jaeger query API instead of a manual look. Skips when the compose Jaeger
is not running.
"""

import time

import httpx
import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.obs import otel
from boerdi.settings import get_settings

_JAEGER_UI = "http://localhost:16686"
_OTLP = "http://localhost:4318"


def _jaeger_available() -> bool:
    try:
        return httpx.get(f"{_JAEGER_UI}/api/services", timeout=3).status_code == 200
    except Exception:
        return False


pytestmark = [
    pytest.mark.jaeger,
    pytest.mark.skipif(
        not _jaeger_available(),
        reason="Jaeger nicht erreichbar — docker compose -f deploy/compose.dev.yml up -d jaeger",
    ),
]


def test_health_trace_reaches_jaeger(monkeypatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", _OTLP)
    get_settings.cache_clear()
    app = create_app()
    assert otel.setup_otel(app) is True

    assert TestClient(app).get("/health").status_code == 200
    otel.force_flush()

    deadline = time.monotonic() + 10
    trace_count = 0
    while time.monotonic() < deadline:
        r = httpx.get(
            f"{_JAEGER_UI}/api/traces",
            params={"service": "boerdi-backend", "limit": 20},
            timeout=5,
        )
        if r.status_code == 200 and r.json().get("data"):
            trace_count = len(r.json()["data"])
            break
        time.sleep(0.5)
    assert trace_count > 0, "no boerdi-backend trace arrived in Jaeger within 10s"
