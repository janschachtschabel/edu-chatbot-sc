"""Was der bereitgestellte MCP-Server kann (Plan 2026-11-14, N3).

Chatbot und MCP-Server werden getrennt bereitgestellt. Einen neuen Parameter des Servers — zuerst
``collection``, eine Sammlung über ihren Titel — darf der Chatbot dem Modell erst anbieten, wenn der
Server ihn kennt: Der ältere Stand lehnt den Aufruf ab oder verwirft Unbekanntes, und das Modell
verlöre einen Zug. Ein Schalter im Deploy wäre eine Handlung mehr, die vergessen wird; der Server
sagt es selbst (``tools/list``).

Ein Takt (:func:`starte`) fragt beim Start und danach alle fünf Minuten — je Prozess, ohne
gemeinsamen Speicher: Die Antwort ist klein genug und für alle Prozesse gleich. Gefragt wird die
eine eingestellte Adresse (``MCP_SERVER_URL``); eine je Einbettung gibt es nicht.

**Unbekannt heißt „kann es nicht“.** Bis zur ersten Antwort bleibt alles beim Alten. Scheitert eine
spätere Abfrage, gilt der letzte Stand noch für :data:`FEHLVERSUCHE_BIS_UNBEKANNT` Abfragen — ein
kurzer Ausfall nimmt dem Modell nichts weg —, danach wieder „unbekannt“: Antwortet der Server nach
einem Rückbau dauerhaft nicht auf ``tools/list``, böte der Chatbot sonst ohne Ende an, was es
dort nicht mehr gibt (Review N3, Befund 6).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from typing import Any, Final

from boerdi.obs.drossel import gedrosselt

logger = logging.getLogger(__name__)

TAKT_S: Final = 300.0
#: Nach einer gescheiterten Abfrage früher wieder: Der Start trifft oft einen noch kalten Server.
TAKT_NACH_FEHLER_S: Final = 30.0
FEHLVERSUCHE_BIS_UNBEKANNT: Final = 3
#: Eine Warnung je Viertelstunde und Prozess, nicht je Fehlversuch (Hausregel seit Paket 19, N-15).
_WARN_ABSTAND_S: Final = 900.0

#: Werkzeug → Parameter → seine Aufzählungswerte (leer ohne ``enum``); leer, solange der Server
#: nicht geantwortet hat.
_parameter: dict[str, dict[str, frozenset[str]]] = {}
_fehlversuche = 0


def kennt(werkzeug: str, parameter: str) -> bool:
    """Führt der Server ``parameter`` an ``werkzeug``? ``False``, solange das offen ist."""
    return parameter in _parameter.get(werkzeug, {})


def kennt_wert(werkzeug: str, parameter: str, wert: str) -> bool:
    """Nennt der Server ``wert`` in der Aufzählung (``enum``) von ``parameter``? N2 (2026-11-14):
    ein neuer Wert an einem alten Parameter, etwa ``contentType`` an ``vocabulary``."""
    return wert in _parameter.get(werkzeug, {}).get(parameter, frozenset())


def uebernehmen(werkzeuge: Iterable[Mapping[str, Any]]) -> bool:
    """Die Werkzeugliste des Servers übernehmen (Form von ``discover_server_tools``).

    Eine leere Liste ist keine Auskunft: Der Server führt immer Werkzeuge, und „kann nichts
    mehr“ nach einer kaputten Antwort nähme dem Modell alles Neue weg. Dann bleibt der Stand.
    """
    global _parameter, _fehlversuche
    neu: dict[str, dict[str, frozenset[str]]] = {}
    for w in werkzeuge:
        if not isinstance(w, Mapping):
            continue
        name = w.get("name")
        schema = w.get("input_schema")
        eigenschaften = schema.get("properties") if isinstance(schema, Mapping) else None
        if isinstance(name, str) and name:
            neu[name] = {str(p): _aufzaehlung(s) for p, s in eigenschaften.items()} if isinstance(
                eigenschaften, Mapping) else {}
    if not neu:
        return False
    _parameter = neu
    _fehlversuche = 0
    return True


def _aufzaehlung(schema: Any) -> frozenset[str]:
    werte = schema.get("enum") if isinstance(schema, Mapping) else None
    if not isinstance(werte, list):
        return frozenset()
    return frozenset(w for w in werte if isinstance(w, str))


def vergessen() -> None:
    """Den Stand leeren (Tests)."""
    global _parameter, _fehlversuche
    _parameter = {}
    _fehlversuche = 0


def _gescheitert(grund: str) -> None:
    """Eine Abfrage ohne brauchbare Antwort: zählen, gedrosselt warnen, nach der dritten in Folge
    den Stand verwerfen."""
    global _parameter, _fehlversuche
    _fehlversuche += 1
    gedrosselt(logger, logging.WARNING, "mcp-faehigkeiten", _WARN_ABSTAND_S,
               "MCP-Fähigkeiten: Abfrage gescheitert (%s)", grund)
    if _fehlversuche >= FEHLVERSUCHE_BIS_UNBEKANNT and _parameter:
        _parameter = {}
        logger.warning("MCP-Fähigkeiten: %d Abfragen in Folge gescheitert, Stand verworfen",
                       _fehlversuche)


async def erkunden() -> bool:
    """Den Server einmal fragen. ``False``, wenn er nicht (brauchbar) geantwortet hat."""
    from boerdi.services.mcp.transport import discover_server_tools

    try:
        gelungen = uebernehmen(await discover_server_tools(""))
    except Exception as err:  # noqa: BLE001 — der nächste Takt fragt wieder
        _gescheitert(type(err).__name__)
        return False
    if not gelungen:
        _gescheitert("keine Werkzeuge genannt")
        return False
    logger.debug("MCP-Fähigkeiten: %d Werkzeuge", len(_parameter))
    return True


async def _schleife() -> None:
    while True:
        gelungen = False
        try:
            gelungen = await erkunden()
        except Exception:  # noqa: BLE001 — der Takt darf nicht still enden
            gedrosselt(logger, logging.WARNING, "mcp-faehigkeiten-takt", _WARN_ABSTAND_S,
                       "MCP-Fähigkeiten: Takt gescheitert", exc_info=True)
        await asyncio.sleep(TAKT_S if gelungen else TAKT_NACH_FEHLER_S)


def starte() -> asyncio.Task[None]:
    """Den Takt im Hintergrund starten (erste Abfrage sofort); der Aufrufer bricht die Aufgabe
    beim Herunterfahren ab."""
    return asyncio.create_task(_schleife(), name="mcp-faehigkeiten-takt")
