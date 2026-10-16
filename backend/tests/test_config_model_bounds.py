"""ST-2c: eine Grenze, die ein Lader kappt, steht auch im Modell.

Sonst zeigt das Studio sie nicht an, ein Wert außerhalb wird beim Speichern
angenommen und beim Lesen still gekappt — die Redaktion sieht 200 %, der Chat
rechnet mit 100 %. Die Zahlen sind die der Kappungen in
``services/config_loader`` (widget.py, tone.py, safety.py); die Kappung dort
bleibt als zweite Sicherung für Altbestände.
"""

import pytest
from pydantic import BaseModel, ValidationError

from boerdi.domain.config_models.base_governance import GuideModeBlock, ToneModifier
from boerdi.domain.config_models.base_widget import (
    GroupsRules,
    InlineCardLinksRules,
    InlineDocumentsRules,
    QuickRepliesRules,
    SingleContentBoxRules,
    WidgetModesBlock,
)
from boerdi.domain.config_models.dimensions import PersonaFrontmatter

GRENZEN: list[tuple[type[BaseModel], str, float, float]] = [
    (InlineDocumentsRules, "font_size_percent", 70, 100),
    (GroupsRules, "themenseiten_max", 1, 20),
    (GroupsRules, "sammlungen_max", 1, 20),
    (GroupsRules, "materialien_max", 1, 8),
    (GroupsRules, "materialien_max_lernpfad", 1, 8),
    (GroupsRules, "webseiten_max", 1, 30),
    (SingleContentBoxRules, "max_count", 1, 8),
    (InlineCardLinksRules, "limit", 1, 6),
    (InlineCardLinksRules, "title_max_chars", 30, 200),
    (QuickRepliesRules, "max_count", 0, 6),
    (WidgetModesBlock, "cards_inline_link_limit", 1, 6),
    (WidgetModesBlock, "cards_inline_link_title_max", 30, 200),
    (GuideModeBlock, "max_guide_quick_replies", 1, 3),
    (ToneModifier, "length_bias", -0.3, 0.3),
    (PersonaFrontmatter, "length_bias", -0.3, 0.3),
]
_IDS = [f"{m.__name__}.{f}" for m, f, *_ in GRENZEN]


def _zweig(prop: dict) -> dict:
    """Bei ``X | None`` steht die Grenze im Nicht-null-Zweig des ``anyOf``."""
    return next((o for o in prop.get("anyOf", [prop]) if o.get("type") != "null"), prop)


@pytest.mark.parametrize(("modell", "feld", "unten", "oben"), GRENZEN, ids=_IDS)
def test_die_grenze_steht_im_schema(modell, feld, unten, oben) -> None:
    prop = _zweig(modell.model_json_schema()["properties"][feld])
    assert (prop.get("minimum"), prop.get("maximum")) == (unten, oben)


@pytest.mark.parametrize(("modell", "feld", "unten", "oben"), GRENZEN, ids=_IDS)
def test_ein_wert_ausserhalb_wird_abgewiesen(modell, feld, unten, oben) -> None:
    for wert in (unten - 1, oben + 1):
        with pytest.raises(ValidationError):
            modell(**{feld: wert})
    assert getattr(modell(**{feld: oben}), feld) == oben


def _rohe_grenzen(knoten: object, pfad: str = "") -> list[str]:
    if isinstance(knoten, list):
        return [f for i, k in enumerate(knoten) for f in _rohe_grenzen(k, f"{pfad}[{i}]")]
    if not isinstance(knoten, dict):
        return []
    eigen = [f"{pfad}.{k}" for k in ("ge", "gt", "le", "lt")
             if isinstance(knoten.get(k), int | float)]
    return eigen + [f for k, v in knoten.items() for f in _rohe_grenzen(v, f"{pfad}/{k}")]


def test_keine_grenze_bleibt_als_rohes_stichwort_im_schema() -> None:
    # Paket 9: steht ``Field(ge=0)`` in ``Annotated`` HINTER einem
    # ``BeforeValidator``, schreibt pydantic ``"ge": 0`` statt ``"minimum": 0`` —
    # das Studio-Formular kennt die Grenze dann nicht (und die Fixture übersetzt
    # nicht mehr). Die Reihenfolge ist die Falle, nicht der Validator.
    from boerdi.domain.config_models import AREA_MODELS

    funde = [f"{key}{f}" for key, model in AREA_MODELS.items()
             for f in _rohe_grenzen(model.model_json_schema())]
    assert funde == []
