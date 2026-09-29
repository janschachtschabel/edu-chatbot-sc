"""Ton-Modifier (``config_loader/tone.py``): EIN Kachel-Vokabular (Befund 2026-09-27).

Lader und Antwort-Prompt kannten zwei Wortschätze für ``card_text_mode``: der
Lader ließ ``minimal|kurz|explanation|ausfuehrlich`` durch, der Prompt
(``render_card_text_mode_block``) kennt ``minimal|reference|highlight``. Jeder
Wert außer ``minimal`` fiel damit durch eine der beiden Maschen: ``reference``
und ``highlight`` machte der Lader zu ``minimal``, ``explanation`` (P-ELT, P-LER
im Seed) fand im Prompt keine Regel — dort stand gar keine Kachel-Regel. Der
ALT hatte denselben Widerspruch; sein Studio bot beide Listen an.
"""

from __future__ import annotations

import pytest

from boerdi.services.config_loader import tone
from boerdi.services.response_prompt_display_blocks import render_card_text_mode_block


def _modus(wert: object) -> str:
    return tone._coerce_tone_modifier({"card_text_mode": wert})["card_text_mode"]


def test_jeder_wert_des_laders_hat_eine_kachelregel_im_prompt():
    ohne_regel = [m for m in tone._CARD_TEXT_MODES if not render_card_text_mode_block(m)]
    assert ohne_regel == []


@pytest.mark.parametrize("wert", ["minimal", "reference", "highlight"])
def test_jeder_modus_des_prompts_kommt_durch_den_lader(wert):
    assert _modus(wert) == wert


def test_explanation_aus_dem_alten_vokabular_wird_highlight():
    # „explanation — mehr Kontext" (ALT-Studio) trugen P-ELT und P-LER. Gespeicherte
    # Bereiche behalten so ihre Absicht, auch ohne neuen Seed-Import.
    assert _modus("explanation") == "highlight"


@pytest.mark.parametrize("wert", ["kurz", "ausfuehrlich", "bunt", "", None])
def test_sonstige_werte_werden_minimal(wert):
    assert _modus(wert) == "minimal"
