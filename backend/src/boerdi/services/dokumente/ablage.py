"""Ablage hochgeladener Dokumente (Paket U3-2a, Plan 2026-11-04 §16.6).

Tabelle ``dokument_uploads``, ein Dokument je Sitzung: ein neues ersetzt das alte (eine
Transaktion). Gelesen wird nur in derselben Sitzung und — bei angemeldeten Personen — unter
demselben Kennzeichen; ein anonym gelesenes Dokument übernimmt die Person, die sich in derselben
Sitzung anmeldet (:func:`zuschreiben`, TB-E1). Eine abgelaufene Zeile (``verfaellt_am`` vorbei)
ist sofort unlesbar; physisch weg ist sie nach dem Aufbewahrungslauf
(:func:`verfallene_loeschen`) oder dem nächsten Hochladen derselben Sitzung. Kennungen uuid4.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import DokumentUpload
from boerdi.services import vorgaenge


def _jetzt() -> datetime:
    return datetime.now(UTC)


async def speichern(s: AsyncSession, *, session_id: str, block_id: str, aufrufer: str | None,
                    name: str, format: str, groesse: int, befund: dict[str, Any],
                    gliederung: list[dict[str, Any]], markdown: str, ttl_h: float) -> str:
    """Speichert das Dokument der Sitzung (ersetzt ein vorhandenes); gibt die Kennung zurück.
    Der Aufrufer schreibt die Transaktion fest."""
    ersetzt = await s.execute(delete(DokumentUpload).where(DokumentUpload.session_id == session_id)
                              .returning(DokumentUpload.id))
    if ids := list(ersetzt.scalars()):
        # Review Q3, Befund 7: das ersetzte Dokument nimmt seinen Teil in Vorgängen mit.
        await vorgaenge.dokument_teile_entfernen(s, ids)
    jetzt = _jetzt()
    kennung = str(uuid.uuid4())
    s.add(DokumentUpload(id=kennung, session_id=session_id, block_id=block_id, aufrufer=aufrufer,
                         name=name, format=format, groesse=groesse, befund=befund,
                         gliederung=gliederung, markdown=markdown, erstellt=jetzt, genutzt=jetzt,
                         verfaellt_am=jetzt + timedelta(hours=ttl_h)))
    await s.flush()
    return kennung


def _lesbar(session_id: str, aufrufer: str | None):  # noqa: ANN202 — SQLAlchemy-Ausdruck
    bedingung = (DokumentUpload.session_id == session_id) & (DokumentUpload.verfaellt_am > _jetzt())
    if aufrufer is not None:
        bedingung &= DokumentUpload.aufrufer == aufrufer
    else:
        bedingung &= DokumentUpload.aufrufer.is_(None)
    return bedingung


async def lesen(s: AsyncSession, session_id: str, upload_id: str, aufrufer: str | None
                ) -> DokumentUpload | None:
    stmt = select(DokumentUpload).where(_lesbar(session_id, aufrufer),
                                        DokumentUpload.id == upload_id)
    return (await s.execute(stmt)).scalar_one_or_none()


async def aktuelles(s: AsyncSession, session_id: str, aufrufer: str | None
                    ) -> DokumentUpload | None:
    return (await s.execute(select(DokumentUpload).where(_lesbar(session_id, aufrufer)))
            ).scalar_one_or_none()


async def zuschreiben(s: AsyncSession, session_id: str, aufrufer: str
                      ) -> DokumentUpload | None:
    """Plan 2026-11-10, TB-E1 (Nutzer-Entscheid N2): Das anonym gelesene Dokument dieser Sitzung
    gehört ab jetzt der angemeldeten Person, die damit arbeitet. Nur ein noch lesbares Dokument
    **ohne** Besitzerin derselben Sitzung — eines, das schon einer Person gehört, bleibt bei ihr.
    Abmelden gibt es nicht wieder frei (anonym liest nur ``aufrufer IS NULL``). Der Aufrufer
    schreibt fest."""
    ergebnis = await s.execute(
        update(DokumentUpload).where(_lesbar(session_id, None))
        .values(aufrufer=aufrufer).returning(DokumentUpload))
    return ergebnis.scalar_one_or_none()


async def fuer_aufrufer(s: AsyncSession, session_id: str, aufrufer: str | None
                       ) -> DokumentUpload | None:
    """Das Dokument der Sitzung für diesen Aufrufer — einziger Leseweg für den Zug (Lader und
    Teil ``document``; Review TB-E1, Befund 1). Eine angemeldete Person ohne eigenes Dokument
    übernimmt das anonyme (:func:`zuschreiben`). Findet sie keins mehr ohne Besitzerin, hat es ein
    paralleler Zug derselben Person gerade übernommen — dann liest sie noch einmal (Befund 2).
    Der Aufrufer schreibt fest."""
    zeile = await aktuelles(s, session_id, aufrufer)
    if zeile is not None or aufrufer is None:
        return zeile
    return (await zuschreiben(s, session_id, aufrufer)
            or await aktuelles(s, session_id, aufrufer))


async def beruehren(s: AsyncSession, upload_id: str, *, ttl_h: float) -> None:
    """Nutzung vermerken: die Frist beginnt neu."""
    jetzt = _jetzt()
    await s.execute(update(DokumentUpload).where(DokumentUpload.id == upload_id)
                    .values(genutzt=jetzt, verfaellt_am=jetzt + timedelta(hours=ttl_h)))


async def loeschen(s: AsyncSession, session_id: str, upload_id: str) -> None:
    """Löscht nur in der eigenen Sitzung — eine fremde Kennung bewirkt nichts (verrät nichts). Der
    Teil ``document`` in Vorgängen geht mit (Querschnitts-Review 2026-11-06)."""
    weg = await s.execute(delete(DokumentUpload).where(DokumentUpload.id == upload_id,
                                                       DokumentUpload.session_id == session_id)
                          .returning(DokumentUpload.id))
    if ids := list(weg.scalars()):
        await vorgaenge.dokument_teile_entfernen(s, ids)


async def der_sitzung_loeschen(s: AsyncSession, session_id: str) -> int:
    """„Arbeitsstand löschen“: das Dokument der Sitzung samt seinem Teil in Vorgängen. Der
    Aufrufer schreibt fest."""
    weg = await s.execute(delete(DokumentUpload).where(DokumentUpload.session_id == session_id)
                          .returning(DokumentUpload.id))
    if ids := list(weg.scalars()):
        await vorgaenge.dokument_teile_entfernen(s, ids)
    return len(ids)


async def verfallene_loeschen(sitzungen: async_sessionmaker[AsyncSession], jetzt: datetime) -> int:
    """Für den Aufbewahrungslauf: alle abgelaufenen Dokumente; Zahl der gelöschten."""
    async with sitzungen() as s:
        ergebnis = await s.execute(
            delete(DokumentUpload).where(DokumentUpload.verfaellt_am <= jetzt)
            .returning(DokumentUpload.id))
        ids = list(ergebnis.scalars())
        # Mit dem Dokument geht sein Teil in Vorgängen (Querschnitts-Review 2026-11-06) — auch
        # der eines Dokuments, das auf anderem Weg ging (Review Q3, Befund 7).
        await vorgaenge.dokument_teile_entfernen(s, ids)
        await vorgaenge.verwaiste_dokument_teile_entfernen(s)
        await s.commit()
    return len(ids)
