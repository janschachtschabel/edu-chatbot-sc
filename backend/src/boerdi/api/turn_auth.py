"""Der Zugangsblock einer Anfrage (C5-a), für alle Endpunkte, die einen MCP rufen.

Herausgezogen aus ``api/chat.py``, unverändert im Verhalten. Anlass ist der
zweite Verbraucher (``api/agent.py``). Dass diese Funktion **nur einmal**
existiert, ist kein Ordnungssinn: sie *löscht* den ContextVar auch im Normalfall
„keine Kopfzeile". Eine zweite Fassung, die das vergisst, ließe eine Anfrage an
der Anmeldung der vorigen hängen — die schwerste denkbare Verwechslung.
"""

from __future__ import annotations

import logging

from fastapi import Request, Security

from boerdi.api.deps import require_studio_key, studio_key_header
from boerdi.services.mcp.auth import is_personal_block, set_turn_auth_block
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

# Kopfzeile, über die ein Gastgeber den Zugangsblock der angemeldeten Person
# mitschickt. **Nicht** ``Authorization``: die Kopfzeile bedeutet dort „berechtige
# mich gegenüber DIESEM Server", der Block gilt aber dem MCP-Server dahinter.
#
# Bewusst NICHT als ``Header()``-Parameter deklariert: das trüge sie in das
# eingefrorene OpenAPI-Dokument ein. Dieselbe Naht nutzt schon
# ``Accept-Language`` (C1-e1). Preis: sie steht nicht in ``/docs``.
ACCESS_BLOCK_HEADER = "WLO-Access-Block"


def adopt_turn_auth_block(request: Request) -> None:
    """Übernimm den Zugangsblock dieser Anfrage aus der Kopfzeile.

    Wird **immer** gerufen, auch ohne Kopfzeile: der ``ContextVar`` überlebt die
    Task, und eine Anfrage darf niemals an der Anmeldung der vorigen hängen. Der
    unbenutzbare Fall wird gemeldet — ohne den Wert, der ein WLO-Passwort
    verschlüsselt und damit selbst ein Geheimnis ist.
    """
    roh = request.headers.get(ACCESS_BLOCK_HEADER)
    if not set_turn_auth_block(roh) and roh:
        logger.warning(
            "Kopfzeile %s vorgelegt, aber unbrauchbar (Form oder Länge) — die "
            "Anfrage läuft ohne persönliche Anmeldung weiter.",
            ACCESS_BLOCK_HEADER,
        )


async def require_agent_caller(
    request: Request,
    x_studio_key: str | None = Security(studio_key_header),
) -> None:
    """Wer darf einen Agenten-Lauf auslösen? (Nutzer-Entscheid 2026-08-12)

    Vorher hing der Endpunkt am Studio-Schlüssel, also am **Admin**-Schlüssel.
    In einem Browser-Plugin hätte der nichts zu suchen: wer es installiert,
    könnte ihn herauslesen und danach die ganze Anlage verwalten. Der normale
    Weg herein ist deshalb die Anmeldung der Person, nicht der Admin-Schlüssel.

    Drei Wege, in dieser Reihenfolge geprüft:

    1. ``AGENT_OPEN`` — der ausdrückliche Ausweg für Testläufe, Vorgabe **aus**.
    2. Eine **persönliche Anmeldung** in der Kopfzeile (der anonyme Block zählt
       nicht, :func:`is_personal_block`).
    3. Der **Studio-Schlüssel** — Server-zu-Server lief schon und bleibt gültig;
       er ist strikt mächtiger als eine persönliche Anmeldung, also kein Loch.

    **Weg 2 ist eine Form-, keine Echtheitsprüfung** — belegen kann den Block
    nur der MCP-Server. Er ist damit keine Kostenschranke, und deshalb liegt auf
    dem Endpunkt seit demselben Entscheid die **Drosselung** (``api/agent.py``).
    Die Rechte bleiben davon unberührt: was der Lauf auf WLO darf, entscheidet
    weiterhin allein der MCP-Server, und Schreiben verlangt ohnehin eine echte
    Person (``services/agent_write``).
    """
    if get_settings().agent_open:
        return
    if is_personal_block(request.headers.get(ACCESS_BLOCK_HEADER)):
        return
    await require_studio_key(x_studio_key)
