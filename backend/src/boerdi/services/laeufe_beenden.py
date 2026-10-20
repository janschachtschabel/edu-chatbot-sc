"""Beim Herunterfahren die Läufe dieses Pods ehrlich beenden (Gesamt-Review Paket 17, C2).

Uvicorn schließt auf SIGTERM zuerst die Annahme neuer Verbindungen. Ein Eval-Lauf ruft den
Chat über die Loopback-Adresse (``EVAL_CHAT_URL``) und sammelte bis zum Ende der Gnadenfrist
nur noch Verbindungsfehler — als Lauf mit falscher Quote, womöglich „done“. Der Herzschlag
hilft erst, wenn der Prozess tot ist.

Die Registry (``obs.tasks.RUN_TASKS``) kennt die Läufe DIESES Pods; ein Besitzer je Zeile ist
dafür nicht nötig. Reihenfolge wie beim Stoppen-Knopf: erst die Zeile auf ``failed`` (nur, wo
sie noch läuft), dann den Task abbrechen — sein ``finally`` prallt an der geschlossenen Zeile
ab. Ohne auf die Tasks zu warten: die Gnadenfrist gehört den Zügen.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.obs.tasks import RUN_TASKS

logger = logging.getLogger(__name__)

GRUND: Final = "abgebrochen: Pod beendet (Rollout oder Herunterfahren)"
#: Obergrenze für die Schreibvorgänge — sie kommt von der Gnadenfrist (Values: 5 s Luft).
_FRIST_S: Final = 5.0

_LASTTEST = text(
    "UPDATE loadtest_runs SET status = 'failed', "
    "result = COALESCE(result, '{}'::jsonb) || jsonb_build_object('error', CAST(:g AS text), "
    "'finished_at', COALESCE(result->>'finished_at', CAST(:ende AS text))) "
    "WHERE id = ANY(CAST(:ids AS text[])) AND status = 'running'"
)
_EVAL = text(
    "UPDATE eval_runs SET status = 'failed', completed_at = now(), error_message = :g "
    "WHERE id = ANY(CAST(:ids AS text[])) AND status = 'running'"
)


async def beende(engine: AsyncEngine) -> int:
    """Die laufenden Läufe dieses Pods schließen und ihre Tasks abbrechen; gibt ihre Zahl."""
    ids = [run_id for run_id, task in RUN_TASKS.items() if not task.done()]
    if not ids:
        return 0
    try:
        async with asyncio.timeout(_FRIST_S), engine.begin() as conn:
            werte = {"g": GRUND, "ids": ids, "ende": datetime.now(UTC).isoformat()}
            await conn.execute(_LASTTEST, werte)
            await conn.execute(_EVAL, werte)
    except Exception:  # dann räumt der ausbleibende Herzschlag die Zeilen ab
        logger.warning("Läufe beim Herunterfahren nicht geschlossen: %s", ids, exc_info=True)
    for run_id in ids:
        task = RUN_TASKS.get(run_id)
        if task is not None:
            task.cancel()
    logger.info("Herunterfahren: %d Lauf/Läufe beendet (%s)", len(ids), ", ".join(ids))
    return len(ids)
