"""ST-2i: ``x-marker`` — eine Liste hebt EINEN Eintrag hervor, der Wert steht im
Nachbarfeld. Der Wächter hält fest, dass jeder Marker auf ein Nachbarfeld zeigt,
das es gibt und das Text trägt; sonst schriebe das Studio ins Leere.
"""

from typing import Any

from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.base_widget import WelcomeArea


def _objekte(node: Any, root: dict) -> list[dict]:
    """Alle Objekt-Schemata mit Eigenschaften, ``$defs`` eingeschlossen."""
    gefunden = [node] if isinstance(node, dict) and node.get("properties") else []
    for definition in (root.get("$defs") or {}).values():
        if definition.get("properties"):
            gefunden.append(definition)
    return gefunden


def _typ(prop: dict) -> str | None:
    return prop.get("type") or next(
        (o.get("type") for o in prop.get("anyOf", []) if o.get("type") != "null"), None,
    )


def test_jeder_marker_zeigt_auf_ein_text_nachbarfeld() -> None:
    gesehen = 0
    for model in set(AREA_MODELS.values()):
        schema = model.model_json_schema()
        for objekt in _objekte(schema, schema):
            props = objekt["properties"]
            for key, prop in props.items():
                ziel = prop.get("x-marker")
                if not ziel:
                    continue
                gesehen += 1
                assert _typ(prop) == "array", f"{model.__name__}.{key}: Marker nur an Listen"
                assert ziel in props, f"{model.__name__}.{key}: Nachbarfeld {ziel} fehlt"
                assert _typ(props[ziel]) == "string", f"{model.__name__}.{ziel}: kein Text"
    assert gesehen >= 2


def test_die_start_chips_markieren_den_tour_chip() -> None:
    block = WelcomeArea.model_json_schema()["$defs"]["WelcomeBlock"]["properties"]
    assert block["quick_replies"]["x-marker"] == "tour_reply"
    assert block["quick_replies_en"]["x-marker"] == "tour_reply_en"
