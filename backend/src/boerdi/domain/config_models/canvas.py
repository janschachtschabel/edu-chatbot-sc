"""05-canvas/* areas. Shapes verified against the ALT tree inventory."""

from boerdi.domain.config_models._shared import AreaModel


class CanvasCreateTriggersArea(AreaModel):
    create_triggers: list[str] = []
    search_verbs: list[str] = []


class CanvasEditTriggersArea(AreaModel):
    edit_triggers: list[str] = []
    explicit_create_overrides: list[str] = []


class CanvasPersonaPrioritiesArea(AreaModel):
    analytical_personas: list[str] = []


class MaterialType(AreaModel):
    id: str
    label: str = ""
    # Die Beschriftung ist zugleich der Chip-Text, der beim Klick zurückkommt:
    # zu jeder gepflegten Fassung muss ein Alias in `type-aliases.yaml` stehen
    # (C1-g2e). `structure` bleibt einsprachig — sie ist Prompt (Klasse B), die
    # Ausgabesprache regelt `i18n/prompt_language` seit C1-f2a.
    label_en: str = ""
    emoji: str = ""
    category: str = ""
    structure: str = ""


class CanvasMaterialTypesArea(AreaModel):
    material_types: list[MaterialType] = []


class CanvasTypeAliasesArea(AreaModel):
    aliases: dict[str, str] = {}
    short_whitelist: list[str] = []
    lrt_to_type: dict[str, str] = {}
