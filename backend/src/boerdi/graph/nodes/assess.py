"""Assess-Node — Safety ∥ Classify ∥ Memory als Parallel-Gruppe (P4-3).

Port von ALT ``chat_pipeline_phases._assess_safety_classify_memory``. Ablauf:
Regex-Pre-Gate → bei harter Krise Kurzschluss (kein LLM: minimale
``ClassificationResult`` synthetisieren, damit die Pipeline unverändert
weiterläuft; die Pattern-Engine wählt M01 später über
``safety.enforced_pattern``) → sonst Safety/Classify/Memory nebenläufig
(``asyncio.gather(return_exceptions=True)``) mit Per-Zweig-Fallbacks. Schreibt
``safety``/``classification``/``memories`` in den ``TurnContext``.

Dependency-Injection (Regel 3 — kein globaler Engine): ``memory_fetch`` wird
injiziert, weil Memory ein pro-App-DB-Handle braucht; der Graph-Bau (P4-6) bindet
das echte ``services.db_sessions.get_memory`` an die App-Engine. ``assess_safety`` /
``classify_input`` sind global (über Settings) konfigurierte Services →
Direktaufruf (in Tests am Modul monkeypatchbar).

simplify: ALTs Studio-Trace-Instrumentierung (``tracer.parallel_group`` /
``task_start`` / ``task_end`` / ``finish``) ist bis zum Tracer-Subsystem
zurückgestellt — sie ist reine Telemetrie und ändert das Routing-Tripel nicht.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from boerdi.api.schemas import ClassificationResult
from boerdi.graph.state import TurnContext
from boerdi.obs.progress import NO_PROGRESS, TurnProgress
from boerdi.obs.tasks import cancel_and_drain
from boerdi.obs.zeiten import schritt
from boerdi.services.classify import classify_input
from boerdi.services.engine_choice import laeuft_ueber_die_schleife
from boerdi.services.rag.vorab import rag_einbettung_vorab
from boerdi.services.safety import assess_safety
from boerdi.services.safety.regex_gate import regex_gate
from boerdi.services.safety.service import regex_rueckfall

logger = logging.getLogger(__name__)

# (session_id) -> Erinnerungs-Dicts. Gebunden an die App-Engine in P4-6.
MemoryFetch = Callable[[str], Awaitable[list[dict[str, Any]]]]

#: Wie lange ``assess`` nach Sicherheit und Klassifikation noch auf die Vorab-
#: Einbettung (T1) wartet — Review Paket 7, B-1. Gemessen läuft sie in 0,3–1 s, die
#: Klassifikation in 2–4 s: fast immer ist sie vorher fertig. Hängt der Dienst,
#: kostet es den Zug höchstens diese Frist; der Abruf bettet dann selbst ein.
_EINBETTUNG_NACHFRIST_S = 0.5


async def _nach_der_frist(vorab: asyncio.Task) -> Any:
    """Das Ergebnis der Vorab-Einbettung — oder ``None`` nach der Nachfrist bzw.
    bei einem Fehler. Eine nicht fertige Aufgabe wird abgebrochen, nicht liegen
    gelassen."""
    try:
        return await asyncio.wait_for(asyncio.shield(vorab), _EINBETTUNG_NACHFRIST_S)
    except TimeoutError:
        await cancel_and_drain([vorab])
        return None
    except Exception as e:  # noqa: BLE001 — Vorarbeit; der Abruf bettet dann selbst ein
        logger.warning("rag embedding ahead failed: %s", e)
        return None


def _fallback_classification(
    session_state: dict, intent_id: str, **extra: Any
) -> ClassificationResult:
    """Minimale ``ClassificationResult`` mit Persona/State aus der Session, damit
    die Pipeline bei Krise/Classify-Fehler unverändert weiterläuft (ALT-Parität:
    Persona ``or P-AND``, State ``or S1``, Confidence 0.0)."""
    return ClassificationResult(
        persona_id=session_state.get("persona_id") or "P-AND",
        intent_id=intent_id,
        intent_confidence=0.0,
        next_state=session_state.get("state_id") or "S1",
        **extra,
    )


async def assess(
    ctx: TurnContext,
    memory_fetch: MemoryFetch,
    progress: TurnProgress = NO_PROGRESS,
    engine: str = "pattern",
) -> TurnContext:
    """Safety + Classify + Memory als parallele Gruppe; liefert den mutierten
    ``ctx`` (safety, classification, memories gesetzt)."""
    # C9: vor der Arbeit melden, nicht danach — dieser Abschnitt dauert ~2,5 s und
    # war im Widget bisher stummer Spinner.
    progress.start("safety_classify", "Safety + Classify + Memory (parallel)")
    ss = ctx.session_state
    signals = ss.get("signal_history", [])
    quick_gate = regex_gate(ctx.req.message, signals)

    if quick_gate.risk_level == "high":
        # Harte Krise aus Regex → keine LLM-Zyklen für Classify verschwenden.
        ctx.safety = quick_gate
        ctx.classification = _fallback_classification(
            ss, "I07", signals=[], entities={}, turn_type="initial",
        )
        ctx.memories = []
        return ctx

    # Safety + Classify + Memory-Fetch parallel — Memory hängt nur an der
    # session_id, ist also unabhängig von Klassifikation/Safety.
    async def _safety():
        # Regex + Moderation ohne eigenen LLM-Aufruf — steht sonst nirgends im
        # Debug-Block (Plan 2026-09-30, T8).
        with schritt("assess.safety", ctx.usage):
            return await assess_safety(ctx.req.message, signals, usage_acc=ctx.usage)

    async def _classify():
        # A4b: Der Agent-Modus hat keinen Klassifikator — das ist sein Zweck
        # („eine einfachere und schnellere Variante ohne Klassifikationsprompt").
        # Die Bedingung fragt nach der Schleife und nicht nach einem Namen.
        # Die nachgelagerten Knoten brauchen trotzdem eine gültige Form, und die
        # gibt es hier schon: dieselbe Funktion trägt den Krisen-Kurzschluss und
        # den Classify-Fehlerfall. Die Verzweigung sitzt IN der Coroutine und
        # nicht am ``gather`` darunter — so bleibt der Weg der Muster-Engine
        # Zeile für Zeile derselbe.
        if laeuft_ueber_die_schleife(engine):
            return _fallback_classification(ss, "I01")
        return await classify_input(
            ctx.req.message, ctx.history, ss, ctx.env,
            ctx.req.canvas_state, usage_acc=ctx.usage,
        )

    async def _memory():
        return await memory_fetch(ctx.req.session_id)

    async def _einbettung():
        # T1 (Paket 7): die Einbettung für den RAG-Vorabruf des Muster-Wegs —
        # neben der Klassifikation statt nach der Musterwahl (``rag/vorab``). Die
        # Schleife holt Wissen nur auf Zuruf, mit der Suchanfrage des Modells.
        if laeuft_ueber_die_schleife(engine):
            return None
        return await rag_einbettung_vorab(ctx.req.message)

    haupt = asyncio.gather(_safety(), _classify(), _memory(), return_exceptions=True)
    # Erst nach dem Hauptteil gestartet: hinter der b-api teilen sich alle Aufrufe
    # wenige Plätze — Sicherheit und Klassifikation reihen sich zuerst ein (B-1).
    vorab = asyncio.create_task(_einbettung())
    try:
        safety, classification, memories = await haupt
        einbettung = await _nach_der_frist(vorab)
    finally:
        if not vorab.done():
            vorab.cancel()
    # ``BaseException``: ``gather`` liefert ein ``CancelledError`` als Ergebnis, das
    # keine ``Exception`` ist — es lief sonst als Entscheidung weiter (Paket 18A).
    if isinstance(safety, BaseException):
        logger.error("safety task failed: %s: %s", type(safety).__name__, safety)
        safety = regex_rueckfall(ctx.req.message, signals)
    if isinstance(classification, BaseException):
        logger.error("classify task failed: %s: %s", type(classification).__name__,
                     classification)
        classification = _fallback_classification(ss, "I01")
    if isinstance(memories, BaseException):
        logger.warning("memory fetch failed (will use empty list): %s", memories)
        memories = []

    ctx.safety = safety
    ctx.classification = classification
    ctx.memories = memories
    ctx.rag_einbettung = einbettung
    return ctx
