"""Paket M4 (Plan 2026-11-07): neue und erweiterte Lese-Werkzeuge des MCP (Stand 2026-11-07).

- ``get_collection_overview``: eine Sammlung auf einen Blick (Teile parallel geladen);
- ``count_wlo_content_matches``: Trefferzahlen für bis zu 30 Anfragen zugleich;
- ``browse_collection_tree``: Tiefe bis 3;
- ``get_skill_registry``: ``task`` wählt den passenden Skill und liefert die Anleitung mit.
"""

from __future__ import annotations

import pathlib

import yaml

from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds"


def _def(name: str) -> dict:
    return next(d["function"] for d in TOOL_DEFINITIONS if d["function"]["name"] == name)


def test_sammlung_auf_einen_blick():
    fn = _def("get_collection_overview")
    assert fn["parameters"]["required"] == ["collectionId"]
    out = validate_tool_args("get_collection_overview", {
        "collectionId": "c-1", "include": ["stats", "unbekannt", "contents"],
        "maxContents": 99, "maxSubcollections": 500})
    assert out["include"] == ["stats", "contents"]          # Unbekanntes fällt weg
    assert out["maxContents"] == 50 and out["maxSubcollections"] == 100


def test_trefferzahlen_fuer_viele_anfragen():
    fn = _def("count_wlo_content_matches")
    assert fn["parameters"]["required"] == ["queries"]
    anfragen = [{"id": f"a{i}", "query": f"Thema {i}"} for i in range(35)]
    out = validate_tool_args("count_wlo_content_matches", {"queries": anfragen, "top": 9})
    assert len(out["queries"]) == 30 and out["top"] == 3


def test_baum_bis_tiefe_drei():
    out = validate_tool_args("browse_collection_tree", {"nodeId": "n", "depth": 3})
    assert out["depth"] == 3
    assert "3" in _def("browse_collection_tree")["parameters"]["properties"]["depth"][
        "description"]


def test_skill_passend_zur_aufgabe():
    out = validate_tool_args("get_skill_registry", {"collectionId": "c-1",
                                                    "task": "Arbeitsblatt erstellen"})
    assert out["task"] == "Arbeitsblatt erstellen"
    assert "task" in _def("get_skill_registry")["parameters"]["properties"]


def test_das_server_register_kennt_die_neuen_werkzeuge():
    server = yaml.safe_load((_SEEDS / "05-knowledge" / "mcp-servers.yaml").read_text(
        encoding="utf-8"))
    alle = {w for s in server["servers"] for w in s.get("tools") or []}
    assert {"get_collection_overview", "count_wlo_content_matches"} <= alle
