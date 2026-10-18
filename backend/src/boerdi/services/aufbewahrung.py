"""Aufbewahrungsfristen durchsetzen (Paket 8, A — P5-4).

Drei Bereiche führen ``logging.retention_days``: ``01-base/privacy-config`` für die
Gesprächsverläufe (``messages`` und ``memory``, Vorgabe 30 Tage — Nutzer 2026-10-09),
``01-base/safety-config`` für das Sicherheitsprotokoll (``safety_logs``) und
``01-base/quality-log-config`` für das Qualitätsprotokoll (``quality_logs``). Die
beiden Protokoll-Fristen las bis Paket 8 niemand — die Einstellung versprach eine
Frist, die keiner durchsetzte (Audit 2026-09-29, §1.5). Jetzt löscht ein Lauf alle
:data:`TAKT_S` die Einträge, die älter als ihre Frist sind; 0 heißt unbegrenzt. Fehlt
das Feld, gilt die Vorgabe des Bereichsmodells — die zeigt auch das Studio an.

Gelöscht wird in Stapeln (:data:`STAPEL`), jeder in seiner eigenen Transaktion: eine
lange Löschung hielte sonst Sperren auf Tabellen, in die jeder Zug schreibt.

**Über alle Kopien nur ein Lauf** — über die Lease-Tabelle der Sitzungssperre
(``services/sitzungssperre``) mit dem festen Schlüssel :data:`SPERRE`; Sitzungen heißen
``bb-<uuid>``, ein Zusammenstoß ist ausgeschlossen.

**Text im Qualitätsprotokoll** (Paket 16, D1): seine Zeilen bleiben bis zur Frist des
Protokolls, ihr Text (Nachricht, Entities, Begründungen — ``services/qualitaet_text``) nur so
lange wie die Gesprächsverläufe; danach leert ihn :data:`QUALITAETSTEXT`.

Sitzungen selbst bleiben: mit ihnen gingen ihre Verbrauchszahlen (``usage_events``,
ON DELETE CASCADE), und die Kostenübersicht verlöre ihre Vergangenheit. Sie löschen nur
„Gespräche löschen“ im Studio und das Löschen einer einzelnen Sitzung
(``DELETE /api/sessions/{id}``).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import ColumnElement, Select, delete, func, literal_column, or_, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from boerdi.db.models import ChatMessage, ChatSession, MemoryItem, QualityLog, SafetyLog
from boerdi.domain.config_models.base_governance import (
    PrivacyLoggingBlock,
    QualityLoggingBlock,
    SafetyLoggingBlock,
)
from boerdi.services.config_loader import area, load_quality_log_config, load_safety_config
from boerdi.services.qualitaet_text import MARKE, text_entfernen
from boerdi.services.sitzungssperre import SitzungBeschaeftigt, sitzungssperre

logger = logging.getLogger(__name__)

#: Abstand der Läufe; der erste folgt :data:`ERSTER_LAUF_S` nach dem Start, nicht
#: mitten in die Vorwärmung hinein.
TAKT_S = 6 * 3600
ERSTER_LAUF_S = 300
STAPEL = 5000
#: Paket 16 (Review B-2): der Text-Schritt holt ganze Zeilen samt Debug nach Python — kleinere
#: Stapel, und das Rechnen läuft neben der Ereignisschleife (der erste Lauf nach dem Deploy
#: arbeitet den ganzen Rückstand ab, während Züge laufen).
TEXT_STAPEL = 500
#: Lease in der Sitzungssperre. Der Doppelpunkt hält sie aus dem Raum der Chat-
#: Sitzungen: deren Kennung prüft ``api/schemas.SITZUNGSKENNUNG`` (Paket 9).
SPERRE = "__lauf:aufbewahrung"

#: Paket 9 (V7, Review Paket 7): der Gesprächsstand einer Sitzung — Entities (Thema,
#: Seitentitel, Suchbegriffe), Signale, Tour. Er verfällt mit den Verläufen, wenn die
#: Sitzung so lange ruht (``updated_at``); die Sitzung selbst bleibt, mit ihr ihre
#: Verbrauchszahlen (Nutzer-Entscheid Paket 8).
SITZUNGSSTAND = "session_state"
#: Paket 16, D1: der Text im Qualitätsprotokoll — mit der Frist der Gesprächsverläufe.
QUALITAETSTEXT = "quality_text"

_TABELLEN = {
    "messages": ChatMessage, "memory": MemoryItem,
    "safety_logs": SafetyLog, "quality_logs": QualityLog,
}


@dataclass(frozen=True)
class Frist:
    bereich: str
    tage: int


def _tage(bereich: dict[str, Any] | None, block: type[BaseModel]) -> int:
    """Die Frist, gelesen wie im Studio (das Modell ``block``): ``"30"`` ist 30, ein
    fehlendes Feld die Vorgabe des Modells (Paket 9). Was das Modell nicht annimmt —
    auch ``true`` —, löscht nichts: eine Frist, die niemand lesen kann, ist keine."""
    logging_ = (bereich or {}).get("logging") or {}
    if "retention_days" not in logging_:
        tage: int = block().retention_days  # type: ignore[attr-defined]
        return tage
    try:
        gelesen = block.model_validate({"retention_days": logging_["retention_days"]})
    except ValidationError:
        logger.warning("Aufbewahrung: retention_days=%r ist keine Frist — nichts gelöscht",
                       logging_["retention_days"])
        return 0
    tage = gelesen.retention_days  # type: ignore[attr-defined]
    return tage


def fristen() -> list[Frist]:
    """Die gepflegten Fristen, Gesprächsverläufe zuerst.

    ``load_privacy_config`` gibt nur die Schalter zurück (ein kuratiertes Dict) —
    die Frist steht im rohen Bereich.
    """
    gespraeche = _tage(area("01-base/privacy-config"), PrivacyLoggingBlock)
    return [
        Frist("messages", gespraeche),
        Frist("memory", gespraeche),
        Frist(SITZUNGSSTAND, gespraeche),
        Frist("safety_logs", _tage(load_safety_config(), SafetyLoggingBlock)),
        Frist("quality_logs", _tage(load_quality_log_config(), QualityLoggingBlock)),
        # Nach dem Löschen: was ohnehin fällt, wird nicht erst geleert.
        Frist(QUALITAETSTEXT, gespraeche),
    ]


async def ueberblick(session: AsyncSession) -> list[dict[str, Any]]:
    """Je Protokoll: Frist, jetzt fällige Einträge, ältester Eintrag (fürs Studio)."""
    jetzt = datetime.now(UTC)
    zeilen = []
    for frist in fristen():
        if frist.bereich == SITZUNGSSTAND:
            zeilen.append(await _stand_ueberblick(session, frist, jetzt))
            continue
        if frist.bereich == QUALITAETSTEXT:
            zeilen.append(await _text_ueberblick(session, frist, jetzt))
            continue
        tabelle = _TABELLEN[frist.bereich]
        aeltester = (await session.execute(select(func.min(tabelle.created_at)))).scalar_one()
        faellig = 0
        if frist.tage > 0:
            grenze = jetzt - timedelta(days=frist.tage)
            faellig = (await session.execute(
                select(func.count()).select_from(tabelle).where(tabelle.created_at < grenze)
            )).scalar_one()
        zeilen.append({"bereich": frist.bereich, "tage": frist.tage, "faellig": faellig,
                       "aeltester": aeltester.isoformat() if aeltester else None})
    return zeilen


async def _bereinige(sitzungen: async_sessionmaker[AsyncSession], frist: Frist,
                     jetzt: datetime) -> int:
    if frist.tage <= 0:
        return 0
    if frist.bereich == SITZUNGSSTAND:
        return await _stand_leeren(sitzungen, frist, jetzt)
    if frist.bereich == QUALITAETSTEXT:
        return await _text_leeren(sitzungen, frist, jetzt)
    tabelle = _TABELLEN[frist.bereich]
    grenze = jetzt - timedelta(days=frist.tage)
    gesamt = 0
    while True:
        stapel = select(tabelle.id).where(tabelle.created_at < grenze).limit(STAPEL)
        async with sitzungen() as s:
            n = (await s.execute(delete(tabelle).where(tabelle.id.in_(stapel)))).rowcount or 0
            await s.commit()
        gesamt += n
        if n < STAPEL:
            return gesamt


def _stand_nicht_leer() -> ColumnElement[bool]:
    leeres_objekt, leere_liste = literal_column("'{}'::jsonb"), literal_column("'[]'::jsonb")
    return or_(ChatSession.entities != leeres_objekt,
               ChatSession.signal_history != leere_liste,
               ChatSession.tour_state != leeres_objekt)


async def _stand_ueberblick(session: AsyncSession, frist: Frist,
                            jetzt: datetime) -> dict[str, Any]:
    nicht_leer = _stand_nicht_leer()
    aeltester = (await session.execute(
        select(func.min(ChatSession.updated_at)).where(nicht_leer))).scalar_one()
    faellig = 0
    if frist.tage > 0:
        grenze = jetzt - timedelta(days=frist.tage)
        faellig = (await session.execute(
            select(func.count()).select_from(ChatSession)
            .where(ChatSession.updated_at < grenze, nicht_leer))).scalar_one()
    return {"bereich": frist.bereich, "tage": frist.tage, "faellig": faellig,
            "aeltester": aeltester.isoformat() if aeltester else None}


async def _stand_leeren(sitzungen: async_sessionmaker[AsyncSession], frist: Frist,
                        jetzt: datetime) -> int:
    """Den Gesprächsstand ruhender Sitzungen leeren — in Stapeln wie das Löschen;
    ``updated_at`` bleibt, wie es war.

    Die Bedingungen stehen auch im äußeren ``WHERE`` (Review Paket 9): schreibt ein
    Zug die Sitzung, während der Stapel auf ihre Zeile wartet, prüft Postgres danach
    nur das äußere ``WHERE`` neu — mit ``session_id IN (…)`` allein leerte es den
    frischen Stand, auch einen offenen Schreibvorgang."""
    grenze = jetzt - timedelta(days=frist.tage)
    gesamt = 0
    while True:
        stapel = (select(ChatSession.session_id)
                  .where(ChatSession.updated_at < grenze, _stand_nicht_leer()).limit(STAPEL))
        async with sitzungen() as s:
            n = (await s.execute(
                update(ChatSession)
                .where(ChatSession.session_id.in_(stapel),
                       ChatSession.updated_at < grenze, _stand_nicht_leer())
                .values(entities={}, signal_history=[], tour_state={}))).rowcount or 0
            await s.commit()
        gesamt += n
        if n < STAPEL:
            return gesamt


def _text_ungeleert() -> ColumnElement[bool]:
    """Wörtlich die Bedingung des Teilindex ``ix_quality_logs_text_offen`` (Migration 0013) —
    sonst nutzt Postgres ihn nicht und liest jede geleerte Zeile samt Debug erneut."""
    return QualityLog.data[MARKE].astext.is_(None)


def _faellige_texte(grenze: datetime, nach_id: int) -> Select[Any]:
    """Der nächste Stapel ungeleerter Zeilen vor ``grenze`` — fortgesetzt hinter ``nach_id``
    (Keyset), damit ein Lauf übersprungene Zeilen nicht erneut liest (Review PR #18)."""
    return (select(QualityLog.id, QualityLog.data)
            .where(QualityLog.created_at < grenze, _text_ungeleert(), QualityLog.id > nach_id)
            .order_by(QualityLog.id).limit(TEXT_STAPEL))


async def _text_ueberblick(session: AsyncSession, frist: Frist,
                           jetzt: datetime) -> dict[str, Any]:
    ungeleert = _text_ungeleert()
    aeltester = (await session.execute(
        select(func.min(QualityLog.created_at)).where(ungeleert))).scalar_one()
    faellig = 0
    if frist.tage > 0:
        grenze = jetzt - timedelta(days=frist.tage)
        faellig = (await session.execute(
            select(func.count()).select_from(QualityLog)
            .where(QualityLog.created_at < grenze, ungeleert))).scalar_one()
    return {"bereich": frist.bereich, "tage": frist.tage, "faellig": faellig,
            "aeltester": aeltester.isoformat() if aeltester else None}


def _ohne_texte(zeilen: Any) -> list[dict[str, Any]]:
    return [{"id": i, "data": text_entfernen(d or {})} for i, d in zeilen]


async def _text_leeren(sitzungen: async_sessionmaker[AsyncSession], frist: Frist,
                       jetzt: datetime) -> int:
    """Den Text alter Zeilen des Qualitätsprotokolls leeren, in Stapeln.

    In Python statt mit JSONB-Operatoren: Fehlertexte stehen in einer Liste
    (``debug.outcomes[*].error``), der Freitext der Rechtsprüfung mitten in einem Grund —
    rein gerechnet ist es testbar (``services/qualitaet_text``). Alte Zeilen schreibt sonst
    niemand; die Marke hält einen zweiten Lauf (auch nach einem Abbruch) leer."""
    grenze = jetzt - timedelta(days=frist.tage)
    gesamt = 0
    letzte_id = 0
    while True:
        async with sitzungen() as s:
            zeilen = (await s.execute(_faellige_texte(grenze, letzte_id))).all()
            if zeilen:
                letzte_id = zeilen[-1][0]
                neu = await asyncio.to_thread(_ohne_texte, zeilen)
                # ORM-Sammel-Update nach Primärschlüssel: eine Anweisung, eine Zeile je Eintrag.
                await s.execute(update(QualityLog), neu)
                await s.commit()
        gesamt += len(zeilen)
        if len(zeilen) < TEXT_STAPEL:
            return gesamt


async def lauf(engine: AsyncEngine,
               sitzungen: async_sessionmaker[AsyncSession]) -> dict[str, int] | None:
    """Fällige Einträge löschen; je Protokoll die Zahl. ``None``, wenn der Lauf gerade
    auf einer anderen Kopie läuft."""
    try:
        async with sitzungssperre(engine, SPERRE, warten_s=0.0):
            jetzt = datetime.now(UTC)
            ergebnis = {f.bereich: await _bereinige(sitzungen, f, jetzt) for f in fristen()}
    except SitzungBeschaeftigt:
        logger.info("Aufbewahrung: läuft schon auf einer anderen Kopie")
        return None
    if any(ergebnis.values()):
        logger.info("Aufbewahrung: gelöscht %s", ergebnis)
    return ergebnis


async def _schleife(engine: AsyncEngine, sitzungen: async_sessionmaker[AsyncSession]) -> None:
    await asyncio.sleep(ERSTER_LAUF_S)
    while True:
        try:
            await lauf(engine, sitzungen)
        except Exception:  # noqa: BLE001 — der nächste Takt versucht es wieder
            logger.warning("Aufbewahrung: Lauf gescheitert", exc_info=True)
        await asyncio.sleep(TAKT_S)


def starte(engine: AsyncEngine, sitzungen: async_sessionmaker[AsyncSession]) -> asyncio.Task[None]:
    """Den Lauf im Hintergrund starten; der Aufrufer bricht die Aufgabe beim Herunterfahren ab."""
    return asyncio.create_task(_schleife(engine, sitzungen), name="aufbewahrung")
