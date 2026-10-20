"""Herzschlag langer Läufe (Paket 17, C1/C2): verwaist ist nur, wessen Herzschlag ausbleibt.

Eval- und Lasttest-Läufe laufen als Aufgabe im Web-Prozess. Bei mehreren Repliken kann ein
anderer Pod nicht wissen, ob eine ``running``-Zeile noch lebt — bis Paket 17 galt jede beim
Prozessstart als verwaist (Lasttest) bzw. erst nach 2 h (Eval). Solange die Arbeit läuft,
schreibt dieser Helfer alle :data:`TAKT_S` Sekunden ``heartbeat_at``; die Aufräumer werten das
aus (``services/loadtest``, ``services/eval/run_store``).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable
from typing import Any

from sqlalchemy import text

log = logging.getLogger(__name__)

TAKT_S = 15.0
#: Fest verdrahtet: der Tabellenname geht in das SQL (Bezeichner sind nicht bindbar).
_TABELLEN = frozenset({"eval_runs", "loadtest_runs"})


async def mit_herzschlag[T](factory: Any, tabelle: str, run_id: str, arbeit: Awaitable[T]) -> T:
    """``arbeit`` ausführen und währenddessen den Herzschlag von ``run_id`` schreiben."""
    if tabelle not in _TABELLEN:
        if asyncio.iscoroutine(arbeit):
            arbeit.close()  # nie gestartet — sonst warnt Python „never awaited“
        raise ValueError(f"keine Lauf-Tabelle: {tabelle!r}")
    sql = text(f"UPDATE {tabelle} SET heartbeat_at = now() WHERE id = :id")  # noqa: S608

    async def schlagen() -> None:
        while True:
            try:
                async with factory() as sitzung:
                    await sitzung.execute(sql, {"id": run_id})
                    await sitzung.commit()
            except Exception:  # ein ausgefallener Schlag kostet nie den Lauf
                log.warning("Herzschlag %s/%s nicht geschrieben", tabelle, run_id, exc_info=True)
            await asyncio.sleep(TAKT_S)

    schlag = asyncio.create_task(schlagen())
    try:
        return await arbeit
    finally:
        schlag.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await schlag
