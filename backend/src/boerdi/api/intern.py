"""Die App des internen Ports (Paket 17, D1/D3): Liveness, Readiness, Metriken.

Leitfaden „Übergabe an Team 6“: Infrastruktur-Endpunkte erscheinen nicht in der öffentlichen
Spec und sind von außen nicht erreichbar; Kubernetes nutzt diesen Port für seine Proben.
Eine eigene kleine App statt eines Pfads in der Haupt-App, damit der Ingress nur den
öffentlichen Port freigibt und nichts ausblenden muss.

- ``/health`` (Liveness): der Prozess lebt — ohne Datenbank, ein startender Pod ist lebendig.
- ``/ready`` (Readiness): der Hauptserver läuft (Lifespan durch, Port gebunden), Postgres
  antwortet, und der Hauptserver fährt nicht gerade herunter (dann soll der Pod sofort aus
  dem Service). Die Datenbank-Probe hat eine eigene Engine ohne Pool: ein ausgeschöpfter
  Chat-Pool unter Last darf nicht alle Pods zugleich „nicht bereit“ melden (Review Phase D).
  Seit Paket 19 (M-1) zählt auch der Config-Abgleich (``ConfigStore.bereit``): steht weder
  ``LISTEN`` noch gelang ein Versionsabgleich in drei Takten, liest die Kopie womöglich alte
  Konfiguration (Datenschutz-Schalter eingeschlossen) — Grund ``konfiguration``.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from boerdi.obs.metrics import antwort as metrik_antwort
from boerdi.settings import get_settings

log = logging.getLogger(__name__)

#: Höchstens so lange darf die Datenbank-Probe dauern — die Probe von Kubernetes hat
#: selbst eine Frist (Vorgabe 1 s); eine hängende Verbindung soll „nicht bereit“ heißen.
_DB_FRIST_S = 2.0

_OK = {"status": "ok"}


async def _bereitschaft(
    beendet: Callable[[], bool], gestartet: Callable[[], bool], engine: Any,
    store: Any = None,
) -> tuple[bool, str]:
    if beendet():
        return False, "beendet"
    if not gestartet():
        return False, "startet"
    try:
        async with asyncio.timeout(_DB_FRIST_S), engine.connect() as verbindung:
            await verbindung.execute(text("SELECT 1"))
    except Exception as fehler:  # jede Störung heißt „nicht bereit“, nie 500
        # Der Text kann Verbindungsdaten tragen: ins Log, nicht in die Antwort.
        log.warning("Readiness: Datenbank nicht erreichbar: %s", type(fehler).__name__)
        return False, "datenbank"
    if store is not None and not store.bereit():
        log.warning("Readiness: Konfiguration nicht abgeglichen (kein LISTEN, kein "
                    "Versionsabgleich in drei Takten)")
        return False, "konfiguration"
    return True, "ok"


def create_intern_app(
    haupt: FastAPI,
    *,
    beendet: Callable[[], bool],
    gestartet: Callable[[], bool] = lambda: False,
    probe_engine: AsyncEngine | Any | None = None,
) -> FastAPI:
    """Die interne App zur Haupt-App ``haupt``.

    ``beendet``/``gestartet`` fragen den Hauptserver (``serve``); ``probe_engine`` ersetzt in
    Tests die eigene Engine der Datenbank-Probe (sonst einmal angelegt, ohne Pool).
    """
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    probe: dict[str, Any] = {"engine": probe_engine}

    def _probe_engine() -> Any:
        if probe["engine"] is None:
            probe["engine"] = create_async_engine(get_settings().database_url,
                                                  poolclass=NullPool)
        return probe["engine"]

    @app.get("/health")
    @app.head("/health")
    def health() -> dict[str, str]:
        return _OK

    @app.get("/openapi-full.json")
    def openapi_voll() -> dict:
        """Die volle Spec der Haupt-App (Studio, Eval, Konfiguration) — nur im Cluster."""
        return haupt.openapi()

    @app.get("/metrics")
    def metrics() -> Response:
        inhalt, art = metrik_antwort()
        return Response(content=inhalt, media_type=art)

    @app.get("/ready")
    @app.head("/ready")
    async def ready() -> JSONResponse:
        bereit, grund = await _bereitschaft(
            beendet, gestartet, _probe_engine(),
            getattr(haupt.state, "config_store", None))
        if bereit:
            return JSONResponse({"status": "ready", "version": get_settings().boerdi_version})
        return JSONResponse({"status": "not_ready", "grund": grund}, status_code=503)

    return app
