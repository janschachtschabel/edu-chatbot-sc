"""Die httpx-Fabrik mit dem Zugangsblock (aus ``auth`` gelöst, Paket 10 — Dateigrößen).

``auth`` sagt, welcher Block für den laufenden Aufruf gilt; hier wird er zur
``Authorization``-Kopfzeile der Verbindung. Den Block bekommt nur der primäre Server
(``transport._client_fabrik``) — ebenso den Client-Schlüssel (``MCP_CLIENT_KEY``, Plan
2026-11-07, S1/CB-7), mit dem der Server den Chatbot in einem eigenen Budget zählt.
"""

from __future__ import annotations

import httpx
from mcp.client.streamable_http import create_mcp_http_client
from mcp.shared._httpx_utils import McpHttpClientFactory

from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.mcp.auth import _effective_token
from boerdi.settings import get_settings

__all__ = ["CLIENT_KEY_HEADER", "McpHttpClientFactory", "build_http_client_factory",
           "client_schluessel_kopf", "mit_verbindungsfrist"]

#: Kopfzeile des Client-Schlüssels (MCP ``client-budget.ts``: ``x-wlo-client-key``).
CLIENT_KEY_HEADER = "X-WLO-Client-Key"
#: Die Fristen des SDK (``create_mcp_http_client``), wenn es keine mitgibt.
_SDK_FRIST = httpx.Timeout(30.0, read=300.0)


def mit_verbindungsfrist(timeout: httpx.Timeout | None) -> httpx.Timeout:
    """``timeout`` mit der Verbindungsfrist ``MCP_CONNECT_TIMEOUT_S`` (Plan 2026-11-07, CB-3):
    ein Server, der nicht annimmt, kostet 5 s statt der 30 s des SDK. Die übrigen Fristen
    bleiben; die Gesamtfrist trägt ``transport`` (``MCP_CALL_TIMEOUT_S``)."""
    basis = timeout or _SDK_FRIST
    return httpx.Timeout(connect=get_settings().mcp_connect_timeout_s, read=basis.read,
                         write=basis.write, pool=basis.pool)


def client_schluessel_kopf() -> dict[str, str]:
    """Der Kopf mit dem Client-Schlüssel — leer, wenn keiner gesetzt ist. Nur für den primären
    Server; der Schlüssel erscheint nie im Log."""
    schluessel = (get_settings().mcp_client_key.get_secret_value() or "").strip()
    return {CLIENT_KEY_HEADER: schluessel} if schluessel else {}


def build_http_client_factory() -> McpHttpClientFactory:
    """Die httpx-Fabrik, die das SDK je Verbindung aufruft.

    Immer mit der kurzen Verbindungsfrist (CB-3). Mit Block ergänzt die Fabrik die
    ``Authorization``-Kopfzeile, mit ``MCP_CLIENT_KEY`` den Client-Schlüssel, und lässt
    alles andere durch, was das SDK mitgibt (eigene Kopfzeilen, ``auth``).

    Welcher Block gilt, entscheidet :func:`_effective_token` — Zug vor Anlage.
    Die Fabrik wird je Aufruf in ``transport._open_session`` neu gebaut, also
    liest sie den Block des gerade laufenden Zuges und nicht den beim Start.

    Bewusst ``httpx_client_factory`` und NICHT der ``headers=``-Parameter von
    ``streamablehttp_client``: der ist im SDK als veraltet markiert
    („Parameters headers, timeout, sse_read_timeout, and auth are deprecated").
    ``create_mcp_http_client`` kommt aus demselben öffentlichen Modul wie
    ``streamablehttp_client`` — kein privater SDK-Pfad.
    """
    block = _effective_token()
    # Paket 17 (D4): die Trace-ID der Anfrage — nur an den eigenen Server; fremde Server der
    # Registry bekommen eine andere Fabrik (``transport._client_fabrik``).
    zusatz = {**ausgehende_koepfe(), **client_schluessel_kopf()}
    if block:
        zusatz["Authorization"] = f"Bearer {block}"

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return create_mcp_http_client(
            headers={**(headers or {}), **zusatz},
            timeout=mit_verbindungsfrist(timeout),
            auth=auth,
        )

    return factory
