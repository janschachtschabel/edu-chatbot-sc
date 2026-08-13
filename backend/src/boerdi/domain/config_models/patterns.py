"""03-patterns/* (MD, grouped area): frontmatter + body per pattern file.
Common base = 12 keys; optional extensions per inventory (2026-07-11).
"""

from typing import Annotated

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices


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
    # Die drei Quellen, auf die der Code prüft (`"mcp" in sources` in
    # response_tool_selection/respond, `"rag"` im RAG-Gate). Ein vertippter
    # vierter Wert fällt still durch — deshalb hier eine Auswahl.
    sources: list[Annotated[str, Choices("llm", "mcp", "rag")]] | None = None
    # Die Auszeichnung sitzt am EINTRAG: gewählt wird eine Zeile, nicht die
    # Liste. `rag_areas` deckt sich mit den Schlüsseln von
    # `05-knowledge/rag-config`, `tools` mit der Server-Registry.
    rag_areas: list[Annotated[str, Catalog("rag_areas")]] | None = None
    tools: list[Annotated[str, Catalog("tools")]] | None = None
    precondition_slots: list[Annotated[str, Catalog("entities")]] | None = None
    card_text_link_required: bool | None = None
    # `quick_reply_policy` fällt bei jedem anderen Wert auf "exact" zurück, und
    # PUT /api/config/patterns weist ihn mit 400 ab — echt geschlossen.
    quick_replies_mode: Annotated[
        str, Choices("exact", "speculative", "none")
    ] | None = None
    forbidden_phrases: list[str] | None = None
    anti_patterns: list[str] | None = None


class PatternArea(AreaModel):
    frontmatter: PatternFrontmatter = PatternFrontmatter()
    body: str = ""
