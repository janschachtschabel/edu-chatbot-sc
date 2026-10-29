"""Die Zugriffszeile (Paket 18C/D, Phase 2) — statt Uvicorns.

Uvicorns Zeile trug je Anfrage die IP und den rohen Pfad, beim Verlaufsabruf also die
Sitzungs-ID, die wie ein Schlüssel zum Verlauf wirkt; ``serve`` schaltet sie ab. Diese Zeile
nennt Methode, Pfad-Vorlage, Status und Dauer — keine IP, keine Abfrage; die Trace-ID steht in
jeder Zeile. Eine Drosselung erscheint hier als ``status=429``. Ausgelieferte Dateien (Widget,
Studio-Oberfläche) und die Liveness-Probe stehen nur auf DEBUG: sie wären sonst die Mehrheit
der Zeilen, ohne etwas zu sagen.
"""

from __future__ import annotations

import logging

from boerdi.obs.log_inhalt import ereignis

log = logging.getLogger("boerdi.zugriff")


def _nur_debug(route: str) -> bool:
    return route == "/studio" or route == "/health" or route.startswith("/widget")


def zugriff(methode: str, route: str, status: int, dauer_ms: int) -> None:
    """Eine Zeile je Anfrage; aufgerufen von ``obs.metrics.MetrikMiddleware``."""
    ereignis(log, "zugriff", stufe=logging.DEBUG if _nur_debug(route) else logging.INFO,
             methode=methode, route=route, status=status, dauer_ms=dauer_ms)
