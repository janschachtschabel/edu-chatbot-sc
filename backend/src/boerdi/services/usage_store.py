"""Verbrauchszeilen schreiben (K2b) — die einzige Stelle mit SQL auf ``usage_events``.

Der Merkposten eines Zuges (``obs/usage.py``) sammelt je Modell; hier wird
daraus **eine Zeile je Modell** dieses Zuges. Warum je Modell und nicht je
LLM-Aufruf: abgerechnet wird die Sitzung, und der Merkposten summiert schon
über den Zug. Die feinere Aufteilung nach Phasen bleibt zur Diagnose im
Debug-JSONB der Nachricht — sie hat einen anderen Zweck und eine andere
Lebensdauer als die Abrechnung.

**Ein Schreibfehler darf den Zug niemals scheitern lassen.** Eine kaputte
Buchhaltung ist ärgerlich; ein Chat, der deswegen abbricht, ist ein Ausfall.
Fehler werden darum geloggt und verschluckt — bewusst die eine Stelle, an der
das richtig ist.

**Und er darf auch nichts anderes mitreißen.** Geschrieben wird auf der
anfragegebundenen Sitzung; ein blankes ``rollback()`` verwürfe alles, was auf
ihr sonst noch offen ist. Aus „die Buchhaltung ist kaputt" würde dann „ein
fremder Schreibvorgang ist still verschwunden". Der SAVEPOINT
(``begin_nested``) begrenzt die Rücknahme auf die eigenen Zeilen: die Buchung
ist der letzte Schreiber einer Anfrage, aber nicht der Eigentümer ihrer
Transaktionsgrenze.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import UsageEvent

logger = logging.getLogger(__name__)


def _warne(session_id: str) -> None:
    """Einmal formuliert, aus beiden Fehlerzweigen gerufen."""
    logger.warning(
        "usage: Verbrauchszeilen für Sitzung %s nicht geschrieben",
        session_id, exc_info=True,
    )


async def record_turn_usage(
    session: AsyncSession, session_id: str, acc: dict[str, Any] | None
) -> int:
    """Den Merkposten eines Zuges als Zeilen ablegen; Rückgabe: geschriebene Zeilen.

    ``acc`` ist der Merkposten aus ``obs/usage.py`` (``TurnContext.usage``).
    Ein Zug ohne LLM-Aufruf hat keine Modelle und schreibt nichts — das ist der
    Normalfall bei Tour, Kontext-Begrüßung und Drosselung, kein Fehler.

    Die beiden „davon"-Werte wandern unverändert durch: ``cached`` steckt in
    ``prompt``, ``reasoning`` in ``completion``. Wer sie hier aufaddierte,
    machte die Rechnung doppelt.
    """
    modelle = (acc or {}).get("models") or {}
    if not modelle:
        return 0

    try:
        # Der SAVEPOINT schreibt beim Verlassen des Blocks; scheitert das,
        # nimmt er sich selbst zurück und lässt die umgebende Transaktion
        # stehen. Kein ``rollback()`` hier — es wäre genau der Griff, der
        # fremde offene Arbeit mitnähme (siehe Modul-Docstring).
        async with session.begin_nested():
            for name, m in modelle.items():
                session.add(UsageEvent(
                    session_id=session_id,
                    model=name or "unknown",
                    prompt_tokens=int(m.get("prompt", 0) or 0),
                    cached_tokens=int(m.get("cached", 0) or 0),
                    completion_tokens=int(m.get("completion", 0) or 0),
                    reasoning_tokens=int(m.get("reasoning", 0) or 0),
                    calls=int(m.get("calls", 0) or 0),
                ))
    except Exception:
        _warne(session_id)  # kein ``raise``: siehe Modul-Docstring
        return 0

    try:
        await session.commit()
    except Exception:
        # Hier ist der Rollback richtig: nach einem gescheiterten Commit ist
        # die Transaktion ohnehin verloren, und ohne ihn bliebe die Sitzung
        # in einem Zustand zurück, in dem jeder weitere Schreibversuch
        # scheitert.
        _warne(session_id)
        try:
            await session.rollback()
        except Exception:
            logger.debug("usage: rollback ebenfalls fehlgeschlagen", exc_info=True)
        return 0
    return len(modelle)
