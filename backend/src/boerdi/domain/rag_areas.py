"""Die zwei Bereichs-Listen zu einer machen (Paket R).

**Der Befund** (gemessen 2026-08-18): Wissensbereiche stehen an zwei Stellen, und
die beiden koennen still auseinanderlaufen.

* Was in der **Datenbank** liegt: ``services/rag/admin.list_areas`` gruppiert
  ueber ``RagChunk.area``. Daraus speist sich die Wissen-Seite im Studio.
* Was in der **Konfiguration** steht: ``config_loader.load_rag_config`` behaelt
  nur Eintraege mit ``mode``. Daraus speist sich, was der Chatbot durchsucht.

Wer im Studio beim Einlesen einen neuen Bereichsnamen tippt, legt ihn nur in der
Datenbank an. Der Chatbot durchsucht ihn nie — und nichts sagte es. Das ist die
teuerste Sorte Fehler, weil sie wie ein Bedienfehler aussieht: die Dokumente sind
sichtbar, die Antworten kennen sie nicht.

Diese Funktion **behebt den Zustand nicht, sie macht ihn sichtbar**. Absicht: die
Konfiguration soll weiterhin entscheiden, was der Chatbot nutzt. Wuerde ein
eingelesener Bereich automatisch mitgesucht, waere das Einlesen zugleich eine
Freigabe — und ein Probe-Upload aenderte still das Verhalten im Betrieb.
"""

from __future__ import annotations

from typing import Any


def zusammenfuehren(
    db_zeilen: list[dict[str, Any]], rag_config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Datenbank-Bestand und Konfiguration zu EINER Liste, nach Namen sortiert.

    Jede Zeile traegt ``configured``: steht der Bereich in der Konfiguration?
    Bereiche, die nur dort stehen, kommen mit ``chunks``/``documents`` = 0 dazu —
    sonst bliebe der zweite Fall unsichtbar (angekuendigt, aber immer leer).
    """
    zusammen: dict[str, dict[str, Any]] = {}
    for zeile in db_zeilen:
        name = zeile["area"]
        zusammen[name] = {
            "area": name,
            "chunks": zeile.get("chunks", 0),
            "documents": zeile.get("documents", 0),
            "configured": name in rag_config,
        }
    for name in rag_config:
        if name not in zusammen:
            zusammen[name] = {"area": name, "chunks": 0, "documents": 0,
                              "configured": True}
    return [zusammen[name] for name in sorted(zusammen)]
