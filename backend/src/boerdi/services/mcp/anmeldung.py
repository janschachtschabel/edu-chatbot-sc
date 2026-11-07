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

**Seit dem MCP-Stand 2026-11-07** (Plan Stabilität, CB-4/CB-7):

* gefragt wird ``GET /auth/status`` (eine Anfrage statt einer MCP-Sitzung); ein Server ohne den
  Endpunkt (404) bekommt wie bisher ``wlo_auth_status``;
* drei Ausgänge — **Person**, **abgelehnt**, **unklar**. *Unklar* (Frist, Netz, 429/5xx,
  Ausfall-Schalter, ``upstream: "unreachable"``; ohne das Feld ``authority: null``) mit einer
  Bestätigung derselben Person in den letzten
  ``AUTH_GRACE_S`` (30 min) gilt weiter als Person; ohne frühere Bestätigung anonym, aber nicht
  gemerkt — der nächste Zug fragt wieder;
* ``expiresAt`` (R1: Ticket- und Widget-Blöcke, 12 h) begrenzt, wie lange eine Bestätigung gilt,
  und geht ans Widget (``auth_expires_at``);
* nach einer 429 auf ``/auth/status`` wird ``Retry-After`` eingehalten — je Block beim
  Anmelde-Schutz (``too_many_logins``), für alle beim erschöpften Budget (``rate_limited``).

Den Block protokolliert dieses Modul nie; der Cache hält nur Fingerabdrücke.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from boerdi.services.mcp import anmelde_endpunkte, auth, transport
from boerdi.settings import get_settings

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
    #: Der Server konnte nicht prüfen (CB-4) — weder Person noch abgelehnt.
    unklar: bool = False
    #: ``time.monotonic()`` der Bestätigung durch den Server — Anfang der Gnadenfrist.
    bestaetigt_um: float = 0.0
    #: ``expiresAt`` des Blocks (R1), ISO — ``None``: läuft nicht ab.
    ablauf: str | None = None
    #: Nach einer 429 auf ``/auth/status``: so lange nicht neu fragen (``Retry-After``) — für
    #: alle Blöcke, wenn das Budget des Chatbots erschöpft ist (``rate_limited``).
    pause_s: float = 0.0
    pause_alle: bool = False


#: Fingerabdruck → (gültig bis, Befund), in LRU-Reihenfolge (zuletzt benutzt am Ende).
_cache: OrderedDict[str, tuple[float, Befund]] = OrderedDict()
#: Fingerabdruck → bis wann nach einer 429 nicht gefragt wird. Die Bestätigung im Speicher bleibt
#: davon unberührt — so trägt die Gnadenfrist durch die Pause.
_pause: dict[str, float] = {}
#: Schlüssel in :data:`_pause` für „alle Blöcke“ — das Budget des Chatbots ist erschöpft.
_ALLE = "*"


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


def ist_bestaetigte_person(block: str | None) -> bool:
    """Liegt für ``block`` eine bestätigte, noch gültige Person im Speicher? Fragt nie den
    Server und ändert nichts — für die Drosselung, die vor der Übernahme des Blocks entscheidet
    (Paket 19, M-4 / P19-E3). Ein erfundener oder abgelaufener Block ist keine Person."""
    if not auth.is_personal_block(block):
        return False
    gemerkt = _cache.get(auth.fingerabdruck(block))
    return gemerkt is not None and gemerkt[0] > time.monotonic() and gemerkt[1].person


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
        if max(_pause.get(fingerabdruck, 0.0), _pause.get(_ALLE, 0.0)) > jetzt:
            # Der Server hat eine Wartezeit genannt — nicht vorher fragen (Antwort des MCP-Teams
            # zu ``too_many_logins``: wer früher fragt, verbraucht nur sein Budget).
            befund = Befund(person=False, unklar=True)
        else:
            _pause.pop(fingerabdruck, None)
            befund = await _fragen()
            if befund.pause_s > 0:
                if len(_pause) >= HOECHSTENS:
                    _pause.clear()
                _pause[_ALLE if befund.pause_alle else fingerabdruck] = jetzt + befund.pause_s
        if befund.unklar:
            befund = _gnadenfrist(fingerabdruck, gemerkt, jetzt, befund)
        else:
            if befund.person:
                befund = replace(befund, bestaetigt_um=jetzt)
            _merken(fingerabdruck, (jetzt + _gueltig_s(befund), befund))
    if befund.abgelehnt:
        _verwerfen()
    else:
        auth.setze_bestaetigung(person=befund.person, kennung=befund.kennung)
        auth.merke_ablauf(befund.ablauf if befund.person else None)
        if befund.unklar:
            auth.merke_anmeldung_unklar()
    return befund


def _rest_bis_ablauf_s(ablauf: str | None) -> float | None:
    """Sekunden bis ``expiresAt`` — ``None`` ohne (lesbare) Angabe."""
    if not ablauf:
        return None
    try:
        return datetime.fromisoformat(ablauf.replace("Z", "+00:00")).timestamp() - time.time()
    except ValueError:
        return None


def _gueltig_s(befund: Befund) -> float:
    """Wie lange ein Befund ohne neue Frage gilt — eine Person nie über ihren Ablauf hinaus."""
    if not befund.person:
        return NEGATIV_S
    rest = _rest_bis_ablauf_s(befund.ablauf)
    return POSITIV_S if rest is None else max(0.0, min(POSITIV_S, rest))


def _gnadenfrist(fingerabdruck: str, gemerkt: tuple[float, Befund] | None, jetzt: float,
                 unklar: Befund) -> Befund:
    """CB-4: die Prüfung blieb ohne Ergebnis. Bestätigte der Server dieselbe Person in den
    letzten ``AUTH_GRACE_S`` und ist ihr Block nicht abgelaufen, gilt sie weiter — bis zur
    nächsten Frage nach :data:`NEGATIV_S`. Sonst anonym, und nichts wird gemerkt."""
    frueher = gemerkt[1] if gemerkt is not None else None
    if frueher is None or not frueher.person:
        return unklar
    rest = _rest_bis_ablauf_s(frueher.ablauf)
    if jetzt - frueher.bestaetigt_um > get_settings().auth_grace_s or (
            rest is not None and rest <= 0):
        return unklar
    logger.info("Anmeldung nicht prüfbar — die letzte Bestätigung gilt weiter")
    befund = replace(frueher, unklar=True)
    _merken(fingerabdruck, (jetzt + (NEGATIV_S if rest is None else min(NEGATIV_S, rest)), befund))
    return befund


async def _fragen() -> Befund:
    try:
        async with asyncio.timeout(FRIST_S):
            art, stand = await anmelde_endpunkte.status_abfragen(auth._effective_token(), FRIST_S)
            if art == "kein_endpunkt":
                return _auswerten(await transport.call_tool("wlo_auth_status", {}))
    except TimeoutError:
        return _auswerten({"error": {"kind": "timeout"}})
    if art == "abgelehnt":
        return Befund(person=False, abgelehnt=True)
    if art == "unklar":
        return _unklar("keine Antwort", pause_s=float(stand.get("retry_after") or 0),
                       pause_alle=stand.get("code") == "rate_limited")
    return _aus_stand(stand)


def _unklar(grund: str, *, pause_s: float = 0.0, pause_alle: bool = False) -> Befund:
    logger.warning("Anmeldung nicht prüfbar (%s)", grund)
    return Befund(person=False, unklar=True, pause_s=pause_s, pause_alle=pause_alle)


def _auswerten(antwort: dict[str, Any]) -> Befund:
    """Die Antwort des Werkzeugs ``wlo_auth_status`` (Rückfall ohne ``/auth/status``)."""
    fehler = antwort.get("error")
    if fehler:
        if fehler.get("kind") == "auth":
            return Befund(person=False, abgelehnt=True)
        return _unklar(fehler.get("kind") or "unbekannt")
    return _aus_stand((antwort.get("result") or {}).get("structuredContent") or {})


def _aus_stand(stand: dict[str, Any]) -> Befund:
    """Die gemeinsame Nutzlast von ``/auth/status`` und ``wlo_auth_status``.

    Ob ``authenticated: false`` eine Ablehnung ist, sagt seit der Antwort des MCP-Teams auf
    unsere Rückmeldung (Befund 2) das Feld ``upstream``: ``ok`` = das Repository hat geantwortet
    und abgelehnt, ``unreachable`` = kein Urteil (Ausfall, Überlast, Frist). Ein Server ohne das
    Feld: ``authority: null`` zählt als *unklar* — sonst verlöre bei jedem Repository-Ausfall
    jede Person ihre Anmeldung; lehnt es wirklich ab, kommt ``login_rejected`` am nächsten
    Werkzeug."""
    authority = stand.get("authority")
    upstream = stand.get("upstream")
    # Ein eindeutig positives Urteil zuerst: hat das Repository die Person bestätigt, ändert ein
    # widersprüchliches ``upstream`` daran nichts.
    if stand.get("mode") == "user" and stand.get("authenticated") is True and authority:
        streuwert = hashlib.sha256(str(authority).encode("utf-8")).hexdigest()[:16]
        ablauf = stand.get("expiresAt")
        return Befund(person=True, kennung=f"p:{streuwert}",
                      ablauf=ablauf if isinstance(ablauf, str) else None)
    if upstream == "unreachable":
        return _unklar("Repository ohne Antwort")
    if stand.get("mode") in ("user", "service") and stand.get("authenticated") is False:
        if authority is None and upstream != "ok":
            return _unklar("Repository ohne Antwort")
        return Befund(person=False, abgelehnt=True)
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


def abgemeldet(block: str) -> None:
    """Die Person hat sich abgemeldet (R2): ihr Block gilt hier sofort als abgewiesen — sonst
    hielte der Speicher eine kopierte Fassung bis zu :data:`POSITIV_S` für eine Person
    (Review 2026-11-07, Befund 4). Nach :data:`NEGATIV_S` fragt der Server wieder (dann 401)."""
    _merken(auth.fingerabdruck(block),
            (time.monotonic() + NEGATIV_S, Befund(person=False, abgelehnt=True)))


def _verwerfen() -> None:
    auth.verwirf_zug_block()
    logger.info("Zugangsblock abgewiesen — der Zug läuft ohne ihn weiter")


def abgelehnt_in_diesem_zug() -> bool:
    """Wurde in diesem Zug der Block der Person abgewiesen? (Signal an das Widget)"""
    return auth.zug_block_abgewiesen()
