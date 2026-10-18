"""Paket 15 (A3): the studio shows a missing key with the schema's default — so the schema
must carry every default the runtime applies, including ``default_factory`` ones.

Before: ``agent_rolle.schutzregeln`` (factory default R-05/R-08/R-13/R-15) had no default in
the schema, the studio showed an empty list, and adding one rule silently replaced the four.
"""

from __future__ import annotations

from typing import Any, get_args, get_origin

from pydantic import BaseModel
from pydantic_core import PydanticUndefined, to_jsonable_python

from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.engine import EngineArea
from boerdi.domain.config_models.schema import area_schema


def _node(schema: dict[str, Any], model: type[BaseModel]) -> dict[str, Any] | None:
    """The schema node describing ``model``: the root or its ``$defs`` entry."""
    if schema.get("title") == model.__name__ and "properties" in schema:
        return schema
    return schema.get("$defs", {}).get(model.__name__)


def _nested_models(annotation: Any) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    return [m for arg in get_args(annotation) for m in _nested_models(arg)] if get_origin(
        annotation) is not None or get_args(annotation) else []


def _mismatches(schema: dict[str, Any], model: type[BaseModel], seen: set[str]) -> list[str]:
    if model.__name__ in seen:
        return []
    seen.add(model.__name__)
    node = _node(schema, model)
    if node is None:
        return []
    out: list[str] = []
    for name, info in model.model_fields.items():
        prop = node.get("properties", {}).get(info.alias or name)
        if prop is None:
            continue
        if info.default is not PydanticUndefined or info.default_factory is not None:
            expected = to_jsonable_python(info.get_default(call_default_factory=True))
            if prop.get("default", PydanticUndefined) != expected:
                out.append(f"{model.__name__}.{name}")
        for nested in _nested_models(info.annotation):
            out += _mismatches(schema, nested, seen)
    return out


def test_factory_defaults_are_in_the_schema() -> None:
    rolle = area_schema(EngineArea)["$defs"]["AgentRolle"]["properties"]
    assert rolle["schutzregeln"]["default"] == ["R-05", "R-08", "R-13", "R-15"]


def test_every_area_schema_default_equals_the_model_default() -> None:
    falsch: list[str] = []
    for model in {m.__name__: m for m in AREA_MODELS.values()}.values():
        falsch += _mismatches(area_schema(model), model, set())
    assert falsch == [], f"schema default != model default: {sorted(set(falsch))}"
