"""MCP server registry loaders — port of ALT config_loader/mcp.py.

Primary server ``wlo-mcp``: URL comes from env MCP_SERVER_URL (settings),
never from YAML/DB; save strips it and restores the primary at index 0.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services.config_loader import _store
from boerdi.services.config_loader._store import area
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_PRIMARY_ID = "wlo-mcp"
_UI_META_KEYS = ("url_source", "url_env_var", "url_readonly", "tool_descriptions")
_PRIMARY_SKELETON: dict[str, Any] = {
    "id": _PRIMARY_ID,
    "name": "WLO MCP",
    "description": "Primärer WLO-Suchserver",
    "enabled": True,
    "tools": [],
}


def load_mcp_servers() -> list[dict[str, Any]]:
    servers = area("05-knowledge/mcp-servers").get("servers") or []
    out: list[dict[str, Any]] = []
    for raw in servers:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        server = dict(raw)
        if server["id"] == _PRIMARY_ID:
            server["url"] = get_settings().mcp_server_url
            server["url_source"] = "env"
            server["url_env_var"] = "MCP_SERVER_URL"
            server["url_readonly"] = True
        else:
            server["url_source"] = "yaml"
            server["url_readonly"] = False
        out.append(server)
    return out


def get_enabled_mcp_servers() -> list[dict[str, Any]]:
    return [s for s in load_mcp_servers() if s.get("enabled", True)]


async def save_mcp_servers(servers: list[dict[str, Any]]) -> None:
    """Persist the registry: strip UI meta + primary URL; primary always
    restored at index 0 (ALT protection against dropping it)."""
    cleaned: list[dict[str, Any]] = []
    for raw in servers or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        server = {k: v for k, v in raw.items() if k not in _UI_META_KEYS}
        if server["id"] == _PRIMARY_ID:
            server.pop("url", None)  # env-owned, never persisted
        cleaned.append(server)

    if not any(s["id"] == _PRIMARY_ID for s in cleaned):
        existing = next(
            (s for s in (area("05-knowledge/mcp-servers").get("servers") or [])
             if isinstance(s, dict) and s.get("id") == _PRIMARY_ID),
            None,
        )
        logger.warning("mcp-servers save without primary — restoring %s", _PRIMARY_ID)
        restored = {k: v for k, v in (existing or _PRIMARY_SKELETON).items()
                    if k not in _UI_META_KEYS}
        restored.pop("url", None)
        cleaned.insert(0, restored)

    if _store._store is None:
        raise RuntimeError("config store not bound")
    await _store._store.put(
        "05-knowledge/mcp-servers", {"servers": cleaned}, updated_by="studio"
    )
