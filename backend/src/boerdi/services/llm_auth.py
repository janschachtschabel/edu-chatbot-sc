"""Der B-API-Schlüssel eines Zuges (Paket 17, Phase B).

Hinter dem b-api-Proxy (``/api/v1/proxy/badboerdichat/…``, ``forwardApiKey``) trägt
jede Anfrage ``Authorization: Bearer <key>`` — den Schlüssel, den edu-sharing für die
angemeldete Person oder den Gast gewählt hat. Die b-api bucht Nutzung, Kosten und Limits
auf ihn; der Chatbot reicht ihn deshalb bei allen LLM-Aufrufen des Zuges weiter. Ohne
Kopf gilt ``B_API_KEY`` (Direktaufruf, Hintergrundläufe) — Nutzer-Entscheid 2026-10-20
„Header vor Env“.

Regeln der b-api (gemessen 13.10.2026): unverändert weitergeben, ``bearer`` klein → 401,
genau EIN Kopf (ein zusätzlicher ``X-API-KEY`` → 401). Der Wert ist ein Geheimnis: nie
loggen, nie speichern — er lebt nur im ``ContextVar`` dieses Zuges.

Gesetzt wird er wie der WLO-Zugangsblock **im Endpunkt** (``api/turn_auth``), vor dem
Graphen: LangGraph-Knoten laufen als eigene Tasks mit Kontextkopie, lesen also, was der
Endpunkt gesetzt hat.
"""

from __future__ import annotations

import contextvars as _ctxvars
import re

from boerdi.settings import get_settings

# Nur der Schlüssel, ohne ``Bearer ``; leer = keiner durchgereicht.
_zug_schluessel: _ctxvars.ContextVar[str] = _ctxvars.ContextVar("_zug_schluessel", default="")

# Genau ``Bearer `` (Groß-B, ein Leerzeichen) und sichtbare ASCII-Zeichen — nur so baut
# das SDK aus dem Schlüssel wieder WÖRTLICH den eingehenden Kopf. Die Längen umschließen
# die b-api-Schlüssel (36 Zeichen) mit Reserve; CR/LF fallen unter ``[!-~]`` heraus.
_FORM = re.compile(r"Bearer ([!-~]{8,512})")


def setze_llm_schluessel(roh: str | None) -> bool:
    """Den Schlüssel dieses Zuges aus dem rohen ``Authorization``-Wert übernehmen.

    Ein unbrauchbarer oder fehlender Wert **löscht** einen früher gesetzten — ein Zug
    darf nie unter dem Schlüssel eines anderen laufen. Gibt zurück, ob einer gilt.
    """
    treffer = _FORM.fullmatch(roh or "")
    _zug_schluessel.set(treffer.group(1) if treffer else "")
    return treffer is not None


def hat_zug_schluessel() -> bool:
    """Gilt für diesen Zug ein durchgereichter Schlüssel? (Für Meldungen — nie der Wert.)"""
    return bool(_zug_schluessel.get())


def b_api_schluessel() -> str:
    """Der Schlüssel für einen b-api-Aufruf: der durchgereichte, sonst ``B_API_KEY``."""
    return _zug_schluessel.get() or get_settings().b_api_key.get_secret_value().strip()
