"""Was in dieser Sammlung steckt — die zwei Zahlen der Kontext-Bestätigung.

Nutzer-Vorgabe (2026-08-14): die Begrüßung soll **zeigen**, dass der Kontext
wirklich angekommen ist — „35 Materialien, 28 freigegebene Anleitungen" statt
einer Behauptung. Beide Zahlen liefern Werkzeuge, die es längst gibt:

* ``get_collection_stats`` → ``fileCount`` / ``subCollectionCount``
* ``get_skill_registry``   → Länge von ``registry.entries``

**Nebeneinander, nicht nacheinander** — die beiden Abrufe zueinander. Die
Wartezeit ist die des langsamsten, nicht ihre Summe.

**Was NICHT stimmt und beim Bauen richtiggestellt wurde:** parallel zur
Metadaten-Auflösung laufen sie nicht. ``resolve_page_context`` steht im Knoten
``page_context_enrich`` und ist längst fertig, wenn die Begrüßung baut; diese
Abrufe kommen also OBEN DRAUF. Gemessen sind das ~0.9 s (die Registry ist die
langsamere), gedeckelt bei :data:`DEADLINE`. Wer sie wirklich nebenher haben
will, startet sie in ``page_context_enrich`` und wartet hier nur noch ab — das
ist ein eigener Schritt und kein Nebeneffekt dieses Moduls.

**Mit Deckel** (:data:`DEADLINE`). Antwortet ein Werkzeug nicht rechtzeitig,
geht die Begrüßung ohne seine Zahl raus. Sie ist das ERSTE, was jemand sieht;
eine Bestätigung, die auf ein langsames Repositorium wartet, ist schlechter als
eine ohne Zahl.

**Wirft nie, und jede Zahl ist einzeln optional.** Fällt ein Abruf aus, fehlt
genau seine Zahl — der Satz nennt dann, was da ist. Ein halber Ausfall darf
weder den Zug kosten noch die andere Hälfte.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from boerdi.services.mcp.client import call_mcp_tool
from boerdi.services.page_context import MAX_SKILL_ENTRIES

logger = logging.getLogger(__name__)

#: Schlüssel, mit dem ein ERGEBNISLOSER Abruf datiert wird.
#:
#: Er steht im Faktenobjekt selbst, damit beide Leser ihn ohne Zutun
#: überspringen: weder ``page_context._bestands_zeilen`` noch die Begrüßung
#: finden darin ``materials`` oder ``skills`` — sie schweigen also, wie sie es
#: auch bei gar keinen Fakten täten. Ein zweites Feld neben ``context_facts``
#: hätte die Form an einer dritten Stelle bekannt gemacht.
EMPTY_MARKER = "_leer_seit"

#: Wie lange ein ergebnisloser Abruf ruht, bevor er wiederholt wird.
#:
#: Ohne diese Pause lief er JEDEN Zug erneut — der Fall ist real: eine Sammlung,
#: deren Statistik 404 liefert und die keine Freigabeliste führt, ergibt zweimal
#: nichts. Dieselbe Halbwertszeit wie ``page_context._UNRESOLVED_TTL_SECONDS``,
#: damit es EINE Regel bleibt: was gerade nicht auflösbar war, wird bald wieder
#: versucht, aber nicht dauernd.
EMPTY_RETRY_SECONDS = 120.0

#: Wie lange die Begrüßung höchstens auf die Zahlen wartet.
#:
#: **Gemessen über boerdis eigenen Client** (2026-08-14, echter Server), und das
#: ist der Wert, auf den es ankommt — nicht die Dauer eines nackten
#: Werkzeugaufrufs: **kalt 4.2–5.0 s**, **warm 0.00 s**. Der Unterschied ist der
#: Verbindungsaufbau plus der Werkzeug-Cache; kalt ist es einmal je Sammlung und
#: Cache-Zeitfenster, danach kostet es nichts.
#:
#: Die erste Fassung stand auf 2.0 s — geraten, nicht gemessen. Ergebnis: beide
#: Abrufe liefen in den Deckel, die Begrüßung kam ohne Zahlen, und im Protokoll
#: stand ein ``TimeoutError`` mit leerer Meldung. Genau der Befund des Nutzers.
#:
#: 6.0 s war die zweite Schätzung und ebenfalls zu knapp: beim allerersten
#: Kontakt eines Prozesses überschritt ``get_skill_registry`` sie (34 kB
#: Antwort plus Verbindungsaufbau, gemessener Zug 7.3 s), und beide Engines
#: verloren den Bestand für diesen Zug. 9 s decken auch den kalten Erstkontakt
#: und bleiben, was der Wert sein soll: ein Netz gegen ein klemmendes
#: Repositorium, kein Wartebudget.
DEADLINE = 9.0


def _zahl(wert: Any) -> int | None:
    """Eine nicht-negative ganze Zahl, oder ``None``.

    ``bool`` ist in Python ein ``int`` — hier aber sicher ein Fehler und
    deshalb ausgeschlossen. Fremd beschriebene Felder kommen auch mal als
    Zeichenkette; eine Zahl, die keine ist, gehört nicht in einen Satz, der
    Verlässlichkeit behauptet.
    """
    if isinstance(wert, bool) or not isinstance(wert, int) or wert < 0:
        return None
    return wert


async def _sammlungs_zahlen(collection_id: str) -> dict[str, int]:
    roh = await call_mcp_tool(
        "get_collection_stats", {"nodeId": collection_id, "outputFormat": "json"})
    daten = json.loads(roh)
    if not isinstance(daten, dict):
        return {}
    paare = (("materials", "fileCount"), ("sub_collections", "subCollectionCount"))
    return {name: z for name, feld in paare if (z := _zahl(daten.get(feld))) is not None}


async def _skill_fakten(collection_id: str) -> dict[str, Any]:
    """Die Anzahl der Anleitungen — und ihre Titel als Übersicht.

    Die Zahl trägt die Begrüßung, die Titel den Seitenblock beider Engines
    (Nutzer-Vorgabe 2026-08-14). **Titel und sonst nichts**: keine
    Beschreibungen, keine ``nodeId`` — die Vorgabe „nur die Übersicht, höchstens
    eine A4 Seite" und „vollständig bis 100" gehen nur so zusammen (Rechnung
    im Docstring von ``page_context._bestands_zeilen``). Den Volltext holt das
    Modell gezielt über ``search_skill`` → ``get_skill``.

    ``skills`` zählt die Einträge der Registry, nicht die benennbaren — es ist
    die Aussage „so viele Anleitungen sind hier freigegeben". Ein Eintrag ohne
    Titel fällt nur aus der Liste, nicht aus der Zahl; der Renderer macht die
    Differenz sichtbar statt sie zu verschlucken.
    """
    roh = await call_mcp_tool(
        "get_skill_registry", {"collectionId": collection_id, "outputFormat": "json"})
    daten = json.loads(roh)
    registry = daten.get("registry") if isinstance(daten, dict) else None
    eintraege = registry.get("entries") if isinstance(registry, dict) else None
    if not isinstance(eintraege, list) or not eintraege:
        return {}
    katalog = [
        titel for e in eintraege
        if isinstance(e, dict) and (titel := str(e.get("title") or "").strip())
    ]
    # Gekappt schon hier und nicht erst beim Rendern: die Fakten landen als
    # jsonb in ``session_state['entities']`` und werden je Zug mitgeschrieben.
    # Was der Prompt nie zeigt, muss auch nicht gespeichert werden.
    return {"skills": len(eintraege), "skill_titles": katalog[:MAX_SKILL_ENTRIES]}


def retry_due(fakten: Any) -> bool:
    """Ist ein (erneuter) Bestandsabruf fällig?

    Drei Fälle: keine Fakten → ja. Echte Fakten → nein. Ein datierter
    Leer-Vermerk → erst nach :data:`EMPTY_RETRY_SECONDS` wieder.

    Der Zeitstempel kommt aus persistiertem jsonb und ist damit fremd
    beschrieben; ist er unlesbar, wird lieber neu abgerufen als für immer
    geschwiegen. Dasselbe gilt für einen Zeitstempel aus der ZUKUNFT: das
    Alter wäre negativ, negativ ist nie ``>= EMPTY_RETRY_SECONDS``, und der
    Vermerk hielte bis die Wanduhr aufgeholt hat. Er ist kein junger Vermerk,
    sondern ein kaputter.
    """
    if not isinstance(fakten, dict) or not fakten:
        return True
    if EMPTY_MARKER not in fakten:
        return False
    try:
        alter = time.time() - float(fakten[EMPTY_MARKER])
    except (TypeError, ValueError):
        return True
    return alter < 0 or alter >= EMPTY_RETRY_SECONDS


def empty_marker() -> dict[str, float]:
    """Der Vermerk „hier kam nichts" — siehe :func:`retry_due`."""
    return {EMPTY_MARKER: time.time()}


async def collect_context_facts(collection_id: str) -> dict[str, Any]:
    """Die Zahlen zu ``collection_id`` — so viele, wie rechtzeitig da sind.

    :returns: ``{"materials": …, "sub_collections": …, "skills": …,
        "skill_entries": [{"title", "node_id"}, …]}``; jeder Schlüssel fehlt,
        wenn sein Abruf nichts Brauchbares ergab. Ohne Sammlungs-ID ein leeres
        Dict, **ohne** einen Abruf zu starten: es gäbe nichts zu fragen, und ein
        Rundlauf ins Leere kostet trotzdem Zeit.
    """
    if not (collection_id or "").strip():
        return {}

    # Der Deckel gilt JE ABRUF, nicht dem Paar: ein hängendes Werkzeug darf nur
    # seine eigene Zahl kosten. Ein gemeinsamer Deckel warf auch die längst
    # fertige zweite weg — genau das hat der Test gezeigt.
    fakten: dict[str, Any] = {}
    ergebnisse = await asyncio.gather(
        asyncio.wait_for(_sammlungs_zahlen(collection_id), DEADLINE),
        asyncio.wait_for(_skill_fakten(collection_id), DEADLINE),
        return_exceptions=True,
    )

    for ergebnis in ergebnisse:
        if isinstance(ergebnis, BaseException):
            logger.info("Kontext-Zahl nicht abrufbar: %s", ergebnis)
            continue
        fakten.update(ergebnis)
    return fakten
