"""Schutz der MCP-Anbindung: Ausfall-Schalter und Budget-Wächter (Plan 2026-11-07, CB-3/CB-5).

**Ausfall-Schalter (je Server).** ``MCP_BREAKER_FAILURES`` Transportfehler (keine Antwort, eigene
Frist, 503) innerhalb von ``MCP_BREAKER_WINDOW_S`` öffnen ihn für ``MCP_BREAKER_OPEN_S``. Solange
scheitert jeder Aufruf sofort als „ausgelastet“, ohne dass etwas gesendet wird. Danach fragt
**ein** Aufruf zuerst ``GET /ready`` des Servers (S5: keine Kosten am Budget, höchstens eine Probe
je 30 s am Server). Antwortet der Server, schließt der Schalter; sonst bleibt er offen. Ein Server
ohne ``/ready`` (404, älterer Stand oder fremder Server) lässt den Aufruf selbst die Probe sein.

**Budget-Wächter (nur der primäre Server).** Der MCP-Server zählt Werkzeugaufrufe je Minute
(S1: nur ``tools/call``). Der Wächter hält ein gleitendes 60-s-Fenster mit höchstens
``MCP_BUDGET_RPM`` Aufrufen — ein gleitendes Fenster überschreitet das feste des Servers nie.
Ist es voll, wartet ein Aufruf bis ``MCP_BUDGET_WAIT_S`` und endet sonst als „ausgelastet“. So
läuft der Chatbot nicht selbst in das 429.

Beides gilt je Prozess; der Betrieb fährt eine Replik (``BACKEND_REPLICAS=1``). Bei mehreren
Repliken teilt man ``MCP_BUDGET_RPM`` durch ihre Zahl.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field

import httpx

from boerdi.obs import metrics
from boerdi.obs.drossel import gedrosselt
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Länge des Budget-Fensters — so zählt der Server (``RATE_LIMIT_RPM`` je Minute).
FENSTER_S = 60.0
#: Frist der Bereitschaftsprobe; der Server wartet selbst höchstens 5 s auf das Repository.
PROBE_FRIST_S = 6.0


def wurzel(url: str) -> str:
    """Die Wurzel eines MCP-Servers: seine Adresse ohne das abschließende ``/mcp`` — dort liegen
    ``/ready``, ``/auth/*`` und ``/api/uploads``. Ein Pfad davor bleibt (Review 2026-11-07,
    Befund 5: ``https://gw/wlo/mcp`` → ``https://gw/wlo``, nicht ``https://gw``; sonst gingen Block
    und Client-Schlüssel an einen anderen Dienst derselben Herkunft)."""
    url = url.rstrip("/")
    return url[: -len("/mcp")] if url.endswith("/mcp") else url


def _jetzt() -> float:
    """Test-Naht."""
    return time.monotonic()


@dataclass
class _Schalter:
    fehler: deque[float] = field(default_factory=deque)
    offen_bis: float = 0.0
    probe_laeuft: bool = False


_schalter: dict[str, _Schalter] = {}
_aufrufe: dict[str, deque[float]] = {}


def zuruecksetzen() -> None:
    """Test-Naht: alle Schalter zu, alle Fenster leer."""
    _schalter.clear()
    _aufrufe.clear()


def melde_fehler(url: str) -> None:
    """Ein Aufruf an ``url`` bekam keine Antwort."""
    s = get_settings()
    sch = _schalter.setdefault(url, _Schalter())
    jetzt = _jetzt()
    sch.fehler.append(jetzt)
    while sch.fehler and jetzt - sch.fehler[0] > s.mcp_breaker_window_s:
        sch.fehler.popleft()
    if len(sch.fehler) >= s.mcp_breaker_failures and sch.offen_bis <= jetzt:
        sch.offen_bis = jetzt + s.mcp_breaker_open_s
        logger.warning("MCP %s: Ausfall-Schalter offen für %g s (%d Fehler in %g s)",
                       url, s.mcp_breaker_open_s, len(sch.fehler), s.mcp_breaker_window_s)
        metrics.mcp_schalter(url, True)


def melde_erfolg(url: str) -> None:
    """Der Server hat geantwortet — auch eine Ablehnung ist eine Antwort."""
    sch = _schalter.get(url)
    if sch is None:
        return
    sch.fehler.clear()
    if sch.offen_bis:
        sch.offen_bis = 0.0
        logger.info("MCP %s: Ausfall-Schalter wieder zu", url)
        metrics.mcp_schalter(url, False)


def ist_offen(url: str) -> bool:
    """Ist der Schalter für ``url`` gerade offen (ohne Probe)? Für Prüfungen, die nicht warten."""
    sch = _schalter.get(url)
    return sch is not None and bool(sch.offen_bis) and (_jetzt() < sch.offen_bis
                                                         or sch.probe_laeuft)


async def durchlassen(url: str) -> bool:
    """Darf ein Aufruf an ``url`` hinaus? ``False`` = Schalter offen, sofort beenden."""
    sch = _schalter.get(url)
    if sch is None or not sch.offen_bis:
        return True
    if _jetzt() < sch.offen_bis or sch.probe_laeuft:
        return False
    sch.probe_laeuft = True
    try:
        bereit = await _bereit(url)
    finally:
        sch.probe_laeuft = False
    if bereit:
        melde_erfolg(url)
        return True
    sch.offen_bis = _jetzt() + get_settings().mcp_breaker_open_s
    return False


async def _bereit(url: str) -> bool:
    """``GET /ready``: antwortet der Server? ``upstream: "unreachable"`` zählt als Ausfall —
    dann scheitert ohnehin jedes Werkzeug. 404 (kein ``/ready``) lässt den Aufruf proben."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(
                PROBE_FRIST_S, connect=get_settings().mcp_connect_timeout_s)) as client:
            antwort = await client.get(f"{wurzel(url)}/ready")
    except httpx.HTTPError as exc:
        logger.info("MCP %s: Bereitschaftsprobe ohne Antwort (%s)", url, type(exc).__name__)
        return False
    if antwort.status_code == 404:
        return True
    try:
        stand = antwort.json()
    except ValueError:
        return False
    return isinstance(stand, dict) and stand.get("upstream") != "unreachable" and (
        antwort.status_code == 200 or stand.get("upstream") == "slow")


async def budget_platz(url: str) -> bool:
    """Einen Platz im Budget von ``url`` nehmen — ``False``, wenn keiner binnen
    ``MCP_BUDGET_WAIT_S`` frei wird. ``MCP_BUDGET_RPM`` 0 schaltet den Wächter ab."""
    s = get_settings()
    if s.mcp_budget_rpm <= 0:
        return True
    fenster = _aufrufe.setdefault(url, deque())
    frist = _jetzt() + s.mcp_budget_wait_s
    while True:
        jetzt = _jetzt()
        while fenster and jetzt - fenster[0] >= FENSTER_S:
            fenster.popleft()
        if len(fenster) < s.mcp_budget_rpm:
            fenster.append(jetzt)
            return True
        warte = fenster[0] + FENSTER_S - jetzt
        if jetzt + warte > frist:
            gedrosselt(logger, logging.WARNING, f"mcp:{url}:budget", FENSTER_S,
                       "MCP %s: Budget von %d Aufrufen je Minute erschöpft", url,
                       s.mcp_budget_rpm)
            return False
        await asyncio.sleep(warte)
