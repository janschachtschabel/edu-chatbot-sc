"""Logzeilen ohne Inhalt (Paket 18C/D, Phase 2).

Grundsatz: Das Log sagt, dass etwas geschah und wie lange; was, steht im gespeicherten Zug
(``services/zugakte``), und die Trace-ID verbindet beides. Freitext — Nachricht, Thema,
Suchbegriff, Antwort — erscheint deshalb nur als Länge (:func:`inhalt`), eine Sitzung nur als
Kurzkennung (:func:`kennung`): die Sitzungs-ID selbst wirkt wie ein Schlüssel zum öffentlichen
Verlauf. Werkzeugargumente behalten ihre Filterwerte (:func:`filterwerte`) — die tragen keine
Personendaten, und Filterfehler sind der häufigste Fehlertyp.

Neue Logzeilen mit festen Feldern laufen über :func:`ereignis`; im JSON-Format stehen die Felder
dann auch einzeln (``event``, ``fields``).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from pydantic import ValidationError

from boerdi.domain.write_confirm import CONFIRM_TOKEN_FIELD

#: Werkzeugargumente, deren Wert ins Log darf: Filter des WLO-Katalogs, Kennungen, Steuerung.
#: Alles andere — ``query``, ``url``, Titel, Beschreibungen, Metadaten — nur als Länge. Ein
#: neuer Filter, der hier fehlt, erscheint also nur als Länge, nie mit Inhalt.
FILTER_SCHLUESSEL = frozenset({
    "discipline", "educationalContext", "learningResourceType", "license", "userRole",
    "targetGroup", "publisher", "contentFilter", "language", "outputFormat", "variantId",
    "nodeId", "nodeIds", "collectionId", "parentNodeId", "excludeNodeIds", "topicPageId",
    "swimlaneId", "sortBy", "sortAscending",
    # Review Phase 2: weitere Aufzählungen und Kennungen der WLO-Werkzeuge.
    "subject", "vocabulary", "parentId", "suggestionId", "field", "method", "decision", "status",
    "contentFormat", "licenseKey", "licenseVersion", "contentType",
})
#: Längere Listen (``excludeNodeIds`` bis 200) erscheinen nur als Anzahl.
MAX_LISTE = 5


def inhalt(text: str | None) -> str:
    """Freitext fürs Log: nur seine Länge."""
    return f"‹{len(text or '')} Zeichen›"


def kennung(session_id: str | None) -> str:
    """Eine Sitzung fürs Log: die ersten 8 Hex-Zeichen ihres SHA-256 — dieselbe Sitzung gibt
    dieselbe Kennung, aus der Kennung führt kein Weg zurück zur ID."""
    if not session_id:
        return "-"
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:8]


def _wert(schluessel: str, wert: Any) -> Any:
    if schluessel == CONFIRM_TOKEN_FIELD:
        return "‹geschwärzt›"
    if wert is None or isinstance(wert, bool | int | float):
        return wert
    if isinstance(wert, dict):
        return f"‹{len(wert)} Einträge›"
    if isinstance(wert, list | tuple):
        if schluessel in FILTER_SCHLUESSEL and len(wert) <= MAX_LISTE:
            return [_wert(schluessel, w) for w in wert]
        return f"‹{len(wert)} Einträge›"
    text = str(wert)
    return text if schluessel in FILTER_SCHLUESSEL else inhalt(text)


def filterwerte(argumente: Any) -> dict[str, Any]:
    """Werkzeugargumente fürs Log: Filter und Kennungen mit Wert, Freitext nur als Länge, der
    Bestätigungs-Schlüssel nie."""
    if not isinstance(argumente, dict):
        return {}
    return {str(k): _wert(str(k), v) for k, v in argumente.items()}


def fehlerorte(fehler: ValidationError) -> str:
    """Wo und welcher Art die Fehler einer Prüfung sind — ohne ``input_value``: der trägt
    Suchanfrage, Thema oder Eintragsdaten ins Log (Paket 18)."""
    return "; ".join(f"{'.'.join(str(t) for t in f['loc'])} ({f['type']})"
                     for f in fehler.errors())


def ereignis(logger: logging.Logger, name: str, *, stufe: int = logging.INFO,
             **felder: Any) -> None:
    """Eine Logzeile ``name feld=wert …``; im JSON-Format zusätzlich ``event`` und ``fields``.

    Nur Kennungen, Zahlen, Aufzählungen und Filterwerte gehören in die Felder — Inhalte gehen
    in die Zugakte."""
    if not logger.isEnabledFor(stufe):
        return
    teile = " ".join(f"{k}={v}" for k, v in felder.items())
    logger.log(stufe, "%s %s" if teile else "%s%s", name, teile,
               extra={"ereignis": name, "ereignis_felder": felder})
