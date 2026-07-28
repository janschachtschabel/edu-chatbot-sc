"""Golden-flow loader — port of ALT config_loader/gold_flows.py."""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def load_gold_flows() -> list[dict[str, Any]]:
    """Only dict entries that have turns (ALT filter); [] on missing/corrupt."""
    flows = area("eval/gold-flows").get("flows")
    if not isinstance(flows, list):
        return []
    return [f for f in flows if isinstance(f, dict) and f.get("turns")]
