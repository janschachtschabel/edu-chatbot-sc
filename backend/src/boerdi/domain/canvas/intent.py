"""Canvas intent heuristics — ported 1:1 from ALT
``app/services/canvas_intent.py``: the pure regex helpers
(``_phrase_matches`` / ``resolve_material_type`` /
``extract_material_type_from_message`` / ``named_artifact_label``) plus the
nouns constants and regex. The three trigger heuristics
(``looks_like_create_intent`` / ``looks_like_edit_intent`` /
``has_explicit_new_create_override``) had no production caller and went with
their areas in Paket 7 (K4). Consumes the canvas_types getters
sideways (acyclic). Pure (stdlib re + the config-driven type getters) ->
``domain/``.
"""
from __future__ import annotations

import re

from boerdi.domain.canvas.types import (
    get_short_alias_whitelist,
    get_type_aliases,
)


def resolve_material_type(raw: str | None) -> str | None:
    """Map a user-supplied or classifier-extracted material type label to the canonical key.

    Returns the canonical key (e.g. 'arbeitsblatt') or None if unknown/missing.
    """
    if not raw:
        return None
    key = raw.strip().lower()
    # strip leading emoji + whitespace (e.g. "📝 Arbeitsblatt" -> "arbeitsblatt")
    while key and not key[0].isalpha():
        key = key[1:].strip()
    # strip "-karten", "-/test" variants
    key = key.replace("/", " ").strip()
    # pick first word if multi-word
    first = key.split()[0] if key else ""
    aliases = get_type_aliases()
    return aliases.get(key) or aliases.get(first)


def extract_material_type_from_message(msg: str) -> str | None:
    """Heuristic scan of a user message for a material type keyword.

    Used when the classifier did not extract `material_typ` into `entities`
    but the intent is I05. Prefers longer aliases first to avoid
    mismatches (e.g. 'arbeitsblatt' wins over 'blatt').

    Short aliases (< 6 chars) only match with word-boundary awareness so
    that 'test' in 'testen' does NOT hit, but 'test' in 'ein Test zu X'
    does. Long aliases use substring match (safer because of length).

    Welle E v4+12 (eval-316d36-Befund): Bindestriche werden vor dem
    Match entfernt — „Info-Blatt", „Arbeits-Blatt", „Lehr-Material"
    treffen so auf dieselben Aliase wie ohne Bindestrich. Hyphenierung
    ist im Deutschen häufig stilistisch (vor allem Redaktions-/
    Verwaltungstexte) und sollte die Material-Typ-Erkennung nicht
    blockieren.
    """
    if not msg:
        return None
    low = msg.lower()
    # Bindestrich-freie Variante als zweiter Match-Versuch — gleicher Text,
    # nur ohne ``-``. Wir matchen zuerst gegen das Original (häufigere Form),
    # fallen erst dann auf die de-hyphenisierte Variante zurück, damit
    # legitime Multi-Wort-Aliase wie „quiz/test" nicht zerschossen werden.
    low_nohyp = low.replace("-", "") if "-" in low else None
    aliases = get_type_aliases()
    whitelist = get_short_alias_whitelist()
    for alias in sorted(aliases.keys(), key=len, reverse=True):
        if len(alias) >= 6:
            if alias in low:
                return aliases[alias]
            if low_nohyp is not None and alias in low_nohyp:
                return aliases[alias]
        elif alias in whitelist:
            # Short whitelisted alias: require word boundary on both sides.
            if _phrase_matches(low, alias):
                return aliases[alias]
            if low_nohyp is not None and _phrase_matches(low_nohyp, alias):
                return aliases[alias]
    return None


# Generic placeholder nouns that do NOT count as a concretely named artifact —
# for these the slot-clarification (M03 "Welcher Typ?") stays correct.
_GENERIC_ARTIFACT_NOUNS = {
    "material", "materialien", "inhalt", "inhalte", "sache", "ding", "dinge",
    "etwas", "was", "dokument", "dokumente", "unterlage", "unterlagen", "zeug",
}

# "ein/eine/einen <optionale Adjektive> <Großgeschriebenes Nomen>"
_NAMED_ARTIFACT_RE = re.compile(
    r"\b(?:ein|eine|einen|das|den|die)\s+"
    r"(?:[a-zäöüß]+\s+){0,2}"
    r"([A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-]{4,})"
)


def named_artifact_label(msg: str, classifier_type: str | None = None) -> str:
    """Literal artifact noun when the user clearly NAMED a material type that
    is not a known alias (e.g. 'Argumentationshilfe', 'Lernplakat').

    Returns '' when no concrete artifact is named (e.g. 'mach mir was / ein
    Material') — so genuine slot-clarification (M03) stays intact.

    Such a request is generated via the 'auto' type with this label passed
    through; the LLM then picks the closest REAL format from the material-type
    vocabulary instead of asking 'Welcher Typ?'. Robuster Fallback gegen
    ungelistete-aber-klar-benannte Artefakt-Typen (eval-1eda-Befund GS-4.3).
    """
    # 1) Classifier already extracted a type label that doesn't resolve?
    cand = (classifier_type or "").strip()
    if (cand and cand.lower() not in _GENERIC_ARTIFACT_NOUNS
            and resolve_material_type(cand) is None):
        return cand
    # 2) Scan the message for "ein/eine <Adj>* <Nomen>"
    for m in _NAMED_ARTIFACT_RE.finditer(msg or ""):
        noun = m.group(1)
        if noun.lower() in _GENERIC_ARTIFACT_NOUNS:
            continue
        if resolve_material_type(noun) is not None:
            continue  # known type → handled via the alias path, not here
        return noun
    return ""


_WORD_BOUNDARY_CHARS = " ,.;:!?\t\n"


def _phrase_matches(haystack: str, needle: str) -> bool:
    """Match a phrase with word-boundary awareness.

    Avoids false positives like "mach ein" matching "mach es einfacher"
    (where "mach e" would greedily prefix-match). We require the needle to
    either start the haystack or follow a non-word char, AND to end at
    end-of-string or at a word boundary char.
    """
    if not needle:
        return False
    idx = 0
    n_len = len(needle)
    h_len = len(haystack)
    while idx <= h_len - n_len:
        pos = haystack.find(needle, idx)
        if pos < 0:
            return False
        left_ok = pos == 0 or haystack[pos - 1] in _WORD_BOUNDARY_CHARS
        end = pos + n_len
        # If the needle ends with whitespace (e.g. "zeig "), the caller
        # already encoded the right boundary — accept anything after.
        right_ok = (
            end >= h_len
            or needle.endswith(" ")
            or haystack[end] in _WORD_BOUNDARY_CHARS
        )
        if left_ok and right_ok:
            return True
        idx = pos + 1
    return False
