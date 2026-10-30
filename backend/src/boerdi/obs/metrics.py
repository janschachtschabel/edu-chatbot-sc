"""Prometheus-Metriken (Paket 17, D3) — ausgeliefert nur am internen Port (``api/intern``).

Basis-Metriken (Prozess, Python, GC) bringt ``prometheus_client`` in seiner Standard-Registry
mit; dazu wenige gezielte Applikationsmetriken (Leitfaden „Übergabe an Team 6“). Die Labels
bleiben endlich: Routen als Pfad-Vorlage, MCP-Server als Host, LLM-Aufrufe je Phase — nie
eine Sitzungs-ID, ein Werkzeugname aus fremden Servern oder ein Modellname aus der Antwort.

Ein Prozess, eine Registry: öffentlicher und interner Port laufen im selben Prozess
(``boerdi.serve``). Mehrere Uvicorn-Worker sind ohnehin ausgeschlossen (Dockerfile).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from boerdi.api.scope_pfad import route_path
from boerdi.obs.zugriffslog import zugriff
from boerdi.settings import get_settings

_SEKUNDEN = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120)

HTTP_ANFRAGEN = Counter(
    "boerdi_http_requests_total", "HTTP-Anfragen am öffentlichen Port",
    ["route", "method", "status"])
HTTP_DAUER = Histogram(
    "boerdi_http_request_duration_seconds",
    "Dauer je Anfrage (bei SSE: bis der Strom endet, also etwa die Zugdauer)",
    ["route", "method"], buckets=_SEKUNDEN)
ZUEGE = Counter("boerdi_turns_total", "Beantwortete Züge je Maschine", ["engine"])
LLM_AUFRUFE = Counter(
    "boerdi_llm_calls_total", "LLM-Aufrufe je Phase und Ausgang", ["phase", "outcome"])
LLM_DAUER = Histogram(
    "boerdi_llm_call_duration_seconds", "Dauer je LLM-Aufruf samt Warten auf einen Platz",
    ["phase"], buckets=_SEKUNDEN)
MCP_AUFRUFE = Counter(
    "boerdi_mcp_calls_total", "MCP-Aufrufe je Server und Ausgang (ok, tool, transport, "
    "timeout, auth)", ["server", "outcome"])
MCP_DAUER = Histogram(
    "boerdi_mcp_call_duration_seconds", "Dauer je MCP-Aufruf", ["server"], buckets=_SEKUNDEN)
SICHERHEITSSTUFEN = Counter(
    "boerdi_safety_stage_total",
    "Ausgang je Sicherheitsstufe (ok, fehler, keine_zugangsdaten) — ein Ausfall ist "
    "fail-open und wäre sonst nur eine Logzeile", ["stage", "outcome"])
HTTP_LAUFEND = Gauge(
    "boerdi_http_requests_in_progress",
    "Laufende Anfragen am öffentlichen Port — überwiegend offene SSE-Ströme der Züge")
BUILD = Gauge("boerdi_build_info", "Stand des Abbilds (Wert immer 1)", ["version"])
# Paket 18F: an der LLM-Engstelle (``services/llm_ereignisse``) — je Aufruf, die Logzeile dazu
# ist gedrosselt.
LLM_SCHLUESSEL_ABGELEHNT = Counter(
    "boerdi_llm_schluessel_abgelehnt_total",
    "LLM-Aufrufe, deren Schlüssel der Anbieter abwies (401), je Anbieter und Quelle",
    ["anbieter", "quelle"])
LLM_PLATZ_FRIST = Counter(
    "boerdi_llm_platz_frist_total",
    "Chat-Aufrufe ohne LLM-Platz binnen LLM_SLOT_WAIT_S — der Zug galt als ausgelastet")

log = logging.getLogger(__name__)

#: Label für Pfade ohne eigene Route (unbekannt, statische Mounts, Studio-Proxy).
SAMMEL_ROUTE = "andere"


def llm_aufruf(phase: str | None, ok: bool, sekunden: float) -> None:
    LLM_AUFRUFE.labels(phase or "ohne", "ok" if ok else "fehler").inc()
    LLM_DAUER.labels(phase or "ohne").observe(sekunden)


@contextlib.asynccontextmanager
async def llm_messung(phase: str | None) -> AsyncIterator[None]:
    """Einen LLM-Aufruf zählen und messen; die Ausnahme geht unverändert weiter.

    Ausgang ``fehler`` bei einer Störung, ``abbruch`` bei einem abgebrochenen Aufruf (Client
    aufgelegt, Zug beendet, Frist) — sonst feuerte die Alarmregel auf die LLM-Fehlerquote bei
    gewöhnlichen Abbrüchen (Review Phase D, C3).
    """
    beginn = time.perf_counter()
    try:
        yield
    except asyncio.CancelledError:
        _llm_ausgang(phase, "abbruch", time.perf_counter() - beginn)
        raise
    except BaseException as fehler:
        # Ein eigener Ausgang je Fehlerart, die keine Störung des Anbieters ist (Paket 18F:
        # ``LlmAusgelastet`` → ``ausgelastet``); gelesen über ein Attribut, ohne Import.
        if ausgang := getattr(fehler, "metrik_ausgang", None):
            _llm_ausgang(phase, ausgang, time.perf_counter() - beginn)
            raise
        llm_aufruf(phase, False, time.perf_counter() - beginn)
        raise
    llm_aufruf(phase, True, time.perf_counter() - beginn)


def _llm_ausgang(phase: str | None, ausgang: str, sekunden: float) -> None:
    LLM_AUFRUFE.labels(phase or "ohne", ausgang).inc()
    LLM_DAUER.labels(phase or "ohne").observe(sekunden)


def sicherheitsstufe(stufe: str, ausgang: str) -> None:
    SICHERHEITSSTUFEN.labels(stufe, ausgang).inc()


def mcp_aufruf(url: str, outcome: str, sekunden: float) -> None:
    server = urlsplit(url).hostname or "unbekannt"
    MCP_AUFRUFE.labels(server, outcome).inc()
    MCP_DAUER.labels(server).observe(sekunden)


def zug(engine: str | None) -> None:
    ZUEGE.labels(engine or "keine").inc()


def antwort() -> tuple[bytes, str]:
    """Der Inhalt von ``/metrics`` und sein Content-Type."""
    BUILD.labels(get_settings().boerdi_version or "unbekannt").set(1)
    return generate_latest(), CONTENT_TYPE_LATEST


_METHODEN = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


class MetrikMiddleware:
    """Zählt jede HTTP-Anfrage am öffentlichen Port — reines ASGI, damit SSE nicht puffert.

    Die Route ist die Pfad-Vorlage aus der OpenAPI der App (``/api/sessions/{session_id}/…``),
    feste Pfade vor solchen mit Parametern; das Studio zählt als ``/studio``, der Rest als
    ``andere``. Bewusst nicht über den Router: Starlette 1.3 setzt kein ``scope["route"]``,
    ein gesetztes ``endpoint`` kommt aus der Scope-Kopie des Routers nicht zurück, und
    FastAPI 0.139 hängt eingebundene Router als ``_IncludedRouter`` ohne Pfad ein
    (alles gemessen 2026-10-20) — die OpenAPI ist die stabile, öffentliche Quelle.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app
        self._vorlagen: list[tuple[re.Pattern[str], str]] | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        beginn = time.perf_counter()
        status = {"code": 500}

        async def _senden(nachricht: Message) -> None:
            if nachricht["type"] == "http.response.start":
                status["code"] = nachricht["status"]
            await send(nachricht)

        # Vor dem Aufruf: ein Mount (Studio-SPA) setzt ``root_path`` im Scope um, danach sähe
        # ``/studio/`` aus wie ``/`` (Review Phase D, C1).
        pfad = route_path(scope)
        HTTP_LAUFEND.inc()
        try:
            await self.app(scope, receive, _senden)
        finally:
            HTTP_LAUFEND.dec()
            # Gesamt-Review Paket 17 (D3): Labels bleiben endlich — fremde Methoden als
            # ``OTHER``, und ein 405 traf keine Route (die Vorlage gehört nur echten Treffern).
            code = status["code"]
            route = SAMMEL_ROUTE if code == 405 else self._route(pfad, scope.get("app"))
            methode = scope.get("method", "")
            methode = methode if methode in _METHODEN else "OTHER"
            dauer = time.perf_counter() - beginn
            HTTP_ANFRAGEN.labels(route, methode, str(code)).inc()
            HTTP_DAUER.labels(route, methode).observe(dauer)
            # Paket 18C/D: die Zugriffszeile statt Uvicorns (ohne IP, Abfrage, rohen Pfad).
            zugriff(methode, self._log_route(pfad, route, scope.get("app")), code,
                    round(dauer * 1000))

    def _log_route(self, pfad: str, route: str, app: Any) -> str:
        """Wie ``route``, nur zählen Studio-Aufrufe der API mit ihrer Vorlage
        (``/studio/api/sessions/{session_id}/…``); die Metrik fasst sie als ``/studio``
        zusammen."""
        if not pfad.startswith("/studio/api/"):
            return route
        innen = self._route(pfad[len("/studio"):], app)
        return "/studio" + innen if innen.startswith("/") else "/studio/api"

    def _route(self, pfad: str, app: Any) -> str:
        if self._vorlagen is None:
            try:
                self._vorlagen = _vorlagen_aus(app)
            except Exception:  # eine Metrik darf nie eine Antwort kosten
                log.warning("Metriken: Pfad-Vorlagen nicht lesbar — Routen zählen als "
                            "%r", SAMMEL_ROUTE, exc_info=True)
                self._vorlagen = []
        for muster, vorlage in self._vorlagen:
            if muster.fullmatch(pfad):
                return vorlage
        return "/studio" if pfad == "/studio" or pfad.startswith("/studio/") else SAMMEL_ROUTE


def _vorlagen_aus(app: Any) -> list[tuple[re.Pattern[str], str]]:
    """Pfad-Vorlagen der App als Muster — feste zuerst, damit ``/x/stats`` nicht als ``/x/{id}``
    zählt."""
    erzeuge = getattr(app, "openapi", None)
    pfade = list((erzeuge() if callable(erzeuge) else {}).get("paths", {}))
    pfade.sort(key=lambda v: ("{" in v, v))
    # ``re.escape`` macht aus ``{name}`` ``\{name\}`` — das ersetzt ein Segment-Muster.
    parameter = re.compile(r"\\\{[^/]+?\\\}")
    return [(re.compile(parameter.sub("[^/]+", re.escape(v))), v) for v in pfade]
