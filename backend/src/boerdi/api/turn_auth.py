"""Der Zugangsblock einer Anfrage (C5-a), für alle Endpunkte, die einen MCP rufen.

Herausgezogen aus ``api/chat.py``, unverändert im Verhalten. Anlass ist der
zweite Verbraucher (``api/agent.py``). Dass diese Funktion **nur einmal**
existiert, ist kein Ordnungssinn: sie *löscht* den ContextVar auch im Normalfall
„keine Kopfzeile". Eine zweite Fassung, die das vergisst, ließe eine Anfrage an
der Anmeldung der vorigen hängen — die schwerste denkbare Verwechslung.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, Security, status

from boerdi.api import fehlversuche
from boerdi.api.deps import (
    expected_studio_key,
    require_studio_key,
    schluessel_passt,
    studio_key_header,
)
from boerdi.services.llm_auth import setze_llm_schluessel
from boerdi.services.mcp.anmeldung import bestaetige_anmeldung
from boerdi.services.mcp.auth import is_personal_block, set_turn_auth_block
from boerdi.settings import get_settings, studio_schluessel_zu_kurz

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


def ist_interner_zug(request: Request) -> bool:
    """Fragt die Anlage selbst? Über den Studio-Proxy (Studio-Proben, Verlauf) oder mit gültigem
    Studio-Schlüssel (Evaluation, Lasttest). Daran hängen die Diagnose für dieses Publikum
    (Paket 18C/D: Debug-Block und Zugakte) und die Buchung auf ``B_API_KEY`` — der
    Proxy-Kopf fehlt solchen Zügen, und der Studio-Proxy reicht ``Authorization`` nie durch
    (Review-Runde 3, Befund 1).

    Bei offenem Tor (``BOERDI_ALLOW_OPEN_ADMIN`` ohne Passwort) kommt jeder durch den Proxy.
    Ist zugleich ein Schlüssel gesetzt, setzt der Proxy ihn nicht ein
    (``studio_proxy._injectable_key``) — dann ist der Durchgang keine Freigabe (Review Phase 1).
    Den Entwicklungsmodus zählt erst :func:`darf_diagnose` — hier hängt die Buchung daran
    (Review Phase 3).

    Im reinen Entwicklungsmodus (offenes Tor, KEIN Schlüssel) zählt jeder Zug über den Proxy als
    intern und bucht auf ``B_API_KEY`` — auch mit ``B_API_KEY_MODE=forward``. Gewollt: die
    Chat-Probe im Studio läuft lokal ohne eigenen Schlüssel. Auf einem erreichbaren Server hätte
    dieser Modus ohnehin das ganze Studio offen (Paket 18G, G-E2)."""
    from boerdi.api.studio_auth import gate_is_open
    from boerdi.api.studio_proxy import ueber_studio  # zirkulär: studio_proxy → deps

    erwartet = expected_studio_key()
    if ueber_studio(request):
        # Ein zu kurzer Schlüssel ist gesetzt, nur unbrauchbar (Paket 19) — kein Entwicklungsmodus.
        return not (gate_is_open() and (erwartet or studio_schluessel_zu_kurz()))
    gegeben = (request.headers.get("x-studio-key") or "").strip()
    if not gegeben:
        return False
    # Paket 19 (H-3): auch hier ein Orakel (Diagnose im Chat) — ein falscher Schlüssel zählt als
    # Fehlversuch, einmal je Anfrage. Eine gesperrte IP bekommt 429, laut statt still (Review,
    # Punkt 5): mit ``False`` sähen Eval und Lasttest ein irreführendes 422 oder 401.
    if fehlversuche.gesperrt(request):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=fehlversuche.ZU_VIELE,
            headers={"Retry-After": str(fehlversuche.RETRY_AFTER_S)},
        )
    # Beide Seiten ASCII, dann als Bytes (Review 2026-10-30): ``compare_digest`` warf bei einem
    # Nicht-ASCII-STUDIO_API_KEY — jeder Zug mit Kopfzeile wurde zum 500. Wie ``deps``: ein
    # solcher Schlüssel passt nie (die Startwarnung sagt es).
    if schluessel_passt(gegeben, erwartet):
        return True
    if erwartet:
        fehlversuche.zaehle_fehlversuch(request, gegeben)
    return False


def darf_diagnose(request: Request) -> bool:
    """Bekommt diese Anfrage Diagnose (Debug-Block, Zugakte im Verlauf)?

    Wie :func:`ist_interner_zug`, dazu der reine Entwicklungsmodus (``BOERDI_ALLOW_OPEN_ADMIN``
    ohne Schlüssel): dort ist ohnehin alles offen (``require_studio_key``), und der Lasttest
    behält lokal seine Kennzahlen (Plan R4). Getrennt von der Buchung (Review Phase 3): sonst
    buchte ein so eingerichteter Betrieb mit ``B_API_KEY_MODE=forward`` jeden anonymen Zug auf
    den gemeinsamen Schlüssel."""
    if ist_interner_zug(request):
        return True
    return (not expected_studio_key() and not studio_schluessel_zu_kurz()
            and get_settings().allow_open_admin)


def uebernimm_llm_schluessel(request: Request, *, pflicht: bool = True) -> None:
    """Den b-api-Schlüssel des Zuges aus ``Authorization`` übernehmen (Paket 17).

    Wie der Zugangsblock **immer** gerufen, auch ohne Kopfzeile — ein leerer Wert löscht.
    Ein unbrauchbarer Wert wird gemeldet, nie ausgegeben. Was dann gilt, sagt
    ``B_API_KEY_MODE`` (AB2): ``auto`` nimmt ``B_API_KEY``; ``static`` liest den Kopf gar
    nicht; ``forward`` weist einen Zug ohne gültigen Schlüssel mit 401 ab, sofern das LLM
    über die b-api läuft — außer Züge der Anlage selbst (:func:`ist_interner_zug`).
    ``pflicht=False`` für Auskünfte, die kein Zug sind. ``forward`` verlangt einen Schlüssel,
    es prüft ihn nicht: das tut die b-api (ungültig → 401 dort).
    """
    einst = get_settings()
    if einst.b_api_key_mode == "static":
        setze_llm_schluessel(None)
        return
    roh = request.headers.get("authorization")
    gilt = setze_llm_schluessel(roh)
    if not gilt and roh:
        logger.warning(
            "Kopfzeile Authorization vorgelegt, aber unbrauchbar (erwartet „Bearer "
            "<Schlüssel>“)."
        )
    if (not gilt and pflicht and einst.b_api_key_mode == "forward"
            and einst.llm_provider.startswith("b-api") and not ist_interner_zug(request)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="b-api key required: Authorization: Bearer <key> (B_API_KEY_MODE=forward)",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def uebernimm_zugang(request: Request) -> None:
    """Den Block übernehmen UND seine Echtheit prüfen (Paket 10, Kurzaudit A-1).

    Was ein Zug darf — Deckel, Schreibangebot, Abnahme —, hängt seither an einer
    Person, die der MCP-Server bestätigt hat; die Form allein reicht nicht mehr. Ein
    Rundlauf je Fingerabdruck und einige Minuten (``services/mcp/anmeldung``).

    Seit Paket 17 auch den b-api-Schlüssel des Zuges — beide Werte gehören zur Anfrage,
    und jeder Endpunkt, der einen Zug fährt, ruft genau diese Funktion.
    """
    uebernimm_llm_schluessel(request)
    adopt_turn_auth_block(request)
    await bestaetige_anmeldung()


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
    Person (``services/agent_write``). Deckel und Schreibmodus des Laufs hängen
    seit Paket 10 an der Bestätigung durch den Server (:func:`uebernimm_zugang`),
    nicht mehr an der Form.
    """
    if get_settings().agent_open:
        return
    if is_personal_block(request.headers.get(ACCESS_BLOCK_HEADER)):
        return
    await require_studio_key(request, x_studio_key)
