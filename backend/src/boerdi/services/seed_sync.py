"""Der Auslieferungsstand aus dem Image gegen den gelebten Stand (S2).

Der Seed-Baum reist im Image mit (``Dockerfile``: ``COPY backend/seeds ./seeds``,
``WORKDIR /app``), das Backend kann ihn also zur Laufzeit lesen. Bisher kam er
nur über die CLI in die Datenbank — das brauchte SSH auf den Server. Dieses Modul
ist die Grundlage dafür, dasselbe im Studio anzubieten.

**Vergleich und Schreiben teilen sich die Quelle.** Beide Wege lesen den Baum
über ``seed_io.import_tree``; ein zweiter Leser wäre eine Driftquelle, und zwar
die gefährlichste von allen: die Zählung im Panel würde etwas anderes zeigen als
der Knopf danach tut.

**Zwei Modi, und nur einer ist harmlos.**

* ``missing`` schreibt ausschließlich Bereiche, die es in der Datenbank **nicht**
  gibt. Entspricht ``boerdi import-config --only-missing``.
* ``exact`` stellt den Auslieferungsstand her: schreibt neue **und abweichende**
  Bereiche und **löscht**, was nur in der Datenbank steht. Das vernichtet
  redaktionelle Arbeit — der Aufrufer legt vorher einen Schnappschuss an
  (``api/config_snapshots.py``). Nutzer-Entscheid 2026-08-17.

Dazu (Paket 12) der **Werksabgleich** (:func:`werksabgleich`): Fehlendes anlegen, unberührte
Bereiche auf eine neue Werksfassung heben, Angepasstes und Gelöschtes lassen — der Schritt des
``migrate``-Dienstes bei jedem Hochfahren (``import-config --werksabgleich``).
"""

from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Awaitable, Callable, Collection
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, Literal

from boerdi.services import seed_io, werkfassung

logger = logging.getLogger(__name__)

Modus = Literal["missing", "exact"]

MODI: Final = ("missing", "exact")

# src/boerdi/services/ → backend/. Zweiter Anker der Pfadsuche in ``seed_pfad``.
_BACKEND: Final = Path(__file__).resolve().parents[2].parent


@dataclass(frozen=True)
class SeedDiff:
    """Was der Seed gegenüber dem gelebten Stand bedeutet — je Liste Bereichs-Schlüssel."""

    neu: list[str] = field(default_factory=list)
    gleich: list[str] = field(default_factory=list)
    abweichend: list[str] = field(default_factory=list)
    nur_in_db: list[str] = field(default_factory=list)

    def zu_schreiben(self, modus: Modus) -> list[str]:
        """Welche Bereiche dieser Modus schreibt — sortiert, damit ein zweiter
        Aufruf dieselbe Reihenfolge zeigt wie der erste."""
        if modus == "missing":
            return sorted(self.neu)
        return sorted([*self.neu, *self.abweichend])

    def zu_loeschen(self, modus: Modus) -> list[str]:
        """Nur ``exact`` löscht. ``missing`` fasst Bestehendes nicht an — das ist
        der ganze Unterschied zwischen dem harmlosen und dem scharfen Knopf."""
        return sorted(self.nur_in_db) if modus == "exact" else []


def vergleiche(seed: dict[str, Any], live: dict[str, Any]) -> SeedDiff:
    """Seed gegen gelebten Stand. Rein — kein I/O, damit testbar ohne Datenbank.

    Verglichen werden die geparsten Dokumente, nicht ihr Text: der Seed kommt aus
    YAML/Markdown, die Datenbank aus ``jsonb``. Dieselben Daten nehmen also zwei
    Wege, und ein Vergleich über Zeichenketten oder Schlüssel-Reihenfolge meldete
    Abweichungen, die es nicht gibt. Python-Gleichheit auf verschachtelten
    dict/list-Bäumen ist genau der richtige Maßstab.
    """
    gemeinsam = seed.keys() & live.keys()
    return SeedDiff(
        neu=sorted(seed.keys() - live.keys()),
        gleich=sorted(k for k in gemeinsam if seed[k] == live[k]),
        abweichend=sorted(k for k in gemeinsam if seed[k] != live[k]),
        nur_in_db=sorted(live.keys() - seed.keys()),
    )


def seed_pfad(roh: str) -> Path | None:
    """Den ausgelieferten Baum finden, oder ``None`` — dann bleibt das Panel aus.

    ``CONFIG_SEED_DIR`` ist als **relative** Angabe voreingestellt (``seeds``),
    und das mit Absicht: im Bild liegt der Baum unter ``/app/seeds``, das
    Arbeitsverzeichnis ist ``/app``, und die CLI löst genau so auf. Ein Backend,
    das lokal aus dem Wurzelverzeichnis gestartet wird, sieht dort aber nichts —
    deshalb der zweite Anker ``backend/``. Kein Raten: beide Kandidaten müssen
    ein echtes Verzeichnis sein, sonst ``None``.

    ``None`` ist kein Fehler, sondern eine Aussage: dieses Bild bringt keinen
    Auslieferungsstand mit (fremd gebaut, Variable falsch gesetzt). Der Endpunkt
    antwortet dann ``available: false`` statt mit einem 500.
    """
    angabe = (roh or "").strip()
    if not angabe:
        return None
    kandidat = Path(angabe)
    if kandidat.is_absolute():
        return kandidat if kandidat.is_dir() else None
    for pfad in (Path.cwd() / kandidat, _BACKEND / kandidat):
        if pfad.is_dir():
            return pfad
    return None


async def anwenden(
    diff: SeedDiff,
    seed: dict[str, Any],
    modus: Modus,
    *,
    schreiben: Callable[[str, dict[str, Any]], Awaitable[Any]],
    loeschen: Callable[[str], Awaitable[Any]],
) -> dict[str, int]:
    """Den Auslieferungsstand herstellen — Bericht: ``{written, deleted}``.

    Die beiden Rückrufe halten dieses Modul von der Loader-Fassade frei und
    machen den Ablauf ohne Datenbank prüfbar (dieselbe Naht wie ``import_tree``).

    **Erst schreiben, dann löschen.** Bricht der Lauf mitten im Lösch-Durchgang
    ab, ist der Stand eine Obermenge des Seeds — es fehlt nichts. Umgekehrt stünde
    die Konfiguration zeitweise unvollständig da, und eine Replika, die in genau
    diesem Moment liest, servierte eine Lücke.

    Ein unbekannter Modus ist ein Fehler, kein Rückfall: ein Tippfehler darf nicht
    stillschweigend den verlustbehafteten Weg wählen.
    """
    if modus not in MODI:
        raise ValueError(f"unbekannter Modus {modus!r} — erlaubt: {MODI}")
    zu_schreiben = diff.zu_schreiben(modus)
    zu_loeschen = diff.zu_loeschen(modus)
    for area in zu_schreiben:
        await schreiben(area, seed[area])
    for area in zu_loeschen:
        await loeschen(area)
    return {"written": len(zu_schreiben), "deleted": len(zu_loeschen)}


async def herstellen(
    pfad: Path,
    modus: Modus,
    *,
    pruefen: Callable[[dict[str, dict[str, Any]]], dict[str, dict[str, Any]]],
    lesen: Callable[[], Awaitable[dict[str, dict[str, Any]]]],
    sichern: Callable[[dict[str, dict[str, Any]]], Awaitable[str]],
    schreiben: Callable[[dict[str, dict[str, Any]], list[str]], Awaitable[Any]],
    entfernt: Collection[str] = (),
    geschuetzt: Collection[str] = (),
) -> dict[str, Any]:
    """Den Auslieferungsstand herstellen — ein Ablauf für Studio und
    Kommandozeile (Paket 6, W2). Bericht: ``{written, deleted, snapshot_id}``.

    1. Seed lesen und **prüfen**, wie ein Wiederherstellen prüft (``pruefen``
       gibt die schreibbaren Bereiche zurück oder wirft). Bis Paket 6 schrieb
       das Anwenden ungeprüft; ein ungültiger Seed bricht jetzt ab, bevor etwas
       gesichert oder geschrieben ist.
    2. Den gelebten Stand **einmal** lesen. Schnappschuss (nur ``exact``) und
       Vergleich kommen aus demselben Lesevorgang — vorher waren es zwei, und
       ein Speichern dazwischen wurde überschrieben, stand aber nicht im
       Schnappschuss.
    3. Schreiben und löschen mit ``schreiben`` in einem Rutsch (der Aufrufer
       legt beides in eine Transaktion, Paket 4 D4).

    Die Rückrufe halten das Modul frei von Studio, Datenbank und Kommandozeile;
    die Grenze für Schnappschüsse prüft ``sichern``.
    """
    if modus not in MODI:
        raise ValueError(f"unbekannter Modus {modus!r} — erlaubt: {MODI}")
    seed = pruefen(await seed_lesen(pfad))
    live = await lesen()
    snapshot_id = await sichern(live) if modus == "exact" else None
    zu_schreiben: dict[str, dict[str, Any]] = {}
    zu_loeschen: list[str] = []

    async def _vormerken(area: str, data: dict[str, Any]) -> None:
        zu_schreiben[area] = data

    async def _streichen(area: str) -> None:
        zu_loeschen.append(area)

    diff = vergleiche(seed, live)
    # Paket 12: ``missing`` holt im Studio gelöschte Werksbereiche nicht zurück (Review 2 #7;
    # ``exact`` stellt den ganzen Werksstand her, auch sie); ein Bereich mit stillgelegter eigener
    # Fassung wird nie gelöscht (Review 2 #1) — er bleibt und wird gemeldet.
    if modus == "missing":
        diff = replace(diff, neu=[a for a in diff.neu if a not in entfernt])
    behalten = sorted(set(diff.nur_in_db) & set(geschuetzt))
    diff = replace(diff, nur_in_db=[a for a in diff.nur_in_db if a not in geschuetzt])
    bericht = await anwenden(diff, seed, modus, schreiben=_vormerken, loeschen=_streichen)
    await schreiben(zu_schreiben, zu_loeschen)
    # Erst nach dem Schreiben (Review Paket 6): ``anwenden`` merkt hier nur vor.
    logger.info("Auslieferungsstand angewandt (%s): %d geschrieben, %d gelöscht",
                modus, bericht["written"], bericht["deleted"])
    return {**bericht, "snapshot_id": snapshot_id, "behalten": behalten}


async def seed_lesen(pfad: Path) -> dict[str, dict[str, Any]]:
    """Den Seed-Baum als Bereichs-Abbild lesen — ohne etwas zu schreiben.

    ``import_tree`` erwartet einen Schreib-Rückruf; hier sammelt er nur ein.
    Damit ist garantiert, dass der Vergleich dieselben Bereiche und dieselbe
    Parse-Logik sieht wie ein echter Import (Frontmatter-Trennung bei ``.md``,
    Schlüssel-Normalisierung bei YAML).

    **Je Prozess einmal** (Paket 12, Review #4): Lesen und Parsen kostet für ~60 Bereiche rund
    360 ms und lief synchron auf dem Event-Loop — jeder Studio-Aufruf hielt die Chat-Züge der
    Replika an. Der Baum ist im Abbild unveränderlich; gelesen wird deshalb in einem Thread und
    nur neu, wenn sich Name, Größe oder Zeitstempel einer Datei ändern (lokale Entwicklung). Jeder
    Aufrufer bekommt eine eigene Kopie — ein Schreibender träfe sonst den Speicher.
    """
    schluessel = str(pfad)
    signatur = await asyncio.to_thread(_signatur, pfad)
    treffer = _SEED_SPEICHER.get(schluessel)
    if treffer is None or treffer[0] != signatur:
        treffer = (signatur, await asyncio.to_thread(_lesen, pfad))
        _SEED_SPEICHER[schluessel] = treffer
    return copy.deepcopy(treffer[1])


_SEED_SPEICHER: dict[str, tuple[tuple[tuple[str, int, int], ...], dict[str, dict[str, Any]]]] = {}


def _signatur(pfad: Path) -> tuple[tuple[str, int, int], ...]:
    eintraege = []
    for datei in pfad.rglob("*"):
        if datei.is_file():
            st = datei.stat()
            eintraege.append((datei.relative_to(pfad).as_posix(), st.st_mtime_ns, st.st_size))
    return tuple(sorted(eintraege))


def _lesen(pfad: Path) -> dict[str, dict[str, Any]]:
    """Im Thread: ``import_tree`` ist async, läuft hier auf einer eigenen Schleife."""
    gesammelt: dict[str, dict[str, Any]] = {}

    async def einsammeln(area: str, data: dict[str, Any]) -> None:
        gesammelt[area] = data

    stats = asyncio.run(seed_io.import_tree(pfad, einsammeln))
    logger.info("Seed gelesen: %d Bereiche (%d yaml, %d md) aus %s",
                stats["areas"], stats["yaml"], stats["md"], pfad)
    return gesammelt


async def werksabgleich(
    pfad: Path,
    *,
    pruefen: Callable[[dict[str, dict[str, Any]]], dict[str, dict[str, Any]]],
    lesen: Callable[[], Awaitable[list[dict[str, Any]]]],
    entfernte: Callable[[], Awaitable[set[str]]],
    schreiben: Callable[
        [dict[str, tuple[dict[str, Any], str, int | None, dict[str, Any] | None]]],
        Awaitable[dict[str, int]]],
    zuordnen: Callable[[dict[str, str]], Awaitable[Any]],
    kollisionen: Callable[[dict[str, dict[str, Any]], dict[str, dict[str, Any]]], set[str]]
    | None = None,
) -> dict[str, int]:
    """Die Werksfassung nachziehen, ohne Angepasstes anzufassen (Paket 12).

    Anders als ``missing`` hebt er unberührte Bereiche auf eine neue Werksfassung, anders als
    ``exact`` überschreibt und löscht er nie, was jemand angepasst hat — deshalb ohne
    Schnappschuss, und deshalb darf ihn der ``migrate``-Dienst bei jedem Hochfahren ausführen.
    Ablauf: Seed lesen und prüfen (wie ``herstellen``), gelebten Stand einmal lesen
    (``lesen``: Zeilen mit ``area, data, werk_hash, updated_by, version``), planen, schreiben,
    gleichende Bereiche nur zuordnen.

    **Bedingt schreiben** (Review #2): ``schreiben`` bekommt je Bereich ``(Werksfassung,
    Prüfsumme, gelesene Version, stillzulegender alter Inhalt oder None)`` und schreibt nur,
    was sich seit dem Lesen nicht geändert hat — ``migrate`` läuft, während alte Replikas noch
    bedienen. Was dazwischen gespeichert, gelöscht oder umgeschaltet wurde, zählt als
    ``uebersprungen``; der nächste Abgleich sieht es neu.
    **Kennungs-Kollisionen** (Review #6, ``kollisionen``: zu schreibende Bereiche gegen den
    Bestand → kollidierende): übersprungen und als ``konflikt`` gemeldet, nicht abgebrochen.
    """
    seed = pruefen(await seed_lesen(pfad))
    zeilen = {z["area"]: z for z in await lesen()}
    plan = werkfassung.plane_werksabgleich(seed, zeilen, entfernt=await entfernte())
    konflikt = (kollisionen(plan.schreiben, {a: z["data"] for a, z in zeilen.items()})
                if kollisionen and plan.schreiben else set())
    for area in konflikt:
        plan.neu -= plan.versionen[area] is None
        del plan.schreiben[area], plan.versionen[area]
    eintraege = {a: (d, werkfassung.pruefsumme(d), plan.versionen[a], plan.parken.get(a))
                 for a, d in plan.schreiben.items()}
    geschrieben = await schreiben(eintraege) if eintraege else {}
    if plan.zuordnen:
        await zuordnen(plan.zuordnen)
    # Gezählt wird, was geschrieben wurde, nicht was geplant war (Review 2 #3).
    neu = sum(1 for a in geschrieben if plan.versionen[a] is None)
    bericht = {**plan.bericht(), "neu": neu, "aktualisiert": len(geschrieben) - neu,
               "uebersprungen": len(eintraege) - len(geschrieben), "konflikt": len(konflikt)}
    if konflikt:
        logger.warning("Werksabgleich: Kennung schon vergeben, nicht angelegt: %s",
                       sorted(konflikt))
    logger.info("Werksabgleich: %s", bericht)
    return bericht


async def werk_bereiche(roh_pfad: str) -> set[str]:
    """Die Bereiche der Werksfassung (``CONFIG_SEED_DIR``) — leer ohne Seed. Für Löschwege, die
    wissen müssen, ob ein Bereich zum Werk gehört (Löschvermerk, Paket 12 Review 2 #2)."""
    pfad = seed_pfad(roh_pfad)
    return set() if pfad is None else set(await seed_lesen(pfad))

