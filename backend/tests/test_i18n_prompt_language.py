"""The two atoms every German prompt needs to produce another language (C1-f2a).

Pinned here because five prompts share them: the response path (C1-f1), canvas,
curation, learning path and quick replies. The German case must stay EMPTY /
byte-identical — that is the whole point of the split into name + hint.
"""

from __future__ import annotations

from boerdi.i18n import language_name, template_hint


def test_sprachname_steht_im_deutschen_satz():
    assert language_name("de") == "Deutsch"
    assert language_name("en") == "Englisch (British English)"


def test_unbekannte_sprache_faellt_auf_deutsch_zurueck():
    assert language_name("fr") == "Deutsch"  # type: ignore[arg-type]
    assert template_hint("fr") == ""  # type: ignore[arg-type]


def test_hinweis_ist_fuer_deutsch_leer():
    """Ein leerer Hinweis laesst den deutschen Prompt bytegleich."""
    assert template_hint("de") == ""


def test_hinweis_nennt_ausgabe_sprache_trennung_und_eigennamen():
    hint = template_hint("en")
    assert hint.startswith("\n\n")  # anhaengbar ohne Satzbau am Aufrufort
    assert "Englisch (British English)" in hint
    # Die Vorlagen ringsum sind deutsch — der Hinweis muss beides sagen:
    # uebersetze die Vorgaben, aber nicht die zitierten Titel.
    assert "deutsch" in hint.lower()
    assert "Titel" in hint
