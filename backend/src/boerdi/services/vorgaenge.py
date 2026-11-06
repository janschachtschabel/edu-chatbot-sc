"""Vorgänge: der Arbeitsstand einer Person (Paket V1, Plan 2026-11-05 §2; Tabellen aus 0018).

Ein Vorgang trägt die Daten eines Vorhabens als **benannte Teile** einer Akte (``wlo.vorgang@1``):
``teile: {name → {typ, version, zusammenfassung, geaendert, wert | ref}}``, ``historie: {name →
[ref …]}``, ``lauf`` (Zeiger eines Ablaufs, sonst ``null``). Große Teile (über :data:`INLINE_BYTES`)
und frühere Fassungen liegen in ``vorgang_ablage``; die Akte bleibt klein.

Regeln: Lesen und Schreiben nur mit derselben ``aufrufer``-Kennung (bestätigte Person oder
``sitzung:<id>``, nie aus Eingaben); abgelaufen ist sofort unlesbar; höchstens
:data:`MAX_JE_PERSON` je Besitzerin (abgeschlossene weichen zuerst, sonst der älteste); jede
Änderung prüft ``akte_version`` (:class:`VorgangKonflikt` statt still zu überschreiben). Der
Aufrufer schreibt die Transaktion fest.
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final

from sqlalchemy import case, delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from boerdi.db.models import DokumentUpload, Vorgang, VorgangAblage

FORMAT: Final = "wlo.vorgang@1"
MAX_JE_PERSON: Final = 3
#: Größer als das (als JSON, Bytes) wandert ein Teil in die Ablage.
INLINE_BYTES: Final = 8_000
#: So viele frühere Fassungen je Teil bleiben.
HISTORIE: Final = 5
#: Nur diese Teile behalten frühere Fassungen (Querschnitts-Review 2026-11-06, Datensparsamkeit:
#: ``ablage`` bekäme sonst je Datei eine neue Fassung mit Titeln). Für den Entwurf ist ein Leser
#: geplant (zurück zur vorigen Gliederung, :func:`historie_wert`) — heute liest sie noch niemand
#: (Review Q3, Befund 12); sie gehen mit dem Vorgang.
MIT_HISTORIE: Final = frozenset({"draft"})
ABGESCHLOSSEN: Final = ("fertig", "abgebrochen")


class VorgangKonflikt(Exception):
    """Ein anderer Zug hat den Vorgang inzwischen geändert."""


def _jetzt() -> datetime:
    return datetime.now(UTC)


def leere_akte() -> dict[str, Any]:
    return {"format": FORMAT, "teile": {}, "historie": {}, "lauf": None}


async def anlegen(s: AsyncSession, *, aufrufer: str, session_id: str | None, titel: str,
                  zweck: str, tage: float) -> Vorgang:
    """Einen neuen Vorgang anlegen; über der Grenze weicht der älteste (abgeschlossene zuerst).
    Zählen und Verdrängen laufen unter einer Sperre je Besitzerin (Review V1, Befund 8)."""
    await s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:a))"), {"a": aufrufer})
    vorhanden = (await s.execute(
        select(Vorgang.id).where(Vorgang.aufrufer == aufrufer).order_by(
            case((Vorgang.status.in_(ABGESCHLOSSEN), 0), else_=1), Vorgang.geaendert)
    )).scalars().all()
    if (zu_viel := len(vorhanden) - MAX_JE_PERSON + 1) > 0:
        await s.execute(delete(Vorgang).where(Vorgang.id.in_(vorhanden[:zu_viel])))
    jetzt = _jetzt()
    v = Vorgang(id=str(uuid.uuid4()), aufrufer=aufrufer, session_id=session_id,
                titel=titel[:120], zweck=zweck, status="aktiv", akte=leere_akte(), akte_version=0,
                erstellt=jetzt, geaendert=jetzt, verfaellt_am=jetzt + timedelta(days=tage))
    s.add(v)
    await s.flush()
    return v


async def lesen(s: AsyncSession, vorgang_id: str, aufrufer: str) -> Vorgang | None:
    stmt = (select(Vorgang)
            .where(Vorgang.id == vorgang_id, Vorgang.aufrufer == aufrufer,
                   Vorgang.verfaellt_am > _jetzt())
            .execution_options(populate_existing=True))
    return (await s.execute(stmt)).scalar_one_or_none()


async def sperren(s: AsyncSession, vorgang_id: str, aufrufer: str) -> None:
    """Die Zeile des Vorgangs bis zum Ende der (Teil-)Transaktion sperren (``FOR UPDATE``) — wer
    liest, ändert und zurückschreibt, sieht so keinen gleichzeitigen Schreiber dazwischen (Review
    Q1, Befund 3)."""
    await s.execute(select(Vorgang.id)
                    .where(Vorgang.id == vorgang_id, Vorgang.aufrufer == aufrufer)
                    .with_for_update())


async def juengster(s: AsyncSession, aufrufer: str) -> Vorgang | None:
    """Der zuletzt geänderte offene Vorgang der Besitzerin — damit ihn eine neue Sitzung derselben
    Person wiederfindet (Review V1, Befund 1)."""
    stmt = (select(Vorgang)
            .where(Vorgang.aufrufer == aufrufer, Vorgang.verfaellt_am > _jetzt(),
                   Vorgang.status.not_in(ABGESCHLOSSEN))
            .order_by(Vorgang.geaendert.desc()).limit(1)
            .execution_options(populate_existing=True))
    return (await s.execute(stmt)).scalar_one_or_none()


async def beruehren(s: AsyncSession, vorgang_id: str, *, tage: float) -> None:
    """Nutzung vermerken (auch beim Lesen): die Frist beginnt neu (Review V1, Befund 14)."""
    await s.execute(update(Vorgang).where(Vorgang.id == vorgang_id)
                    .values(verfaellt_am=_jetzt() + timedelta(days=tage))
                    .execution_options(synchronize_session=False))


def _groesse(wert: Any) -> int:
    return len(json.dumps(wert, ensure_ascii=False).encode())


async def _ablegen(s: AsyncSession, vorgang_id: str, schluessel: str, typ: str, wert: Any,
                   groesse: int) -> None:
    await s.merge(VorgangAblage(vorgang_id=vorgang_id, schluessel=schluessel, typ=typ,
                                inhalt=wert, groesse=groesse))


async def teil_setzen(s: AsyncSession, v: Vorgang, name: str, *, typ: str, wert: Any,
                      zusammenfassung: str, tage: float) -> Vorgang:
    """Teil ``name`` setzen (Version + 1, vorige Fassung in die Historie); die Frist beginnt neu.
    Wirft :class:`VorgangKonflikt`, wenn ``v`` nicht mehr der gespeicherte Stand ist — geprüft vor
    jeder Schreibung in die Ablage (Review V1, Befund 4: sonst träfe ein zweiter Schreiber auf einen
    Schlüsselkonflikt statt auf den Konflikt)."""
    beansprucht = await s.execute(
        update(Vorgang).where(Vorgang.id == v.id, Vorgang.akte_version == v.akte_version)
        .values(akte_version=v.akte_version + 1)
        .execution_options(synchronize_session=False))
    if not beansprucht.rowcount:
        raise VorgangKonflikt(v.id)
    akte = copy.deepcopy(v.akte)
    teile, historie = akte.setdefault("teile", {}), akte.setdefault("historie", {})
    alt = teile.get(name)
    if alt is not None and name in MIT_HISTORIE:
        ref = alt.get("ref")
        if ref is None:
            ref = f"{name}@{alt['version']}"
            await _ablegen(s, v.id, ref, alt["typ"], alt.get("wert"), _groesse(alt.get("wert")))
        liste = [*historie.get(name, []), ref]
        for weg in liste[:-HISTORIE]:
            await _weg(s, v.id, weg)
        historie[name] = liste[-HISTORIE:]
    elif alt is not None:
        # Ohne Historie: eine große vorige Fassung in der Ablage geht mit (und eine früher
        # angelegte Historie dieses Teils ebenso).
        for weg in [*([alt["ref"]] if alt.get("ref") else []), *historie.pop(name, [])]:
            await _weg(s, v.id, weg)
    version = (alt or {}).get("version", 0) + 1
    jetzt = _jetzt()
    eintrag: dict[str, Any] = {"typ": typ, "version": version,
                               "zusammenfassung": zusammenfassung[:200],
                               "geaendert": jetzt.isoformat()}
    if (groesse := _groesse(wert)) > INLINE_BYTES:
        eintrag["ref"] = f"{name}@{version}"
        await _ablegen(s, v.id, eintrag["ref"], typ, wert, groesse)
    else:
        eintrag["wert"] = wert
    teile[name] = eintrag
    ergebnis = await s.execute(
        update(Vorgang).where(Vorgang.id == v.id)
        .values(akte=akte, geaendert=jetzt, verfaellt_am=jetzt + timedelta(days=tage))
        .returning(Vorgang)
        .execution_options(synchronize_session=False, populate_existing=True))
    return ergebnis.scalar_one()


async def _weg(s: AsyncSession, vorgang_id: str, schluessel: str) -> None:
    await s.execute(delete(VorgangAblage).where(VorgangAblage.vorgang_id == vorgang_id,
                                                VorgangAblage.schluessel == schluessel))


async def _aus_ablage(s: AsyncSession, vorgang_id: str, schluessel: str) -> Any:
    zeile = await s.get(VorgangAblage, (vorgang_id, schluessel))
    return None if zeile is None else zeile.inhalt


async def teil_wert(s: AsyncSession, v: Vorgang, name: str) -> Any:
    """Der Wert des Teils — aus der Akte oder der Ablage; ``None`` ohne den Teil."""
    eintrag = (v.akte.get("teile") or {}).get(name)
    if eintrag is None:
        return None
    if "ref" in eintrag:
        return await _aus_ablage(s, v.id, eintrag["ref"])
    return eintrag.get("wert")


async def historie_wert(s: AsyncSession, v: Vorgang, name: str, version: int) -> Any:
    """Eine frühere Fassung eines Teils (``None``, wenn sie nicht mehr da ist)."""
    if f"{name}@{version}" not in (v.akte.get("historie") or {}).get(name, []):
        return None
    return await _aus_ablage(s, v.id, f"{name}@{version}")


async def dokument_teile_entfernen(s: AsyncSession, upload_ids: list[str]) -> int:
    """Den Teil ``document`` aus jedem Vorgang, der auf eines dieser Dokumente zeigt (Querschnitts-
    Review 2026-11-06, Datenschutz): Name und Befund überdauerten sonst die 24 h des Dokuments und
    dessen Löschen. Auch eine große Fassung in der Ablage geht mit. Der Aufrufer schreibt fest.
    Gibt die Zahl der betroffenen Vorgänge zurück."""
    refs = [f"dokument:{i}" for i in upload_ids if isinstance(i, str) and i]
    if not refs:
        return 0
    inline = select(Vorgang.id).where(
        Vorgang.akte[("teile", "document", "wert", "ref")].astext.in_(refs))
    abgelegt = select(VorgangAblage.vorgang_id).where(
        VorgangAblage.schluessel.like("document@%"), VorgangAblage.inhalt["ref"].astext.in_(refs))
    ids = set((await s.execute(inline)).scalars()) | set((await s.execute(abgelegt)).scalars())
    return sum([await _entfernen_unter_sperre(s, vid, set(refs)) for vid in sorted(ids)])


async def _entfernen_unter_sperre(s: AsyncSession, vid: str, refs: set[str]) -> bool:
    """Review Q3, Befund 6: gesperrt gelesen — sonst überschriebe das Zurückschreiben ein
    gleichzeitiges ``teil_setzen`` zwischen Lesen und Schreiben (aufsteigend: keine Verklemmung).
    Unter der Sperre noch einmal geprüft (Nachprüfung, Befund 5): ``document`` geht nur, wenn es
    noch auf eines der Dokumente zeigt — ein inzwischen neues bleibt."""
    v = await s.get(Vorgang, vid, populate_existing=True, with_for_update=True)
    alt = ((v.akte or {}).get("teile") or {}).get("document") if v is not None else None
    if not isinstance(alt, dict):
        return False
    wert = await _aus_ablage(s, vid, alt["ref"]) if alt.get("ref") else alt.get("wert")
    if not isinstance(wert, dict) or wert.get("ref") not in refs:
        return False
    akte = copy.deepcopy(v.akte)
    akte["teile"].pop("document", None)
    for weg in [*([alt["ref"]] if alt.get("ref") else []),
                *(akte.get("historie") or {}).pop("document", [])]:
        await _weg(s, vid, weg)
    await s.execute(update(Vorgang).where(Vorgang.id == vid)
                    .values(akte=akte, akte_version=Vorgang.akte_version + 1)
                    .execution_options(synchronize_session=False))
    return True


async def verwaiste_dokument_teile_entfernen(s: AsyncSession) -> int:
    """Den Teil ``document`` aus jedem Vorgang, dessen Dokument nicht mehr da ist — gelöscht auf
    einem Weg ohne :func:`dokument_teile_entfernen` (die Sitzung ging, Kaskade; Review Q3,
    Befund 7). Für den Aufbewahrungslauf; der Aufrufer schreibt fest."""
    ref = Vorgang.akte[("teile", "document", "wert", "ref")].astext
    inline = select(ref).where(ref.like("dokument:%"))
    abgelegt = select(VorgangAblage.inhalt["ref"].astext).where(
        VorgangAblage.schluessel.like("document@%"))
    refs = set((await s.execute(inline)).scalars()) | set((await s.execute(abgelegt)).scalars())
    ids = {r.removeprefix("dokument:") for r in refs if isinstance(r, str)}
    if not ids:
        return 0
    da = set((await s.execute(select(DokumentUpload.id).where(DokumentUpload.id.in_(ids))))
             .scalars())
    return await dokument_teile_entfernen(s, sorted(ids - da))


async def loeschen(s: AsyncSession, vorgang_id: str, aufrufer: str) -> None:
    """Nur die Besitzerin löscht — eine fremde Kennung bewirkt nichts (und verrät nichts)."""
    await s.execute(delete(Vorgang).where(Vorgang.id == vorgang_id, Vorgang.aufrufer == aufrufer))


async def alle_loeschen(s: AsyncSession, aufrufer: str) -> int:
    """„Arbeitsstand löschen“ (Review Q3, Befund 5): alle Vorgänge der Besitzerin, auch die schon
    abgeschlossenen — Ablage und Aufträge gehen per Kaskade mit."""
    ergebnis = await s.execute(delete(Vorgang).where(Vorgang.aufrufer == aufrufer))
    return int(ergebnis.rowcount or 0)


async def anonyme_der_sitzung_loeschen(s: AsyncSession, session_id: str) -> int:
    ergebnis = await s.execute(delete(Vorgang).where(Vorgang.aufrufer == f"sitzung:{session_id}"))
    return int(ergebnis.rowcount or 0)


async def alle_anonymen_loeschen(s: AsyncSession) -> int:
    """Für ``purge_all(sessions=True)``: ohne Sitzungen keine anonymen Besitzerinnen mehr."""
    ergebnis = await s.execute(delete(Vorgang).where(Vorgang.aufrufer.like("sitzung:%")))
    return int(ergebnis.rowcount or 0)


async def verfallene_loeschen(sitzungen: async_sessionmaker[AsyncSession], jetzt: datetime) -> int:
    """Für den Aufbewahrungslauf: alle abgelaufenen Vorgänge (die Ablage geht mit)."""
    async with sitzungen() as s:
        ergebnis = await s.execute(delete(Vorgang).where(
            (Vorgang.verfaellt_am <= jetzt)
            # Review V1, Befund 10: anonyme, deren Sitzung schon weg ist (SET NULL).
            | (Vorgang.aufrufer.like("sitzung:%") & Vorgang.session_id.is_(None))))
        await s.commit()
    return int(ergebnis.rowcount or 0)


async def lauf_setzen(s: AsyncSession, v: Vorgang, lauf: dict[str, Any] | None, *,
                      status: str, tage: float) -> Vorgang:
    """Den Zeiger des Ablaufs (``akte.lauf``) und den Status setzen (Paket A1) — bedingt wie
    :func:`teil_setzen`; wirft :class:`VorgangKonflikt`."""
    akte = {**copy.deepcopy(v.akte), "lauf": lauf}
    jetzt = _jetzt()
    ergebnis = await s.execute(
        update(Vorgang).where(Vorgang.id == v.id, Vorgang.akte_version == v.akte_version)
        .values(akte=akte, akte_version=v.akte_version + 1, status=status, geaendert=jetzt,
                verfaellt_am=jetzt + timedelta(days=tage))
        .returning(Vorgang)
        .execution_options(synchronize_session=False, populate_existing=True))
    neu = ergebnis.scalar_one_or_none()
    if neu is None:
        raise VorgangKonflikt(v.id)
    return neu
