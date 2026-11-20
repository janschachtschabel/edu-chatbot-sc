"""Grenze, Sperre und Zwischenspeicher der Texterkennung je Sitzung (Review Paket C, Befund 3;
zweites Review 2 und 5).

Ohne sie ließ sich dieselbe Scan-PDF in einer Sitzung beliebig oft lesen — jede Seite ein
bezahlter Aufruf; abgewiesene oder ersetzte Uploads zählen in keiner Grenze.

- **Seitenbudget je Sitzung** aus der Datenbank: die Aufrufe, die unter der Quelle
  :data:`ocr.PHASE` in ``usage_events`` gebucht sind (:func:`seiten_gebucht`) — auch je Seite, die
  die Frist mitten im Aufruf abbrach (``ocr._abgebrochen_buchen``: ein Aufruf, Token 0), und jede
  Wiederholung nach einem vorübergehenden Fehler (bezahlt ist bezahlt). Höchstens
  ``lokal_max_dateien × ocr_max_seiten`` (Studio); der Rest deckelt ``seiten_max``, ist nichts mehr
  frei, wirft der Leser :class:`ocr.OcrGrenze` (die Aufnahme antwortet 429 ``grenze_ocr``).
- **Sperre je Sitzung** (zweites Review 2): je Prozess liest eine Sitzung nur eine PDF zugleich;
  den Rest liest sie erst unter der Sperre, und gebucht wird, bevor die Sperre fällt — ein zweiter
  Upload sieht also den neuen Rest. Dieselbe Datei zugleich wartet und bekommt das Ergebnis aus dem
  Zwischenspeicher. **Grenze:** über mehrere Kopien gibt es keine Reservierung — je Kopie gilt das
  Budget getrennt (Vorgabe ist eine Kopie, ``BACKEND_REPLICAS=1``).
- **Zwischenspeicher** im Prozess, je ``(Sitzung, SHA-256 des Rumpfs)``, nur ganz gelesene
  Ergebnisse (nicht ``gekuerzt``), höchstens :data:`MAX_EINTRAEGE`, :data:`MAX_ZEICHEN` Zeichen
  zusammen (die ältesten gehen zuerst) und :data:`HALTBAR_S`. Gehalten wird nur der Text, den die
  Ablage ohnehin speichert (``dokument_uploads``).
"""

from __future__ import annotations

import asyncio
import hashlib
import time
import weakref
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from boerdi.db.models import UsageEvent
from boerdi.obs.usage import new_accumulator
from boerdi.services.dokumente import ocr
from boerdi.services.dokumente.ocr import OcrErgebnis, OcrGrenze, OcrLesen

__all__ = ["OcrGrenze", "leser", "leeren", "seiten_gebucht"]

MAX_EINTRAEGE: Final = 64
MAX_ZEICHEN: Final = 5_000_000
HALTBAR_S: Final = 3600.0

_ablage: OrderedDict[tuple[str, str], tuple[float, OcrErgebnis]] = OrderedDict()
_sperren: weakref.WeakValueDictionary[tuple[int, str], asyncio.Lock] = (
    weakref.WeakValueDictionary())


def leeren() -> None:
    """Zwischenspeicher leeren (Tests)."""
    _ablage.clear()


async def seiten_gebucht(session: AsyncSession, session_id: str) -> int:
    """So viele Seitenaufrufe der Texterkennung hat die Sitzung schon gebucht."""
    summe = await session.scalar(
        select(func.coalesce(func.sum(UsageEvent.calls), 0))
        .where(UsageEvent.session_id == session_id, UsageEvent.quelle == ocr.PHASE))
    return int(summe or 0)


def _sperre(session_id: str) -> asyncio.Lock:
    """Die Sperre der Sitzung in dieser Ereignisschleife (lebt, solange sie jemand hält)."""
    schluessel = (id(asyncio.get_running_loop()), session_id)
    sperre = _sperren.get(schluessel)
    if sperre is None:
        sperre = _sperren[schluessel] = asyncio.Lock()
    return sperre


def _gemerkt(schluessel: tuple[str, str]) -> OcrErgebnis | None:
    eintrag = _ablage.get(schluessel)
    if eintrag is None:
        return None
    if time.monotonic() - eintrag[0] > HALTBAR_S:
        del _ablage[schluessel]
        return None
    _ablage.move_to_end(schluessel)
    return eintrag[1]


def _merken(schluessel: tuple[str, str], ergebnis: OcrErgebnis) -> None:
    _ablage[schluessel] = (time.monotonic(), ergebnis)
    _ablage.move_to_end(schluessel)
    while len(_ablage) > MAX_EINTRAEGE or (
            len(_ablage) > 1 and sum(len(e.markdown) for _, e in _ablage.values()) > MAX_ZEICHEN):
        _ablage.popitem(last=False)


def leser(*, session_id: str, budget: int, seiten_max: int,
          gebucht: Callable[[], Awaitable[int]],
          buchen: Callable[[dict[str, Any]], Awaitable[Any]], frist_ende: float) -> OcrLesen:
    """Die Texterkennung für ``aufnahme.aufbereiten`` (``ocr_lesen``) mit Budget, Sperre und
    Zwischenspeicher. ``gebucht()`` liefert die schon gebuchten Seiten der Sitzung, ``buchen(acc)``
    schreibt den Verbrauch eines Laufs (unter der Sperre, auch nach einer Ausnahme)."""

    async def lesen(rumpf: bytes) -> OcrErgebnis:
        schluessel = (session_id, hashlib.sha256(rumpf).hexdigest())
        if (gemerkt := _gemerkt(schluessel)) is not None:
            return gemerkt
        async with _sperre(session_id):
            if (gemerkt := _gemerkt(schluessel)) is not None:
                return gemerkt          # dieselbe Datei lief gerade
            rest = budget - await gebucht()
            if rest <= 0:
                raise OcrGrenze
            verbrauch = new_accumulator()
            try:
                ergebnis = await ocr.seiten_lesen(rumpf, seiten_max=min(seiten_max, rest),
                                                  frist_ende=frist_ende, usage_acc=verbrauch)
            finally:
                if verbrauch["models"]:
                    await buchen(verbrauch)
            if ergebnis.gelesen and not ergebnis.gekuerzt:
                _merken(schluessel, ergebnis)
            return ergebnis

    return lesen
