"""Die beiden Anmelde-Endpunkte des MCP-Servers ohne MCP-Sitzung (Plan 2026-11-07, CB-7/CB-9).

* ``GET /auth/status`` (S4) — der Anmeldestand in **einer** Anfrage statt einer ganzen Sitzung
  für ``wlo_auth_status``; dieselbe Nutzlast, dazu ``expiresAt`` für Ticket- und Widget-Blöcke
  (R1). Ein unbrauchbarer Block (widerrufen, abgelaufen) bekommt 401.
* ``POST /auth/revoke`` mit dem Block als Bearer (R2) — das Abmelden im Widget beendet den
  Zugang am Server, nicht nur im Browser.

Beide nur am primären Server und nur aus dem Backend: ``/auth*`` hat kein CORS. Beide tragen den
Client-Schlüssel (``MCP_CLIENT_KEY``); den Block und den Schlüssel protokolliert dieses Modul nie.
"""

from __future__ import annotations

import logging
from typing import Any, Literal

import httpx

from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.mcp import schutz, transport
from boerdi.services.mcp.http_fabrik import client_schluessel_kopf
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: ``stand``: Antwort des Servers · ``abgelehnt``: 401 · ``unklar``: keine verwertbare Antwort ·
#: ``kein_endpunkt``: 404 (ein Server vor dem 07.11.) — dann fragt der Aufrufer das Werkzeug.
StatusArt = Literal["stand", "abgelehnt", "unklar", "kein_endpunkt"]
#: Längste Wartezeit, die übernommen wird (der Anmelde-Schutz des Servers zählt 10 min).
_WARTEZEIT_DECKEL_S = 600
#: Eine 429 ohne lesbare ``Retry-After``: so lange nicht neu fragen.
_WARTEZEIT_VORGABE_S = 60


def _koepfe(block: str) -> dict[str, str]:
    return {**ausgehende_koepfe(), **client_schluessel_kopf(), "Authorization": f"Bearer {block}"}


def _client(frist_s: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(
        frist_s, connect=get_settings().mcp_connect_timeout_s), follow_redirects=False)


async def status_abfragen(block: str, frist_s: float) -> tuple[StatusArt, dict[str, Any]]:
    """``GET /auth/status`` für ``block``. Steht der Ausfall-Schalter offen, wird nicht gefragt."""
    url = transport.resolve_mcp_url()
    if schutz.ist_offen(url):
        return "unklar", {}
    try:
        async with _client(frist_s) as client:
            antwort = await client.get(f"{schutz.wurzel(url)}/auth/status",
                                       headers=_koepfe(block))
    except httpx.HTTPError as exc:
        logger.info("Anmeldestand nicht abfragbar (%s)", type(exc).__name__)
        return "unklar", {}
    if antwort.status_code == 401:
        return "abgelehnt", {}
    if antwort.status_code == 404:
        return "kein_endpunkt", {}
    if antwort.status_code == 429:
        # Budget oder Anmelde-Schutz (bis 600 s). Die genannte Wartezeit einhalten: wer früher
        # fragt, bekommt wieder 429 und verbraucht dabei sein Budget (Antwort des MCP-Teams).
        roh = (antwort.headers.get("retry-after") or "").strip()
        warte = min(int(roh), _WARTEZEIT_DECKEL_S) if roh.isdigit() else _WARTEZEIT_VORGABE_S
        logger.info("Anmeldestand nicht abfragbar (HTTP 429, %s s warten)", warte)
        # ``rate_limited`` = das Budget des Chatbots (gilt für alle Personen), ``too_many_logins``
        # = der Anmelde-Schutz dieses einen Blocks.
        return "unklar", {"retry_after": warte, "code": _code(antwort)}
    if antwort.status_code != 200:
        # 5xx: der Server konnte gerade nicht prüfen.
        status = antwort.status_code
        logger.info("Anmeldestand nicht abfragbar (HTTP %s)", status)
        return "unklar", {}
    try:
        stand = antwort.json()
    except ValueError:
        return "unklar", {}
    return ("stand", stand) if isinstance(stand, dict) else ("unklar", {})


def _code(antwort: httpx.Response) -> str:
    """``code`` aus dem REST-Rumpf einer Ablehnung — ``""``, wenn keiner lesbar ist."""
    try:
        rumpf = antwort.json()
    except ValueError:
        return ""
    return str(rumpf.get("code") or "") if isinstance(rumpf, dict) else ""


async def widerrufen(block: str, frist_s: float = 10.0) -> bool | None:
    """``POST /auth/revoke`` mit ``block`` als Bearer. ``True``/``False`` wie der Server
    (``revoked``; ``False`` heißt auch „war schon weg“ — bewusst nicht unterscheidbar),
    ``None``, wenn der Server nicht zu fragen war."""
    url = transport.resolve_mcp_url()
    try:
        async with _client(frist_s) as client:
            antwort = await client.post(f"{schutz.wurzel(url)}/auth/revoke",
                                        headers=_koepfe(block))
    except httpx.HTTPError as exc:
        logger.warning("Widerruf des Zugangsblocks nicht möglich (%s)", type(exc).__name__)
        return None
    if antwort.status_code != 200:
        # 404: diese Anlage gibt keine Blöcke aus; 429: Adress-Budget von ``/auth*``.
        status = antwort.status_code
        logger.warning("Widerruf des Zugangsblocks abgelehnt (HTTP %s)", status)
        return None
    try:
        return bool(antwort.json().get("revoked"))
    except (ValueError, AttributeError):
        return None
