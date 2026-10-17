"""Die httpx-Fabrik mit dem Zugangsblock (aus ``auth`` gelöst, Paket 10 — Dateigrößen).

``auth`` sagt, welcher Block für den laufenden Aufruf gilt; hier wird er zur
``Authorization``-Kopfzeile der Verbindung. Den Block bekommt nur der primäre Server
(``transport._client_fabrik``).
"""

from __future__ import annotations

import httpx
from mcp.client.streamable_http import create_mcp_http_client
from mcp.shared._httpx_utils import McpHttpClientFactory

from boerdi.services.mcp.auth import _effective_token

__all__ = ["McpHttpClientFactory", "build_http_client_factory"]


def build_http_client_factory() -> McpHttpClientFactory:
    """Die httpx-Fabrik, die das SDK je Verbindung aufruft.

    Ohne Block ist das der SDK-Standard, unverändert. Mit Block ergänzt die
    Fabrik die ``Authorization``-Kopfzeile und lässt alles andere durch, was das
    SDK mitgibt (eigene Kopfzeilen, Timeout, ``auth``).

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
    if not block:
        return create_mcp_http_client

    def factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        return create_mcp_http_client(
            headers={**(headers or {}), "Authorization": f"Bearer {block}"},
            timeout=timeout,
            auth=auth,
        )

    return factory
