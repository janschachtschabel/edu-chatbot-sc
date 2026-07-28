"""Pydantic entry models for the structured dimension editors (P2-5).
Ported from ALT config_elements.py; extracted so config_elements.py stays
focused on the handlers.
"""

from __future__ import annotations

from pydantic import BaseModel


# ── top-level PUT body wrappers (malformed body -> 422 automatically) ──
class IntentsPayload(BaseModel):
    intents: list


class StatesPayload(BaseModel):
    states: list


class PersonasPayload(BaseModel):
    personas: list


class PatternsPayload(BaseModel):
    patterns: list


class EntitiesPayload(BaseModel):
    entities: list


# ── intents ──
class IntentNegativeTrigger(BaseModel):
    phrase: str
    redirect_to: str | None = None
    rationale: str | None = None
    when: str | None = None


class IntentDiscriminator(BaseModel):
    vs: str
    rule: str
    example_a: str | None = None
    example_b: str | None = None


class IntentEntry(BaseModel):
    id: str
    label: str
    description: str | None = None
    examples: list[str] = []
    trigger_verbs: list[str] = []
    negative_triggers: list[IntentNegativeTrigger] = []
    discriminators: list[IntentDiscriminator] = []


# ── states ──
class StateEntry(BaseModel):
    id: str
    label: str
    description: str | None = None
    role: str | None = None
    bot_directive: str | None = None
    next_likely: list[str] = []
    selection_criteria: list[str] = []


# ── entities ──
class EntityPositiveExample(BaseModel):
    text: str
    value: str | None = None


class EntityNegativeExample(BaseModel):
    text: str
    rationale: str | None = None


class EntityDiscriminator(BaseModel):
    vs: str
    rule: str
    example_a: str | None = None
    example_b: str | None = None


class EntityEntry(BaseModel):
    id: str
    label: str | None = None
    type: str = "string"
    description: str | None = None
    examples: list[str] = []
    positive_examples: list[EntityPositiveExample] = []
    negative_examples: list[EntityNegativeExample] = []
    discriminators: list[EntityDiscriminator] = []


# ── personas ──
class PersonaAntiMarker(BaseModel):
    phrase: str
    redirect_to: str | None = None
    rationale: str | None = None


class PersonaDiscriminator(BaseModel):
    vs: str
    rule: str
    example_a: str | None = None
    example_b: str | None = None


class PersonaEntry(BaseModel):
    id: str
    label: str
    description: str | None = None
    tone: str | None = None
    length_bias: float | None = None
    formality: str | None = None
    card_text_mode: str | None = None
    override: bool | None = None
    positive_markers: list[str] = []
    anti_markers: list[PersonaAntiMarker] = []
    discriminators: list[PersonaDiscriminator] = []
    goals: list[str] = []
    rules: list[str] = []
    typical_intents: list[str] = []
    personality_text: str | None = None


# ── patterns ──
class PatternEntry(BaseModel):
    id: str
    label: str
    short_purpose: str | None = None
    priority: int | None = None
    default_tone: str | None = None
    default_length: str | None = None
    response_type: str | None = None
    sources: list[str] = []
    rag_areas: list[str] = []
    tools: list[str] = []
    output_mode: str | None = None
    precondition_slots: list[str] = []
    card_text_link_required: bool | None = None
    quick_replies_mode: str | None = None
    quick_replies_max: int | None = None
    core_rule: str | None = None
    forbidden_phrases: list[str] = []
    anti_patterns: list[str] = []
    when_to_use: list[str] = []
    when_not_to_use: list[str] = []
    trigger_phrases: list[str] = []
    discriminators: list[dict[str, str]] = []
    body_md: str | None = None
