"""The JSON schema of an area model as the studio form reads it (Paket 15, A3).

The studio shows a key the document does not carry with the schema's ``default`` — the
value the runtime applies. Pydantic leaves ``default_factory`` defaults out of the schema,
so a list default (``agent_rolle.schutzregeln``) showed as empty, and the first added rule
replaced the four the agent actually got. Pydantic's documented hook for this is
``GenerateJsonSchema.get_default_value``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic.json_schema import GenerateJsonSchema, NoDefault
from pydantic_core import core_schema


class _MitFabrikVorgaben(GenerateJsonSchema):
    def get_default_value(self, schema: core_schema.WithDefaultSchema) -> Any:
        factory = schema.get("default_factory")
        if factory is not None and not schema.get("default_factory_takes_data"):
            return factory()
        return schema.get("default", NoDefault)


def area_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema of ``model`` with factory defaults filled in."""
    return model.model_json_schema(schema_generator=_MitFabrikVorgaben)
