"""Den Sitzungs-Tausch an den MCP-Server weiterreichen (Plan 2026-11-15, SA-16).

Der Browser schickt das Sitzungs-Cookie des Repositorys nur an Adressen unter ``/edu-sharing``
auf dessen Host (``Path=/edu-sharing``, ``HttpOnly``). Eine eigene Ingress-Regel unseres Charts
(``sessionIngress``, wie beim md-editor) leitet genau einen Pfad dort auf dieses Backend; hier
geht der Tausch server-zu-server an ``POST /auth/session`` des MCP-Servers. So kann der MCP
bleiben, wo er ist, und der Betrieb des Chatbots steuert den Weg selbst.

Was durchgeht und was nicht:

* **hinaus:** genau eine ``JSESSIONID`` und höchstens ein ``INGRESSCOOKIE`` (Bindung an den
  Knoten des Repositorys), die geprüfte Herkunft, der Client-Schlüssel, die Adresse der Person
  (nur eine gültige IP); kein ``Authorization`` (edu-sharing sieht sonst die Sitzung nicht an).
  Zwei **verschiedene** Sitzungen in einer Anfrage weist schon die Route ab — der MCP tut das
  auch, aber nur, wenn er beide sieht; eine Nachbar-Subdomain könnte sonst wählen, wessen
  Sitzung gilt.
* **zurück:** nur die Felder des Vertrags (``ok``, ``block``, ``authority``, ``displayName``,
  ``error``, ``code``, ``retryAfter``) und nur die Status, die ein Urteil sind. Die Wartezeit
  reist im Rumpf (``retryAfter``); den Kopf ``Retry-After`` setzt die IP-Drossel des Backends an
  jeder Antwort selbst, und das Widget liest ohnehin zuerst den Rumpf.
* **nie:** ins Protokoll. Weder Cookie noch Block noch Kontoname; nur Status und Art eines
  Fehlers.

**Budget.** Ab MCP 1.3.0 zahlen Tausch und Abmelden mit einem vertrauten Client-Schlüssel
(``TRUSTED_CLIENT_KEYS`` am MCP) aus dessen Protokoll-Budget (3 × rpm je Minute, geteilt mit
``/mcp`` und ``/auth/status``); den Schutz vor vielen Sitzungen zählt der MCP dann je Adresse,
die wir im ``X-Forwarded-For`` nennen. Ohne Schlüssel zählt alles auf die Adresse dieses
Backends, im Topf ``API_RATE_LIMIT_RPM`` (Vorgabe 30 je Minute), geteilt mit dem Abmelden.
Darum gilt hier eine Gesamtgrenze (:func:`gesamtgrenze`): ``MCP_SESSION_EXCHANGE_RPM``, Vorgabe
20, über 20 nur mit Schlüssel. Weit wird sie nur auf ausdrücklichen Wunsch des Betriebs, weil das
Backend nicht sieht, ob der MCP den Schlüssel kennt (Review SA-17). Gezählt wird im gemeinsamen
Speicher der Drossel — im Cluster Valkey, also für alle
Repliken zusammen; gezählt wird nur, was wirklich zum MCP geht. Dazu drosselt die Route je
Adresse.

Den Ausfall-Schalter liest der Weiterreicher nur: Ein Ausfall des Tauschs soll nicht die
Werkzeuge des Chats sperren.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx
from limits import parse

from boerdi.api.ratelimit import limiter
from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services.mcp import schutz, transport
from boerdi.services.mcp.http_fabrik import client_schluessel_kopf
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Eine Sitzungs-Kennung, wie der MCP sie annimmt (``upstream-auth.ts``, ``SESSION_ID``):
#: Unsinn geht so gar nicht erst hinaus.
_SITZUNGS_WERT = re.compile(r"[A-Za-z0-9._-]{16,128}")
#: Die Knotenbindung des Repository-Ingress (mit ``|``). Leerraum, Anführungszeichen und
#: Steuerzeichen fallen durch.
_KNOTEN_WERT = re.compile(r"[A-Za-z0-9._|-]{1,200}")
#: Gesamtfrist des Abrufs samt Verbindung — kürzer als die des Widgets (10 s), damit es die
#: Antwort noch bekommt.
_FRIST_S = 8.0
#: Wartezeit, die das Widget genannt bekommt, wenn der MCP nicht zu erreichen war.
_WARTEZEIT_S = 10
#: Status, die ein Urteil der Tauschstelle sind. Alles andere ist für das Widget ``502``.
_URTEILE = frozenset({200, 400, 403, 404, 415, 429, 503})
#: Felder der Antwort mit ihrem Typ und ihrer Höchstlänge.
_FELDER: dict[str, tuple[type, int]] = {
    "ok": (bool, 0), "block": (str, 4096), "authority": (str, 200),
    "displayName": (str, 200), "error": (str, 300), "code": (str, 60), "retryAfter": (int, 0),
}
#: Höchstens so viele Tausche je Minute für die ganze Anlage ohne Client-Schlüssel: Vom Topf des
#: MCP (30 je Minute für Tausch und Abmelden) bleiben zehn für das Abmelden.
OBERGRENZE_OHNE_SCHLUESSEL = 20
_GESAMT_SCHLUESSEL = "sitzung-tausch:gesamt"


@dataclass
class TauschAntwort:
    """Was die Route dem Widget zurückgibt."""

    status: int
    rumpf: dict[str, Any]


@dataclass
class SitzungsCookies:
    """Die Cookies der Repository-Sitzung, so wie sie weitergehen."""

    kopf: str
    """Wert für den ``Cookie``-Kopf an den MCP; ``""`` ohne brauchbare Sitzung."""
    zwei_sitzungen: bool = False
    """Zwei verschiedene ``JSESSIONID`` in einer Anfrage — dann geht nichts weiter."""


def sitzungs_cookies(roh: str | None) -> SitzungsCookies:
    """Die Cookies der Repository-Sitzung aus dem ``Cookie``-Kopf des Browsers."""
    sitzungen: list[str] = []
    knoten = ""
    for teil in (roh or "").split(";"):
        name, sep, wert = teil.strip().partition("=")
        if not sep:
            continue
        if name == "JSESSIONID" and _SITZUNGS_WERT.fullmatch(wert) and wert not in sitzungen:
            sitzungen.append(wert)
        elif name == "INGRESSCOOKIE" and _KNOTEN_WERT.fullmatch(wert) and not knoten:
            # Das erste, wie es auch der MCP nimmt (``upstream-auth.ts``).
            knoten = wert
    if len(sitzungen) > 1:
        return SitzungsCookies("", zwei_sitzungen=True)
    if not sitzungen:
        return SitzungsCookies("")
    kopf = f"JSESSIONID={sitzungen[0]}" + (f"; INGRESSCOOKIE={knoten}" if knoten else "")
    return SitzungsCookies(kopf)


#: Wann zuletzt „Gesamtgrenze erreicht“ ins Protokoll ging — einmal je Minute genügt, sonst ließe
#: sich das Protokoll über viele Adressen fluten.
_letzte_warnung = 0.0


def gesamt_je_minute() -> int:
    """Tausche je Minute für die ganze Anlage: ``MCP_SESSION_EXCHANGE_RPM``, ohne Client-Schlüssel
    höchstens :data:`OBERGRENZE_OHNE_SCHLUESSEL`."""
    wert = get_settings().mcp_session_exchange_rpm
    return wert if client_schluessel_kopf() else min(wert, OBERGRENZE_OHNE_SCHLUESSEL)


def gesamtgrenze() -> str:
    """Die Gesamtgrenze als Angabe für die Drossel."""
    return f"{gesamt_je_minute()}/minute"


def _gesamt_warten_s(angabe: str) -> int:
    """``0``, wenn ein Tausch jetzt geht (und zählt ihn); sonst die Sekunden bis zum nächsten
    Fenster. Im Speicher der Drossel, damit alle Repliken einen Zähler teilen."""
    grenze = parse(angabe)
    if limiter.limiter.hit(grenze, _GESAMT_SCHLUESSEL):
        return 0
    rest = limiter.limiter.get_window_stats(grenze, _GESAMT_SCHLUESSEL).reset_time - time.time()
    return max(1, math.ceil(rest))


def _gueltige_adresse(adresse: str) -> str:
    """Eine IP-Adresse, wie der MCP sie zählt — sonst ``""`` (ein Name oder Fremdes geht nicht
    als Kopfwert hinaus)."""
    try:
        return str(ipaddress.ip_address((adresse or "").strip()))
    except ValueError:
        return ""


def _gefiltert(rumpf: Any) -> dict[str, Any]:
    if not isinstance(rumpf, dict):
        return {}
    aus: dict[str, Any] = {}
    for name, (art, laenge) in _FELDER.items():
        wert = rumpf.get(name)
        # ``bool`` ist eine Unterart von ``int``: ``retryAfter: true`` soll nicht durchgehen.
        if not isinstance(wert, art) or (art is int and isinstance(wert, bool)):
            continue
        aus[name] = wert[:laenge] if isinstance(wert, str) else wert
    return aus


async def weiterreichen(cookies: str, herkunft: str, adresse: str) -> TauschAntwort:
    """Den Tausch an ``POST /auth/session`` des primären MCP-Servers reichen.

    ``cookies`` aus :func:`sitzungs_cookies` (``kopf``), ``herkunft`` die geprüfte Herkunft der
    Seite, ``adresse`` die der Person (für das Adress-Budget des MCP, wenn er ihr glaubt).
    """
    url = transport.resolve_mcp_url()
    nicht_erreichbar = TauschAntwort(
        503, {"error": "Die WLO-Anmeldung ist gerade nicht erreichbar.",
              "code": "upstream_unreachable", "retryAfter": _WARTEZEIT_S})
    if schutz.ist_offen(url):
        return nicht_erreichbar
    grenze = gesamtgrenze()
    warte = _gesamt_warten_s(grenze)
    if warte:
        global _letzte_warnung
        if time.monotonic() - _letzte_warnung >= 60.0:
            _letzte_warnung = time.monotonic()
            logger.warning("Sitzungs-Tausch: Gesamtgrenze erreicht (%s)", grenze)
        return TauschAntwort(429, {"error": "Gerade melden sich viele an. Gleich noch einmal.",
                                   "code": "rate_limited", "retryAfter": warte})
    koepfe = {**ausgehende_koepfe(), **client_schluessel_kopf(),
              "Content-Type": "application/json", "Origin": herkunft, "Cookie": cookies}
    # Ein einziger Eintrag: Was der Browser selbst behauptet hat, geht nicht weiter. Der MCP liest
    # den Eintrag vor dem seines eigenen Proxys (``TRUST_PROXY``), also diesen.
    if ip := _gueltige_adresse(adresse):
        koepfe["X-Forwarded-For"] = ip
    try:
        async with asyncio.timeout(_FRIST_S), httpx.AsyncClient(
                timeout=httpx.Timeout(_FRIST_S, connect=get_settings().mcp_connect_timeout_s),
                follow_redirects=False) as client:
            antwort = await client.post(f"{schutz.wurzel(url)}/auth/session",
                                        headers=koepfe, content=b"{}")
    except (httpx.HTTPError, TimeoutError) as exc:
        logger.warning("Sitzungs-Tausch: MCP nicht erreichbar (%s)", type(exc).__name__)
        return nicht_erreichbar
    status = antwort.status_code
    if status not in _URTEILE:
        logger.warning("Sitzungs-Tausch: unerwartete Antwort (HTTP %s)", status)
        return TauschAntwort(502, {"error": "Die WLO-Anmeldung hat unerwartet geantwortet."})
    try:
        rumpf = antwort.json()
    except ValueError:
        logger.warning("Sitzungs-Tausch: Antwort des MCP ohne JSON (HTTP %s)", status)
        return TauschAntwort(502, {"error": "Die WLO-Anmeldung hat unerwartet geantwortet."})
    if status != 200:
        logger.info("Sitzungs-Tausch: abgelehnt (HTTP %s)", status)
    return TauschAntwort(status, _gefiltert(rumpf))
