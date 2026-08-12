"""The words the anti-hallucination watchdog looks for in OUR OWN text (C1-f2b4).

The watchdog in ``services/turn_links`` reads the answer we just produced and
rewrites claims about collections and topic pages that no visible box backs up;
``services/turn_persist`` drops the quick replies that would contradict the
rewrite. Both read the same vocabulary, so it lives in one place — two copies
would let the text and the chips disagree after a single one-sided edit.

Since C1-f1 that answer is in the user's language. With the German patterns
alone the watchdog simply stopped matching in English: no crash, no log line,
just a claim about boxes that are not there.

Patterns, not prose — that is why they are here and not in ``bot_text``: a
regex has no translation, it has a per-language counterpart. Same call as
``_SOLUTIONS_PATTERNS`` in ``services/canvas_fast_path``.

**The English entries keep the German product terms.** ``Sammlung`` and
``Themenseite`` name WLO surfaces, and the C1-f2a prompt hint tells the model to
leave proper nouns alone — so they turn up inside English answers. A German word
in an English sentence is exactly the claim the watchdog exists to catch, so
matching it is right, not over-matching. The verbs are ordinary prose and get
translated by the model, so ``DELIVERY_VERBS["en"]`` does not carry the German
ones.

Known gap, deliberately not closed here: whether the model really writes
"collections" or something else we do not list can only be settled by a live run
per language. What is proven is the mechanism — see ``tests/test_turn_links.py``.
"""

from typing import Final

from boerdi.i18n.locale import Locale

# Die eigentlichen Daten: die Nomen-Alternativen ohne Wortgrenzen. Die drei
# fertigen Muster darunter werden daraus gebaut, damit die Einzel-Muster und
# das Sammel-Muster nicht auseinanderlaufen können.
_COLLECTION: Final[dict[Locale, str]] = {
    "de": r"Sammlung(?:en)?",
    "en": r"collections?|Sammlung(?:en)?",
}
_TOPIC_PAGE: Final[dict[Locale, str]] = {
    "de": r"Themenseite(?:n)?",
    "en": r"topic\s+pages?|Themenseite(?:n)?",
}

COLLECTION_WORD: Final[dict[Locale, str]] = {
    lang: rf"\b(?:{alt})\b" for lang, alt in _COLLECTION.items()
}
TOPIC_PAGE_WORD: Final[dict[Locale, str]] = {
    lang: rf"\b(?:{alt})\b" for lang, alt in _TOPIC_PAGE.items()
}
#: Beides zusammen — für den Satz-Rewrite bei Typ-Fokus und für den
#: Quick-Reply-Filter in ``turn_persist``.
CLAIM_WORDS: Final[dict[Locale, str]] = {
    lang: rf"\b(?:{alt}|{_TOPIC_PAGE[lang]})\b" for lang, alt in _COLLECTION.items()
}

#: Optionales Determinativ/Adjektiv direkt vor dem Nomen. Ohne das blieb im
#: Deutschen die Beugung stehen („passenden passende Treffer in der Suche",
#: Bug 2026-05-22). Englisch dekliniert nicht, braucht dafür aber die
#: Artikel- und Mengenwörter, die das Modell tatsächlich schreibt.
DETERMINER_PREFIX: Final[dict[Locale, str]] = {
    "de": (
        r"(?:\b(?:"
        r"zwei|drei|vier|fünf|sechs|sieben|acht|neun|zehn|"
        r"ein(?:e[srnm]?)?|"
        r"d(?:er|ie|as|em|en|es)|"
        r"diese[srnm]?|"
        r"meine[srnm]?|deine[srnm]?|seine[srnm]?|"
        r"unsere[srnm]?|eure[srnm]?|ihre[srnm]?|"
        r"passende[srnm]?|"
        r"einige|mehrere|alle[srnm]?|viele|wenige|"
        r"weitere|andere[srnm]?|"
        r"ähnliche[srnm]?|verwandte[srnm]?"
        r")\s+)?"
    ),
    "en": (
        r"(?:\b(?:"
        r"two|three|four|five|six|seven|eight|nine|ten|"
        r"an?|the|"
        r"th(?:is|at|ese|those)|"
        r"my|your|his|her|its|our|their|"
        r"matching|suitable|relevant|fitting|"
        r"some|several|all|many|few|"
        r"more|other|further|"
        r"similar|related"
        r")\s+)?"
    ),
}

#: „ich hab dir … rausgesucht" — die Liefer-Behauptung. Steht keine Box im UI,
#: ist der ganze Satz erfunden und wird durch einen Suchverweis ersetzt.
DELIVERY_VERBS: Final[dict[Locale, str]] = {
    "de": (
        r"rausgezogen|rausgesucht|zusammengestellt|"
        r"herausgesucht|gefunden|kuratiert"
    ),
    "en": (
        r"put\s+together|pulled\s+together|picked\s+out|"
        r"compiled|curated|gathered|collected|found"
    ),
}

__all__: Final = [
    "CLAIM_WORDS", "COLLECTION_WORD", "DELIVERY_VERBS",
    "DETERMINER_PREFIX", "TOPIC_PAGE_WORD",
]
