"""Listen in den Filtern der WLO-Suchwerkzeuge: auspacken oder auffächern (Paket 18B).

Der MCP-Server erwartet je Filter EINEN Wert (``z.string()``). Fragt jemand nach
„Arbeitsblatt oder interaktives Material“, kommt ``learningResourceType`` aber als
Liste — vom Modell oder aus den Entitäten. Bisher ging sie roh hinaus (-32602), und
nur der Retry des Modells rettete den Zug (externes Audit 2026-10).

Hier, an einer Stelle vor ``validate_tool_args``, gilt:
- eine Liste mit einem Wert wird ausgepackt, eine leere fällt weg;
- eine Liste mit mehreren Werten wird in einzelne Aufrufe aufgefächert (höchstens
  :data:`_MAX_WERTE`), die Treffer werden zusammengeführt und nach ``nodeId``
  entdoppelt;
- hat mehr als ein Filter mehrere Werte, wird nur der erste aufgefächert, die übrigen
  nehmen ihren ersten Wert (ein Kreuzprodukt wäre teuer und selten gemeint).

simplify: das Auffächern kostet je Wert einen MCP-Aufruf. Kann der Server Listen
(``values: [...]`` in ``criteria`` ODER-verknüpft), reicht einer — dann entfällt das
hier.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from boerdi.domain.content_types import als_liste
from boerdi.services.mcp.parsers.json_scan import _first_json_object, load_envelope

logger = logging.getLogger(__name__)

_SUCHWERKZEUGE = frozenset({"search_wlo_content", "search_wlo_within_collection",
                            "search_wlo_all"})
_FILTER = ("learningResourceType", "discipline", "educationalContext", "userRole", "license")
_MAX_WERTE = 3

Rufe = Callable[..., Awaitable[tuple[str, str]]]


def braucht_umformung(tool_name: str, arguments: dict[str, Any]) -> bool:
    """Trägt ein Suchwerkzeug-Aufruf einen Filter als Liste?"""
    return tool_name in _SUCHWERKZEUGE and any(
        isinstance(arguments.get(k), (list, tuple)) for k in _FILTER)


async def mit_listen(tool_name: str, arguments: dict[str, Any], rufe: Rufe,
                     **kwargs: Any) -> tuple[str, str]:
    """Den Aufruf mit ausgepackten bzw. aufgefächerten Listen ausführen.

    ``rufe`` ist der Einzelaufruf (``call_mcp_tool_status``); Rückgabe wie dort
    ``(text, art)``. Scheitern alle Teilaufrufe, kommt der erste Fehler zurück;
    scheitern einige, zählen die Treffer der übrigen, und der Text nennt dem Modell
    die gescheiterten Werte."""
    args = dict(arguments)
    mehrfach: tuple[str, list[str]] | None = None
    for schluessel in _FILTER:
        wert = args.get(schluessel)
        if not isinstance(wert, (list, tuple)):
            continue
        werte = als_liste(wert)
        if not werte:
            args.pop(schluessel)
        elif len(werte) == 1 or mehrfach is not None:
            if len(werte) > 1:
                logger.info("MCP %s: %s has %d values, only %s is fanned out — using the "
                            "first", tool_name, schluessel, len(werte), mehrfach[0])
            args[schluessel] = werte[0]
        else:
            mehrfach = (schluessel, werte)
    if mehrfach is None:
        return await rufe(tool_name, args, **kwargs)

    schluessel, werte = mehrfach
    if len(werte) > _MAX_WERTE:
        logger.info("MCP %s: %s has %d values, querying the first %d", tool_name,
                    schluessel, len(werte), _MAX_WERTE)
        werte = werte[:_MAX_WERTE]
    # ``return_exceptions``: wirft ein Teilaufruf, liefe der andere sonst verwaist weiter.
    ergebnisse = await asyncio.gather(
        *(rufe(tool_name, {**args, schluessel: w}, **kwargs) for w in werte),
        return_exceptions=True)
    treffer = [e[0] for e in ergebnisse if isinstance(e, tuple) and not e[1]]
    gescheitert = [w for w, e in zip(werte, ergebnisse, strict=True)
                   if not isinstance(e, tuple) or e[1]]
    if gescheitert:
        logger.info("MCP %s: %d of %d fanned-out calls failed", tool_name,
                    len(gescheitert), len(werte))
    if not treffer:
        antworten = [e for e in ergebnisse if isinstance(e, tuple)]
        if antworten:
            return antworten[0]
        raise ergebnisse[0]
    text = vereinige_umschlaege(treffer)
    if gescheitert:
        text += "\n\n" + "\n".join(
            f"Hinweis: Die Teilsuche mit {schluessel}={w!r} ist fehlgeschlagen; "
            "ihre Treffer fehlen." for w in gescheitert)
    return text, ""


def vereinige_umschlaege(texte: list[str]) -> str:
    """JSON-Umschläge mehrerer Suchen zu einem: Listen verbunden und nach ``nodeId``
    entdoppelt, ``total`` der Inhaltssuche addiert, ``count`` neu gezählt; der
    Begleittext des Servers (Hinweise nach dem Umschlag) bleibt, entdoppelt, dahinter
    stehen. Ist ein Text kein JSON-Objekt, gilt der erste unverändert."""
    if len(texte) == 1:
        return texte[0]
    objekte = [load_envelope(t) for t in texte]
    if not all(isinstance(o, dict) for o in objekte):
        return texte[0]
    gesamt: dict[str, Any] = dict(objekte[0])
    for weiteres in objekte[1:]:
        gesamt = _vereinige(gesamt, weiteres, summieren=True)
    begleit = list(dict.fromkeys(b for b in map(_begleittext, texte) if b))
    return "\n\n".join([json.dumps(gesamt, ensure_ascii=False), *begleit])


def _begleittext(text: str) -> str:
    """Was ein Ergebnis außer dem JSON-Umschlag trägt: der Server hängt Hinweise als
    eigenen Block an (nicht aufgelöster Filter, Lizenz, Skill-Liste — Review 18)."""
    try:
        json.loads(text)
        return ""
    except (ValueError, TypeError):
        ausschnitt = _first_json_object(text or "")
    return text.replace(ausschnitt, "", 1).strip() if ausschnitt else ""


def _vereinige(a: dict[str, Any], b: dict[str, Any], *, summieren: bool) -> dict[str, Any]:
    """``summieren``: nur oben und unter ``content`` hängt ``total`` am Filter — die
    Sammlungen und Themenseiten von ``search_wlo_all`` fanden beide Teilsuchen gleich."""
    aus = dict(a)
    for schluessel, wert in b.items():
        bisher = aus.get(schluessel)
        if isinstance(wert, list) and isinstance(bisher, list):
            aus[schluessel] = _entdoppelt(bisher + wert)
        elif isinstance(wert, dict) and isinstance(bisher, dict):
            aus[schluessel] = _vereinige(bisher, wert, summieren=schluessel == "content")
        elif (summieren and schluessel == "total" and isinstance(wert, int)
              and isinstance(bisher, int)):
            aus[schluessel] = bisher + wert
        elif schluessel not in aus:
            aus[schluessel] = wert
    if isinstance(aus.get("results"), list) and "count" in aus:
        aus["count"] = len(aus["results"])
    return aus


def _entdoppelt(eintraege: list[Any]) -> list[Any]:
    gesehen: set[str] = set()
    aus: list[Any] = []
    for e in eintraege:
        kennung = (e.get("nodeId") or e.get("id")) if isinstance(e, dict) else None
        if isinstance(kennung, str):
            if kennung in gesehen:
                continue
            gesehen.add(kennung)
        aus.append(e)
    return aus
