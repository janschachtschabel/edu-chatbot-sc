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


def test_server_spans_ohne_ip_browserkennung_und_abfrage():
    """Paket 18G (G-E3): weder IP noch User-Agent noch ``?session_id=…`` am Collector."""
    from opentelemetry.sdk.trace import TracerProvider

    from boerdi.obs.otel import ohne_personenbezug

    tracer = TracerProvider().get_tracer("probe")
    with tracer.start_as_current_span("GET /api/quality/logs", attributes={
        "net.peer.ip": "203.0.113.7", "client.address": "203.0.113.7",
        "http.user_agent": "Mozilla/5.0 Probe", "url.query": "session_id=geheim",
        "http.url": "http://x/api/quality/logs?session_id=geheim",
        "http.target": "/api/quality/logs?session_id=geheim", "http.method": "GET",
        "http.route": "/api/quality/logs",
    }) as span:
        ohne_personenbezug(span, {})
        attribute = dict(span.attributes)
    assert "203.0.113.7" not in str(attribute) and "geheim" not in str(attribute)
    assert "Probe" not in str(attribute)
    assert attribute["http.url"] == "http://x/api/quality/logs"
    assert attribute["http.target"] == "/api/quality/logs"
    assert attribute["http.method"] == "GET"


def test_der_hook_sitzt_am_echten_server_span() -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    app = create_app()
    assert otel.setup_otel(app, exporter=exporter) is True
    client = TestClient(app)
    assert client.get("/health?session_id=geheim",
                      headers={"User-Agent": "Mozilla/5.0 Probe"}).status_code == 200
    otel.force_flush()
    werte = [str(v) for s in exporter.get_finished_spans() for v in s.attributes.values()]
    assert werte, "keine Spans"
    assert not [w for w in werte if "geheim" in w or "Probe" in w or w == "testclient"]



def test_ausnahmen_gehen_nur_mit_ihrer_art_an_den_collector() -> None:
    """Paket 18G (G-E3): FastAPI und SQLAlchemy zeichnen den Ausnahmetext auf — hier nur die Art."""
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import Status, StatusCode

    from boerdi.obs.otel import _OhneAusnahmetexte

    innen = InMemorySpanExporter()
    anbieter = TracerProvider()
    anbieter.add_span_processor(SimpleSpanProcessor(_OhneAusnahmetexte(innen)))
    with anbieter.get_tracer("probe").start_as_current_span("POST /api/chat") as span:
        span.record_exception(ValueError("DETAIL: Key (session_id)=(bb-geheim) fehlt"))
        span.set_status(Status(StatusCode.ERROR, "ValueError: Key (session_id)=(bb-geheim)"))
    (fertig,) = innen.get_finished_spans()
    assert "geheim" not in str([dict(e.attributes) for e in fertig.events])
    assert fertig.events[0].attributes["exception.type"] == "ValueError"
    assert fertig.status.description == "ValueError"



def test_eine_beschreibung_ohne_doppelpunkt_geht_nicht_wortlich_hinaus() -> None:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )
    from opentelemetry.trace import Status, StatusCode

    from boerdi.obs.otel import _OhneAusnahmetexte

    innen = InMemorySpanExporter()
    anbieter = TracerProvider()
    anbieter.add_span_processor(SimpleSpanProcessor(_OhneAusnahmetexte(innen)))
    with anbieter.get_tracer("probe").start_as_current_span("SELECT") as span:
        span.set_status(Status(StatusCode.ERROR, "Key (session_id)=(bb-geheim) is not present"))
    (fertig,) = innen.get_finished_spans()
    assert "geheim" not in (fertig.status.description or "")


_SID = "bb-0123456789abcdef0123456789abcdef"


def test_server_spans_tragen_die_route_statt_des_pfads():
    """Paket 19 (H-1): der Pfad trägt Kennungen (Sitzung, Lauf, Schnappschuss) — an den Collector
    geht die Routen-Vorlage, nie der Pfad."""
    from opentelemetry.sdk.trace import TracerProvider

    from boerdi.obs.otel import ohne_personenbezug

    route = "/api/usage/session/{session_id}"
    tracer = TracerProvider().get_tracer("probe")
    with tracer.start_as_current_span(f"GET {route}", attributes={
        "http.route": route, "http.target": f"/api/usage/session/{_SID}?x=1",
        "url.path": f"/api/usage/session/{_SID}",
        "http.url": f"https://boerdi.example/api/usage/session/{_SID}?x=1",
        "url.full": f"https://boerdi.example/api/usage/session/{_SID}",
    }) as span:
        ohne_personenbezug(span, {})
        attribute = dict(span.attributes)
    assert _SID not in str(attribute)
    assert attribute["http.target"] == route and attribute["url.path"] == route
    assert attribute["http.url"] == f"https://boerdi.example{route}"
    assert attribute["url.full"] == f"https://boerdi.example{route}"


def test_ohne_route_geht_kein_pfad_hinaus():
    """Ein Pfad ohne passende Route (404, Abtaster) kann alles tragen — dann bleibt nur der Host."""
    from opentelemetry.sdk.trace import TracerProvider

    from boerdi.obs.otel import ohne_personenbezug

    tracer = TracerProvider().get_tracer("probe")
    with tracer.start_as_current_span("GET", attributes={
        "http.target": f"/irgendwo/{_SID}", "http.url": f"https://boerdi.example/irgendwo/{_SID}",
    }) as span:
        ohne_personenbezug(span, {})
        attribute = dict(span.attributes)
    assert _SID not in str(attribute)
    assert attribute["http.url"].startswith("https://boerdi.example/")


def test_der_echte_server_span_traegt_keine_kennung_aus_dem_pfad() -> None:
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    app = create_app()

    @app.get("/probe-otel/{kennung}")
    def _probe(kennung: str) -> dict:
        return {}

    assert otel.setup_otel(app, exporter=exporter) is True
    assert TestClient(app).get(f"/probe-otel/{_SID}?q=geheim").status_code == 200
    otel.force_flush()
    spans = exporter.get_finished_spans()
    werte = [str(v) for s in spans for v in s.attributes.values()]
    assert not [w for w in werte if _SID in w or "geheim" in w]
    assert [s for s in spans if s.attributes.get("http.target") == "/probe-otel/{kennung}"]


def test_traceparent_geht_nur_an_eigene_dienste(monkeypatch) -> None:
    """Paket 19 (N-2): ``traceparent`` verrät Fremden (OpenAI, Fremd-MCP), welche Aufrufe zu einem
    Zug gehören — er geht nur an die b-api und den eigenen MCP-Server (wie ``trace_id``)."""
    import asyncio

    import httpcore
    import httpx
    from opentelemetry import trace as ot_trace
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    monkeypatch.setenv("B_API_BASE_URL", "https://b-api.example/api")
    monkeypatch.setenv("MCP_SERVER_URL", "https://mcp.example:8443/mcp")
    get_settings.cache_clear()
    assert otel.setup_otel(create_app(), exporter=InMemorySpanExporter()) is True
    gesehen: dict[str, dict[str, str]] = {}

    class _Pool:
        async def __aenter__(self) -> "_Pool":
            return self

        async def __aexit__(self, *_a) -> None:
            return None

        async def handle_async_request(self, request: httpcore.Request) -> httpcore.Response:
            ziel = f"{request.url.host.decode()}:{request.url.port or 443}"
            gesehen[ziel] = {k.decode().lower(): v.decode() for k, v in request.headers}
            return httpcore.Response(200, content=b"{}")

    async def _abruf(url: str) -> None:
        transport = httpx.AsyncHTTPTransport()
        transport._pool = _Pool()  # kein Netz: die gebaute Anfrage wird hier abgefangen
        async with httpx.AsyncClient(transport=transport) as client:
            await client.get(url)

    async def _lauf() -> None:
        with ot_trace.get_tracer("probe").start_as_current_span("zug"):
            for url in ("https://b-api.example/api/openai/responses", "https://mcp.example:8443/mcp",
                        "https://api.openai.com/v1/responses", "https://fremd.example/mcp",
                        "https://mcp.example/mcp"):
                await _abruf(url)

    asyncio.run(_lauf())
    assert "traceparent" in gesehen["b-api.example:443"]
    assert "traceparent" in gesehen["mcp.example:8443"]
    for fremd in ("api.openai.com:443", "fremd.example:443", "mcp.example:443"):
        assert "traceparent" not in gesehen[fremd], fremd
