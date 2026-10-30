"""OpenTelemetry wiring (P1-5, spec §8 / improvement in place of ALT's
own tracer). Active only when OTEL_EXPORTER_OTLP_ENDPOINT is set — the empty
default means zero overhead. GenAI attributes on LLM spans arrive with P3 (V10).

The tracer provider is process-global by OTel design (set-once). Subsequent
``setup_otel`` calls attach additional span processors / instrument additional
app instances against the same provider (needed by tests; prod calls it once).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status

from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_SERVICE_NAME = "boerdi-backend"
#: Paket 18C/D: Spans tragen den rohen Pfad, hier mit der Sitzungs-ID, die wie ein Schlüssel
#: zum öffentlichen Verlauf wirkt — diese Pfade werden nicht gemessen (``re.search`` je Muster,
#: ``/api/sessions/`` deckt also auch ``/studio/api/sessions/``).
_OHNE_MESSUNG = "/api/sessions/,/studio/api/sessions/,/api/usage/session/"
#: Paket 18G (Entscheid G-E3, Datenschutz): die IP der Person, ihre Browserkennung und der
#: Abfrage-Teil (``session_id=``, ``q=``) gehen nicht an den Collector. Das Instrument setzt sie
#: beim Start des Spans; der Hook überschreibt sie — löschen kennt die Span-API nicht.
_PERSONENBEZUG = ("net.peer.ip", "net.peer.port", "client.address", "client.port",
                  "http.client_ip", "http.user_agent", "user_agent.original",
                  "user_agent.synthetic.type", "url.query")
_MIT_ABFRAGE = ("http.url", "http.target", "url.full")
_ENTFERNT = "‹entfernt›"
_provider: TracerProvider | None = None


def ohne_personenbezug(span: Any, _scope: Any) -> None:
    """``server_request_hook``: IP, Browserkennung und Abfrage aus dem Server-Span."""
    if span is None or not span.is_recording():
        return
    attribute = getattr(span, "attributes", None) or {}
    for schluessel in _PERSONENBEZUG:
        if schluessel in attribute:
            span.set_attribute(schluessel, _ENTFERNT)
    for schluessel in _MIT_ABFRAGE:
        wert = attribute.get(schluessel)
        if isinstance(wert, str) and "?" in wert:
            span.set_attribute(schluessel, wert.split("?", 1)[0])


class _OhneAusnahmetexte(SpanExporter):
    """Spans ohne Ausnahmetexte an den Exporter (Paket 18G, G-E3).

    FastAPI zeichnet eine Ausnahme samt Text und Traceback als Ereignis auf und setzt
    ``Typ: Text`` als Status; SQLAlchemy dasselbe mit ``str()`` des Treiberfehlers — samt
    Postgres-``DETAIL`` (die Sitzungs-ID). Am Formatierer der Logs vorbei. Hier bleibt die Art;
    Text und Traceback stehen nur im Log, geschwärzt."""

    def __init__(self, inneres: SpanExporter) -> None:
        self._inneres = inneres

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._inneres.export([_bereinigt(s) for s in spans])

    def shutdown(self) -> None:
        self._inneres.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self._inneres.force_flush(timeout_millis)


def _bereinigt(span: ReadableSpan) -> ReadableSpan:
    ereignisse = [
        Event(e.name, timestamp=e.timestamp, attributes={
            k: v for k, v in (e.attributes or {}).items()
            if k not in ("exception.message", "exception.stacktrace")})
        if e.name == "exception" else e
        for e in span.events]
    status = span.status
    if status.description:
        status = Status(status.status_code, status.description.split(":", 1)[0][:80])
    if ereignisse == list(span.events) and status is span.status:
        return span
    return ReadableSpan(
        name=span.name, context=span.context, parent=span.parent, resource=span.resource,
        attributes=span.attributes, events=ereignisse, links=span.links, kind=span.kind,
        status=status, start_time=span.start_time, end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope)


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

    _provider.add_span_processor(BatchSpanProcessor(_OhneAusnahmetexte(exporter)))
    FastAPIInstrumentor.instrument_app(app, tracer_provider=_provider,
                                       excluded_urls=_OHNE_MESSUNG,
                                       server_request_hook=ohne_personenbezug)
    return True


def force_flush(timeout_ms: int = 5000) -> None:
    if _provider is not None:
        _provider.force_flush(timeout_ms)
