"""Züge, die das Widget von sich aus schickt — nicht die Person (Befund 2026-10-08).

Zwei gibt es (``frontend/projects/ui/src/controllers``):

* den **Kontext-Ping** ``[context-open]`` mit ``page_event`` ``context_open`` bzw.
  ``context_open_initial`` — beim ersten Laden, bei jeder Änderung der Gastseite
  und bei ``replaceContext`` der Browser-Erweiterung. Beantwortet wird er von
  ``graph/nodes/context_greeting``.
* den **Tour-Tick** ``[tour-tick]`` mit ``tour_action: tick`` — bei jedem
  Seitenaufruf mit gesetztem Tour-Flag oder über einen ``?bsid=``-Link.
  Beantwortet wird er von ``graph/nodes/tour``.

Das Widget zeigt ihre Antwort nur, wenn sie Inhalt hat, und schluckt ihre Fehler
still. Für die Person sind sie deshalb kein Zug, solange sie nichts zeigen. Wer
eine Regel „nur der direkt folgende Zug zählt“ baut, muss sie ausnehmen — die
Schreib-Abnahme verfiel bis 2026-10-08 an einem stummen Ping.
"""

from __future__ import annotations

from typing import Protocol

KONTEXT_PING_FORTSETZUNG = "context_open"
KONTEXT_PING_ERSTLADEN = "context_open_initial"
TOUR_TICK = "tick"


class _Umgebung(Protocol):
    page_event: str | None
    tour_action: str | None


def _wort(wert: str | None) -> str:
    return (wert or "").strip().lower()


def ist_kontext_ping(page_event: str | None) -> bool:
    """Trägt der Zug eines der beiden Ping-Ereignisse?"""
    return _wort(page_event) in (KONTEXT_PING_FORTSETZUNG, KONTEXT_PING_ERSTLADEN)


def ist_tour_tick(tour_action: str | None) -> bool:
    """Ist der Zug der Tour-Tick?"""
    return _wort(tour_action) == TOUR_TICK


def ist_hintergrund_anfrage(umgebung: _Umgebung) -> bool:
    """Hat das Widget diesen Zug von sich aus geschickt?

    Eine Tour-Aktion geht vor: der Tour-Knoten läuft vor der Begrüßung, und jede
    andere Aktion als der Tick (``start`` usw.) ist ein Klick der Person.
    """
    if _wort(umgebung.tour_action):
        return ist_tour_tick(umgebung.tour_action)
    return ist_kontext_ping(umgebung.page_event)
