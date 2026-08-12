"""Verbrauch auswerten (K4) — Gegenstück zu ``usage_store.py`` auf der Lesehand.

Zwei Fragen, eine Antwortform: „was hat diese Sitzung gekostet" und „was hat
dieser Zeitraum gekostet". Beide fassen die Zeilen aus ``usage_events`` **je
Modell** zusammen und legen die gepflegte Preistafel darüber.

**Der Betrag verlässt den Dienst als Zeichenkette.** Als JSON-Zahl würde aus
``13.27743099`` beim Serialisieren wieder ``13.277430990000001`` — die ganze
``Decimal``-Rechnung aus K3 wäre auf dem letzten Meter verloren. Formatiert
wird im Studio (K5), nicht hier.

**Der Betrag deckt nur die bepreisten Modelle.** Ist für eines kein Preis
gepflegt, steht sein Name in ``price_unavailable``; ist für keines einer
gepflegt, ist ``amount`` ``None`` statt ``0``. Wer den Betrag anzeigt, muss die
Liste daneben anzeigen — sonst liest sich eine Teilsumme als Gesamtsumme.

**Der Zeitraum nennt zusätzlich die teuersten Sitzungen** (K5a). Die Rangfolge
entsteht in Python und nicht in SQL, weil der Preis in der Config lebt und
nicht in der Datenbank: ein ``ORDER BY`` könnte nur nach Token sortieren, und
das ist eine andere Reihenfolge, sobald zwei Modelle verschieden viel kosten.
Der Preis dafür ist eine Zeile je Sitzung **und** Modell im Speicher.

    simplify: Für eine Anlage mit sehr vielen Sitzungen je Zeitraum wäre der
    Ausweg, den Betrag beim Schreiben einzufrieren (siehe Risiken im Plan) —
    dann kann Postgres selbst ranken und deckeln. Heute nicht nötig und nicht
    umsonst: es verdoppelt die Wahrheit (Token **und** Betrag).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from boerdi.db.models import UsageEvent
from boerdi.domain.config_models.pricing import PricingArea
from boerdi.domain.pricing import TokenCounts, cost_for
from boerdi.services.config_loader import load_pricing

#: Wie viele Sitzungen die Spitzenliste nennt. Eine Konstante und kein
#: Parameter: es gibt genau einen Aufrufer, und eine einstellbare Zahl ohne
#: Einsteller wäre eine Zusage ohne Verbraucher.
_TOP_SESSIONS = 10


def _as_text(amount: Decimal) -> str:
    """Ein Betrag als stabiler Text — exakt, ohne Exponenten, ohne Zierzahlen.

    Nur ``str(amount)`` genügt nicht: der Exponent hängt an den Eingaben, also
    erschienen dieselben 2 € je nach Preistafel als ``2``, ``2.0`` oder
    ``2.00``. ``normalize()`` allein genügt auch nicht — es macht aus 100 die
    Schreibweise ``1E+2``, die im Studio als Text ankäme. Erst beides zusammen
    ist stabil.

    **Nicht** auf zwei Nachkommastellen gerundet: ein einzelner Zug kostet oft
    Bruchteile eines Cents, und ``0,00 €`` läse sich wie „hat nichts gekostet"
    — derselbe Fehler, den K3 bei der ungepflegten Tafel vermeidet.
    """
    return format(amount.normalize(), "f")


async def _grouped_by_model(
    session: AsyncSession, *where: ColumnElement[bool]
) -> list[Any]:
    """Die Zeilen der Auswahl, je Modell aufsummiert und nach Namen sortiert.

    Sortiert, damit die Antwort stabil ist: eine Tabelle, deren Reihenfolge
    sich zwischen zwei Abrufen ändert, liest sich wie geänderte Daten.
    """
    stmt = (
        select(
            UsageEvent.model,
            func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cached_tokens), 0),
            func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
            func.coalesce(func.sum(UsageEvent.calls), 0),
        )
        .where(*where)
        .group_by(UsageEvent.model)
        .order_by(UsageEvent.model)
    )
    return list((await session.execute(stmt)).all())


def _assemble(rows: list[Any]) -> dict[str, Any]:
    """Aus den Modellzeilen die Antwort bauen — Summen, Beträge, Lücken."""
    geladen = load_pricing()
    # Unlesbar rechnet wie ungepflegt (kein Preis, aber die Zahlen bleiben
    # stehen) — nur sagt die Antwort, dass es zwei verschiedene Zustände sind.
    table = geladen if geladen is not None else PricingArea()
    models: list[dict[str, Any]] = []
    unavailable: list[str] = []
    total = Decimal(0)
    priced = False

    for model, prompt, cached, completion, reasoning, calls in rows:
        amount = cost_for(
            TokenCounts(model=model, prompt=prompt, cached=cached,
                        completion=completion),
            table,
        )
        if amount is None:
            unavailable.append(model)
        else:
            total += amount
            priced = True
        models.append({
            "model": model,
            "prompt_tokens": prompt, "cached_tokens": cached,
            "completion_tokens": completion, "reasoning_tokens": reasoning,
            "calls": calls,
            "amount": None if amount is None else _as_text(amount),
        })

    return {
        "empty": not models,
        "calls": sum(m["calls"] for m in models),
        "prompt_tokens": sum(m["prompt_tokens"] for m in models),
        "cached_tokens": sum(m["cached_tokens"] for m in models),
        "completion_tokens": sum(m["completion_tokens"] for m in models),
        "reasoning_tokens": sum(m["reasoning_tokens"] for m in models),
        "currency": table.currency,
        "amount": _as_text(total) if priced else None,
        "price_unavailable": unavailable,
        "price_config_broken": geladen is None,
        "models": models,
    }


@dataclass(slots=True)
class _SessionTally:
    """Was von einer Sitzung übrig bleibt, wenn ihre Modellzeilen addiert sind.

    ``amount`` bleibt ``None``, solange KEIN Modell dieser Sitzung einen
    gepflegten Preis hat — dieselbe Unterscheidung wie oben: ein ungepflegter
    Preis ist nicht „kostenlos".
    """

    calls: int = 0
    prompt: int = 0
    cached: int = 0
    completion: int = 0
    reasoning: int = 0
    amount: Decimal | None = None
    unavailable: list[str] = field(default_factory=list)

    @property
    def tokens(self) -> int:
        """Was ohne Preistafel die einzige verfügbare Größe ist."""
        return self.prompt + self.completion


async def _grouped_by_session(
    session: AsyncSession, *where: ColumnElement[bool]
) -> list[Any]:
    """Wie ``_grouped_by_model``, nur eine Ebene feiner: je Sitzung UND Modell.

    Je Modell, obwohl die Liste je Sitzung ausgibt: der Preis hängt am Modell,
    und eine Sitzung, die zwei davon benutzt hat, wäre sonst nicht zu rechnen.
    """
    stmt = (
        select(
            UsageEvent.session_id,
            UsageEvent.model,
            func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UsageEvent.cached_tokens), 0),
            func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
            func.coalesce(func.sum(UsageEvent.reasoning_tokens), 0),
            func.coalesce(func.sum(UsageEvent.calls), 0),
        )
        .where(*where)
        .group_by(UsageEvent.session_id, UsageEvent.model)
        .order_by(UsageEvent.session_id, UsageEvent.model)
    )
    return list((await session.execute(stmt)).all())


def _tally_sessions(rows: list[Any], table: Any) -> dict[str, _SessionTally]:
    """Die Modellzeilen je Sitzung zusammenlegen und dabei bepreisen."""
    per: dict[str, _SessionTally] = {}
    for session_id, model, prompt, cached, completion, reasoning, calls in rows:
        tally = per.setdefault(session_id, _SessionTally())
        tally.calls += calls
        tally.prompt += prompt
        tally.cached += cached
        tally.completion += completion
        tally.reasoning += reasoning
        amount = cost_for(
            TokenCounts(model=model, prompt=prompt, cached=cached,
                        completion=completion),
            table,
        )
        if amount is None:
            tally.unavailable.append(model)
        else:
            tally.amount = amount if tally.amount is None else tally.amount + amount
    return per


def _by_cost(item: tuple[str, _SessionTally]) -> tuple[bool, Decimal, int, str]:
    """Teuerste zuerst; ohne Preis nach Token, und stets hinter den bepreisten.

    Der Token-Rang ist nicht bloß ein Gleichstand-Brecher: der ausgelieferte
    Seed pflegt **keine** Preise, also wäre die Liste ohne ihn beim ersten
    Blick auf eine frische Anlage unsortiert — genau dann, wenn man sie
    zuerst öffnet. Die Kennung zuletzt, damit zwei gleich teure Sitzungen
    nicht bei jedem Abruf die Plätze tauschen.
    """
    session_id, tally = item
    return (tally.amount is None, -(tally.amount or Decimal(0)),
            -tally.tokens, session_id)


def _top_sessions(rows: list[Any], table: Any) -> list[dict[str, Any]]:
    """Die teuersten Sitzungen der Auswahl, in derselben Form wie ein Modell."""
    ranked = sorted(_tally_sessions(rows, table).items(), key=_by_cost)
    return [
        {
            "session_id": session_id,
            "calls": tally.calls,
            "prompt_tokens": tally.prompt, "cached_tokens": tally.cached,
            "completion_tokens": tally.completion,
            "reasoning_tokens": tally.reasoning,
            "amount": None if tally.amount is None else _as_text(tally.amount),
            "price_unavailable": tally.unavailable,
        }
        for session_id, tally in ranked[:_TOP_SESSIONS]
    ]


async def session_usage(session: AsyncSession, session_id: str) -> dict[str, Any]:
    """Verbrauch EINER Sitzung.

    Eine Sitzung ohne Zeilen ist kein Fehler, sondern der Normalfall bei Tour
    und Kontext-Begrüßung: die Antwort meldet dann ``empty`` und Nullen.
    """
    return _assemble(
        await _grouped_by_model(session, UsageEvent.session_id == session_id)
    )


async def period_usage(
    session: AsyncSession, start: datetime, end: datetime
) -> dict[str, Any]:
    """Verbrauch eines Zeitraums, Grenzen einschließlich.

    ``start``/``end`` müssen zeitzonenbehaftet sein — die Route setzt UTC an,
    wenn der Aufrufer keine Zone mitschickt (``created_at`` ist
    ``timestamptz``, eine zonenlose Grenze verschöbe sich sonst je nach
    Server).

    Zusätzlich zur Modelltabelle steht hier ``sessions``: die teuersten
    Sitzungen des Zeitraums. Bei der Einzelsitzung fehlt das Feld bewusst —
    „die teuersten Sitzungen dieser Sitzung" ist keine Frage.
    """
    fenster = (UsageEvent.created_at >= start, UsageEvent.created_at <= end)
    antwort = _assemble(await _grouped_by_model(session, *fenster))
    antwort["sessions"] = _top_sessions(
        await _grouped_by_session(session, *fenster), load_pricing() or PricingArea(),
    )
    return antwort
