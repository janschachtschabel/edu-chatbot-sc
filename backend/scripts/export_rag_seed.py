"""ALT-``rag_chunks`` in den Seed-Baum schreiben (`backend/seeds/rag/*.jsonl`).

Einmalig gedacht: die ALT-sqlite war die Bruecke, der Seed ist der Dauerzustand.
Danach pflegt die Redaktion die Dateien im Repositorium — oder ein spaeterer Lauf
dieses Skripts holt einen neuen ALT-Stand.

**Nur Text, keine Vektoren.** Dieselbe Begruendung wie im Import
(``services/rag/import_rag``): das Einbettungsmodell darf sich aendern, deshalb
wird beim Einlesen neu eingebettet statt Zahlen zu kopieren. Der Seed bleibt damit
lesbar, diffbar und modell-unabhaengig.

**Lesend auf der Quelle**: ``mode=ro``, nur SELECT. Die ALT-Datei wird nie
veraendert.

Aufruf::

    uv run python scripts/export_rag_seed.py --sqlite <KOPIE-der-badboerdi.db>
    uv run python scripts/export_rag_seed.py --sqlite … --to seeds/rag
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Der Leser wird NICHT nachgebaut: Auswahl und Sortierung sind der Vertrag
# zwischen beiden Quellen (siehe ``import_rag._read_seed_chunks``). Zwei Kopien
# derselben ORDER BY liefen irgendwann auseinander, und das faellt erst an
# anderen Dokumentgrenzen auf — also an einer Stelle, die niemand damit
# verbindet.
from boerdi.services.rag.import_rag import _read_alt_chunks

#: Was aus einem Bereichsnamen ein Dateiname werden darf. Alles andere wird zu
#: ``-``: der Name in der Datei bleibt unangetastet, der Dateiname ist nur
#: Lesbarkeit (siehe ``import_rag._read_seed_chunks``).
_UNSAUBER = re.compile(r"[^A-Za-z0-9._-]+")


def _dateiname(area: str) -> str:
    return _UNSAUBER.sub("-", area.strip()).strip("-.") or "ohne-bereich"


def _schreibe(zeilen: list[dict], ziel: Path) -> dict[str, int]:
    ziel.mkdir(parents=True, exist_ok=True)
    je_bereich: dict[str, list[dict]] = {}
    for z in zeilen:
        je_bereich.setdefault(z["area"], []).append(z)
    for area, gruppe in je_bereich.items():
        datei = ziel / f"{_dateiname(area)}.jsonl"
        with datei.open("w", encoding="utf-8", newline="\n") as fh:
            for z in gruppe:
                fh.write(json.dumps({
                    "area": area,
                    "title": z["title"] or "",
                    "source": z["source"] or "",
                    "chunk_index": int(z["chunk_index"] or 0),
                    "content": z["content"],
                }, ensure_ascii=False) + "\n")
    return {area: len(g) for area, g in je_bereich.items()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="export_rag_seed")
    parser.add_argument("--sqlite", required=True,
                        help="Pfad zu einer KOPIE der ALT-badboerdi.db")
    parser.add_argument("--to", dest="ziel", default="seeds/rag",
                        help="Zielverzeichnis (Vorgabe: seeds/rag)")
    args = parser.parse_args(argv)

    quelle = Path(args.sqlite)
    if not quelle.is_file():
        print(f"sqlite db not found: {quelle}", file=sys.stderr)
        return 2

    zeilen = _read_alt_chunks(quelle)
    if not zeilen:
        print("keine Zeilen in rag_chunks — nichts geschrieben", file=sys.stderr)
        return 1
    verteilung = _schreibe(zeilen, Path(args.ziel))
    for area in sorted(verteilung):
        print(f"  {area:32} {verteilung[area]:5d} Abschnitte")
    print(f"{len(zeilen)} Abschnitte in {len(verteilung)} Dateien -> {args.ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
