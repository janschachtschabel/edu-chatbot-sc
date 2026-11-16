"""Ablage hochgeladener Dokumente (Paket U3-2a, Plan 2026-11-04 §16.6).

Tabelle ``dokument_uploads``. Plan 2026-11-16, TG-3e (Nutzer: „aus einem oder mehreren
Strukturdokumenten“): bis zu :data:`MAX_JE_SITZUNG` lesbare Dokumente je Sitzung und Aufrufer; ein
weiteres ersetzt nur das älteste über der Grenze (vorher: ein Dokument je Sitzung, ein neues
ersetzte das alte). Review TG-3d–f, MINOR 5: vorher gehen die abgelaufenen der Sitzung und ein
Dokument desselben Aufrufers mit gleichem Namen und gleicher Größe (erneutes Hochladen). Gelesen
wird je Kennung oder alle zusammen (:func:`alle_fuer_aufrufer`), nur in derselben Sitzung und — bei
angemeldeten Personen — unter demselben Kennzeichen; anonym gelesene Dokumente übernimmt die
Person, die sich in derselben Sitzung anmeldet (:func:`zuschreiben`, TB-E1). Eine abgelaufene
Zeile (``verfaellt_am`` vorbei) ist sofort unlesbar; physisch weg ist sie nach dem
Aufbewahrungslauf (:func:`verfallene_loeschen`). Kennungen uuid4.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import DokumentUpload
from boerdi.services import vorgaenge

#: Plan 2026-11-16, TG-3e: so viele Strukturdokumente hält eine Sitzung höchstens.
MAX_JE_SITZUNG: Final = 5


def _jetzt() -> datetime:
    return datetime.now(UTC)


async def speichern(s: AsyncSession, *, session_id: str, block_id: str, aufrufer: str | None,
                    name: str, format: str, groesse: int, befund: dict[str, Any],
                    gliederung: list[dict[str, Any]], markdown: str, ttl_h: float) -> str:
    """Speichert ein Dokument der Sitzung; gibt die Kennung zurück. Über
    :data:`MAX_JE_SITZUNG` geht nur das älteste (TG-3e) — samt seinem Teil in Vorgängen (Review
    Q3, Befund 7). Der Aufrufer schreibt die Transaktion fest."""
    # TG-3e: zwei Uploads derselben Sitzung zugleich zählen nacheinander — sonst blieben sechs
    # liegen (die Eindeutigkeit der Sitzung, die das vorher regelte, ist weg; Migration 0023).
    await s.execute(select(func.pg_advisory_xact_lock(func.hashtext(f"dokumente:{session_id}"))))
    jetzt = _jetzt()
    # Review TG-3d–f, MINOR 5: was ohnehin weg ist oder ersetzt wird, verdrängt nichts — erst die
    # abgelaufenen der Sitzung, dann dasselbe Dokument noch einmal (erneutes Hochladen nach einem
    # Netzfehler, dessen Antwort verloren ging): derselbe Aufrufer, dasselbe Feld, gleicher Name,
    # gleiche Größe und — Nachprüfung, MINOR 3 — gleicher Text (zwei verschiedene Dokumente
    # gleichen Namens und gleicher Größe bleiben beide)
    weg = list((await s.execute(
        delete(DokumentUpload).where(
            DokumentUpload.session_id == session_id,
            (DokumentUpload.verfaellt_am <= jetzt) | (
                _gleicher_aufrufer(aufrufer) & (DokumentUpload.block_id == block_id)
                & (DokumentUpload.name == name) & (DokumentUpload.groesse == groesse)
                & (func.md5(DokumentUpload.markdown)
                   == hashlib.md5(markdown.encode(), usedforsecurity=False).hexdigest())))
        .returning(DokumentUpload.id))).scalars())
    kennung = str(uuid.uuid4())
    s.add(DokumentUpload(id=kennung, session_id=session_id, block_id=block_id, aufrufer=aufrufer,
                         name=name, format=format, groesse=groesse, befund=befund,
                         gliederung=gliederung, markdown=markdown, erstellt=jetzt, genutzt=jetzt,
                         verfaellt_am=jetzt + timedelta(hours=ttl_h)))
    await s.flush()
    # Über der Grenze geht nur das älteste lesbare DESSELBEN Aufrufers — ein anonymes Dokument
    # verdrängt nie das einer Person und umgekehrt
    ueber = (select(DokumentUpload.id).where(_lesbar(session_id, aufrufer))
             .order_by(DokumentUpload.erstellt.desc(), DokumentUpload.id.desc())
             .offset(MAX_JE_SITZUNG))
    if ids := list((await s.execute(ueber)).scalars()):
        await s.execute(delete(DokumentUpload).where(DokumentUpload.id.in_(ids)))
        weg += ids
    if weg:
        await vorgaenge.dokument_teile_entfernen(s, weg)
    return kennung


def _gleicher_aufrufer(aufrufer: str | None):  # noqa: ANN202 — SQLAlchemy-Ausdruck
    if aufrufer is None:
        return DokumentUpload.aufrufer.is_(None)
    return DokumentUpload.aufrufer == aufrufer


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


async def alle_lesbaren(s: AsyncSession, session_id: str, aufrufer: str | None
                        ) -> list[DokumentUpload]:
    """TG-3e: die lesbaren Dokumente der Sitzung für diesen Aufrufer, das älteste zuerst (die
    Reihenfolge, in der die Person sie hat lesen lassen)."""
    stmt = (select(DokumentUpload).where(_lesbar(session_id, aufrufer))
            .order_by(DokumentUpload.erstellt, DokumentUpload.id))
    return list((await s.execute(stmt)).scalars())


async def aktuelles(s: AsyncSession, session_id: str, aufrufer: str | None
                    ) -> DokumentUpload | None:
    """Das jüngste lesbare Dokument — der Leseweg „das Dokument der Sitzung“ von vor TG-3e."""
    stmt = (select(DokumentUpload).where(_lesbar(session_id, aufrufer))
            .order_by(DokumentUpload.erstellt.desc(), DokumentUpload.id.desc()).limit(1))
    return (await s.execute(stmt)).scalar_one_or_none()


async def zuschreiben(s: AsyncSession, session_id: str, aufrufer: str
                      ) -> DokumentUpload | None:
    """Plan 2026-11-10, TB-E1 (Nutzer-Entscheid N2): Die anonym gelesenen Dokumente dieser Sitzung
    gehören ab jetzt der angemeldeten Person, die damit arbeitet. Nur noch lesbare Dokumente
    **ohne** Besitzerin derselben Sitzung — eines, das schon einer Person gehört, bleibt bei ihr.
    Abmelden gibt es nicht wieder frei (anonym liest nur ``aufrufer IS NULL``). TG-3e: alle auf
    einmal; zurück kommt das jüngste übernommene (``None``: keins). Der Aufrufer schreibt fest."""
    ergebnis = await s.execute(
        update(DokumentUpload).where(_lesbar(session_id, None))
        .values(aufrufer=aufrufer).returning(DokumentUpload))
    zeilen = sorted(ergebnis.scalars(), key=lambda z: (z.erstellt, z.id))
    return zeilen[-1] if zeilen else None


async def alle_fuer_aufrufer(s: AsyncSession, session_id: str, aufrufer: str | None
                             ) -> list[DokumentUpload]:
    """TG-3e: die Dokumente der Sitzung für diesen Aufrufer — der eine Leseweg für den Zug (Lader,
    Teile ``document`` und ``strukturdokument``; Review TB-E1, Befund 1). Eine angemeldete Person
    übernimmt vorher die anonym gelesenen derselben Sitzung (:func:`zuschreiben`); hat ein
    paralleler Zug sie gerade übernommen, findet das Lesen danach sie trotzdem (Befund 2). Der
    Aufrufer schreibt fest."""
    if aufrufer is not None:
        await zuschreiben(s, session_id, aufrufer)
    return await alle_lesbaren(s, session_id, aufrufer)


async def fuer_aufrufer(s: AsyncSession, session_id: str, aufrufer: str | None
                       ) -> DokumentUpload | None:
    """Das jüngste Dokument der Sitzung für diesen Aufrufer (:func:`alle_fuer_aufrufer`) — der
    Leseweg „das Dokument“ von vor TG-3e, für den Teil ``document``. Der Aufrufer schreibt fest."""
    zeilen = await alle_fuer_aufrufer(s, session_id, aufrufer)
    return zeilen[-1] if zeilen else None


async def beruehren(s: AsyncSession, upload_id: str, *, ttl_h: float) -> None:
    """Nutzung vermerken: die Frist beginnt neu."""
    jetzt = _jetzt()
    await s.execute(update(DokumentUpload).where(DokumentUpload.id == upload_id)
                    .values(genutzt=jetzt, verfaellt_am=jetzt + timedelta(hours=ttl_h)))


async def loeschen(s: AsyncSession, session_id: str, upload_id: str) -> None:
    """Löscht nur in der eigenen Sitzung — eine fremde Kennung bewirkt nichts (verrät nichts). Der
    Teil ``document`` in Vorgängen geht mit (Querschnitts-Review 2026-11-06), ebenso der Eintrag in
    ``strukturdokument`` (TG-3d)."""
    weg = await s.execute(delete(DokumentUpload).where(DokumentUpload.id == upload_id,
                                                       DokumentUpload.session_id == session_id)
                          .returning(DokumentUpload.id))
    if ids := list(weg.scalars()):
        await vorgaenge.dokument_teile_entfernen(s, ids)


async def der_sitzung_loeschen(s: AsyncSession, session_id: str) -> int:
    """„Arbeitsstand löschen“: alle Dokumente der Sitzung samt ihren Teilen in Vorgängen. Der
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
