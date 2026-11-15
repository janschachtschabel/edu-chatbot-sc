"""``POST /api/auth/session`` — der Sitzungs-Tausch über unser Backend (Plan 2026-11-15, SA-16).

Für den Browser ist die Route nur über die eigene Ingress-Regel auf dem Host des Repositorys
erreichbar (Helm-Werte ``sessionIngress``): Nur dort schickt er das Sitzungs-Cookie mit. Die Regel
leitet den Pfad unverändert weiter; das Backend nimmt ihn unter
:data:`PFAD_AM_REPOSITORY` an (dieselbe Funktion, nicht im API-Dokument). So braucht die Regel
kein ``rewrite-target`` — das stellte bei ingress-nginx alle Pfade des Repository-Hosts auf
Regex um. ``MCP_SESSION_URL`` nennt dem Widget die Adresse; ohne sie gibt es den Weg nicht.

Die Route prüft, was ein Browser nicht fälschen kann und was wir weiterreichen würden:

* **``Host``** muss der Host aus ``MCP_SESSION_URL`` sein — sonst 404. Über den Host des Chats
  ist die Route damit nicht zu erreichen (dort kämen ohnehin keine Repository-Cookies an).
* **``Origin``** muss die Herkunft aus ``MCP_SESSION_URL`` sein. Eine fremde Seite kommt nicht an
  die Cookies, aber an diese Route; ohne die Prüfung verbrauchte sie das Budget des Backends am
  MCP-Server.
* **``Content-Type: application/json``** — ein einfaches Formular einer fremden Seite schickt das
  nicht, ohne eine Vorabfrage auszulösen.
* **genau eine brauchbare ``JSESSIONID``**; sonst wird der MCP gar nicht erst gefragt.

``Origin`` und ``Content-Type`` sind außerhalb eines Browsers frei wählbar, und die Host-Prüfung
ist Tiefenverteidigung, keine Grenze. Gegen das Leeren des Budgets am MCP stehen eine Grenze
je Adresse (:func:`grenze_je_adresse`, für beide Pfade gemeinsam) und eine Gesamtgrenze für die
ganze Anlage (``services/mcp/sitzung_tausch``).

Der Rumpf wird nicht gelesen. Das Ergebnis geht in der Form der Tauschstelle zurück, damit das
Widget (``session/session-login.ts``) beide Wege gleich lesen kann.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from boerdi.api.ratelimit import _limit_disabled, limiter, peer_ip
from boerdi.domain.mcp_herkunft import mcp_herkunft
from boerdi.services.mcp import sitzung_tausch
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)
public_router = APIRouter(prefix="/api/auth", tags=["auth"])
#: Der Pfad am Repository-Host, wie ihn die Ingress-Regel unverändert weiterreicht. Vorgabe der
#: Helm-Werte; ein anderer Pfad braucht dort ein ``rewrite-target`` auf ``/api/auth/session``.
PFAD_AM_REPOSITORY = "/edu-sharing/services/boerdi/auth/session"
repository_router = APIRouter(tags=["auth"])
#: Je Adresse (bzw. IPv6-/64) und Minute, für beide Pfade gemeinsam (:func:`grenze_je_adresse`).
#: Eine Person tauscht beim Laden einmal, bei einem Wechsel der Person noch einmal.
#: Eng, solange die Gesamtgrenze eng ist: Eine Adresse nimmt dann höchstens die Hälfte.
GRENZE_JE_ADRESSE_ENG = "10/minute"
#: Weit (Gesamtgrenze über 20, also mit Client-Schlüssel und MCP ab 1.3.0): Eine Schulklasse hinter
#: einem Router lädt auf einmal (wie die Chat-Drossel, Paket 18F).
GRENZE_JE_ADRESSE_WEIT = "60/minute"


def grenze_je_adresse() -> str:
    """Die Grenze je Adresse — weit nur, wenn die Gesamtgrenze weit ist."""
    weit = sitzung_tausch.gesamt_je_minute() > sitzung_tausch.OBERGRENZE_OHNE_SCHLUESSEL
    return GRENZE_JE_ADRESSE_WEIT if weit else GRENZE_JE_ADRESSE_ENG


_KEIN_SPEICHER = {"Cache-Control": "no-store"}
_NICHT_EINGERICHTET = {"error": "Die Übernahme einer WLO-Sitzung ist nicht eingerichtet."}


def _antwort(status: int, rumpf: dict) -> JSONResponse:
    return JSONResponse(rumpf, status_code=status, headers=_KEIN_SPEICHER)


def _host(wert: str | None) -> str:
    """Der Name aus einem ``Host``-Kopf, ohne Port, klein."""
    roh = (wert or "").strip().lower()
    if roh.startswith("["):  # IPv6 in Klammern
        return roh.split("]")[0] + "]"
    return roh.split(":")[0]


@public_router.post("/session")
@repository_router.post(PFAD_AM_REPOSITORY, include_in_schema=False)
@limiter.shared_limit(grenze_je_adresse, scope="sitzung-tausch", exempt_when=_limit_disabled)
async def sitzung_tauschen(request: Request, response: Response) -> JSONResponse:
    """Die Repository-Sitzung des Browsers gegen einen Zugangsblock tauschen (über den MCP)."""
    herkunft = mcp_herkunft(get_settings().mcp_session_url)
    if not herkunft or _host(request.headers.get("host")) != _host(urlparse(herkunft).netloc):
        return _antwort(404, _NICHT_EINGERICHTET)
    if (request.headers.get("origin") or "").strip().rstrip("/").lower() != herkunft.lower():
        return _antwort(403, {"error": "Diese Seite darf keine Anmeldung übernehmen.",
                              "code": "origin_not_allowed"})
    art = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    if art != "application/json":
        return _antwort(415, {"error": "Erwartet wird Content-Type: application/json."})
    cookies = sitzung_tausch.sitzungs_cookies(request.headers.get("cookie"))
    if cookies.zwei_sitzungen:
        # Ein Betriebssignal (der MCP schreibt es ebenso): setzt das Repository selbst ein zweites
        # Sitzungs-Cookie, scheitern alle — ohne diese Zeile fiele das niemandem auf.
        logger.warning("Sitzungs-Tausch: mehr als eine JSESSIONID in der Anfrage")
        return _antwort(400, {"error": "Es kamen zwei verschiedene WLO-Sitzungen mit."})
    if not cookies.kopf:
        return _antwort(400, {"error": "Es kam keine WLO-Sitzung mit."})
    ergebnis = await sitzung_tausch.weiterreichen(cookies.kopf, herkunft, peer_ip(request))
    return _antwort(ergebnis.status, ergebnis.rumpf)
