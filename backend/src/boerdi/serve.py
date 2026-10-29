"""Einstieg des Containers (Paket 17, D1): öffentlicher und interner Port in EINEM Prozess.

``python -m boerdi.serve`` ersetzt ``uvicorn boerdi.main:app``. Zwei Prozesse hätten zwei
Metrik-Registries und zwei abgestimmte Shutdowns gebraucht; hier führt der Hauptserver die
Signale (SIGTERM → Verbindungen schließen, höchstens 30 s, dann Lifespan-Ende). Erst wenn der
Hauptserver läuft, meldet ``/ready`` „bereit“; ab dem Signal wieder „nicht bereit“, der Pod
fällt sofort aus dem Service. Nach dem geordneten Ende löst Uvicorn das abgefangene Signal
erneut aus — der Prozess endet damit wie unter dem bisherigen ``uvicorn``-Befehl (gemessen
2026-10-20), und der interne Server mit ihm. Ein Fehlstart (etwa ohne Postgres) endet in
Uvicorn selbst mit Code 3, wie unter dem CLI.

Die Flags des Hauptservers sind die bisherigen der Dockerfile-CMD (Begründungen dort):
``--proxy-headers``, ``--timeout-graceful-shutdown 30``; wessen weitergeleiteten Köpfen er
glaubt, sagt seit dem Gesamt-Review ``FORWARDED_ALLOW_IPS`` (Vorgabe ``*`` wie bisher).

Zu Beginn des Herunterfahrens — bevor die Annahme schließt — beendet der Hauptserver die Läufe
dieses Pods (``services/laeufe_beenden``, Gesamt-Review Paket 17, C2).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterator
from typing import Any

import uvicorn
from fastapi import FastAPI

from boerdi.settings import get_settings

OEFFENTLICHER_PORT = 8100

log = logging.getLogger(__name__)


class _HauptServer(uvicorn.Server):
    """Der Uvicorn-Server des öffentlichen Ports, mit einem Schritt vor dem Herunterfahren."""

    #: Läuft, bevor Uvicorn die Annahme schließt; ein Fehler darin hält nichts auf.
    bei_ende: Callable[[], Awaitable[None]] | None = None

    async def shutdown(self, sockets: Any = None) -> None:
        if self.bei_ende is not None:
            try:
                await self.bei_ende()
            except Exception:
                log.warning("Schritt vor dem Herunterfahren gescheitert", exc_info=True)
        await super().shutdown(sockets)


class _InternServer(uvicorn.Server):
    """Ein Uvicorn-Server ohne eigene Signal-Handler.

    Uvicorn setzt sie je Server; der zweite überschriebe die des ersten, und ein SIGTERM
    erreichte nur einen von beiden — der Prozess endete nie. Den internen Server beendet
    :func:`laufen`, sobald der Hauptserver fertig ist.
    """

    @contextlib.contextmanager
    def capture_signals(self) -> Iterator[None]:
        yield


def _log_stufe(name: str) -> int:
    """``LOG_LEVEL`` als Zahl für Uvicorn — dessen Namenstabelle kennt etwa ``WARN`` nicht
    (Review Phase D, C2: ``KeyError``, der Container startete nicht). Unbekanntes → INFO, wie
    ``main._configure_logging``."""
    stufe = logging.getLevelName(name.upper())
    return stufe if isinstance(stufe, int) else logging.INFO


def baue_server(haupt: FastAPI, intern: FastAPI) -> tuple[uvicorn.Server, uvicorn.Server]:
    """Hauptserver (öffentlicher Port, mit Lifespan) und interner Server (ohne)."""
    s = get_settings()
    stufe = _log_stufe(s.log_level)
    haupt_server = _HauptServer(uvicorn.Config(
        haupt, host="0.0.0.0", port=OEFFENTLICHER_PORT,  # noqa: S104 — Container-Port
        proxy_headers=True, forwarded_allow_ips=s.forwarded_allow_ips,
        timeout_graceful_shutdown=30,
        # Gesamt-Review Paket 17 (D5): länger als Ingress (60 s) und traefik (90 s) eine leere
        # Verbindung halten — sonst schickt der Proxy die nächste Anfrage auf eine Verbindung,
        # die Uvicorn gerade schließt (sporadisch 502; POST /api/chat wird nicht wiederholt).
        timeout_keep_alive=120,
        # Paket 17 (D4): Uvicorn richtet kein eigenes Logging ein — seine Zeilen laufen über
        # die Wurzel und damit im Format von ``LOG_FORMAT`` samt Trace-ID (``main``).
        # Paket 18C/D: seine Zugriffszeile (IP, roher Pfad) ist aus; die eigene schreibt
        # ``obs.metrics.MetrikMiddleware`` (``obs/zugriffslog``).
        log_config=None, log_level=stufe, access_log=False,
    ))
    intern_server = _InternServer(uvicorn.Config(
        intern, host="0.0.0.0", port=s.internal_port,  # noqa: S104
        lifespan="off", access_log=False, log_config=None, log_level=stufe,
    ))
    return haupt_server, intern_server


def beendet_von(server: Any) -> Callable[[], bool]:
    """Die Frage „fährt dieser Server herunter?“ für ``/ready``."""
    return lambda: bool(server.should_exit)


def gestartet_von(server: Any) -> Callable[[], bool]:
    """Die Frage „läuft dieser Server (Lifespan durch, Port gebunden)?“ für ``/ready``."""
    return lambda: bool(server.started)


async def laufen(haupt: Any, intern: Any) -> None:
    """Beide Server betreiben; der interne endet, sobald der Hauptserver fertig ist."""
    intern_lauf = asyncio.create_task(intern.serve())
    try:
        await haupt.serve()
    finally:
        intern.should_exit = True
        await intern_lauf


async def laeufe_der_app_beenden(app: FastAPI) -> None:
    """Die Läufe dieses Pods schließen — sofern der Lebenszyklus eine Engine hinterlegt hat."""
    from boerdi.services import laeufe_beenden

    engine = getattr(app.state, "engine", None)
    if engine is not None:
        await laeufe_beenden.beende(engine)


def main() -> None:
    from boerdi.api.intern import create_intern_app
    from boerdi.main import app

    haupt_server, intern_server = baue_server(app, FastAPI())
    intern_server.config.app = create_intern_app(
        app, beendet=beendet_von(haupt_server), gestartet=gestartet_von(haupt_server))
    haupt_server.bei_ende = lambda: laeufe_der_app_beenden(app)
    asyncio.run(laufen(haupt_server, intern_server))


if __name__ == "__main__":
    main()
