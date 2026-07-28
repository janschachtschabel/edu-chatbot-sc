"""P1-5: OTel wiring — off by default (empty endpoint), instrumented spans
when configured. Live Jaeger delivery is covered in test_otel_live.py.
"""

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.obs import otel
from boerdi.settings import get_settings


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    get_settings.cache_clear()
    return monkeypatch


def test_off_by_default() -> None:
    app = create_app()
    assert otel.setup_otel(app) is False  # empty endpoint => no-op


def test_spans_emitted_when_configured(monkeypatch) -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
    get_settings.cache_clear()
    exporter = InMemorySpanExporter()
    app = create_app()
    assert otel.setup_otel(app, exporter=exporter) is True

    client = TestClient(app)
    assert client.get("/health").status_code == 200
    otel.force_flush()

    spans = exporter.get_finished_spans()
    assert spans, "no spans captured"
    root = [s for s in spans if s.attributes.get("http.route") == "/health"]
    assert root, f"no /health span in {[dict(s.attributes) for s in spans]}"
    assert root[0].resource.attributes["service.name"] == "boerdi-backend"
