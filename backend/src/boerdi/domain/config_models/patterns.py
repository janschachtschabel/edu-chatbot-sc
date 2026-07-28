"""03-patterns/* (MD, grouped area): frontmatter + body per pattern file.
Common base = 12 keys; optional extensions per inventory (2026-07-11).
"""

from boerdi.domain.config_models._shared import AreaModel


class PatternDiscriminator(AreaModel):
    vs: str = ""
    rule: str = ""
    example: str = ""


class PatternFrontmatter(AreaModel):
    id: str = ""
    label: str = ""
    short_purpose: str = ""
    priority: int = 50
    default_tone: str = ""
    default_length: str = ""
    response_type: str = ""
    core_rule: str = ""
    when_to_use: list[str] = []
    when_not_to_use: list[str] = []
    trigger_phrases: list[str] = []
    discriminators: list[PatternDiscriminator] = []
    # optional extensions (subset per pattern)
    output_mode: str | None = None
    sources: list[str] | None = None
    rag_areas: list[str] | None = None
    tools: list[str] | None = None
    precondition_slots: list[str] | None = None
    card_text_link_required: bool | None = None
    quick_replies_mode: str | None = None
    forbidden_phrases: list[str] | None = None
    anti_patterns: list[str] | None = None


class PatternArea(AreaModel):
    frontmatter: PatternFrontmatter = PatternFrontmatter()
    body: str = ""
