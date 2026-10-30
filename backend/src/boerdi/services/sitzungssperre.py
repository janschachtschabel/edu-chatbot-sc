"""Sitzungssperre über alle Kopien (Paket 7, P1 — P5-1, Audit C-H1).

Ein Zug hält die Sperre seiner Sitzung vom Anfang bis zum Ende — auch über die
mehreren Commits eines Zugs hinweg, an denen eine xact-Advisory-Sperre jedes Mal
fiele. Sie ist ein Eintrag in ``session_locks`` (Migration 0008):

* **Nehmen**: ``INSERT … ON CONFLICT DO UPDATE … WHERE expires_at < now()`` —
  frei oder verfallen gewinnt, sonst kommt keine Zeile zurück. Wer sie nicht
  bekommt, fragt bis ``warten_s`` nach und bekommt dann :class:`SitzungBeschaeftigt`
  (eine zweite gleichzeitige Nachricht: „Sitzung beschäftigt“). Kurze
  Überlappungen — etwa ein Kontext-Ping neben einem Zug — warten so wie bisher.
* **Halten**: eine Hintergrund-Aufgabe verlängert im Takt ``takt_s`` um ``ttl_s``.
  Stirbt die Kopie, verfällt die Sperre nach höchstens ``ttl_s``.
* **Freigeben**: nur der eigene Eintrag (``owner``), damit eine nach Ablauf
  übernommene Sperre nicht vom Verlierer gelöscht wird.

Jede Abfrage ist eine kurze eigene Transaktion: keine Verbindung bleibt über den
Zug gehalten (der Pool reicht sonst bei vielen parallelen Zügen nicht).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.obs.log_inhalt import kennung
from boerdi.obs.tasks import cancel_and_drain

logger = logging.getLogger(__name__)

#: Wie lange eine zweite Nachricht derselben Sitzung wartet, bevor sie
#: „beschäftigt“ hört. Ein Zug dauert meist 5–15 s.
WARTEN_S = 20.0
#: Abstand der Nachfragen beim Warten.
ABFRAGE_S = 0.5
#: Ablauf ohne Verlängerung — so lange blockiert ein abgestürzter Zug höchstens.
TTL_S = 60
#: Takt der Verlängerung; deutlich unter ``TTL_S``.
TAKT_S = 20.0

_NEHMEN = text("""
    INSERT INTO session_locks (session_id, owner, expires_at)
    VALUES (:sid, :owner, now() + make_interval(secs => :ttl))
    ON CONFLICT (session_id) DO UPDATE
       SET owner = EXCLUDED.owner, expires_at = EXCLUDED.expires_at
     WHERE session_locks.expires_at < now()
    RETURNING owner
""")
_VERLAENGERN = text("""
    UPDATE session_locks SET expires_at = now() + make_interval(secs => :ttl)
     WHERE session_id = :sid AND owner = :owner
""")
_FREIGEBEN = text("DELETE FROM session_locks WHERE session_id = :sid AND owner = :owner")


class SitzungBeschaeftigt(Exception):
    """Ein anderer Zug derselben Sitzung läuft noch (auch auf einer anderen Kopie)."""

    #: Kennung im SSE-``error``-Rahmen — das Widget zeigt dazu seinen eigenen Text.
    sse_code = "session_busy"


async def _nehmen(engine: AsyncEngine, sid: str, owner: str, ttl_s: float) -> bool:
    async with engine.begin() as conn:
        zeile = (await conn.execute(_NEHMEN, {"sid": sid, "owner": owner, "ttl": ttl_s})).first()
    return zeile is not None


async def _verlaengern(engine: AsyncEngine, sid: str, owner: str,
                       ttl_s: float, takt_s: float) -> None:
    while True:
        await asyncio.sleep(takt_s)
        try:
            async with engine.begin() as conn:
                ergebnis = await conn.execute(
                    _VERLAENGERN, {"sid": sid, "owner": owner, "ttl": ttl_s})
        except Exception:
            # Ein Aussetzer kostet nur einen Takt; erst nach ``ttl_s`` ohne
            # Erfolg kann ein anderer Zug übernehmen.
            logger.warning("Sitzungssperre %s: Verlängerung fehlgeschlagen", kennung(sid),
                           exc_info=True)
            continue
        if ergebnis.rowcount == 0:
            # Review Paket 7, A-8: nach ``ttl_s`` ohne Verlängerung hat ein anderer
            # Zug übernommen — beide laufen jetzt parallel. Nicht zu ändern, aber
            # zu sehen; weiter zu verlängern hieße, es bei jedem Takt neu zu melden.
            logger.warning("Sitzungssperre %s: verloren — ein anderer Zug hält sie "
                           "(länger als %s s ohne Verlängerung)", kennung(sid), ttl_s)
            return


@contextlib.asynccontextmanager
async def sitzungssperre(
    engine: AsyncEngine, session_id: str, *,
    warten_s: float = WARTEN_S, abfrage_s: float = ABFRAGE_S,
    ttl_s: float = TTL_S, takt_s: float = TAKT_S,
) -> AsyncIterator[None]:
    """Halte die Sperre der Sitzung für die Dauer des Blocks — oder wirf
    :class:`SitzungBeschaeftigt`, wenn sie in ``warten_s`` nicht frei wird."""
    owner = uuid4().hex
    frist = time.monotonic() + warten_s
    while not await _nehmen(engine, session_id, owner, ttl_s):
        if time.monotonic() >= frist:
            raise SitzungBeschaeftigt(session_id)
        await asyncio.sleep(abfrage_s)
    waechter = asyncio.create_task(_verlaengern(engine, session_id, owner, ttl_s, takt_s))
    try:
        yield
    finally:
        # Paket 18E: ein Abbruch des Zugs während des Wartens kommt durch — die Freigabe
        # läuft trotzdem (inneres ``finally``).
        try:
            await cancel_and_drain([waechter])
        finally:
            try:
                async with engine.begin() as conn:
                    await conn.execute(_FREIGEBEN, {"sid": session_id, "owner": owner})
            except Exception:
                # Ohne Freigabe verfällt sie nach ``ttl_s`` — kein Grund, den Zug
                # nachträglich scheitern zu lassen.
                logger.warning("Sitzungssperre %s: Freigabe fehlgeschlagen",
                               kennung(session_id), exc_info=True)
