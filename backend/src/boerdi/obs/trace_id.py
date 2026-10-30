"""Trace-ID je Anfrage (Paket 17, D4) — B3-konform, ``x-client-trace-id`` durchgereicht.

Leitfaden „Übergabe an Team 6“: der Header ``x-client-trace-id`` wird durchgereicht, damit
Logs dienstübergreifend gefiltert werden können; Tracing ist B3-konform. Quelle der ID, in
dieser Reihenfolge: ``x-client-trace-id``, ``X-B3-TraceId``, der erste Teil von ``b3``, sonst
eine neue (32 Hex-Zeichen). Sie steht in jeder Logzeile der Anfrage (``TraceIdFilter``) und
geht an die b-api und den eigenen MCP-Server weiter — nie an fremde Server, und nicht als
Kopfzeile zurück an den Client (Leitfaden: Standard ohne Header vom Dienst). Nur ihr Anfang
steht als Fehlernummer in Fehlerblasen (Paket 18C/D, :func:`fehlernummer`).

Unabhängig von OpenTelemetry (``obs/otel.py``): das läuft nur mit gesetztem Endpunkt und
propagiert W3C ``traceparent``; die ID hier gilt immer.
"""

from __future__ import annotations

import contextvars
import logging
import re
import secrets
from collections.abc import Mapping

from starlette.types import ASGIApp, Receive, Scope, Send

_trace_id: contextvars.ContextVar[str] = contextvars.ContextVar("_trace_id", default="")

# Sichtbare Zeichen ohne Leerzeichen, wie sie Logs und Kopfzeilen vertragen.
_CLIENT_ID = re.compile(r"[A-Za-z0-9._:\-]{1,128}")
_B3_ID = re.compile(r"[0-9a-fA-F]{16}|[0-9a-fA-F]{32}")


def _neu() -> str:
    return secrets.token_hex(16)


def aus_kopfzeilen(koepfe: Mapping[str, str]) -> str:
    """Die Trace-ID einer Anfrage aus ihren Kopfzeilen (Namen in Kleinschreibung)."""
    client = koepfe.get("x-client-trace-id", "")
    if _CLIENT_ID.fullmatch(client):
        return client
    b3 = koepfe.get("x-b3-traceid", "")
    if _B3_ID.fullmatch(b3):
        return b3.lower()
    einzeln = koepfe.get("b3", "").split("-", 1)[0]
    if _B3_ID.fullmatch(einzeln):
        return einzeln.lower()
    return _neu()


def aktuelle() -> str:
    """Die Trace-ID der laufenden Anfrage — leer außerhalb einer Anfrage."""
    return _trace_id.get()


def fuer_db() -> str | None:
    """Die Trace-ID für eine Spalte ``trace_id`` (0016): ``None`` außerhalb einer Anfrage, damit
    ein Hintergrundlauf ``NULL`` schreibt statt eines leeren Texts."""
    return _trace_id.get() or None


#: Zeichen der Fehlernummer: kurz genug zum Vorlesen, für die Suche im Studio eindeutig genug.
FEHLERNUMMER_ZEICHEN = 12


def fehlernummer() -> str:
    """Die Fehlernummer für eine Blase (Paket 18C/D): der Anfang der Trace-ID — im Studio führt
    sie über die Suche zum Zug. Außerhalb einer Anfrage ``-``."""
    return _trace_id.get()[:FEHLERNUMMER_ZEICHEN] or "-"


def setze(wert: str) -> contextvars.Token[str]:
    return _trace_id.set(wert)


def zuruecksetzen(token: contextvars.Token[str]) -> None:
    _trace_id.reset(token)


def ausgehende_koepfe() -> dict[str, str]:
    """Die Köpfe für einen Aufruf an die b-api oder den eigenen MCP-Server.

    B3 nur, wenn die ID eine gültige B3-ID ist; je Aufruf ein neuer Span.
    """
    tid = _trace_id.get()
    if not tid:
        return {}
    koepfe = {"x-client-trace-id": tid}
    # B3 verlangt Kleinbuchstaben-Hex und verbietet eine Null-ID (Review Phase D, C10).
    if _B3_ID.fullmatch(tid) and tid.strip("0"):
        koepfe["X-B3-TraceId"] = tid.lower()
        koepfe["X-B3-SpanId"] = secrets.token_hex(8)
    return koepfe


class TraceIdMiddleware:
    """Setzt die Trace-ID für die Dauer der Anfrage — reines ASGI, damit SSE nicht puffert."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        koepfe = {k.decode("latin-1").lower(): v.decode("latin-1")
                  for k, v in scope.get("headers", [])}
        token = _trace_id.set(aus_kopfzeilen(koepfe))
        # Zurückgesetzt nur nach Erfolg: Bei einer Ausnahme loggt sie Uvicorn erst außerhalb
        # („Exception in ASGI application“) — dann soll die ID noch gelten (Review Phase D, C4).
        # Uvicorn führt jede Anfrage in einer eigenen Aufgabe; die ID wandert nicht weiter.
        await self.app(scope, receive, send)
        _trace_id.reset(token)


class TraceIdFilter(logging.Filter):
    """Schreibt die Trace-ID in jeden Logeintrag (``record.trace_id``, ``-`` ohne Anfrage)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = _trace_id.get() or "-"
        return True
