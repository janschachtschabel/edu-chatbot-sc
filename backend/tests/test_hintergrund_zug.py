"""Die Züge, die das Widget von sich aus schickt (Befund 2026-10-08).

Kontext-Ping und Tour-Tick sind keine Nachrichten der Person. Wer sie erkennt,
entscheidet, ob ein offener Schreibvorgang verfällt (``graph/nodes/setup``) und ob
ein Fehler als Blase erscheint (``api/chat``) — beide müssen dasselbe Protokoll
lesen wie das Widget (``context-greeting.controller.ts``, ``tour.controller.ts``).
"""

from __future__ import annotations

import pytest

from boerdi.api.schemas import Environment
from boerdi.domain.hintergrund_zug import (
    ist_hintergrund_anfrage,
    ist_kontext_ping,
    ist_tour_tick,
)


@pytest.mark.parametrize("ereignis, erwartet", [
    ("context_open", True),
    ("context_open_initial", True),
    (" Context_Open ", True),
    ("context_close", False),
    ("", False),
    (None, False),
])
def test_kontext_ping(ereignis, erwartet):
    assert ist_kontext_ping(ereignis) is erwartet


@pytest.mark.parametrize("aktion, erwartet", [
    ("tick", True),
    (" TICK ", True),
    ("start", False),
    ("", False),
    (None, False),
])
def test_tour_tick(aktion, erwartet):
    assert ist_tour_tick(aktion) is erwartet


@pytest.mark.parametrize("umgebung, erwartet", [
    ({"page_event": "context_open"}, True),
    ({"page_event": "context_open_initial"}, True),
    ({"tour_action": "tick"}, True),
    ({}, False),
    # Ein unbekanntes Ereignis beantwortet die Begrüßung nicht — der Zug läuft
    # als gewöhnlicher weiter.
    ({"page_event": "irgendwas"}, False),
    # Eine Tour-Aktion geht vor: der Tour-Knoten läuft zuerst und antwortet.
    ({"tour_action": "start", "page_event": "context_open"}, False),
])
def test_hintergrund_anfrage(umgebung, erwartet):
    assert ist_hintergrund_anfrage(Environment(**umgebung)) is erwartet
