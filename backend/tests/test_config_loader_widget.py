"""Widget-Lader (``services/config_loader/widget.py``): Was das Studio speichern
darf, muss der Lader lesen können — und ein eingebauter Rückfall sagt, was der
Seed sagt.

Befunde vom 2026-09-27 (ST-1, Plan 2026-09-26):

- ``display_rules.inline_documents.intro_text`` war im Modell EIN Text, der
  Lader erwartet eine Zuordnung Muster-ID → Vorlage (so auch ALT). Ein im Studio
  gespeicherter Text bestand die Prüfung von ``PUT /config/data``, dann warf der
  Lader — ungeschützt aufgerufen aus ``turn_persist`` —, und jede Antwort endete
  als Fehler.
- Der eingebaute Begrüßungstext (leeres ``welcome.greeting``) hatte den
  KI-Hinweis nicht, den der Seed seit W12 (EU AI Act Art. 50) trägt.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from boerdi.domain.config_models import model_for
from boerdi.services import config_loader as cl

SEEDS = Path(__file__).parents[1] / "seeds" / "01-base"


class _Store:
    """Nur die Lesezugriffe hinter ``area()`` — gespeichert wird hier nichts."""

    def __init__(self, areas: dict[str, dict[str, Any]]) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


@pytest.fixture()
def bind():
    yield lambda areas: cl.bind_store(_Store(areas))
    cl.bind_store(None)


def _display_rules(intro_text: Any) -> dict[str, Any]:
    return {"display_rules": {"inline_documents": {"intro_text": intro_text}}}


# ── Begleittext der Dokument-Boxen ─────────────────────────────────────────
def test_intro_text_model_accepts_one_text_per_pattern() -> None:
    model = model_for("01-base/display-rules")
    model.model_validate(_display_rules({"M09": "Dein Lernpfad{topic_suffix}:"}))
    # Ein Bestand mit ``null`` (Vorgabe des alten Modells) bleibt speicherbar.
    model.model_validate(_display_rules(None))


def test_intro_text_model_rejects_a_single_text() -> None:
    # Genau dieser Wert brach jede Antwort. Das Studio zeigt die Ablehnung am
    # Feld; der alte Wert erscheint dort im JSON-Editor zur Reparatur.
    with pytest.raises(ValidationError):
        model_for("01-base/display-rules").model_validate(
            _display_rules("Hier ist dein Material"))


def test_intro_text_saved_in_studio_reaches_the_chat_as_mapping(bind) -> None:
    doc = _display_rules({"m09": "  Dein Lernpfad{topic_suffix}:  ", "M10": ""})
    model_for("01-base/display-rules").model_validate(doc)  # die Prüfung beim Speichern
    bind({"01-base/display-rules": doc})

    intro = cl.load_display_rules_config()["inline_documents"]["intro_text"]

    assert intro == {"M09": "Dein Lernpfad{topic_suffix}:"}


@pytest.mark.parametrize("wrong", ["Hier ist dein Material", ["M09"], 3])
def test_intro_text_of_wrong_shape_is_logged_not_raised(bind, caplog, wrong) -> None:
    # Ein Wert, der vor der Korrektur des Modells gespeichert wurde, darf den
    # Chat nicht weiter lahmlegen: überspringen und laut sagen.
    bind({"01-base/display-rules": _display_rules(wrong)})

    with caplog.at_level(logging.WARNING, logger="boerdi.services.config_loader.widget"):
        rules = cl.load_display_rules_config()

    assert rules["inline_documents"]["intro_text"] == {}
    assert "intro_text" in caplog.text


# ── Begrüßung ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize("stored", [
    {"welcome": {"greeting": ""}},
    {"welcome": {"greeting": "   "}},
    {},
])
def test_builtin_greeting_is_the_seed_greeting_with_ai_notice(bind, stored) -> None:
    seed = yaml.safe_load((SEEDS / "welcome-config.yaml").read_text(encoding="utf-8"))
    bind({"01-base/welcome-config": stored})

    greeting = cl.load_welcome_config()["greeting"]

    assert "Ich bin kein Mensch, sondern ein KI-Assistent." in greeting
    assert greeting == seed["welcome"]["greeting"].strip()
