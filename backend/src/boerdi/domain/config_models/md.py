"""MD layer documents (base-persona, guardrails, domain-rules,
wlo-plattform-wissen): {frontmatter, body} with the shared layer header.
"""

from boerdi.domain.config_models._shared import AreaModel


class LayerDocFrontmatter(AreaModel):
    element: str = ""
    variant: str | None = None
    id: str = ""
    layer: int | None = None
    priority: int | None = None
    always_active: bool | None = None
    version: str | float | None = None


class LayerDocArea(AreaModel):
    frontmatter: LayerDocFrontmatter = LayerDocFrontmatter()
    body: str = ""
