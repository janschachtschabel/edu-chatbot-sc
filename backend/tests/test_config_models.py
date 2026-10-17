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

# Bereiche, die es in ALT NICHT gibt und die NEU bewusst hinzufügt — je mit
# Grund, nach dem Vorbild von ``BEWUSST_EINSPRACHIG`` (i18n) und
# ``OHNE_BUCHUNG`` (test_usage_coverage). Ohne diese getrennte Liste müsste
# ``SPEC_AREAS`` wachsen, und die Zusage „35 Bereiche wie in ALT" wäre still
# aufgegeben statt sichtbar erweitert.
NEUE_BEREICHE = {
    "01-base/pricing": (
        "K3 Kostenüberwachung: Preise je Modell, redaktionell pflegbar. "
        "ALT rechnete überhaupt nicht ab, hat also kein Gegenstück."
    ),
    "01-base/rag-retrieval": (
        "Paket 7 (P4): die Werte der Wissenssuche las ``rag/retrieval`` schon "
        "immer aus diesem Bereich — ohne Modell war er im Studio nicht pflegbar "
        "und ein falscher Wert fiel still auf die Vorgabe."
    ),
    "01-base/engine": (
        "Umschalter Muster-Engine ↔ Agent-Schleife plus deren Deckel. ALT kannte "
        "nur einen Weg, hat also kein Gegenstück. Vorgabe seit Paket 7 (K6) "
        "``agent`` — im Betrieb die Vorgabe (D-15)."
    ),
}

# Bereiche aus ALT, die NEU bewusst streicht — je mit Grund, als Gegenstück zu
# ``NEUE_BEREICHE``: die Zusage „35 Bereiche wie in ALT“ wird sichtbar
# eingeschränkt statt still aufgegeben.
GESTRICHENE_BEREICHE = {
    "05-canvas/create-triggers": (
        "Paket 7 (K4, Nutzer-Entscheid 2026-10-09): ihr einziger Leser "
        "(``looks_like_create_intent``) hatte keinen Aufrufer im Produktionscode."
    ),
    "05-canvas/edit-triggers": (
        "Paket 7 (K4, Nutzer-Entscheid 2026-10-09): ihre Leser "
        "(``looks_like_edit_intent``, ``has_explicit_new_create_override``) hatten "
        "keinen Aufrufer im Produktionscode."
    ),
}


def test_registry_covers_exactly_the_spec_areas() -> None:
    assert set(AREA_MODELS) == (
        set(SPEC_AREAS) - set(GESTRICHENE_BEREICHE)) | set(NEUE_BEREICHE)
    assert len(SPEC_AREAS) == 35
    assert not set(SPEC_AREAS) & set(NEUE_BEREICHE), "ALT-Bereich als neu geführt"
    assert set(GESTRICHENE_BEREICHE) <= set(SPEC_AREAS), "gestrichen, aber nie in ALT"
    for key, grund in GESTRICHENE_BEREICHE.items():
        assert len(grund) > 40, f"{key}: Grund zu knapp"


def test_jeder_neue_bereich_traegt_einen_grund() -> None:
    """Gegenrichtung: ein Eintrag ohne Begründung — oder einer, der aus der
    Registry wieder verschwunden ist — fällt hier auf."""
    for key, grund in NEUE_BEREICHE.items():
        assert key in AREA_MODELS, f"{key} steht in NEUE_BEREICHE, aber nicht in AREA_MODELS"
        assert len(grund) > 40, f"{key}: Grund zu knapp"


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
        if file_key in GESTRICHENE_BEREICHE:
            continue
        model = model_for(file_key)
        if model is None:
            failures.append(f"{file_key}: no model resolved")
            continue
        try:
            model.model_validate(data)
        except Exception as e:  # collect all, report together
            failures.append(f"{file_key}: {str(e)[:200]}")
    assert failures == [], "\n".join(failures)


def test_mcp_server_traegt_uebernommene_werkzeuge():
    """Paket 11 (E): ``tool_schemas`` — Name, Beschreibung, Eingabeschema, lesend."""
    from boerdi.domain.config_models.knowledge import McpServer

    s = McpServer.model_validate({"id": "x", "tool_schemas": [
        {"name": "suche", "description": "d", "input_schema": {"type": "object"},
         "read_only": True}]})
    (w,) = s.tool_schemas
    assert (w.name, w.read_only, w.input_schema) == ("suche", True, {"type": "object"})
    assert McpServer.model_validate({"id": "y"}).tool_schemas == []

