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
