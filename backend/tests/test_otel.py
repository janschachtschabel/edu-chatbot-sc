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


def test_spans_emitted_when_configured() -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    # Configured by the exporter alone. With OTEL_EXPORTER_OTLP_ENDPOINT set,
    # create_app() would also build an OTLP exporter for a localhost:4318
    # nobody listens on (finding 2026-10-08).
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


def test_verlaeufe_erzeugen_keine_spans(monkeypatch) -> None:
    """Paket 18C/D (2.9): Spans tragen den rohen Pfad — beim Verlaufsabruf mit der Sitzungs-ID,
    die wie ein Schlüssel zum Verlauf wirkt. Diese Pfade sind von der Messung ausgenommen."""
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    import boerdi.api.sessions as sessions_api
    from boerdi.api.deps import get_session

    async def _leer(*_a, **_k):
        return []

    monkeypatch.setattr(sessions_api, "get_messages", _leer)
    sid = "bb-0123456789abcdef0123456789abcdef"
    exporter = InMemorySpanExporter()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: object()
    assert otel.setup_otel(app, exporter=exporter) is True
    client = TestClient(app)
    assert client.get(f"/api/sessions/{sid}/messages").status_code == 200
    client.get(f"/studio/api/sessions/{sid}/messages")
    otel.force_flush()
    werte = [str(v) for s in exporter.get_finished_spans() for v in s.attributes.values()]
    assert not [w for w in werte if sid in w]
