"""Area model registry (P2-1, spec §5.3 — 35 logical areas).

DB rows are per FILE (55 keys, path sans extension); the 35 logical areas
group 03-patterns/* and 04-personas/* under one model each. ``model_for``
resolves a file key to its model (prefix rule for the two grouped areas).
"""

from pydantic import BaseModel

from boerdi.domain.config_models.base_governance import (
    CardPipelineArea,
    ClassifyOverridesArea,
    GuideModeArea,
    PolicyArea,
    PrivacyConfigArea,
    QualityLogConfigArea,
    SafetyConfigArea,
    ToneModifiersArea,
)
from boerdi.domain.config_models.base_widget import (
    ContextActionsArea,
    DeviceConfigArea,
    DisplayRulesArea,
    HeaderNavArea,
    PlaceholderTopicsArea,
    WebsiteTourArea,
    WelcomeArea,
    WidgetModesArea,
)
from boerdi.domain.config_models.canvas import (
    CanvasCreateTriggersArea,
    CanvasEditTriggersArea,
    CanvasMaterialTypesArea,
    CanvasPersonaPrioritiesArea,
    CanvasTypeAliasesArea,
)
from boerdi.domain.config_models.dimensions import (
    EntitiesArea,
    IntentsArea,
    PersonaArea,
    SignalModulationsArea,
    StatesArea,
)
from boerdi.domain.config_models.engine import EngineArea
from boerdi.domain.config_models.knowledge import (
    GoldFlowsArea,
    GuideRulesArea,
    McpServersArea,
    RagConfigArea,
)
from boerdi.domain.config_models.md import LayerDocArea
from boerdi.domain.config_models.patterns import PatternArea
from boerdi.domain.config_models.pricing import PricingArea

AREA_MODELS: dict[str, type[BaseModel]] = {
    # 01-base (19)
    "01-base/base-persona": LayerDocArea,
    "01-base/guardrails": LayerDocArea,
    "01-base/card-pipeline": CardPipelineArea,
    "01-base/classify-overrides": ClassifyOverridesArea,
    "01-base/context-actions": ContextActionsArea,
    "01-base/device-config": DeviceConfigArea,
    "01-base/display-rules": DisplayRulesArea,
    # Kein ALT-Gegenstück: ALT kannte nur die Muster-Engine. Der Wächter in
    # ``tests/test_config_models.py`` führt diesen Zusatz getrennt mit Grund.
    "01-base/engine": EngineArea,
    "01-base/guide-mode": GuideModeArea,
    "01-base/header-nav": HeaderNavArea,
    "01-base/placeholder-topics": PlaceholderTopicsArea,
    "01-base/policy": PolicyArea,
    # Kein ALT-Gegenstück: ALT rechnete nicht ab (K3). Der Wächter in
    # ``tests/test_config_models.py`` führt diesen Zusatz getrennt mit Grund.
    "01-base/pricing": PricingArea,
    "01-base/privacy-config": PrivacyConfigArea,
    "01-base/quality-log-config": QualityLogConfigArea,
    "01-base/safety-config": SafetyConfigArea,
    "01-base/tone-modifiers": ToneModifiersArea,
    "01-base/website-tour": WebsiteTourArea,
    "01-base/welcome-config": WelcomeArea,
    "01-base/widget-modes": WidgetModesArea,
    # 02-domain (3)
    "02-domain/domain-rules": LayerDocArea,
    "02-domain/guide-rules": GuideRulesArea,
    "02-domain/wlo-plattform-wissen": LayerDocArea,
    # grouped MD areas (2)
    "03-patterns": PatternArea,
    "04-personas": PersonaArea,
    # 04 dimensions (4)
    "04-entities/entities": EntitiesArea,
    "04-intents/intents": IntentsArea,
    "04-signals/signal-modulations": SignalModulationsArea,
    "04-states/states": StatesArea,
    # 05-canvas (5)
    "05-canvas/create-triggers": CanvasCreateTriggersArea,
    "05-canvas/edit-triggers": CanvasEditTriggersArea,
    "05-canvas/material-types": CanvasMaterialTypesArea,
    "05-canvas/persona-priorities": CanvasPersonaPrioritiesArea,
    "05-canvas/type-aliases": CanvasTypeAliasesArea,
    # 05-knowledge (2) + eval (1)
    "05-knowledge/mcp-servers": McpServersArea,
    "05-knowledge/rag-config": RagConfigArea,
    "eval/gold-flows": GoldFlowsArea,
}


def model_for(file_key: str) -> type[BaseModel] | None:
    """Resolve a DB file key to its area model (grouped prefixes first)."""
    if file_key.startswith("03-patterns/"):
        return AREA_MODELS["03-patterns"]
    if file_key.startswith("04-personas/"):
        return AREA_MODELS["04-personas"]
    return AREA_MODELS.get(file_key)
