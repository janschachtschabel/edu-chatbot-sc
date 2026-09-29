"""04-* dimension areas: entities, intents, personas (MD), signals, states.
Shapes verified against the ALT tree inventory (2026-07-11).
"""

from typing import Annotated, Any

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel, Catalog, Primary, Textarea
from boerdi.domain.config_models.base_governance import LENGTH_BIAS_SLIDER


class EntityDef(AreaModel):
    id: str
    label: str = ""
    type: str = ""
    description: Annotated[str, Textarea()] = ""
    examples: list[str] = []
    positive_examples: list[dict[str, Any]] = []
    negative_examples: list[dict[str, Any]] = []
    discriminators: list[dict[str, Any]] = []


class EntitiesArea(AreaModel):
    entities: list[EntityDef] = []
    accumulation_rules: dict[str, str] = {}


class NegativeTrigger(AreaModel):
    phrase: Annotated[str, Textarea()] = ""
    redirect_to: str = ""
    rationale: Annotated[str, Textarea()] = ""
    when: str | None = None


class IntentDef(AreaModel):
    id: str
    label: str = ""
    description: Annotated[str, Textarea()] = ""
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
    description: Annotated[str, Textarea()] = ""
    role: str = ""
    bot_directive: Annotated[str, Textarea()] = ""
    next_likely: list[Annotated[str, Catalog("states")]] = []
    selection_criteria: list[str] = []


class StatesArea(AreaModel):
    states: list[StateDef] = []


class AntiMarker(AreaModel):
    phrase: Annotated[str, Textarea()] = ""
    redirect_to: str | None = None
    rationale: Annotated[str | None, Textarea()] = None
    when: str | None = None


class PersonaDiscriminator(AreaModel):
    vs: str = ""
    rule: Annotated[str, Textarea()] = ""
    example_a: str | None = None
    example_b: str | None = None


class PersonaFrontmatter(AreaModel):
    element: str = ""
    id: str = ""
    label: str = ""
    description: Annotated[str, Textarea()] = ""
    tone: str | None = None
    # ST-2c: Grenze = Kappung im Lader (config_loader/tone.py)
    length_bias: float | None = Field(
        default=None, ge=-0.3, le=0.3, json_schema_extra=LENGTH_BIAS_SLIDER,
    )
    formality: str | None = None
    card_text_mode: str | None = None
    override: bool | None = None
    positive_markers: list[str] | None = None  # absent in and.md (P-AND)
    anti_markers: list[AntiMarker] = []
    discriminators: list[PersonaDiscriminator] = []
    goals: list[str] = []
    rules: list[Annotated[str, Textarea()]] = []
    typical_intents: list[Annotated[str, Catalog("intents")]] = []


class PersonaArea(AreaModel):
    frontmatter: PersonaFrontmatter = PersonaFrontmatter()
    # ST-4: die Beschreibung der Zielgruppe ist der Inhalt — vor den Kopfangaben
    body: Annotated[str, Textarea(), Primary()] = ""
