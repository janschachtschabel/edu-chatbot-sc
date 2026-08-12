"""Die eine Stelle, an der entschieden wird, WER einbettet (W8, 2026-08-09).

Vorher riefen vier Stellen ``services.llm.embedding`` direkt — den
LiteLLM-Transport. Das ist der richtige Baustein für den Anbieter-Weg, aber der
falsche Ort für eine Wahl: ``llm.py`` ist Transport und darf nichts über RAG
oder ONNX wissen (die Abhängigkeit zeigt nach innen, ``rag`` → ``llm``, nicht
umgekehrt — sonst entsteht ein Ring mit ``rag/retrieval``).

Also diese Fassade. Sie kennt beide Wege und sonst nichts:

* ``api`` (Vorgabe) — LiteLLM zum Anbieter. Nutzer-Entscheid 2026-08-09: der
  Betrieb bleibt hier, weil der Chat zeitkritisch ist und ein Netzaufruf
  nebenläufig skaliert, während lokale Inferenz das CPU-Budget teilt.
* ``local`` — ONNX im Haus (``embed_local``), im gedeckelten Rerank-Pool.

**Das ``kind``-Argument ist Pflicht, nicht Deko.** e5-Modelle verlangen
``query:``/``passage:``-Präfixe; wer sie vertauscht, bekommt ein Modell, das
lädt, rechnet und schlechter sucht, ohne dass etwas rot wird. Der Anbieter-Weg
ignoriert es — genau deshalb muss es an der Fassade sitzen und nicht im lokalen
Backend allein, sonst wüsste beim Umschalten niemand mehr, was ein Aufruf war.
"""

from __future__ import annotations

import asyncio
import logging

from boerdi.services.llm import embedding as _api_embedding
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Die beiden Wege. Ein unbekannter Wert ist ein Fehler, kein stiller Rückfall:
#: ein Tippfehler in der Env darf nicht dazu führen, dass Vektoren aus einem
#: anderen Raum in dieselbe Spalte wandern.
BACKENDS = ("api", "local")


def embed_backend() -> str:
    gewaehlt = (get_settings().embed_backend or "api").strip().lower()
    if gewaehlt not in BACKENDS:
        raise ValueError(f"EMBED_BACKEND={gewaehlt!r} unbekannt. Erlaubt: {BACKENDS}")
    return gewaehlt


async def embed_text(text: str, *, kind: str = "query") -> list[float]:
    """Ein Vektor für ``text``.

    ``kind`` ist ``"query"`` (Suchtext) oder ``"passage"`` (gespeicherter
    Abschnitt). Fehler laufen durch — die Aufrufer besitzen die Politik.
    """
    if embed_backend() == "local":
        from boerdi.services.rag.rerank import run_in_rerank_pool

        # Im gedeckelten Pool: lokale Inferenz ist CPU-Arbeit und teilt sich das
        # Budget mit dem Reranker. Direkt im Event-Loop stünde der Worker.
        return await run_in_rerank_pool(_embed_local_sync, text, kind)
    return await _api_embedding(text)


def _embed_local_sync(text: str, kind: str) -> list[float]:
    """Positionale Hülle — der Executor reicht keine Keyword-Argumente durch."""
    from boerdi.services.rag.embed_local import embed_local

    return embed_local(text, kind=kind)


def expected_dim() -> int:
    """Die Vektorlänge, die dieser Prozess erzeugen wird.

    Gebraucht beim Start und im Ingest: passt sie nicht zur pgvector-Spalte,
    schreibt der Prozess Vektoren, die niemand mehr sinnvoll durchsuchen kann.
    """
    if embed_backend() == "local":
        from boerdi.services.rag.embed_local import _model_spec

        return _model_spec().dim
    from boerdi.services.llm_models import get_embed_dim

    return get_embed_dim()


async def embed_many(texts: list[str], *, kind: str = "passage") -> list[list[float] | None]:
    """Viele Texte einbetten — nebenläufig, aber **gedeckelt**.

    Der Ingest bettete bisher streng seriell ein: ein Netz-Roundtrip je Chunk.
    Bei 906 Chunks sind das 906 Wartezeiten hintereinander. Nebenläufig
    schrumpft das auf ``ceil(n / EMBED_INGEST_PARALLEL)`` Runden.

    **Warum ein EIGENER Deckel und nicht der Semaphor aus ``llm.py``.** Der
    dort (``LLM_MAX_CONCURRENCY``, Vorgabe 20) gehört dem Chat. Liesse man den
    Ingest hineinlaufen, könnte ein Redaktions-Import alle 20 Plätze belegen und
    die Züge echter Nutzer warten lassen — genau das Blockieren, das hier
    vermieden werden soll. Der eigene, kleinere Deckel ist die Trennlinie.

    Beim lokalen Backend läuft ohnehin alles durch den Rerank-Pool; die
    Nebenläufigkeit ist dann die des Pools, nicht diese hier.

    Rückgabe: je Text ein Vektor oder ``None``, wenn genau dieser fehlschlug —
    ein kaputter Chunk darf den Import nicht abbrechen (ALT-Verhalten).
    """
    if not texts:
        return []
    deckel = asyncio.Semaphore(max(1, get_settings().embed_ingest_parallel))

    async def einer(text: str) -> list[float] | None:
        async with deckel:
            try:
                return await embed_text(text, kind=kind)
            except Exception as err:  # noqa: BLE001 — je Chunk isoliert
                logger.warning("Embedding fehlgeschlagen: %s", err)
                return None

    return await asyncio.gather(*(einer(t) for t in texts))
