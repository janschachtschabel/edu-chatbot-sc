"""What a German prompt needs in order to produce another language (C1-f2).

C1's decision: the prompts stay German — they are instructions TO the model,
not its output. Only the OUTPUT language switches. That leaves two things every
prompt needs, and they are separated here on purpose:

* :func:`language_name` — the language as it is *named inside* a German
  sentence. Five prompts already carry a hard "… auf Deutsch …" directive
  (response, canvas ×2, curation, learning path); substituting the name in
  place keeps the German prompt byte-identical, position included. The C1-f1
  finding was that appending a second directive instead would have put two
  contradicting instructions into the same prompt.

* :func:`template_hint` — a block appended ONLY for a non-German output. Two
  things make it necessary, and both are invisible until you switch: the
  templates around it prescribe German headings (``'# Arbeitsblatt: [Thema]'``,
  ``### Schritt 1: Einstieg``), and the learning path insists on quoting
  material titles verbatim. Without the hint the model either keeps the German
  headings or, worse, translates the WLO titles and breaks the match against
  the cards. Empty for German, so the German prompt stays byte-identical.
"""

from typing import Final

from boerdi.i18n.locale import DEFAULT, Locale

#: The language named inside a German prompt sentence.
LANGUAGE_NAME: Final[dict[Locale, str]] = {
    "de": "Deutsch",
    "en": "Englisch (British English)",
}

#: Appended to a German prompt template when the output is NOT German.
#: Empty for German — that emptiness is what keeps the German prompt unchanged.
TEMPLATE_HINT: Final[dict[Locale, str]] = {
    "de": "",
    "en": (
        "SPRACHE DER AUSGABE: Englisch (British English), auch wenn die "
        "Vorgaben, Überschriften und Beispiele oben auf Deutsch stehen — "
        "übersetze sie mit. Ausgenommen sind Eigennamen und die Titel "
        "zitierter Materialien: die bleiben wörtlich im Original."
    ),
}


def language_name(lang: Locale) -> str:
    """The output language as it is named inside a German prompt sentence."""
    return LANGUAGE_NAME.get(lang, LANGUAGE_NAME[DEFAULT])


def template_hint(lang: Locale) -> str:
    """The block to append to a German prompt template — empty for German.

    Carries its own leading blank line so a call site can append it
    unconditionally: for German it contributes nothing at all.
    """
    hint = TEMPLATE_HINT.get(lang, TEMPLATE_HINT[DEFAULT])
    return f"\n\n{hint}" if hint else ""
