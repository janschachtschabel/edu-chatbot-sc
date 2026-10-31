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
from urllib.parse import urlsplit

from fastapi import FastAPI
from opentelemetry import propagate, trace
from opentelemetry.context import Context
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagators.textmap import (
    CarrierT,
    Getter,
    Setter,
    TextMapPropagator,
    default_getter,
    default_setter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import SpanKind, Status

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
#: Paket 19 (H-1): auch der Pfad trägt Kennungen (Sitzung, Lauf, Schnappschuss) — an seiner
#: Stelle steht die Routen-Vorlage (``http.route``, vom Instrument beim Start gesetzt), ohne
#: passende Route (404, Abtaster) gar kein Pfad. Volle Adressen behalten Schema und Host.
_PFAD = ("http.target", "url.path")
_VOLLE_ADRESSE = ("http.url", "url.full")
_ENTFERNT = "‹entfernt›"
_provider: TracerProvider | None = None


def ohne_personenbezug(span: Any, _scope: Any) -> None:
    """``server_request_hook``: IP, Browserkennung, Abfrage und Pfad aus dem Server-Span."""
    if span is None or not span.is_recording():
        return
    attribute = getattr(span, "attributes", None) or {}
    for schluessel in _PERSONENBEZUG:
        if schluessel in attribute:
            span.set_attribute(schluessel, _ENTFERNT)
    route = attribute.get("http.route")
    pfad = route if isinstance(route, str) and route else "/" + _ENTFERNT
    for schluessel in _PFAD:
        if isinstance(attribute.get(schluessel), str):
            span.set_attribute(schluessel, pfad)
    for schluessel in _VOLLE_ADRESSE:
        wert = attribute.get(schluessel)
        if isinstance(wert, str):
            teile = urlsplit(wert)
            span.set_attribute(schluessel, f"{teile.scheme}://{teile.netloc}{pfad}")


def _eigene_ziele() -> set[str]:
    """``host:port`` der b-api und des eigenen MCP-Servers — wohin auch ``trace_id`` geht."""
    from boerdi.services.mcp.transport import resolve_mcp_url  # lazy: obs vor services

    ziele = set()
    for adresse in (get_settings().b_api_base_url, resolve_mcp_url()):
        if ziel := _ziel(adresse):
            ziele.add(ziel)
    return ziele


def _ziel(adresse: str) -> str:
    try:
        teile = urlsplit(adresse.strip())
        port = teile.port or (443 if teile.scheme == "https" else 80)
    except ValueError:
        return ""
    return f"{(teile.hostname or '').lower()}:{port}" if teile.hostname else ""


class _NurAnEigene(TextMapPropagator):
    """``traceparent`` nur an die b-api und den eigenen MCP-Server (Paket 19, N-2).

    Das HTTPX-Instrument setzt die Kopfzeile in JEDE ausgehende Anfrage, auch an OpenAI und an
    fremde MCP-Server der Registry — gegen ``obs/trace_id`` („nie an fremde Server“). Den Ziel-Host
    kennt hier nur der Client-Span, den das Instrument vor dem Einsetzen beginnt (mit
    ``http.url`` bzw. ``url.full``). Ohne erkennbares eigenes Ziel: keine Kopfzeile. Das Lesen
    eingehender Kopfzeilen (``extract``) bleibt unverändert."""

    def __init__(self, inneres: TextMapPropagator) -> None:
        self._inneres = inneres

    def extract(self, carrier: CarrierT, context: Context | None = None,
                getter: Getter[CarrierT] = default_getter) -> Context:
        return self._inneres.extract(carrier, context=context, getter=getter)

    def inject(self, carrier: CarrierT, context: Context | None = None,
               setter: Setter[CarrierT] = default_setter) -> None:
        span = trace.get_current_span(context)
        if getattr(span, "kind", None) != SpanKind.CLIENT:
            return
        attribute = getattr(span, "attributes", None) or {}
        adresse = attribute.get("url.full") or attribute.get("http.url")
        if isinstance(adresse, str) and _ziel(adresse) in _eigene_ziele():
            self._inneres.inject(carrier, context=context, setter=setter)

    @property
    def fields(self) -> set[str]:
        return self._inneres.fields


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
        # Die Art aus dem Ereignis; ohne sie nur der Teil vor einem Doppelpunkt — eine
        # Beschreibung ohne Doppelpunkt ist ganz Text (SQLAlchemy: ``str()`` des Treiberfehlers).
        art = next((str(e.attributes.get("exception.type")) for e in span.events
                    if e.name == "exception" and e.attributes
                    and e.attributes.get("exception.type")), "")
        beschreibung = status.description
        status = Status(status.status_code, art or (
            beschreibung.split(":", 1)[0][:80] if ":" in beschreibung else ""))
    if ereignisse == list(span.events) and status is span.status:
        return span
    # Die ``dropped_*``-Zähler gehen beim Neubau verloren (die SDK-Klasse nimmt sie nicht an);
    # bei den Deckeln dieser Anlage sind sie 0.
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
        propagate.set_global_textmap(_NurAnEigene(propagate.get_global_textmap()))
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
