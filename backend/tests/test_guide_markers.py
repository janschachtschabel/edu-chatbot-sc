"""Tests for the guide-marker strip helpers (port of ALT
``tests/test_guide_marker_strip.py`` + ``tests/test_chat_guide_qrs.py``).

``_strip_guide_markers_from_text`` sanitises the bot response text so a leaked
``__guide__|Label|URL`` quick-reply marker never reaches the chat bubble;
``_strip_guide_qrs`` is the fail-safe that drops ``__guide__|…`` entries from the
quick-reply list when lotsen-mode is off. Both pure, offline, deterministic.
"""

from __future__ import annotations

from boerdi.domain.guide_markers import (
    _strip_guide_markers_from_text,
    _strip_guide_qrs,
)

# ══════════════════════════════════════════════════════════════════════════
# _strip_guide_markers_from_text  (port of test_guide_marker_strip.py)
# ══════════════════════════════════════════════════════════════════════════

def test_strips_full_marker_with_underscores():
    text = (
        "Hier sind Treffer. __guide__|Themenseite|"
        "https://wirlernenonline.de/themen/x__ Hilfreich."
    )
    out = _strip_guide_markers_from_text(text)
    assert "guide|" not in out
    assert "https://" not in out
    assert "Hier sind Treffer" in out
    assert "Hilfreich" in out


def test_strips_markdown_eaten_marker():
    """Markdown bold-pre-processing ate the leading ``__``. Result:
    bare ``guide|Label|URL`` text."""
    text = (
        "Klar, ich hab dir die Videos rausgezogen.\n\n"
        "guide|Zur Themenseite Nachhaltigkeit|https://redaktion.openeduhub.net/edu-sharing/components/topic-pages?collectionId=d0ed50e6"
    )
    out = _strip_guide_markers_from_text(text)
    assert "guide|" not in out.lower() or "guides" in out.lower()  # only false-positive matches
    assert "https://" not in out
    assert "Klar, ich hab dir die Videos rausgezogen" in out


def test_idempotent_on_clean_text():
    text = "Normale Bot-Antwort ohne Marker."
    assert _strip_guide_markers_from_text(text) == text


def test_handles_empty_input():
    assert _strip_guide_markers_from_text("") == ""
    assert _strip_guide_markers_from_text(None) == ""


def test_strips_multiple_markers():
    text = (
        "Hier zwei Wege:\n"
        "guide|Themenseite|https://x.de/a\n"
        "guide|Sammlung|https://x.de/b\n"
        "Schau dir das an."
    )
    out = _strip_guide_markers_from_text(text)
    assert "guide|" not in out.lower() or out.lower().count("guide") == 0
    assert "https://" not in out
    assert "Schau dir das an" in out


def test_case_insensitive_match():
    text = "Test: GUIDE|Label|https://x.de"
    out = _strip_guide_markers_from_text(text)
    assert "https://" not in out
    assert "Test:" in out


def test_word_guide_in_normal_sentence_preserved():
    """The word 'guide' in a normal sentence (no pipe) is NOT stripped."""
    text = "Dies ist ein guter Guide zum Lernen."
    out = _strip_guide_markers_from_text(text)
    assert "Guide zum Lernen" in out


# ══════════════════════════════════════════════════════════════════════════
# _strip_guide_qrs  (port of test_chat_guide_qrs.py)
# ══════════════════════════════════════════════════════════════════════════

def test_strips_guide_prefixed_entries():
    assert _strip_guide_qrs(
        ["Normal", "__guide__|Bring mich hin", "Andere"]
    ) == ["Normal", "Andere"]


def test_keeps_non_guide_entries():
    assert _strip_guide_qrs(["a", "b"]) == ["a", "b"]


def test_empty_list():
    assert _strip_guide_qrs([]) == []
