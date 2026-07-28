"""OpenTelemetry wiring (P1-5, spec §8 / improvement in place of ALT's
own tracer). Active only when OTEL_EXPORTER_OTLP_ENDPOINT is set — the empty
default means zero overhead. GenAI attributes on LLM spans arrive with P3 (V10).

The tracer provider is process-global by OTel design (set-once). Subsequent
``setup_otel`` calls attach additional span processors / instrument additional
app instances against the same provider (needed by tests; prod calls it once).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_SERVICE_NAME = "boerdi-backend"
_provider: TracerProvider | None = None


def setup_otel(app: FastAPI, exporter: SpanExporter | None = None) -> bool:
    """Instrument the app (FastAPI/HTTPX/SQLAlchemy). Returns False when
    tracing is off (no endpoint configured and no explicit exporter)."""
    global _provider
    endpoint = get_settings().otel_exporter_otlp_endpoint
    if not endpoint and exporter is None:
        return False

    if exporter is None:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )

        exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")

    if _provider is None:
        _provider = TracerProvider(
            resource=Resource.create({"service.name": _SERVICE_NAME})
        )
        trace.set_tracer_provider(_provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=_provider)
        SQLAlchemyInstrumentor().instrument(tracer_provider=_provider)
        logger.info("OTel tracing active (service=%s)", _SERVICE_NAME)

    _provider.add_span_processor(BatchSpanProcessor(exporter))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_provider)
    return True


def force_flush(timeout_ms: int = 5000) -> None:
    if _provider is not None:
        _provider.force_flush(timeout_ms)
