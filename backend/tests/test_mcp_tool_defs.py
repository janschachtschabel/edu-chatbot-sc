"""Charakterisierungs-Pins für den Tool-Definitions-Leaf des MCP-Pakets.

1:1-Port aus ALT ``tests/test_mcp_tool_defs.py``: statische Tool-Schemas
(``TOOL_DEFINITIONS``, ``_TOOL_ARG_MODELS``, ``_JSON_CAPABLE_TOOLS``) + die reine
Validierung (``validate_tool_args``), ohne geteilten Zustand. Deviation ggü. ALT:
Import aus ``boerdi.services.mcp.tool_defs`` (in ALT lief er über die
``mcp_client``-Re-Export-Fassade, die im Neubau erst mit 5-1 entsteht).
"""

from __future__ import annotations

from boerdi.services.mcp.tool_defs import (
    _JSON_CAPABLE_TOOLS,
    _TOOL_ARG_MODELS,
    TOOL_DEFINITIONS,
    validate_tool_args,
)


# ── validate_tool_args ──────────────────────────────────────────────────
def test_unknown_tool_passes_args_through_unchanged():
    assert validate_tool_args("__unknown__", {"a": 1, "b": ""}) == {"a": 1, "b": ""}


def test_known_tool_applies_defaults():
    # search_wlo_content → SearchWloArgs setzt maxResults=5 als Default.
    assert validate_tool_args("search_wlo_content", {"query": "mathe"}) == {
        "query": "mathe", "maxResults": 5,
    }


def test_known_tool_empty_args_stay_empty():
    assert validate_tool_args("wlo_health_check", {}) == {}


def test_explicit_false_bool_arg_is_preserved():
    # NOTE: Fix 2026-07-10 (C7) — der Export-Filter darf explizite False/0-Werte
    # NICHT droppen. Früher fraß ``v != 0`` (wegen ``False == 0`` in Python) auch
    # Bool-False, z.B. get_subject_portals.includeContentCounts=False (leerer
    # educationalContext bleibt korrekt weg-gefiltert).
    out = validate_tool_args("get_subject_portals", {"includeContentCounts": False})
    assert out == {"includeContentCounts": False}


# ── statische Definitionen ──────────────────────────────────────────────
def test_tool_definitions_shape():
    assert isinstance(TOOL_DEFINITIONS, list) and TOOL_DEFINITIONS
    for td in TOOL_DEFINITIONS:
        assert td.get("type") == "function"
        assert td["function"]["name"]
    names = {td["function"]["name"] for td in TOOL_DEFINITIONS}
    assert "search_wlo_collections" in names


def test_json_capable_tools_is_frozenset_with_known_member():
    assert isinstance(_JSON_CAPABLE_TOOLS, frozenset)
    assert "search_wlo_content" in _JSON_CAPABLE_TOOLS


def test_tool_arg_models_covers_registered_tools():
    assert isinstance(_TOOL_ARG_MODELS, dict)
    assert "search_wlo_content" in _TOOL_ARG_MODELS
    assert "wlo_health_check" in _TOOL_ARG_MODELS
