"""Ist der Zugangsblock dieses Zuges eine angemeldete Person? (Paket 10, Kurzaudit 2026-10-10)

Bis Paket 10 prüfte ``auth.has_personal_auth`` nur die FORM des Blocks. Wer
``WLO-Access-Block: wlo2.x`` mitschickte, bekam im Agent-Modus die vollen Deckel
(A-1), und ein abgelaufener Block bot weiter Schreibwerkzeuge an (A-3). Jetzt fragt
jeder Zug mit persönlich aussehendem Block einmal ``wlo_auth_status`` — am primären
Server, dem einzigen, der den Block bekommt (``transport._client_fabrik``). Das
Ergebnis gilt je Fingerabdruck :data:`POSITIV_S` (Person) bzw. :data:`NEGATIV_S`
(sonst): nicht jeder Zug kostet einen Rundlauf, und ein Ausfall hängt nicht nach.

* ``mode: user`` und ``authenticated: true`` → Person. Ihre Kennung (ein Streuwert
  der ``authority``) bindet eine Abnahme (S-1): jeder Ticket-Tausch verschlüsselt
  den Block neu, derselbe Mensch hätte sonst zwischen Vorschau und „Ja“ einen
  anderen Fingerabdruck.
* abgewiesen (401/403 oder ``authenticated: false``) → der Block fällt für den Rest
  des Zuges weg, der Zug läuft anonym weiter, und das Widget erfährt es (A-3).
* keine Antwort → keine Person (Deckel und Schreibrecht wie anonym), der Block bleibt.

Den Block protokolliert dieses Modul nie; der Cache hält nur Fingerabdrücke.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from boerdi.services.mcp import auth, transport

logger = logging.getLogger(__name__)

#: So lange gilt eine bestätigte Person, ohne neu zu fragen.
POSITIV_S = 300.0
#: So lange gilt „keine Person“ oder „abgewiesen“ — kurz, damit ein Ausfall nachgibt.
NEGATIV_S = 30.0
#: Frist der Prüfung — sie steht vor jedem Zug mit Block, länger warten hieße hängen.
FRIST_S = 5.0
#: Mehr Fingerabdrücke merkt sich der Prozess nicht; darüber verdrängt er (Paket 19, N-10):
#: zuerst negative Einträge, dann die am längsten unbenutzten.
HOECHSTENS = 1024
#: Eigene Obergrenze für „keine Person“/„abgewiesen“ — jeder erfundene ``wlo…``-Block legt einen
#: solchen Eintrag an; sie dürfen die bestätigten Personen nicht hinausdrängen.
HOECHSTENS_NEGATIV = 256


@dataclass(frozen=True)
class Befund:
    person: bool
    kennung: str = ""
    abgelehnt: bool = False


#: Fingerabdruck → (gültig bis, Befund), in LRU-Reihenfolge (zuletzt benutzt am Ende).
_cache: OrderedDict[str, tuple[float, Befund]] = OrderedDict()


def _merken(fingerabdruck: str, eintrag: tuple[float, Befund]) -> None:
    _cache[fingerabdruck] = eintrag
    _cache.move_to_end(fingerabdruck)
    _verdraengen()


def _verdraengen() -> None:
    """Bis Paket 19 ``_cache.clear()`` bei voller Liste — das warf auch alle bestätigten
    Personen hinaus (N-10). Jetzt: negative über ihrer eigenen Grenze, dann bei voller Liste
    erst der älteste negative, sonst der älteste überhaupt."""
    negative = [k for k, (_, b) in _cache.items() if not b.person]
    while len(negative) > HOECHSTENS_NEGATIV:
        _cache.pop(negative.pop(0), None)
    while len(_cache) > HOECHSTENS:
        opfer = negative.pop(0) if negative else next(iter(_cache))
        _cache.pop(opfer, None)


async def bestaetige_anmeldung() -> Befund:
    """Einmal je Zug, gleich nach ``api/turn_auth.adopt_turn_auth_block``."""
    if not auth.zug_block_wirkt_persoenlich():
        return Befund(person=False)
    fingerabdruck = auth.caller_fingerprint()
    jetzt = time.monotonic()
    gemerkt = _cache.get(fingerabdruck)
    if gemerkt is not None and gemerkt[0] > jetzt:
        befund = gemerkt[1]
        _cache.move_to_end(fingerabdruck)
    else:
        befund = await _fragen()
        _merken(fingerabdruck, (jetzt + (POSITIV_S if befund.person else NEGATIV_S), befund))
    if befund.abgelehnt:
        _verwerfen()
    else:
        auth.setze_bestaetigung(person=befund.person, kennung=befund.kennung)
    return befund


async def _fragen() -> Befund:
    try:
        async with asyncio.timeout(FRIST_S):
            antwort = await transport.call_tool("wlo_auth_status", {})
    except TimeoutError:
        antwort = {"error": {"kind": "timeout"}}
    return _auswerten(antwort)


def _auswerten(antwort: dict[str, Any]) -> Befund:
    fehler = antwort.get("error")
    if fehler:
        if fehler.get("kind") == "auth":
            return Befund(person=False, abgelehnt=True)
        logger.warning("Anmeldung nicht prüfbar (%s) — der Zug gilt als anonym",
                       fehler.get("kind") or "unbekannt")
        return Befund(person=False)
    stand = (antwort.get("result") or {}).get("structuredContent") or {}
    if stand.get("mode") in ("user", "service") and stand.get("authenticated") is False:
        return Befund(person=False, abgelehnt=True)
    authority = stand.get("authority")
    if stand.get("mode") == "user" and stand.get("authenticated") is True and authority:
        streuwert = hashlib.sha256(str(authority).encode("utf-8")).hexdigest()[:16]
        return Befund(person=True, kennung=f"p:{streuwert}")
    return Befund(person=False)


def markiere_abgelehnt() -> None:
    """Ein Werkzeug bekam 401/403 (Transport-Art ``auth``): wie eine abgewiesene
    Prüfung — aber nur für den Block des Zuges. Weist der Server den Block der
    ANLAGE ab, ist das ein Fehler des Betriebs, nicht der Person am Widget."""
    if not auth.hat_zug_block():
        logger.warning("Der Zugangsblock der Anlage wird abgewiesen (MCP_AUTH_TOKEN prüfen)")
        return
    _merken(auth.caller_fingerprint(),
            (time.monotonic() + NEGATIV_S, Befund(person=False, abgelehnt=True)))
    _verwerfen()


def _verwerfen() -> None:
    auth.verwirf_zug_block()
    logger.info("Zugangsblock abgewiesen — der Zug läuft ohne ihn weiter")


def abgelehnt_in_diesem_zug() -> bool:
    """Wurde in diesem Zug der Block der Person abgewiesen? (Signal an das Widget)"""
    return auth.zug_block_abgewiesen()
