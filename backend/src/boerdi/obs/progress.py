"""Turn-Fortschritt für den SSE-Stream (C9) — die Naht, durch die ein Graph-Knoten
mitten im Zug melden kann, woran er gerade arbeitet.

Warum es das gibt: ``/api/chat/stream`` sendete nur ``connected`` und ``result``,
also 6-10 s Spinner ohne Rückmeldung. Der Konsument war längst gebaut —
``ui/stream/phase-label.ts`` (Verbatim-Port aus ALT ``chat/chat-text-utils.ts``)
übersetzt ``step``-Werte in deutsche Ladetexte —, nur sendete niemand.

Vertrag (ALT ``trace_service.Tracer`` + Listener in ``chat.py:405``): je Ereignis
ein ``{"kind", "step", "label", "data"}``-Dict. ``kind`` ist ``"start"`` oder
``"record"``; ``"end"`` sendet NEU bewusst nicht (simplify: der einzige Konsument
verwirft ``kind === "end"``, und ALTs ``end`` trug ``duration_ms`` für die
Studio-Trace-Ansicht, die NEU mit dem Tracer gedroppt hat — kommt der Tracer
zurück, kommt ``end`` mit ihm).

Abgrenzung zum Tracer: dieses Modul ist **Transport**, kein Rekorder. Es sammelt
keine Einträge und füllt ``debug.trace`` nicht — das bleibt Aufgabe des
zurückgestellten Tracer-Subsystems, das denselben Sink bedienen kann.

Kein Modul-Global (Regel 3): die Instanz wird pro Anfrage in ``build_turn_graph``
gebunden und über ``functools.partial`` in die Knoten injiziert — dieselbe
DI-Naht wie ``session``/``peer_ip``/``on_token``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Nimmt EIN fertiges Ereignis-Dict entgegen. Muss synchron und nicht-blockierend
# sein — der Sink läuft im Turn-Task, nicht im Stream-Generator.
EventSink = Callable[[dict[str, Any]], None]


class TurnProgress:
    """Meldet Fortschritts-Ereignisse eines Turns an einen Sink.

    Ohne Sink (``TurnProgress()``) ist jede Methode ein No-op — so rufen die
    Knoten unbedingt auf, und der nicht-streamende ``POST /api/chat`` baut
    denselben Graphen ohne Sonderfall.
    """

    def __init__(self, sink: EventSink | None = None) -> None:
        self._sink = sink

    def start(self, step: str, label: str = "") -> None:
        """Ein Schritt beginnt — das Ereignis, aus dem das Widget ein Label macht."""
        self._emit("start", step, label, {})

    def record(self, step: str, label: str = "", data: dict[str, Any] | None = None) -> None:
        """Ein Schritt ist als Punkt-Ereignis passiert (ALT ``Tracer.record``)."""
        self._emit("record", step, label, dict(data or {}))

    def _emit(self, kind: str, step: str, label: str, data: dict[str, Any]) -> None:
        """Zustellen und Sink-Ausnahmen schlucken.

        Ein defekter oder verschwundener Verbraucher darf den Zug nicht
        abbrechen — genau die Garantie aus ALT ``Tracer._emit``. Fortschritt ist
        verlierbar: die Labels sind idempotent und rein informativ.
        """
        if self._sink is None:
            return
        try:
            # ``label or step`` verbatim aus ALT ``Tracer.start``.
            self._sink({"kind": kind, "step": step, "label": label or step, "data": data})
        except Exception:
            logger.debug("progress sink raised", exc_info=True)


# Geteilter Default für Knoten, die ohne Stream laufen (POST /api/chat, Unit-Tests).
# Kein Verstoß gegen „kein Modul-Global-State": das Objekt ist zustandslos und
# effektiv unveränderlich — ``_sink`` wird nur im Konstruktor gesetzt, und ohne
# Sink tut jede Methode nichts. Es gibt hier nichts, was zwischen Anfragen lecken
# könnte; die echte, sink-tragende Instanz entsteht pro Anfrage in ``_stream_turn``.
NO_PROGRESS = TurnProgress()
