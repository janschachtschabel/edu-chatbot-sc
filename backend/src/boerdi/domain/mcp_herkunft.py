"""Die Herkunft des MCP-Servers, an dem sich das Widget im Browser anmeldet (C5-c2).

Zwei Leser: das öffentliche Widget-Bündel (``api/config``, Feld ``mcp_auth_base``) und
die CSP der Studio-Seite (``api/studio_static``, Paket 8) — die Vorschau dort spricht
den MCP-Server direkt an (Entdeckung, Registrierung, Code-Tausch). EINE Funktion, damit
Bündel und Regel nie verschiedene Herkünfte nennen.
"""

from __future__ import annotations

from urllib.parse import urlparse


def mcp_herkunft(url: str | None) -> str:
    """``scheme://host[:port]`` von ``url``; leer bei fehlender oder unbrauchbarer Angabe.

    Nur die Herkunft: der Werkzeug-Pfad (``/mcp``) gehört nicht dazu — die
    Entdeckungs-Dokumente liegen unter ``/.well-known/…`` an der Wurzel. Aus Host und
    Port gebaut, nicht aus ``netloc``: das trüge ``nutzer:geheim@`` ins öffentliche
    Widget-Bündel (Paket 9, Review Paket 7 MINOR 21).
    """
    roh = (url or "").strip()
    if not roh:
        return ""
    teile = urlparse(roh)
    try:
        port = teile.port
    except ValueError:  # kein Port zwischen 0 und 65535
        return ""
    host = teile.hostname
    if teile.scheme not in ("http", "https") or not host:
        return ""
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"{teile.scheme}://{host}" + (f":{port}" if port is not None else "")
