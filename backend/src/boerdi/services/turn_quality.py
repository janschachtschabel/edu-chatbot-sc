"""Der Qualitäts-Eintrag eines Zuges — Tor und Aufruf an einer Stelle (2026-08-15).

**Warum es diese Datei gibt.** ``obs/quality_events`` ist bewusst ein *dummer*
Schreiber; sein Modulkopf sagt es ausdrücklich: „the enabled/privacy GATE is a
caller concern, and must stay there because one writer serves several sites with
different gating". Das Tor für den **Qualitäts**-Eintrag lautet aber für jeden
Aufrufer gleich — ``quality-log-config.logging.enabled`` UND
``privacy-config.logging.quality`` —, und es stand bis heute nur an einer
Stelle ausgeschrieben (``turn_persist``).

Die Folge war eine Lücke, kein Fehler: **jeder Zug, der vor dem
``persist``-Knoten endet, hinterliess keinen Eintrag.** Das betrifft die
Direkt-Aktionen und die Schreib-Abnahme — also gerade die Züge, die auf einen
Knopfdruck hin etwas tun. In der Auswertung sahen sie aus, als hätte es sie nie
gegeben.

Zweimal dasselbe Tor abzuschreiben wäre die naheliegende und falsche Antwort
gewesen: ein Betreiber, der die Protokollierung abschaltet, erwartet, dass sie
*überall* aus ist. Ein Tor, das an fünf Stellen kopiert ist, ist fünf
Gelegenheiten, genau das zu verletzen.

**Was hier NICHT eingetragen wird**, und warum das kein Versehen ist:

* **Tour-Takte und der Kontext-Gruss** — sie beantworten keine Frage und tragen
  kein Muster. Ihre Zeilen wären Zeilen ohne Aussage.
* **Abgewiesene Züge** (Drosselung, Sicherheits-Block) — die führen bereits ein
  *Sicherheits*-Ereignis, und das ist ihr Datensatz. Ein zweiter daneben machte
  die Zählung mehrdeutig.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from boerdi.api.schemas import ChatRequest, DebugInfo

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def log_turn_quality(
    session: AsyncSession | None,
    req: ChatRequest,
    debug: DebugInfo | dict[str, Any] | None,
    *,
    turn_count: int = 0,
    response_length: int = 0,
    cards_count: int = 0,
    page: str = "",
    device: str = "",
) -> None:
    """Schreibe den Qualitäts-Eintrag dieses Zuges — wenn beide Tore offen sind.

    ``page``/``device`` reicht der Aufrufer herein statt sie hier aus
    ``req.environment`` zu ziehen: der Hauptweg liest sie aus dem
    Laufzeit-``env`` des Setup-Knotens, und dieselben zwei Werte aus zwei
    Quellen zu holen wäre der Anfang einer Abweichung. Leer bleibt leer — die
    Spalte ist ohnehin nur eine Facette der Auswertung.

    **Bricht nie den Zug.** Ein Auswertungs-Eintrag ist Beiwerk; dass er fehlt,
    darf eine Antwort nicht kosten. Deshalb fängt diese Funktion alles ab und
    protokolliert es — dieselbe Haltung wie ``_log_turn_safety`` im Graphen.
    """
    try:
        from boerdi.services.config_loader import (
            load_privacy_config,
            load_quality_log_config,
        )
        _cfg = (load_quality_log_config().get("logging") or {})
        if not (_cfg.get("enabled", True) and load_privacy_config().get("quality", True)):
            return

        from boerdi.obs.quality_events import log_quality_event
        await log_quality_event(
            session,
            req.session_id,
            req.message,
            turn_count,
            debug.model_dump() if isinstance(debug, DebugInfo) else dict(debug or {}),
            response_length=response_length,
            cards_count=cards_count,
            page=page,
            device=device,
        )
    except Exception as err:
        logger.warning("quality log failed: %s", err)
