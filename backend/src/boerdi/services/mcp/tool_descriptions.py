"""Studio MCP-registry enrichment: tool-description lookup + per-URL TTL cache.

Backs GET /api/config/mcp-servers. The studio renders each server's tool list as
small tags; without descriptions, near-identical names like ``get_node_details``
(single) and ``get_nodes_details`` (bulk) are visually indistinguishable, so the
registry view is enriched with a ``{tool_name: description}`` map for hover-tooltips.

ALT held this in the config *router* (``app/routers/config_mcp.py``); per spec §4
(``api`` = HTTP only, I/O lives in ``services``) it moves here. The 5-min TTL cache
is a module-global — the same shape as ``tool_cache`` and, like it, explicitly
sanctioned by Eiserne Regel 3 ("MCP-TTL-Cache pro Prozess erlaubt, da nur
Performance"): it never affects correctness, only how often the studio's GET pays a
discover round-trip. ``transport``/``config_loader`` are referenced module-qualified
so the network + registry boundaries stay patchable at call time (like ``client.py``).
"""

from __future__ import annotations

import time

from boerdi.domain.werkzeug_freigabe import wirksam_aus
from boerdi.services import config_loader
from boerdi.services.agent_tools import AUS_DEM_KATALOG
from boerdi.services.config_loader.mcp import _PRIMARY_ID
from boerdi.services.mcp import transport
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

#: Die Werkzeuge, die der Chatbot kennt und dem Modell anbieten kann — nur für sie
#: hat ein Schalter im Studio eine Wirkung (Paket 7, S5).
_KATALOG = frozenset(
    t["function"]["name"] for t in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS))

# Cache MCP tool descriptions for ~5 min so the studio's GET /mcp-servers doesn't
# pay the discover round-trip on every render. Descriptions change rarely (only on
# MCP-server deploys); a short TTL is fine.
_TOOL_DESC_CACHE: dict[str, tuple[float, dict[str, str]]] = {}
_TOOL_DESC_TTL_S = 300.0


async def _fetch_tool_descriptions(url: str) -> dict[str, str]:
    """Get {tool_name: description} for an MCP server, cached.

    Returns an empty dict on any failure so the caller can render the server tile
    without descriptions instead of erroring out.
    """
    now = time.time()
    cached = _TOOL_DESC_CACHE.get(url)
    if cached and (now - cached[0]) < _TOOL_DESC_TTL_S:
        return cached[1]
    # A7 (ALT fix 2026-07-10): do NOT cache errors (no negative caching). The cache
    # write happens only on success; a failure returns {} so the next call contacts
    # the server again instead of blocking for 5 min.
    try:
        tools = await transport.discover_server_tools(url)
    except Exception:
        return {}
    descs = {
        t["name"]: (t.get("description") or "").strip()
        for t in tools
        if isinstance(t, dict) and t.get("name")
    }
    _TOOL_DESC_CACHE[url] = (now, descs)
    return descs


def _lesend_uebernommen(srv: dict) -> set[str]:
    """Paket 11 (E): übernommene lesende Werkzeuge eines weiteren Servers bietet der Chatbot an
    (``domain/fremdwerkzeug``) — also trägt ihr Schalter."""
    if srv.get("id") == _PRIMARY_ID:
        return set()
    return {str(e["name"]) for e in srv.get("tool_schemas") or []
            if isinstance(e, dict) and e.get("name") and e.get("read_only") is True}


async def load_mcp_servers_with_descriptions() -> list[dict]:
    """The registry (``load_mcp_servers``) with tool descriptions inline.

    Best-effort: only enabled servers that carry a url and a tool list are enriched,
    and a failed handshake degrades to no ``tool_descriptions`` map (empty dict), so
    the studio still renders the tags — just without tooltips.
    """
    servers = config_loader.load_mcp_servers()
    for srv in servers:
        live: dict[str, str] = {}
        if srv.get("enabled") and srv.get("url") and srv.get("tools"):
            live = await _fetch_tool_descriptions(srv["url"])
            srv["tool_descriptions"] = live
        # Paket 11 (gemessen 2026-10-15: ``search_skill`` fehlt am Server): Katalog-Werkzeuge,
        # die der Server laut Live-Abfrage nicht führt — eingeschaltet scheiterte jeder Aufruf.
        # Ohne Live-Antwort weiß das niemand, dann keine Warnung.
        srv["werkzeuge_fehlen_am_server"] = sorted(
            (_KATALOG & set(srv.get("tools") or ())) - set(live)) if live else []
        # Paket 7 (S5): die wirksame Liste (die Vorgabe sichtbar gemacht) und
        # welche Werkzeuge überhaupt einen Schalter tragen. Die zweite Angabe ist
        # UI-Beiwerk und wird beim Speichern entfernt (``_UI_META_KEYS``).
        srv["werkzeuge_aus"] = wirksam_aus(
            srv, primaer=srv.get("id") == _PRIMARY_ID, vorgabe=AUS_DEM_KATALOG)
        srv["werkzeuge_im_katalog"] = sorted(
            (_KATALOG & set(srv.get("tools") or ())) | _lesend_uebernommen(srv))
    return servers
