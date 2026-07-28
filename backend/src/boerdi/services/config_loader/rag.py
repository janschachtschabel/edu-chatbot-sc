"""RAG-area config loaders — port of ALT config_loader/rag.py."""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def load_rag_config() -> dict[str, Any]:
    """Root mapping area-name -> {mode, ...}; keeps only dict entries with 'mode'."""
    data = area("05-knowledge/rag-config")
    return {
        name: cfg for name, cfg in data.items()
        if isinstance(cfg, dict) and "mode" in cfg
    }


def get_always_on_rag_areas() -> list[str]:
    return [n for n, c in load_rag_config().items() if c.get("mode") == "always"]


def get_on_demand_rag_areas() -> list[str]:
    return [n for n, c in load_rag_config().items() if c.get("mode") == "on-demand"]


def get_all_rag_areas() -> list[str]:
    return list(load_rag_config().keys())
