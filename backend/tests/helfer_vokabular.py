"""Attrappe des WLO-Vokabulars für ``services/mcp/vokabular_labels`` (Plan 2026-11-19, N2).

``conftest`` ersetzt die Naht ``vokabular_labels._vokabular`` in jedem Test durch „kein
Vokabular“; :func:`mit_vokabular` setzt die echte Naht wieder ein und stellt einen MCP-Server davor,
der den Text von ``lookup_wlo_vocabulary`` liefert — der geht durch den echten Leser in
``arg_resolvers``."""

from __future__ import annotations

import asyncio
from typing import Any

from boerdi.services.mcp import arg_resolvers as ar
from boerdi.services.mcp import client as mcp_client
from boerdi.services.mcp import vokabular_labels as vl

#: Beim Sammeln der Tests gegriffen, bevor ``conftest`` die Naht ersetzt.
ECHT = vl._vokabular


def leeren() -> None:
    """Puffer des Resolvers und die Fehlschlag-Sperre zurücksetzen."""
    for name in ar._label_to_uri_cache:
        ar._label_to_uri_cache[name].clear()
        ar._label_cache_loaded[name] = False
    for labels in ar._uri_to_label.values():
        labels.clear()
    vl._fehlschlag_bis.clear()


def mit_vokabular(monkeypatch, texte: dict[str, str], *, warten: float = 0.0) -> list[str]:
    """Die echte Naht mit Attrappe des MCP-Servers; gibt die Liste der gefragten Vokabulare
    zurück. ``warten`` verzögert jede Antwort (für gleichzeitige Aufrufe)."""
    gefragt: list[str] = []

    async def mcp(name: str, args: dict[str, Any]) -> str:
        assert name == "lookup_wlo_vocabulary"
        gefragt.append(args["vocabulary"])
        if warten:
            await asyncio.sleep(warten)
        return texte.get(args["vocabulary"], "")

    leeren()
    monkeypatch.setattr(mcp_client, "call_mcp_tool", mcp)
    monkeypatch.setattr(vl, "_vokabular", ECHT)
    return gefragt
