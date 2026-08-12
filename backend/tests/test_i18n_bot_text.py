"""Guards for the bot-text catalogue (C1-f2b).

The second catalogue beside ``i18n/messages.py``: what the BOT says to the end
user, as opposed to what the API says to an editor in the studio. Two audiences,
two triggers (``environment.locale`` vs ``Accept-Language``) — but the same
rendering, which is why both go through ``i18n/catalogue.render``.

The guards here are the cheap ones that catch real mistakes: a key that exists
in one language only, and a placeholder that was renamed in one language only.
Both would ship a broken sentence that no unit test of the calling module would
notice, because the calling module only ever asks for one language at a time.
"""

from __future__ import annotations

import re

from boerdi.i18n import bot_text
from boerdi.i18n.bot_text import BOT_TEXT

_PLATZHALTER = re.compile(r"\{(\w+)\}")


def test_beide_sprachen_tragen_dieselben_schluessel():
    assert set(BOT_TEXT["de"]) == set(BOT_TEXT["en"])


def test_jeder_schluessel_hat_in_beiden_sprachen_dieselben_platzhalter():
    for key, deutsch in BOT_TEXT["de"].items():
        englisch = BOT_TEXT["en"][key]
        assert set(_PLATZHALTER.findall(deutsch)) == set(_PLATZHALTER.findall(englisch)), key


def test_kein_satz_ist_leer():
    for lang, katalog in BOT_TEXT.items():
        for key, satz in katalog.items():
            assert satz.strip(), f"{lang}/{key}"


def test_unbekannte_sprache_faellt_auf_deutsch_zurueck():
    assert bot_text("fr", "content.missingNode") == BOT_TEXT["de"]["content.missingNode"]  # type: ignore[arg-type]


def test_platzhalter_werden_ersetzt():
    satz = bot_text("de", "content.lead", title="Bruchrechnung")
    assert "Bruchrechnung" in satz and "{title}" not in satz
