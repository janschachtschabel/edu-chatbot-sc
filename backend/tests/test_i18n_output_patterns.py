"""Guards for the watchdog vocabulary (C1-f2b4).

The tables in ``i18n/output_patterns`` decide whether the anti-hallucination
watchdog sees anything at all. A missing language does not raise here — the call
sites fall back to ``DEFAULT``, so the guard would keep matching German in an
English answer and stay silent about it. That is the exact failure C1-f2b4 was
built to end, so it gets its own guard.

The behaviour of the patterns is pinned where they are used
(``tests/test_turn_links.py``, ``tests/test_turn_persist.py``); what is checked
here is only that every table is complete and compiles.
"""

from __future__ import annotations

import re

from boerdi.i18n.locale import SUPPORTED
from boerdi.i18n.output_patterns import (
    CLAIM_WORDS,
    COLLECTION_WORD,
    DELIVERY_VERBS,
    DETERMINER_PREFIX,
    TOPIC_PAGE_WORD,
)

_TABELLEN = {
    "CLAIM_WORDS": CLAIM_WORDS,
    "COLLECTION_WORD": COLLECTION_WORD,
    "DELIVERY_VERBS": DELIVERY_VERBS,
    "DETERMINER_PREFIX": DETERMINER_PREFIX,
    "TOPIC_PAGE_WORD": TOPIC_PAGE_WORD,
}


def test_jede_tabelle_kennt_jede_unterstuetzte_sprache():
    for name, tabelle in _TABELLEN.items():
        assert set(tabelle) == set(SUPPORTED), name


def test_jedes_muster_ist_uebersetzbar():
    for name, tabelle in _TABELLEN.items():
        for lang, muster in tabelle.items():
            re.compile(muster)                      # wirft bei kaputtem Regex
            assert muster.strip(), f"{name}/{lang}"


# Je Sprache: was das Modell schreibt, wenn es Sammlungen bzw. Themenseiten
# behauptet. Die deutschen Begriffe stehen auch in der englischen Zeile — sie
# sind WLO-Produktnamen und tauchen in englischen Antworten auf.
_PROBEN: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "de": (("Sammlung", "Sammlungen"), ("Themenseite", "Themenseiten")),
    "en": (("collection", "collections", "Sammlungen"),
           ("topic page", "topic pages", "Themenseiten")),
}


def test_einzelmuster_treffen_die_erwarteten_woerter():
    for lang, (samml, themen) in _PROBEN.items():
        for wort in samml:
            assert re.search(COLLECTION_WORD[lang], wort, re.IGNORECASE), f"{lang}/{wort}"
        for wort in themen:
            assert re.search(TOPIC_PAGE_WORD[lang], wort, re.IGNORECASE), f"{lang}/{wort}"


def test_sammelmuster_trifft_alles_was_die_einzelmuster_treffen():
    """Satz-Rewrite (``turn_links``) und Quick-Reply-Filter (``turn_persist``)
    duerfen nicht auf verschiedene Woerter reagieren — sonst bleibt ein Chip
    stehen, den der gerade korrigierte Satz nicht mehr deckt."""
    for lang, (samml, themen) in _PROBEN.items():
        for wort in samml + themen:
            assert re.search(CLAIM_WORDS[lang], wort, re.IGNORECASE), f"{lang}/{wort}"
