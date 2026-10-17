"""Wie viele LLM-Aufrufe gleichzeitig laufen — je Anbieter (Paket 7, L3; Review A-2/A-6).

Aus ``services/llm.py`` gelöst, als die Grenze vom Anbieter abhängig wurde.

**Ein Deckel je Anbieter, für alle Kanäle.** Nutzer-Vorgabe 2026-10-09: bei OpenAI bis
zu 20 gleichzeitige Aufrufe — direkt wie über ``b-api-openai`` (Paket 8) —, auf der
AcademicCloud vorerst 2. Bis zum Review
liefen bei OpenAI Chat (20), Hintergrund (4) und Import (4) getrennt — 28 zugleich —,
hinter der b-api teilten sie sich EINEN FIFO-Semaphor, und ein Import mit 200
Abschnitten stellte jeden Chat-Aufruf hinter sich (Review A-2).

Jetzt zwei Stufen:

- ``live`` (Chat, Klassifikator, Streaming, Such-Einbettung) nimmt nur einen Platz
  am Anbieter-Deckel.
- ``bg`` (Judge, Simulator, Szenarien) und ``ingest`` (Import-Embeddings) stehen
  zuerst hinter ihrem eigenen Deckel (``BG_LLM_MAX_CONCURRENCY`` 4,
  ``EMBED_INGEST_PARALLEL`` 4) und hinter einem gemeinsamen „nebenher“-Deckel von
  Anbieter−1. Einer bleibt so immer für den Chat frei, und in der Schlange am
  Anbieter steht vor ihm höchstens Anbieter−1 Fremdarbeit.

``ingest_semaphore()`` ist der Deckel der LOKALEN Einbettung (CPU, kein Anbieter):
nur der eigene Kanal, kein Platz beim Anbieter.

Die Moderation hat eigene Plätze (:data:`MODERATION_PARALLEL`, Paket 9). Am
Anbieter-Deckel wartete sie innerhalb ihrer Frist hinter laufenden Antwort-Strömen,
die ihren Platz bis zum Ende halten — bei 20 gleichzeitigen Antworten lief die Frist
ab, und jede Nachricht ging ungeprüft durch (Review Paket 7, MAJOR 8). Moderationen
sind kurz; hinter der b-api können sie den Deckel um höchstens diese Zahl
überschreiten — ein 429 lässt dann diese eine Prüfung aus, nicht alle.

Je Ereignisschleife ein Semaphor je Name: ein einziger Semaphor auf Modulebene bände
sich an die erste Schleife und bräche unter ``asyncio.run`` in Tests.
``LLM_MAX_CONCURRENCY`` setzt den Anbieter-Deckel ausdrücklich, mindestens 2.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

from boerdi.services.llm_models import get_provider
from boerdi.settings import get_settings

#: Anbieter-Deckel beider OpenAI-Wege, wenn ``LLM_MAX_CONCURRENCY`` nicht gesetzt ist.
LIVE_VORGABE = 20
#: Abweichende Anbieter-Deckel.
_B_API_DECKEL = {"b-api-academiccloud": 2}
#: Gleichzeitige Moderationen, neben dem Anbieter-Deckel (Modulkopf).
MODERATION_PARALLEL = 4

_semaphores: dict[tuple[int, str], asyncio.Semaphore] = {}


def reset() -> None:
    """Drop cached semaphores (hot-reload / test isolation)."""
    _semaphores.clear()


def _anbieter_deckel() -> int:
    s = get_settings()
    if s.llm_max_concurrency:
        return s.llm_max_concurrency
    return _B_API_DECKEL.get(get_provider(), LIVE_VORGABE)


def _groesse(name: str) -> int:
    s = get_settings()
    if name == "bg":
        return s.bg_llm_max_concurrency
    if name == "ingest":
        return s.embed_ingest_parallel
    if name == "nebenher":
        return max(1, _anbieter_deckel() - 1)
    if name == "moderation":
        return MODERATION_PARALLEL
    return _anbieter_deckel()                    # "anbieter"


def _semaphore(name: str) -> asyncio.Semaphore:
    """Der Semaphor ``name`` dieser Schleife. ``live`` ist der Anbieter-Deckel —
    der Chat nimmt nur ihn (Aufrufer und Tests lesen ihn unter diesem Namen)."""
    if name == "live":
        name = "anbieter"
    key = (id(asyncio.get_running_loop()), name)
    sem = _semaphores.get(key)
    if sem is None:
        sem = asyncio.Semaphore(_groesse(name))
        _semaphores[key] = sem
    return sem


@contextlib.asynccontextmanager
async def platz(kanal: str) -> AsyncIterator[None]:
    """Ein Platz im Kanal ``kanal`` (``live``, ``bg`` oder ``ingest``) — siehe
    Modulkopf. Fremdarbeit wartet zuerst auf ihren eigenen Deckel, dann auf den
    gemeinsamen, und reiht sich erst dann beim Anbieter ein."""
    if kanal == "live":
        async with _semaphore("anbieter"):
            yield
        return
    async with _semaphore(kanal), _semaphore("nebenher"), _semaphore("anbieter"):
        yield


def semaphore(
    *, background: bool = False,
) -> asyncio.Semaphore | contextlib.AbstractAsyncContextManager:
    """Öffentlicher Zugang für die Einstiege außerhalb von ``llm`` (Klassifikator,
    Streaming): der Anbieter-Deckel selbst — bzw. für Hintergrund-Arbeit ein Platz
    über :func:`platz`."""
    return platz("bg") if background else _semaphore("anbieter")


def moderations_semaphore() -> asyncio.Semaphore:
    """Die eigenen Plätze der Moderation (:data:`MODERATION_PARALLEL`, Modulkopf)."""
    return _semaphore("moderation")


def ingest_semaphore() -> asyncio.Semaphore:
    """Der Deckel der LOKALEN Import-Einbettung (``EMBED_INGEST_PARALLEL``): CPU-Arbeit
    im Rerank-Pool, deshalb ohne Platz beim Anbieter (Review A-2). Die Einbettung über
    den Anbieter nimmt ``embedding(kanal="ingest")`` selbst über :func:`platz`."""
    return _semaphore("ingest")
