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
  gibt. Entspricht ``boerdi import-config --only-missing`` und dem, was der
  ``migrate``-Dienst bei jedem Hochfahren tut.
* ``exact`` stellt den Auslieferungsstand her: schreibt neue **und abweichende**
  Bereiche und **löscht**, was nur in der Datenbank steht. Das vernichtet
  redaktionelle Arbeit — der Aufrufer legt vorher einen Schnappschuss an
  (``api/config_snapshots.py``). Nutzer-Entscheid 2026-08-17.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Literal

from boerdi.services import seed_io

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
    logger.info("Auslieferungsstand angewandt (%s): %d geschrieben, %d gelöscht",
                modus, len(zu_schreiben), len(zu_loeschen))
    return {"written": len(zu_schreiben), "deleted": len(zu_loeschen)}


async def seed_lesen(pfad: Path) -> dict[str, dict[str, Any]]:
    """Den Seed-Baum als Bereichs-Abbild lesen — ohne etwas zu schreiben.

    ``import_tree`` erwartet einen Schreib-Rückruf; hier sammelt er nur ein.
    Damit ist garantiert, dass der Vergleich dieselben Bereiche und dieselbe
    Parse-Logik sieht wie ein echter Import (Frontmatter-Trennung bei ``.md``,
    Schlüssel-Normalisierung bei YAML).
    """
    gesammelt: dict[str, dict[str, Any]] = {}

    async def einsammeln(area: str, data: dict[str, Any]) -> None:
        gesammelt[area] = data

    stats = await seed_io.import_tree(pfad, einsammeln)
    logger.info("Seed gelesen: %d Bereiche (%d yaml, %d md) aus %s",
                stats["areas"], stats["yaml"], stats["md"], pfad)
    return gesammelt
