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
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable, Iterator
from typing import Any

import uvicorn
from fastapi import FastAPI

from boerdi.settings import get_settings

OEFFENTLICHER_PORT = 8100

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
    haupt_server = uvicorn.Server(uvicorn.Config(
        haupt, host="0.0.0.0", port=OEFFENTLICHER_PORT,  # noqa: S104 — Container-Port
        proxy_headers=True, forwarded_allow_ips=s.forwarded_allow_ips,
        timeout_graceful_shutdown=30,
        # Gesamt-Review Paket 17 (D5): länger als Ingress (60 s) und traefik (90 s) eine leere
        # Verbindung halten — sonst schickt der Proxy die nächste Anfrage auf eine Verbindung,
        # die Uvicorn gerade schließt (sporadisch 502; POST /api/chat wird nicht wiederholt).
        timeout_keep_alive=120,
        # Paket 17 (D4): Uvicorn richtet kein eigenes Logging ein — seine Zeilen laufen über
        # die Wurzel und damit im Format von ``LOG_FORMAT`` samt Trace-ID (``main``).
        log_config=None, log_level=stufe,
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


def main() -> None:
    from boerdi.api.intern import create_intern_app
    from boerdi.main import app

    haupt_server, intern_server = baue_server(app, FastAPI())
    intern_server.config.app = create_intern_app(
        app, beendet=beendet_von(haupt_server), gestartet=gestartet_von(haupt_server))
    asyncio.run(laufen(haupt_server, intern_server))


if __name__ == "__main__":
    main()
