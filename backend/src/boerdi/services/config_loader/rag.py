"""RAG-area config loaders — port of ALT config_loader/rag.py."""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def load_rag_config() -> dict[str, Any]:
    """Root mapping area-name -> {mode, agent, ...}; every dict entry.

    ``mode`` only steers the pattern path (``route_head._resolve_rag_areas`` reads it), ``agent``
    only the loop (``agent_knowledge.fuer_die_schleife``). Paket 15 (A4): entries without
    ``mode`` used to be dropped here — for the loop too, so an agent-only area was impossible.
    """
    data = area("05-knowledge/rag-config")
    return {name: cfg for name, cfg in data.items() if isinstance(cfg, dict)}


def get_on_demand_rag_areas() -> list[str]:
    return [n for n, c in load_rag_config().items() if c.get("mode") == "on-demand"]


def get_all_rag_areas() -> list[str]:
    return list(load_rag_config().keys())
