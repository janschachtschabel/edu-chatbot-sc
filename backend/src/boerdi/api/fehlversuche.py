"""Fehlgeschlagene Studio-Prüfungen je IP zählen (Paket 19, Audit 2026-10-31 H-3).

Das Studio-Cookie ist eine reine Funktion des Passworts (``studio_auth.studio_token``), und
``X-Studio-Key`` ist ein festes Geheimnis. Gedrosselt war bis hier nur der Login; Cookie und
Schlüssel ließen sich an jeder Verwaltungsroute ungebremst raten.

Die Regel, an allen Prüfstellen gleich (Studio-Proxy, ``GET /studio/api/auth/session``,
``require_studio_key``, ``require_agent_caller``, ``ist_interner_zug``):

* Gezählt wird nur ein **vorgelegter** und **falscher** Wert, höchstens einmal je Anfrage
  (:func:`zaehle_fehlversuch`): wer nichts mitschickt, rät nicht — der erste Besuch im Studio
  fragt ohne Cookie —, und ein Zug prüft den Schlüssel an mehreren Stellen.
* Ist die Grenze erreicht, antwortet jede Prüfung mit einem vorgelegten Wert 429 — auch eine
  richtige (:func:`gesperrt`). Sonst verriete 429 gegen 200 den Treffer, und die Bremse wäre
  keine.

Review-Nachbesserungen (Paket 19): derselbe falsche Wert zählt je IP nur einmal in der Minute
(ein veraltetes Cookie, oft neu geladen, sperrt niemanden aus); eine Sperre meldet sich als
gedrosselte WARNING (ohne IP, ohne Wert) und im Zähler ``boerdi_studio_auth_failures_total``;
ist der Speicher nicht erreichbar, wird nicht gezählt (fail-open), der Vergleich selbst bleibt.
Bewusst KEIN anlagenweiter Deckel: Dritte könnten damit alle aussperren.

Der Zähler liegt im Speicher des slowapi-Limiters (``RATE_LIMIT_STORAGE_URI``): im Cluster über
Valkey geteilt, sonst je Prozess. Schlüssel ist :func:`ratelimit.drossel_schluessel` (IPv6 als
/64). Feste Grenze wie am Login — eine Untergrenze gegen Raten, kein Stellknopf.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Final

from limits import parse
from starlette.requests import HTTPConnection

from boerdi.api.ratelimit import drossel_schluessel, limiter
from boerdi.obs import metrics
from boerdi.obs.drossel import gedrosselt

logger = logging.getLogger(__name__)

#: Fehlversuche je IP und Minute; danach 429 — dieselbe Zahl wie am Login (``studio_bff``).
GRENZE: Final = 10
_FENSTER = parse(f"{GRENZE}/minute")
_BEREICH: Final = "studio-fehlversuch"
#: Derselbe falsche Wert zählt je IP einmal je Minute (Review, Punkt 3).
_WERT_FENSTER = parse("1/minute")
_BEREICH_WERT: Final = "studio-fehlversuch-wert"
#: Merker im ASGI-Scope: diese Anfrage hat ihren Fehlversuch schon gezählt.
_GEZAEHLT: Final = "boerdi.fehlversuch_gezaehlt"
RETRY_AFTER_S: Final = 60
ZU_VIELE: Final = "Too many failed studio authentication attempts — try again later"


def _schluessel(anfrage: HTTPConnection) -> str:
    return drossel_schluessel(anfrage) or "unbekannt"


def _zaehler_aus(fehler: Exception) -> None:
    metrics.STUDIO_FEHLVERSUCHE.labels("zaehler_aus").inc()
    gedrosselt(logger, logging.WARNING, "studio-fehlversuch:speicher", 60.0,
               "Studio-Fehlversuche nicht zählbar (%s) — die Bremse ist aus, der Vergleich "
               "bleibt", type(fehler).__name__)


def gesperrt(anfrage: HTTPConnection) -> bool:
    """Hat diese IP ihre Fehlversuche aufgebraucht? Prüft, ohne zu zählen."""
    if not limiter.enabled:
        return False
    try:
        frei = limiter.limiter.test(_FENSTER, _BEREICH, _schluessel(anfrage))
    except Exception as fehler:  # Valkey weg: fail-open beim Zählen, nie beim Vergleich
        _zaehler_aus(fehler)
        return False
    if not frei:
        metrics.STUDIO_FEHLVERSUCHE.labels("gesperrt").inc()
        gedrosselt(logger, logging.WARNING, "studio-fehlversuch:sperre", 60.0,
                   "Studio-Anmeldung: Fehlversuch-Grenze (%d/Minute) einer Adresse erreicht — "
                   "429 bis zum Ablauf des Fensters", GRENZE)
    return not frei


def zaehle_fehlversuch(anfrage: HTTPConnection, wert: str) -> None:
    """Einen Fehlversuch mit dem falschen ``wert`` buchen — höchstens einmal je Anfrage, und
    derselbe Wert je IP höchstens einmal je Minute. Vom Wert bleibt nur ein Streuwert."""
    if not limiter.enabled or anfrage.scope.get(_GEZAEHLT):
        return
    anfrage.scope[_GEZAEHLT] = True
    netz = _schluessel(anfrage)
    streuwert = hashlib.sha256(wert.encode("utf-8", "replace")).hexdigest()[:16]
    try:
        if not limiter.limiter.hit(_WERT_FENSTER, _BEREICH_WERT, netz, streuwert):
            return  # derselbe Wert in dieser Minute schon gezählt
        limiter.limiter.hit(_FENSTER, _BEREICH, netz)
    except Exception as fehler:
        _zaehler_aus(fehler)
        return
    metrics.STUDIO_FEHLVERSUCHE.labels("fehlversuch").inc()


def zu_viele() -> tuple[int, str]:
    """Die Antwort für eine gesperrte IP, in der Form von ``studio_auth.authorize``."""
    return (429, ZU_VIELE)
