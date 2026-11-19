"""Viele Texte in EINEM Einbettungsaufruf (Paket N3, Plan 2026-11-19).

Geschwister von ``llm.embedding`` (ein Text, der RAG-Weg): dasselbe Modell (``LLM_EMBED_MODEL``
bzw. die Vorgabe des Anbieters), dieselbe Route, Frist und derselbe Deckel (``platz``), aber eine
Liste als ``input`` — die Zuordnung Datei → Punkt bettet Punkte und Materialien zusammen ein.
Anders als ``llm.embedding`` bucht sie den Verbrauch in den Zähler des Zugs (``usage_acc``), wie
``chat_completion``: so steht die Einbettung in der Kostenschau neben den Modellaufrufen.

Immer der Anbieter-Weg; ``EMBED_BACKEND=local`` gilt nur für die Wissensbasis (``rag/embed``).
Fehler laufen durch — der Aufrufer besitzt die Politik.
"""

from __future__ import annotations

import time
from typing import Any

from boerdi.obs import usage as _usage
from boerdi.services import llm
from boerdi.services.llm_models import get_embed_model
from boerdi.services.llm_parallel import platz
from boerdi.settings import get_settings

#: Wie ``llm.embedding``: so viele Zeichen je Text (ALT-Parität).
ZEICHEN: int = 8000


def _vektor(item: Any) -> list[float]:
    return list(item["embedding"] if isinstance(item, dict) else item.embedding)


def _index(item: Any) -> int:
    return int(item["index"] if isinstance(item, dict) else item.index)


async def einbettungen(texte: list[str], *, usage_acc: dict[str, Any] | None = None,
                       phase: str | None = None, kanal: str = "live",
                       platz_frist_s: float | None = None) -> list[list[float]]:
    """Je Text ein Vektor, in der Reihenfolge der Texte (nach ``index`` der Antwort).
    ``platz_frist_s``: so lange höchstens auf einen Platz warten (``llm_parallel.platz``) — kürzer
    als ``LLM_SLOT_WAIT_S`` scheitert nur dieser Aufruf (``LlmAusgelastet``), der Zug nicht."""
    if not texte:
        return []
    litellm_model, api_base, api_key, extra_headers = llm.route(get_embed_model())
    kwargs: dict[str, Any] = {
        "model": litellm_model, "input": [t[:ZEICHEN] for t in texte], "api_base": api_base,
        "api_key": api_key, "timeout": get_settings().llm_read_timeout}
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers
    t0 = time.perf_counter()
    async with platz(kanal, frist_s=platz_frist_s):
        resp = await llm._aembedding(**kwargs)
    ms = int((time.perf_counter() - t0) * 1000)
    if usage_acc is not None:
        _usage.add_usage(usage_acc, _usage.extract_usage(resp), phase, ms=ms)
    return [_vektor(item) for item in sorted(resp.data, key=_index)]
