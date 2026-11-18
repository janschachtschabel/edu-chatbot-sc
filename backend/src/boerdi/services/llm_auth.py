"""Der b-api-Zugang eines Zuges (Paket 17, Phase B; Paket D, Plan 2026-11-17).

Hinter dem b-api-Proxy (``/api/v1/proxy/badboerdichat/…``, ``forwardDelegation``) trägt jede
Anfrage ``Authorization: Bearer bdt_…`` — ein **Delegations-Token** der b-api: verschlüsselt,
Länge unbekannt, gültig nur, solange die eingehende Anfrage läuft (Fehler oder Abbruch beenden
es). Es erlaubt LLM und lesende Repository-Pfade, keine Jobs. Der Chatbot reicht es bei jedem
b-api-Aufruf des Zuges unverändert als ``Authorization: Bearer`` weiter. Ältere Proxy-Einträge
(``forwardApiKey``) reichen statt dessen einen Schlüssel (Art ``schluessel``) — gleich behandelt.

Ohne Kopf gilt ``B_API_KEY`` (Direktbetrieb, Hintergrundläufe) — Nutzer-Entscheid 2026-10-20
„Header vor Env“. **Mit Delegation nie Rückfall** (E3): ein unbrauchbares oder beendetes Token
ergibt :class:`KeinDelegationsToken`, nie ``B_API_KEY`` — der Zug liefe sonst ohne Person.

Regeln der b-api: unverändert weitergeben, ``bearer`` klein → 401, genau EIN Kopf (nie
``X-API-KEY`` daneben, er hätte Vorrang), nie ``X-Edu-User-Id`` (abgeschafft). Der Wert ist ein
Geheimnis: nie loggen, nie speichern — er lebt nur im ``ContextVar`` dieses Zuges, nie im ``repr``.

Gesetzt wird er wie der WLO-Zugangsblock **im Endpunkt** (``api/turn_auth``), vor dem
Graphen: LangGraph-Knoten laufen als eigene Tasks mit Kontextkopie, lesen also, was der
Endpunkt gesetzt hat. Der Stand ist ein geteiltes Objekt (kein ``ContextVar.set`` danach), damit
das Auflegen, das der Strom im Kontext der Anfrage bemerkt, auch die Kopien erreicht
(:func:`delegation_beender`, E4).
"""

from __future__ import annotations

import contextvars as _ctxvars
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from boerdi.settings import get_settings

Art = Literal["delegation", "schluessel", ""]

#: Präfix der Delegations-Tokens der b-api (Plan 2026-11-17, E3).
DELEGATION_PRAEFIX = "bdt_"


@dataclass(eq=False)
class _ZugStand:
    #: Nur der Wert, ohne ``Bearer ``; leer bei einem unbrauchbaren Delegations-Token.
    schluessel: str = field(default="", repr=False)
    art: Art = ""
    #: Die eingehende Anfrage ist zu Ende (Client aufgelegt) — das Token gilt nicht mehr.
    beendet: bool = False


_zug: _ctxvars.ContextVar[_ZugStand | None] = _ctxvars.ContextVar("_zug", default=None)

# Genau ``Bearer `` (Groß-B, ein Leerzeichen) und sichtbare ASCII-Zeichen — nur so baut
# das SDK aus dem Wert wieder WÖRTLICH den eingehenden Kopf. 8–8192 Zeichen umschließen die
# b-api-Schlüssel (36) und das Delegations-Token (JWE, Länge unbekannt; E3); CR/LF fallen
# unter ``[!-~]`` heraus.
_FORM = re.compile(r"Bearer ([!-~]{8,8192})")
#: Ein Kopf, der ein Delegations-Token tragen will, auch in falscher Form (E3: kein Rückfall).
_WILL_DELEGATION = re.compile(r"\s*bearer\s+" + DELEGATION_PRAEFIX, re.IGNORECASE)


class KeinDelegationsToken(RuntimeError):  # noqa: N818 — der Name sagt den Zustand
    """Im Delegationsbetrieb gibt es für diesen Aufruf kein gültiges Token: ``unbrauchbar``
    (falsche Form, nicht weiterzugeben) oder ``beendet`` (der Client legte auf, E4). Es folgt
    kein b-api-Aufruf und kein Rückfall auf ``B_API_KEY``. Trägt nie das Token."""

    def __init__(self, grund: Literal["unbrauchbar", "beendet"]) -> None:
        super().__init__(f"Delegations-Token {grund}")
        self.grund = grund


def setze_llm_schluessel(roh: str | None) -> bool:
    """Den Zugang dieses Zuges aus dem rohen ``Authorization``-Wert übernehmen.

    Ein unbrauchbarer oder fehlender Wert **löscht** einen früher gesetzten — ein Zug
    darf nie unter dem Schlüssel eines anderen laufen. Ein unbrauchbares Delegations-Token
    bleibt als Art ``delegation`` ohne Wert stehen (kein Rückfall). Gibt zurück, ob einer gilt.
    """
    roh = roh or ""
    treffer = _FORM.fullmatch(roh)
    if treffer is not None:
        wert = treffer.group(1)
        art: Art = "delegation" if wert.startswith(DELEGATION_PRAEFIX) else "schluessel"
        _zug.set(_ZugStand(schluessel=wert, art=art))
        return True
    _zug.set(_ZugStand(art="delegation") if _WILL_DELEGATION.match(roh) else None)
    return False


def hat_zug_schluessel() -> bool:
    """Gilt für diesen Zug ein durchgereichter Wert? (Für Meldungen — nie der Wert.)"""
    stand = _zug.get()
    return stand is not None and bool(stand.schluessel)


def zug_art() -> Art:
    """``delegation`` (Token ``bdt_…``), ``schluessel`` (durchgereichter Schlüssel) oder ``""``
    (kein Kopf: ``B_API_KEY``)."""
    stand = _zug.get()
    return stand.art if stand is not None else ""


def darf_jobs() -> bool:
    """Darf dieser Zug b-api-Jobs abfragen, abbrechen oder holen? Nur mit einem durchgereichten
    Schlüssel der Person — das Delegations-Token deckt keine Jobs (Plan 2026-11-17, E1/E2)."""
    return hat_zug_schluessel() and zug_art() != "delegation"


def delegation_beendet() -> bool:
    """Endete das Delegations-Token dieses Zuges mit dem Auflegen (E4)? Für den Satz."""
    stand = _zug.get()
    return stand is not None and stand.art == "delegation" and stand.beendet


def delegation_beender() -> Callable[[], bool]:
    """Für den Strom (``api/sse``): eine Funktion, die das Token DIESES Zuges beendet — gebunden
    beim Start, weil das Auflegen auch außerhalb des Kontexts der Anfrage bemerkt werden kann
    (Abschluss eines Generators). Sie gibt ``True`` zurück, wenn der Zug eines trug."""
    stand = _zug.get()

    def beenden() -> bool:
        if stand is None or stand.art != "delegation":
            return False
        stand.beendet = True
        return True

    return beenden


def b_api_schluessel() -> str:
    """Der Wert für einen b-api-Aufruf: der durchgereichte, sonst ``B_API_KEY``. Im
    Delegationsbetrieb nur das Token — ohne gültiges :class:`KeinDelegationsToken`."""
    stand = _zug.get()
    if stand is not None and stand.art == "delegation":
        if stand.beendet:
            raise KeinDelegationsToken("beendet")
        if not stand.schluessel:
            raise KeinDelegationsToken("unbrauchbar")
        return stand.schluessel
    if stand is not None and stand.schluessel:
        return stand.schluessel
    return get_settings().b_api_key.get_secret_value().strip()
