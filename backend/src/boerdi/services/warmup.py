"""Start-Vorwärmung (W1) — Port von ALTs Hintergrund-Warmups (``main.py:173-178``).

Warum: der erste Zug einer frischen Instanz zahlt sonst die kalten Kosten. Am
2026-07-27 live gemessen: erster Zug ``safety_classify`` bei 1,22 s, zweiter bei
0,10 s. In NEU wiegt das schwerer als in ALT, weil NEU horizontal skaliert
(``compose.prod.yml``: backend ×N) — jede Replica und jedes Rolling-Deploy zahlt
den Aufschlag erneut, und echte Nutzer treffen kalte Replicas.

Zwei Warmups, beide fire-and-forget:

* ``warm_vocabularies`` — lädt die vier WLO-Vokabular-Caches. ``prewarm_vocabularies``
  war bereits gebaut und getestet, und ``mcp/tool_cache.py`` beschrieb sie als „beim
  Backend-Start vorgewärmt" — **gerufen hat sie niemand**. Ohne sie kostet der erste
  Such-Zug mehrere MCP-Round-Trips.
* ``warm_llm_connection`` — Moderations-Ping (bei OpenAI kostenlos), wärmt
  Verbindung + TLS. Grenze wie in ALT: das wärmt den Moderations-Host; läuft der
  Chat über eine andere Basis-URL (B-API), bleibt dessen erster Handshake kalt.

**Bewusst NICHT vorgewärmt** (Nutzer-Entscheid 2026-07-27): ALTs
``_embed_seed_chunks``. Es schreibt Embeddings in die DB — bei N Replicas würden
alle gleichzeitig dieselben berechnen und schreiben, und ein Deploy löste
LLM-Kosten aus. Der Weg dafür bleibt der Admin-Endpunkt ``/api/rag/embed``.
Ebenfalls entfallen, mit eigenem Grund: ``_warmup_reranker`` (V13 — kein
CPU-Reranker in NEU) und ``_warmup_tokenizer`` (keine tiktoken-Infra).

Fail-safe ist Vertrag: Vorwärmung ist reine Beschleunigung. Ein kaltes MCP, ein
fehlender Schlüssel oder ein hängender Anbieter darf den Start nie gefährden —
der Lazy-Pfad (``_ensure_label_cache`` beim ersten echten Bedarf) trägt weiter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from typing import Any

from boerdi.obs.tasks import _spawn_background
from boerdi.services.mcp.arg_resolvers import prewarm_vocabularies
from boerdi.services.rag.rerank import run_in_rerank_pool, warm_reranker
from boerdi.services.safety.moderation import moderate

logger = logging.getLogger(__name__)

# Obergrenze je Warmup (ALT: ``asyncio.wait_for(..., timeout=10.0)``). Ein
# hängender Anbieter soll keinen Task für die Lebensdauer des Prozesses halten.
_WARMUP_TIMEOUT_SECONDS = 10.0


async def warm_vocabularies() -> None:
    """WLO-Vokabular-Caches vorladen, damit schon der erste Such-Zug warm ist."""
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(prewarm_vocabularies(), timeout=_WARMUP_TIMEOUT_SECONDS)
        logger.info("vocabulary warmup done in %.0fms", (time.perf_counter() - t0) * 1000)
    except Exception as err:  # noqa: BLE001 — Beschleunigung, kein Pflichtpfad
        logger.warning("vocabulary warmup skipped: %s", err)


async def warm_llm_connection() -> None:
    """Verbindung zum LLM-Anbieter mit einem kostenlosen Moderations-Ping wärmen.

    ``moderate`` ist fail-open: ohne Credential liefert es ``{}`` und tut nichts —
    der Warmup ist damit auf Setups ohne OpenAI-Schlüssel stumm statt laut.
    """
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(moderate("warmup"), timeout=_WARMUP_TIMEOUT_SECONDS)
        logger.info("llm warmup done in %.0fms", (time.perf_counter() - t0) * 1000)
    except Exception as err:  # noqa: BLE001 — s.o.
        logger.warning("llm warmup skipped: %s", err)


async def warm_cross_encoder() -> None:
    """Den ONNX-Cross-Encoder laden und einmal rechnen lassen (W7).

    Das Laden kostet Sitzungsaufbau und Speicherzuteilung — beim ersten echten
    Zug wäre das ein sichtbarer Aufschlag. **Im Rerank-Pool**, nicht im Loop:
    das Laden ist selbst CPU-Arbeit, und der Pool ist genau dafür da.

    Der Modul-Kopf nannte dieses Warmup bis hierher als „bewusst entfallen
    (V13 — kein CPU-Reranker in NEU)". Mit W7 gibt es ihn wieder.
    """
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(
            run_in_rerank_pool(warm_reranker), timeout=_WARMUP_TIMEOUT_SECONDS,
        )
        logger.info("cross-encoder warmup done in %.0fms", (time.perf_counter() - t0) * 1000)
    except Exception as err:  # noqa: BLE001 — s.o.
        logger.warning("cross-encoder warmup skipped: %s", err)


def spawn_startup_warmups(tasks: list[Coroutine[Any, Any, None]] | None = None) -> None:
    """Alle Warmups im Hintergrund starten und sofort zurückkehren.

    Der Start darf nicht auf einen MCP-Round-Trip warten — sonst verzögert die
    Vorwärmung genau das, was sie beschleunigen soll. ``_spawn_background`` hält
    die starke Referenz (der Loop hält nur Weak-Refs) und holt die Exception ab.
    ``tasks`` ist die Test-Naht; im Betrieb bleibt sie leer.
    """
    vorgabe = [warm_vocabularies(), warm_llm_connection(), warm_cross_encoder()]
    for coro in tasks if tasks is not None else vorgabe:
        _spawn_background(coro)
