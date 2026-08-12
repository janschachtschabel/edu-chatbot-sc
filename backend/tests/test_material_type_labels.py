"""Material-Typ-Beschriftungen tragen einen zweiten, unsichtbaren Auftrag (C1-g2e).

Jede Beschriftung wird als Chip angeboten (``"📝 Arbeitsblatt"``) und kommt beim
Klick WORTGLEICH als Nachricht zurück. Erst der Alias-Erkenner
(``extract_material_type_from_message``) macht daraus wieder eine Typ-ID. Fehlt
der Alias, fällt der Typ still auf ``auto`` — und schlimmer: der Fast-Path
schneidet das Typ-Wort mit denselben Aliassen aus dem Thema, also bliebe es im
Thema stehen („Worksheet zu Photosynthese").

Deshalb wird hier gegen den ECHTEN Seed geprüft, nicht gegen Attrappen: die
Aliasliste und die Typenliste sind zwei Dateien, die auseinanderlaufen können.
Der Wächter gilt für BEIDE Sprachen — die englischen Aliase stehen neben den
deutschen, nicht statt ihrer (Vereinigung, wie in C1-f2c-a und C1-g2d).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from boerdi.domain.canvas import intent as canvas_intent
from boerdi.domain.canvas import types as canvas_types

_SEEDS = Path(__file__).resolve().parents[1] / "seeds" / "05-canvas"


def _load(name: str) -> dict:
    return yaml.safe_load((_SEEDS / name).read_text(encoding="utf-8"))


_TYPES = _load("material-types.yaml")["material_types"]
_ALIASES = _load("type-aliases.yaml")


@pytest.fixture
def seed_aliases(monkeypatch):
    """Der Erkenner liest die Aliase aus dem Seed statt aus dem Config-Store."""
    monkeypatch.setattr(
        canvas_types.config_loader, "load_canvas_type_aliases", lambda: _ALIASES,
    )


@pytest.mark.parametrize("mt", _TYPES, ids=[m["id"] for m in _TYPES])
def test_german_chip_resolves_back_to_its_own_type(mt, seed_aliases):
    chip = f"{mt['emoji']} {mt['label']}"
    assert canvas_intent.extract_material_type_from_message(chip) == mt["id"], (
        f"Chip {chip!r} findet seinen eigenen Typ nicht — Alias fehlt in "
        f"type-aliases.yaml"
    )


@pytest.mark.parametrize("mt", _TYPES, ids=[m["id"] for m in _TYPES])
def test_english_chip_resolves_back_to_its_own_type(mt, seed_aliases):
    label_en = (mt.get("label_en") or "").strip()
    assert label_en, f"Typ {mt['id']} hat keine englische Beschriftung"
    chip = f"{mt['emoji']} {label_en}"
    assert canvas_intent.extract_material_type_from_message(chip) == mt["id"], (
        f"Englischer Chip {chip!r} findet seinen eigenen Typ nicht — Alias "
        f"fehlt in type-aliases.yaml"
    )


def test_english_aliases_do_not_displace_german_ones():
    """Vereinigung, nicht Ablösung: kein deutscher Alias wurde überschrieben."""
    aliases = _ALIASES["aliases"]
    assert aliases["arbeitsblatt"] == "arbeitsblatt"
    assert aliases["präsentation"] == "praesentation"
    assert aliases["übungsaufgaben"] == "uebung"
