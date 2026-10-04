"""Die Gesamtfrist eines Agent-Laufs — auch in laufenden Aufrufen (Paket 4, B1).

Bis Paket 4 prüfte die Schleife die Frist nur am Rundenanfang. Ein Modell- oder
Werkzeugaufruf, der darüber hinaus lief, lief zu Ende (externes Audit F04,
Probe: Frist 5 s, Ende nach 6 s; drei Werkzeuge à 4 s liefen alle). Jetzt läuft
jeder Aufruf höchstens bis zur Frist.

Das Ende steht als Zeitpunkt der Ereignisschleife fest (``loop.time()``), nicht
als Wert der eingereichten ``clock``: Tests fälschen diese Uhr zeilengenau, und
jede zusätzliche Abfrage verschöbe ihre Folge.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable

#: Antwort an das Modell für den Aufruf, der bei Fristende noch lief. Ob er den
#: Server erreicht hat, lässt sich von hier aus nicht sagen — also auch nicht
#: behaupten.
ABGEBROCHEN_FRIST = (
    "Abgebrochen: Die Zeit für diesen Auftrag ist abgelaufen. Ob der Aufruf den "
    "Server noch erreicht hat, ist offen."
)
#: … für die Aufrufe derselben Runde, die nicht mehr begonnen haben.
NICHT_AUSGEFUEHRT_FRIST = "Nicht ausgeführt: Die Zeit für diesen Auftrag ist abgelaufen."
#: … für die Aufrufe einer Runde, die im Stillstand endet.
NICHT_AUSGEFUEHRT_STILLSTAND = (
    "Nicht ausgeführt: Der Lauf endet hier, weil sich die Aufrufe wiederholen."
)


class FristAbgelaufen(Exception):
    """Die Gesamtfrist des Laufs ist während eines Aufrufs abgelaufen."""


def frist_ende(deadline_s: float, vergangen: float) -> float:
    """Das Fristende als Zeitpunkt der laufenden Ereignisschleife."""
    return asyncio.get_running_loop().time() + deadline_s - vergangen


async def innerhalb[T](ende: float, aufruf: Awaitable[T]) -> T:
    """``aufruf`` abwarten, aber höchstens bis ``ende``; danach :class:`FristAbgelaufen`.

    Eine Zeitüberschreitung aus dem Aufruf selbst (etwa eines Transports) bleibt
    unverändert: Nur das eigene Fristende wird zu :class:`FristAbgelaufen`.
    """
    try:
        async with asyncio.timeout_at(ende) as grenze:
            return await aufruf
    except TimeoutError:
        if grenze.expired():
            raise FristAbgelaufen from None
        raise
