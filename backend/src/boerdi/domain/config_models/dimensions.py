"""04-* dimension areas: entities, intents, personas (MD), signals, states.
Shapes verified against the ALT tree inventory (2026-07-11).
"""

from typing import Any

from boerdi.domain.config_models._shared import AreaModel


class EntityDef(AreaModel):
    id: str
    label: str = ""
    type: str = ""
    description: str = ""
    examples: list[str] = []
    positive_examples: list[dict[str, Any]] = []
    negative_examples: list[dict[str, Any]] = []
    discriminators: list[dict[str, Any]] = []


class EntitiesArea(AreaModel):
    entities: list[EntityDef] = []
    accumulation_rules: dict[str, str] = {}


class NegativeTrigger(AreaModel):
    phrase: str = ""
    redirect_to: str = ""
    rationale: str = ""
    when: str | None = None


class IntentDef(AreaModel):
    id: str
    label: str = ""
    description: str = ""
    examples: list[str] = []
    trigger_verbs: list[str] = []
    negative_triggers: list[NegativeTrigger] = []
    discriminators: list[dict[str, Any]] = []


class IntentsArea(AreaModel):
    intents: list[IntentDef] = []


class SignalDef(AreaModel):
    dimension: str = ""
    label: str = ""
    tone: str = ""
    length: str | None = None
    skip_intro: bool | None = None
    one_option: bool | None = None
    show_more: bool | None = None
    add_sources: bool | None = None
    show_overview: bool | None = None


class SignalModulationsArea(AreaModel):
    signals: dict[str, SignalDef] = {}
    reduce_items_signals: list[str] = []


class StateDef(AreaModel):
    id: str
    label: str = ""
    description: str = ""
    role: str = ""
    bot_directive: str = ""
    next_likely: list[str] = []
    selection_criteria: list[str] = []


class StatesArea(AreaModel):
    states: list[StateDef] = []


class AntiMarker(AreaModel):
    phrase: str = ""
    redirect_to: str | None = None
    rationale: str | None = None
    when: str | None = None


class PersonaDiscriminator(AreaModel):
    vs: str = ""
    rule: str = ""
    example_a: str | None = None
    example_b: str | None = None


class PersonaFrontmatter(AreaModel):
    element: str = ""
    id: str = ""
    label: str = ""
    description: str = ""
    tone: str | None = None
    length_bias: float | None = None
    formality: str | None = None
    card_text_mode: str | None = None
    override: bool | None = None
    positive_markers: list[str] | None = None  # absent in and.md (P-AND)
    anti_markers: list[AntiMarker] = []
    discriminators: list[PersonaDiscriminator] = []
    goals: list[str] = []
    rules: list[str] = []
    typical_intents: list[str] = []


class PersonaArea(AreaModel):
    frontmatter: PersonaFrontmatter = PersonaFrontmatter()
    body: str = ""
