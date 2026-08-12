"""Content-type intent classification (whole-module verbatim port of ALT
``chat_content_types.py``): reads the wanted resource types out of a user message
(plus accumulated entities) and matches cards against them. Stateless keyword/string
logic — no I/O, no config → ``domain/``.

Produces the ``wanted_content_types`` set consumed by ``domain/cards/{normalize,select}``
and ``services/card_pipeline``; feeds the type-focus path in the response finalizer.

**NEU-Portierung:** the module has zero app imports, so it is copied byte-for-byte
from ALT (only this docstring differs) — the whole-module AST is identical.
"""

from __future__ import annotations

from typing import Any

# Mapping von User-Stichworten zu kanonischen Substrings, die in den
# Card-Feldern ``learning_resource_types`` matchen sollten. WLO emittiert
# diese Labels mit Capitalisation (z.B. ``['Video']``, ``['Arbeitsblatt']``),
# Match läuft case-insensitive via ``substring in lower(blob)``.
#
# **C1-f2c-b: die Stichwörter sind zweisprachig, der kanonische Schlüssel NICHT.**
# Der Schlüssel ist kein blosser Name — er geht als ``learningResourceType`` in
# die WLO-Suche (``services/prefetch.py:250``) und wird unten in
# ``_card_matches_wanted_types`` als Teilzeichenkette gegen die deutschen
# Labels der Karte gehalten. Übersetzt träfe er nie; dieselbe Doppelrolle wie
# beim Typ-Label in C1-f2b3. Nur die linke Seite, das was der Nutzer schreibt,
# wächst also um englische Wörter.
_CONTENT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "video":          ("video", "videos"),
    "arbeitsblatt":   ("arbeitsblatt", "arbeitsblätter", "arbeitsblaetter",
                       "worksheet", "worksheets", "work sheet"),
    "übung":          ("übung", "uebung", "übungen", "uebungen",
                       "exercise", "exercises", "practice task"),
    "quiz":           ("quiz", "test", "tests", "quizzes"),
    "audio":          ("audio", "podcast", "podcasts", "hörspiel", "hoerspiel",
                       "audio play", "radio play"),
    "präsentation":   ("präsentation", "praesentation", "präsentationen", "praesentationen",
                       "presentation", "presentations", "slide deck", "slides"),
    "interaktiv":     ("interaktiv", "interaktive", "interactive"),
    "kurs":           ("kurs", "kurse", "tutorial", "tutorials",
                       "course", "courses"),
    "spiel":          ("lernspiel", "lernspiele", "spiel",
                       "learning game", "learning games", "educational game"),
    "grafik":         ("infografik", "grafik", "infographic", "infographics",
                       "graphic", "graphics"),
}


def _user_wants_specific_content_type(message: str) -> bool:
    """Heuristik: fragt der User nach einem konkreten Material-Format?

    Wenn der User „Such mir ein Arbeitsblatt zu …" oder „Hast du Videos
    zu …" schreibt, will er Einzelinhalte — keine kuratierten Sammlungen.
    Dann kehren wir in der Inline-Link-Reihenfolge die Standardgruppierung
    um (Einzel zuerst statt Themenseite zuerst).
    """
    msg = (message or "").lower()
    for keywords in _CONTENT_TYPE_KEYWORDS.values():
        if any(kw in msg for kw in keywords):
            return True
    return False


def _extract_wanted_content_types(message: str) -> set[str]:
    """Welche konkreten Material-Typen hat der User in der Nachricht
    erwähnt? Returns lower-case substrings, die in
    ``card.learning_resource_types`` matchen sollten — z.B. ``{"video"}``
    bei „Hast du Videos zur …?" oder ``{"arbeitsblatt"}`` bei
    „Such mir Arbeitsblätter zu …".

    Returns leere Menge, wenn der User keinen Typ-Fokus ausgedrückt hat.
    """
    msg = (message or "").lower()
    wanted: set[str] = set()
    for canonical, keywords in _CONTENT_TYPE_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            wanted.add(canonical)
    return wanted


def _resolve_wanted_content_types(
    message: str,
    session_entities: dict | None = None,
    classification_entities: dict | None = None,
) -> set[str]:
    """Welle C Sprint 6 Hotfix — Vollständiger Type-Filter aus 3 Quellen.

    Zieht den Material-Typ-Wunsch aus:
      1. Aktueller User-Nachricht ("nur videos zeigen" → {"video"})
      2. ``classification.entities.medientyp`` (frisch vom Classifier)
      3. ``session_state.entities.medientyp`` (aus vorherigem Turn akkumuliert)

    Damit überlebt der Filter ein Follow-up wie „nur Videos zeigen"
    auch wenn der Classifier den medientyp nicht erneut extrahiert hat
    (weil das alte session-Wissen bereits präsent ist).

    User-Bug-Report Sprint 6: Ohne diesen Resolver landete der Bot bei
    „nur Videos zeigen" auf M12 und zeigte trotzdem Sammlungen
    statt nur Videos.
    """
    wanted = _extract_wanted_content_types(message)

    for src in (classification_entities, session_entities):
        if not isinstance(src, dict):
            continue
        mt = src.get("medientyp") or src.get("material_typ") or ""
        if not isinstance(mt, str) or not mt.strip():
            continue
        # Map auf canonical key — wenn der Wert direkt einem Keyword
        # entspricht (z.B. "Video"), nutze ihn als Filter-String.
        mt_lower = mt.strip().lower()
        # Bevorzuge canonical-Match wenn möglich
        matched = False
        for canonical, keywords in _CONTENT_TYPE_KEYWORDS.items():
            if mt_lower == canonical or any(kw in mt_lower for kw in keywords):
                wanted.add(canonical)
                matched = True
                break
        if not matched and mt_lower:
            # Fallback: das raw-Wort als Substring nutzen
            wanted.add(mt_lower)

    return wanted


def _card_matches_wanted_types(card: Any, wanted: set[str]) -> bool:
    """True, wenn die ``learning_resource_types`` der Card einen der vom
    User gewünschten Typen enthalten. Wenn ``wanted`` leer ist (kein Typ-
    Fokus), gibt's keine Einschränkung → True. Substring-Match auf der
    lowercase-konkatenierten Type-Liste.
    """
    if not wanted:
        return True
    lrt = (card.get("learning_resource_types") if isinstance(card, dict)
           else getattr(card, "learning_resource_types", None))
    if not lrt:
        return False
    blob = " ".join(str(t).lower() for t in lrt if t)
    return any(w in blob for w in wanted)
