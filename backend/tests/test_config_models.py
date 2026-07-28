"""P2-1: area model registry — 35 logical areas (spec §5.3), every model
JSON-schema-buildable (V3), and every REAL ALT file validates against its
model (skipped in CI where the ALT sibling repo is absent).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from boerdi.domain.config_models import AREA_MODELS, model_for

ALT_TREE = Path(r"C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\backend\chatbots\wlo\v1")

# spec §5.3 — the 35 logical areas (patterns + personas grouped)
SPEC_AREAS = [
    "01-base/base-persona", "01-base/guardrails", "01-base/card-pipeline",
    "01-base/classify-overrides", "01-base/context-actions", "01-base/device-config",
    "01-base/display-rules", "01-base/guide-mode", "01-base/header-nav",
    "01-base/placeholder-topics", "01-base/policy", "01-base/privacy-config",
    "01-base/quality-log-config", "01-base/safety-config", "01-base/tone-modifiers",
    "01-base/website-tour", "01-base/welcome-config", "01-base/widget-modes",
    "02-domain/domain-rules", "02-domain/guide-rules", "02-domain/wlo-plattform-wissen",
    "03-patterns", "04-entities/entities", "04-intents/intents", "04-personas",
    "04-signals/signal-modulations", "04-states/states",
    "05-canvas/create-triggers", "05-canvas/edit-triggers", "05-canvas/material-types",
    "05-canvas/persona-priorities", "05-canvas/type-aliases",
    "05-knowledge/mcp-servers", "05-knowledge/rag-config", "eval/gold-flows",
]


def test_registry_covers_exactly_the_spec_areas() -> None:
    assert set(AREA_MODELS) == set(SPEC_AREAS)
    assert len(SPEC_AREAS) == 35


def test_every_model_builds_json_schema() -> None:
    for key, model in AREA_MODELS.items():
        schema = model.model_json_schema()
        assert "properties" in schema or schema.get("type") == "object", key


def test_model_for_resolves_grouped_file_keys() -> None:
    assert model_for("03-patterns/m01-krisen-empathie") is AREA_MODELS["03-patterns"]
    assert model_for("04-personas/and") is AREA_MODELS["04-personas"]
    assert model_for("01-base/welcome-config") is AREA_MODELS["01-base/welcome-config"]
    assert model_for("does/not-exist") is None


@pytest.mark.skipif(not ALT_TREE.exists(), reason="ALT-Baum nicht vorhanden (CI)")
def test_all_55_real_alt_files_validate() -> None:
    from boerdi.services import seed_io

    areas: dict[str, dict] = {}

    async def put(area: str, data: dict) -> None:
        areas[area] = data

    asyncio.run(seed_io.import_tree(ALT_TREE, put))
    assert len(areas) == 55

    failures: list[str] = []
    for file_key, data in sorted(areas.items()):
        model = model_for(file_key)
        if model is None:
            failures.append(f"{file_key}: no model resolved")
            continue
        try:
            model.model_validate(data)
        except Exception as e:  # collect all, report together
            failures.append(f"{file_key}: {str(e)[:200]}")
    assert failures == [], "\n".join(failures)
