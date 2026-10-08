"""03-patterns/* (MD, grouped area): frontmatter + body per pattern file.
Common base = 12 keys; optional extensions per inventory (2026-07-11).
"""

from typing import Annotated

from pydantic import field_validator

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices, Textarea, Vorgabe

#: Kennungen, die kein Muster tragen darf (Befundliste §2, ST-5 Befund 4).
#: ``AGENT`` kennzeichnet die Züge der Agent-Schleife
#: (``domain/agent_pattern.AGENT_PATTERN_ID``, ein Test hält beide gleich). Eine
#: Muster-Datei mit dieser Kennung schaltete in der Muster-Maschine den
#: Karten-Schutz ab. Hier und nicht dort, weil ``agent_pattern`` die
#: Muster-Maschine importiert.
RESERVIERTE_KENNUNGEN: frozenset[str] = frozenset({"AGENT"})


def ist_reservierte_kennung(kennung: object) -> bool:
    """Gross/klein und Leerraum zählen nicht: auch ``" agent "`` ist belegt."""
    return str(kennung or "").strip().upper() in RESERVIERTE_KENNUNGEN


class PatternDiscriminator(AreaModel):
    vs: str = ""
    rule: Annotated[str, Textarea()] = ""
    example: Annotated[str, Textarea()] = ""


class PatternFrontmatter(AreaModel):
    id: str = ""
    label: str = ""
    short_purpose: Annotated[str, Textarea()] = ""
    priority: int = 50
    default_tone: str = ""
    default_length: str = ""
    response_type: str = ""
    core_rule: Annotated[str, Textarea()] = ""
    when_to_use: list[Annotated[str, Textarea()]] = []
    when_not_to_use: list[Annotated[str, Textarea()]] = []
    trigger_phrases: list[str] = []
    discriminators: list[PatternDiscriminator] = []
    # optional extensions (subset per pattern)
    output_mode: str | None = None
    # Die drei Quellen, auf die der Code prüft (`"mcp" in sources` in
    # response_tool_selection/respond, `"rag"` im RAG-Gate). Ein vertippter
    # vierter Wert fällt still durch — deshalb hier eine Auswahl. Ohne Angabe
    # gilt `["mcp"]` (`PatternDef`), eine leere Liste heißt keine Quelle.
    sources: Annotated[list[Annotated[str, Choices("llm", "mcp", "rag")]] | None, Vorgabe()] = None
    # Die Auszeichnung sitzt am EINTRAG: gewählt wird eine Zeile, nicht die
    # Liste. `rag_areas` deckt sich mit den Schlüsseln von
    # `05-knowledge/rag-config`, `tools` mit der Server-Registry. Ohne Angabe
    # gelten alle Bereiche (bei `rag` in `sources`), eine leere Liste heißt keine.
    rag_areas: Annotated[list[Annotated[str, Catalog("rag_areas")]] | None, Vorgabe()] = None
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

    @field_validator("id")
    @classmethod
    def _nicht_reserviert(cls, kennung: str) -> str:
        """Das Tor für ``PUT /api/config/data/03-patterns/…``; den gespeicherten
        Bestand siebt ``load_pattern_definitions`` aus."""
        if ist_reservierte_kennung(kennung):
            raise ValueError(f"pattern id {kennung.strip()!r} is reserved for agent turns")
        return kennung


class PatternArea(AreaModel):
    frontmatter: PatternFrontmatter = PatternFrontmatter()
    body: Annotated[str, Textarea()] = ""
