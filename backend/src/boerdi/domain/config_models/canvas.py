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
    emoji: str = ""
    category: str = ""
    structure: str = ""


class CanvasMaterialTypesArea(AreaModel):
    material_types: list[MaterialType] = []


class CanvasTypeAliasesArea(AreaModel):
    aliases: dict[str, str] = {}
    short_whitelist: list[str] = []
    lrt_to_type: dict[str, str] = {}
