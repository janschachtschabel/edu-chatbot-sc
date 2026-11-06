"""Aufträge eines Vorgangs in ``vorgang_auftraege`` (Paket K1a, Migration 0019).

Je Vorgang höchstens ein offener Auftrag: ein neuer setzt den offenen auf ``abgebrochen`` (ein Lauf
wartet immer nur auf einen). Gespeichert wird nur die Job-ID — nie der Schlüssel. Wer zu einem
Vorgang fragt, hat dessen Besitz schon über ``vorgaenge.lesen`` geprüft.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value

from boerdi.db.models import VorgangAuftrag

LAEUFT: Final = "laeuft"
ENDSTAENDE: Final = frozenset({"fertig", "fehler", "abgebrochen"})


async def anlegen(s: AsyncSession, vorgang_id: str, *, job_id: str, flow: str,
                  schritt: str) -> VorgangAuftrag:
    jetzt = datetime.now(UTC)
    await s.execute(update(VorgangAuftrag)
                    .where(VorgangAuftrag.vorgang_id == vorgang_id,
                           VorgangAuftrag.status == LAEUFT)
                    .values(status="abgebrochen", geaendert=jetzt))
    a = VorgangAuftrag(id=str(uuid.uuid4()), vorgang_id=vorgang_id, job_id=job_id, flow=flow,
                       schritt=schritt, status=LAEUFT, erstellt=jetzt, geaendert=jetzt)
    s.add(a)
    await s.flush()
    return a


async def offen(s: AsyncSession, vorgang_id: str) -> VorgangAuftrag | None:
    """Der laufende Auftrag des Vorgangs — oder ``None``."""
    stmt = (select(VorgangAuftrag)
            .where(VorgangAuftrag.vorgang_id == vorgang_id, VorgangAuftrag.status == LAEUFT)
            .order_by(VorgangAuftrag.erstellt.desc()).limit(1)
            .execution_options(populate_existing=True))
    return (await s.execute(stmt)).scalar_one_or_none()


async def abschliessen(s: AsyncSession, a: VorgangAuftrag, status: str) -> bool:
    """Den Auftrag auf einen Endstand setzen — bedingt (``laeuft`` und noch da): „Arbeitsstand
    löschen“ in einem zweiten Tab nimmt ihn per Kaskade mit; das ORM-Update träfe dann 0 Zeilen
    (``StaleDataError``, 500; Review Q3, Nachprüfung, Befund 6). ``True``, wenn gesetzt."""
    if status not in ENDSTAENDE:
        raise ValueError(f"kein Endstand: {status}")
    jetzt = datetime.now(UTC)
    ergebnis = await s.execute(
        update(VorgangAuftrag).where(VorgangAuftrag.id == a.id, VorgangAuftrag.status == LAEUFT)
        .values(status=status, geaendert=jetzt).execution_options(synchronize_session=False))
    # Das Objekt zeigt den neuen Stand, ohne als geändert zu gelten (kein zweites Update).
    set_committed_value(a, "status", status)
    set_committed_value(a, "geaendert", jetzt)
    return bool(ergebnis.rowcount)
