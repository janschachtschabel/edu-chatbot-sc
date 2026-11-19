"""Betriebsanzeige der b-api (Plan 2026-11-19, N1): welche Betriebsart sah der Chatbot zuletzt?

Je Nutzeranfrage (``api/turn_auth.uebernimm_zugang``, ohne Züge der Anlage) hält dieser Prozess
die Art aus :func:`llm_auth.zug_art` fest: ``delegation`` (Token ``bdt_…`` vom b-api-Proxy),
``schluessel`` (durchgereichter Schlüssel) oder ``direkt`` (kein Kopf → ``B_API_KEY``), dazu den
Zeitpunkt. **Nie einen Wert** — nur das Wort. Angezeigt in ``/api/health`` (Studio-Schlüssel) und
im Studio (Statusleiste der Übersicht).

simplify: je Prozess, nicht über die DB. Mit mehreren Kopien zeigt ``/api/health`` die Sicht der
Kopie, die antwortet; für eine gemeinsame Sicht fehlt eine Tabelle (Migration) — der Hinweis „so
läuft der Betrieb“ ist auch je Kopie richtig, denn alle stehen hinter demselben Eingang.

Warnungen (Codes, das Studio übersetzt):

- ``forward_ohne_token``: ``B_API_KEY_MODE=forward`` mit b-api-Anbieter, seit dem Start kam kein
  durchgereichter Wert, und mindestens ein Nutzerzug wurde deshalb mit 401 abgewiesen
  (:func:`merke_abgewiesen`). Direkt nach dem Start ist „kein Token“ noch kein Befund.
- ``zugangsblock_fehlt``: mindestens :data:`ZUGANGSBLOCK_AB` Züge mit Delegation, und bei keinem
  kam die Kopfzeile ``WLO-Access-Block`` an — vielleicht fehlt sie am Proxy in
  ``allowedRequestHeaders``. Nur ein Hinweis: ohne angemeldete Person schickt das Widget den Block
  nicht, bei rein anonymer Nutzung ist das normal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final, Literal

from boerdi.services.llm_auth import Art
from boerdi.settings import get_settings

Betriebsart = Literal["delegation", "schluessel", "direkt"]

#: Ab so vielen Delegationszügen ohne Zugangsblock gilt das Fehlen als Hinweis (Review N1/N2).
ZUGANGSBLOCK_AB: Final = 20


@dataclass
class _Stand:
    zuletzt: Betriebsart | None = None
    zuletzt_am: datetime | None = None
    wert_gesehen: bool = False
    #: Nutzerzüge, die ``forward`` mangels Kopf mit 401 abwies.
    abgewiesen: int = 0
    delegation_ohne_block: int = 0
    zugangsblock_bei_delegation: bool = False


_stand = _Stand()


def merke_zug(art: Art, *, zugangsblock: bool) -> None:
    """Einen Nutzerzug festhalten: ``art`` aus :func:`llm_auth.zug_art`; ``zugangsblock`` =
    die Kopfzeile ``WLO-Access-Block`` kam an (gleich, ob brauchbar)."""
    _stand.zuletzt = art or "direkt"
    _stand.zuletzt_am = datetime.now(UTC)
    if art:
        _stand.wert_gesehen = True
    if art == "delegation":
        if zugangsblock:
            _stand.zugangsblock_bei_delegation = True
        else:
            _stand.delegation_ohne_block += 1


def merke_abgewiesen() -> None:
    """Ein Nutzerzug bekam unter ``forward`` 401, weil der Kopf fehlte (``api/turn_auth``)."""
    _stand.abgewiesen += 1


def stand() -> dict[str, Any]:
    """Für ``/api/health``: ``modus`` (``B_API_KEY_MODE``), ``zuletzt``, ``zuletzt_am`` (ISO, UTC),
    ``abgewiesen`` (401 unter ``forward``) und ``warnungen`` — ohne Werte."""
    einst = get_settings()
    warnungen: list[str] = []
    if (einst.b_api_key_mode == "forward" and einst.llm_provider.startswith("b-api")
            and _stand.abgewiesen > 0 and not _stand.wert_gesehen):
        warnungen.append("forward_ohne_token")
    if (not _stand.zugangsblock_bei_delegation
            and _stand.delegation_ohne_block >= ZUGANGSBLOCK_AB):
        warnungen.append("zugangsblock_fehlt")
    return {"modus": einst.b_api_key_mode, "zuletzt": _stand.zuletzt,
            "zuletzt_am": _stand.zuletzt_am.isoformat() if _stand.zuletzt_am else None,
            "abgewiesen": _stand.abgewiesen, "warnungen": warnungen}


def zuruecksetzen() -> None:
    """Für Tests: wie nach dem Start."""
    global _stand
    _stand = _Stand()
