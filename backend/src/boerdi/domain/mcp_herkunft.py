"""Die Herkunft des MCP-Servers, an dem sich das Widget im Browser anmeldet (C5-c2).

Zwei Leser: das öffentliche Widget-Bündel (``api/config``, Feld ``mcp_auth_base``) und
die CSP der Studio-Seite (``api/studio_static``, Paket 8) — die Vorschau dort spricht
den MCP-Server direkt an (Entdeckung, Registrierung, Code-Tausch). EINE Funktion, damit
Bündel und Regel nie verschiedene Herkünfte nennen.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

#: Pfad des Sitzungs-Tauschs: die Wurzel des Repositorys, höchstens sechs schlichte Stufen,
#: dann ``/auth/session``. Dasselbe Muster prüft das Widget (``session/session-login.ts``).
_TAUSCH_PFAD = re.compile(r"/[A-Za-z0-9_-]{1,64}(?:/[A-Za-z0-9_-]{1,64}){0,6}/auth/session")
#: Die ganze Adresse, Zeichen für Zeichen: Schema, Host (Name oder IPv6 in Klammern), Port, Pfad.
#: Rückstrich, Leerraum und Steuerzeichen liest ein Browser anders als ``urlparse`` (der
#: Rückstrich wird dort zum Schrägstrich) — sie fallen hier durch, damit beide Riegel dasselbe
#: sehen (Review 2026-11-15).
_TAUSCH_ADRESSE = re.compile(
    r"https?://(?:[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?|\[[0-9A-Fa-f:.]{2,45}\])"
    r"(?::[0-9]{1,5})?/[A-Za-z0-9_/-]{1,512}")


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
    try:
        teile = urlparse(roh)   # wirft bei ``[…]`` ohne gültige IPv6-Adresse
        port = teile.port
    except ValueError:  # kein Port zwischen 0 und 65535
        return ""
    host = teile.hostname
    if teile.scheme not in ("http", "https") or not host:
        return ""
    if ":" in host:  # IPv6
        host = f"[{host}]"
    return f"{teile.scheme}://{host}" + (f":{port}" if port is not None else "")


def sitzungs_adresse(url: str | None) -> str:
    """Die Adresse, unter der der MCP-Server die Sitzung einer Repository-Seite gegen einen
    Zugangsblock tauscht (Plan 2026-11-15) — geprüft und ohne Beiwerk; leer bei leerer Angabe.

    Der Pfad liegt auf dem Host des Repositorys (nur dorthin schickt der Browser das
    Sitzungs-Cookie), das Widget ruft ihn von einer Seite derselben Herkunft. Erlaubt ist
    deshalb nur ``scheme://host[:port]`` plus ein schlichter Pfad auf ``/auth/session``: keine
    Zugangsdaten, keine Abfrage, kein Anker, keine Kodierung. Alles andere ist ein Tippfehler
    oder ein Versuch, das Widget auf einen anderen Pfad der Seite zu lenken.

    Raises:
        ValueError: die Angabe ist nicht leer und passt nicht — der Start soll daran scheitern,
            statt den Weg still abzuschalten.
    """
    roh = (url or "").strip()
    if not roh:
        return ""
    fehler = ValueError(
        "MCP_SESSION_URL muss die Form scheme://host/<Wurzel des Repositorys>/…/auth/session "
        "haben, ohne Zugangsdaten, Abfrage oder Anker")
    herkunft = mcp_herkunft(roh)
    if not herkunft or not _TAUSCH_ADRESSE.fullmatch(roh):
        raise fehler
    teile = urlparse(roh)   # wirft hier nicht mehr: ``mcp_herkunft`` hat die Adresse gelesen
    if (teile.username or teile.password or teile.params or "?" in roh or "#" in roh
            or not _TAUSCH_PFAD.fullmatch(teile.path)):
        raise fehler
    return herkunft + teile.path
