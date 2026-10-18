"""Nutzung im Überblick (Paket 16, D3) — wer wann wie oft mit dem Chatbot spricht.

Quelle ist das Qualitätsprotokoll (``quality_logs``, eine Zeile je Zug). Es schreibt nur, wenn
``quality-log-config.logging.enabled`` und ``privacy-config.logging.quality`` an sind
(``services/turn_quality.qualitaetsprotokoll_an``) — die Seite sagt es, wenn nicht; Sitzungen
und Verbrauch kennen weder Gerät noch Sprache.

Tag, Wochentag und Stunde rechnet Postgres in :data:`~boerdi.services.usage_tage.TAGES_ZONE`.
Sprache, Seitenart und Maschine stehen seit Paket 16 flach in der Zeile; ältere Zeilen tragen
sie nur im Debug — der wird dort gelesen, solange ihn der Aufbewahrungslauf nicht geleert hat.

**Genaue Zahlen** (Nutzer-Entscheid 2026-10-18): Raster und Verteilungen nennen jede Zelle
genau. Bis dahin kamen Zellen aus weniger als fünf Sitzungen als ``None`` („<5“) — eine
Darstellungshilfe, kein Schutz (Summen und Tageswerte waren ohnehin genau, und wer das Studio
bedient, sieht die Sitzungen selbst); im Raster las sie sich als Störung.

**Maschine** ist die angefragte (``debug.engine``): ein Krisen-Zug unter der Agent-Schleife zählt
hier als ``agent``, in der Analyse über ``pattern_id`` als Muster — die Nutzung fragt, womit
Besucher sprechen, die Analyse, welcher Weg antwortete.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Date, cast, extract, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from boerdi.db.models import QualityLog
from boerdi.services.session_origin import scope_clause
from boerdi.services.usage_tage import TAGES_ZONE

_DATA = QualityLog.data


def _flach_oder_debug(flach: str, *debug_pfad: str) -> ColumnElement[str]:
    """Das flache Feld, sonst derselbe Wert aus dem Debug älterer Zeilen, sonst ``""``."""
    im_debug = _DATA["debug"]
    for teil in debug_pfad[:-1]:
        im_debug = im_debug[teil]
    return func.coalesce(func.nullif(_DATA[flach].astext, ""),
                         im_debug[debug_pfad[-1]].astext, "")


MASCHINE = _flach_oder_debug("engine", "engine")
_FACETTEN: dict[str, ColumnElement[str]] = {
    "maschine": MASCHINE,
    "sprache": _flach_oder_debug("locale", "context", "locale"),
    "geraet": func.coalesce(_DATA["device"].astext, ""),
    "seitenart": _flach_oder_debug("page_type", "entities", "page_type"),
}
#: Nur aus Muster-Zügen: die Agent-Schleife setzt Zielgruppe und Anliegen fest (P-AND, I01).
_NUR_MUSTER: dict[str, ColumnElement[str]] = {
    "persona": func.coalesce(_DATA["persona_id"].astext, ""),
    "anliegen": func.coalesce(QualityLog.intent_id, ""),
}


def _lokal(wann: Any) -> Any:
    return func.timezone(TAGES_ZONE, wann)


async def ueberblick(
    session: AsyncSession, start: datetime, end: datetime, scope: str = "all",
    engine: str | None = None,
) -> dict[str, Any]:
    """Züge, Sitzungen, Tage, Wochentag × Stunde und Verteilungen im Zeitraum (Grenzen
    einschließlich). ``scope`` und ``engine`` wie bei den Kosten."""
    herkunft = scope_clause(scope, QualityLog.session_id)
    auswahl = [QualityLog.created_at >= start, QualityLog.created_at <= end,
               *(() if herkunft is None else (herkunft,)),
               *(() if not engine else (MASCHINE == engine,))]

    zuege = (await session.execute(
        select(func.count()).select_from(QualityLog).where(*auswahl))).scalar_one()
    # In SQL gerechnet: ein Jahr Betrieb sind sonst Hunderttausende Zeilen je Seitenaufruf
    # (Review PR #18). `percentile_cont` mittelt wie `statistics.median` die beiden Mittleren.
    je_sitzung = (select(func.count().label("n"))
                  .where(*auswahl, QualityLog.session_id.is_not(None))
                  .group_by(QualityLog.session_id).subquery())
    sitzungen, mittel, median = (await session.execute(select(
        func.count(), func.avg(je_sitzung.c.n),
        func.percentile_cont(0.5).within_group(je_sitzung.c.n)))).one()

    return {
        "zuege": zuege,
        "sitzungen": sitzungen,
        "zuege_je_sitzung": {
            "mittel": round(float(mittel), 2) if sitzungen else 0.0,
            "median": float(median) if sitzungen else 0.0,
        },
        "tage": await _tage(session, start, end, auswahl),
        "raster": await _raster(session, auswahl),
        "verteilungen": {
            **{name: await _verteilung(session, spalte, auswahl)
               for name, spalte in _FACETTEN.items()},
            **{name: await _verteilung(session, spalte, [*auswahl, MASCHINE == "pattern"])
               for name, spalte in _NUR_MUSTER.items()},
        },
    }


async def _tage(session: AsyncSession, start: datetime, end: datetime,
                auswahl: list[ColumnElement[bool]]) -> list[dict[str, Any]]:
    tag = cast(_lokal(QualityLog.created_at), Date).label("tag")
    zeilen = {t: (s, z) for t, s, z in (await session.execute(
        select(tag, func.count(QualityLog.session_id.distinct()), func.count())
        .where(*auswahl).group_by(tag))).all()}
    erster, letzter = (await session.execute(select(
        cast(_lokal(literal(start)), Date), cast(_lokal(literal(end)), Date)))).one()
    antwort = []
    tag_: date = erster
    while tag_ <= letzter:
        sitzungen, zuege = zeilen.get(tag_, (0, 0))
        antwort.append({"tag": tag_.isoformat(), "sitzungen": sitzungen, "zuege": zuege})
        tag_ += timedelta(days=1)
    return antwort


async def _raster(session: AsyncSession,
                  auswahl: list[ColumnElement[bool]]) -> list[list[int]]:
    """7 × 24: Zeile 0 ist Montag, Spalte die Stunde (Ortszeit)."""
    wochentag = extract("isodow", _lokal(QualityLog.created_at)).label("wt")
    stunde = extract("hour", _lokal(QualityLog.created_at)).label("st")
    raster = [[0] * 24 for _ in range(7)]
    for wt, st, n in (await session.execute(
            select(wochentag, stunde, func.count())
            .where(*auswahl).group_by(wochentag, stunde))).all():
        raster[int(wt) - 1][int(st)] = n
    return raster


async def _verteilung(session: AsyncSession, spalte: ColumnElement[str],
                      auswahl: list[ColumnElement[bool]]) -> list[dict[str, Any]]:
    wert = spalte.label("wert")
    zeilen = (await session.execute(
        select(wert, func.count().label("n"))
        .where(*auswahl).group_by(wert).order_by(func.count().desc(), wert))).all()
    return [{"wert": w, "anzahl": n} for w, n in zeilen]
