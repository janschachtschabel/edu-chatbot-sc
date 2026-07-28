"""Canvas config loaders — port of ALT config_loader/canvas.py."""

from __future__ import annotations

from typing import Any

from boerdi.services.config_loader._store import area


def load_canvas_material_types() -> list[dict[str, Any]]:
    return area("05-canvas/material-types").get("material_types") or []


def load_canvas_type_aliases() -> dict[str, Any]:
    data = area("05-canvas/type-aliases")
    return {
        "aliases": data.get("aliases") or {},
        "short_whitelist": data.get("short_whitelist") or [],
        "lrt_to_type": data.get("lrt_to_type") or {},
    }


def load_canvas_create_triggers() -> dict[str, Any]:
    data = area("05-canvas/create-triggers")
    return {
        "create_triggers": data.get("create_triggers") or [],
        "search_verbs": data.get("search_verbs") or [],
    }


def load_canvas_edit_triggers() -> dict[str, Any]:
    data = area("05-canvas/edit-triggers")
    return {
        "edit_triggers": data.get("edit_triggers") or [],
        "explicit_create_overrides": data.get("explicit_create_overrides") or [],
    }


def load_canvas_persona_priorities() -> dict[str, Any]:
    data = area("05-canvas/persona-priorities")
    return {"analytical_personas": data.get("analytical_personas") or []}
