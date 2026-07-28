"""Shared bases for area models (P2-1). extra='allow' everywhere — the ALT
loaders tolerate unknown keys, and editors must not 422 on additive fields.
"""

from pydantic import BaseModel, ConfigDict


class AreaModel(BaseModel):
    model_config = ConfigDict(extra="allow")
