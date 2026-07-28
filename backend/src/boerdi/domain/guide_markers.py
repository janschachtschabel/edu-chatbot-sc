"""Guide-marker strip helpers (P4-5 assembly prerequisite, port of ALT
``chat_guide_markers.py``'s strip cluster): drop a leaked ``__guide__|Label|URL``
quick-reply marker from the bot response text (``_strip_guide_markers_from_text``)
and the fail-safe that removes ``__guide__|…`` entries from the quick-reply list
when lotsen-mode is off (``_strip_guide_qrs``).

Pure text/list logic (stdlib ``re`` only, no I/O) -> ``domain/``. The strip
helpers carry NO app imports in ALT, so this is a **zero-deviation** port: every
body and the ``import re as _re_guide_markers`` alias are byte-identical to ALT
(AST-diff gate). The alias is kept verbatim (like ``guide_mode``'s ``_re_es``) so
the ``_re_guide_markers.sub`` / ``.compile`` calls stay unchanged.

The inject/attach half of ALT ``chat_guide_markers`` (``_attach_guide_qr`` ->
``guide_qr_injector.inject_guide_qr``; ``_attach_guide_urls`` -> ``guide_mode``
card annotation) follows as its own slice once ``guide_qr_injector`` is ported.
"""

from __future__ import annotations

import re as _re_guide_markers


def _strip_guide_qrs(quick_replies: list[str]) -> list[str]:
    """Remove every ``__guide__|...`` entry from the QR list. Used as
    the fail-safe when guide mode is off — the LLM can still emit the
    magic prefix but the user must not see it."""
    if not quick_replies:
        return list(quick_replies or [])
    return [q for q in quick_replies if not (
        isinstance(q, str) and q.startswith("__guide__|")
    )]


# Match-Variants: mit und ohne führende ``__``, weil Markdown sie u.U.
# bereits weggefressen hat. Greedy bis zur nächsten Whitespace-Grenze
# nach der URL (so dass „<…> Wahnsinnig" am Zeilenende sauber stehen
# bleibt).
_GUIDE_MARKER_RE = _re_guide_markers.compile(
    r"(?:__)?guide(?:__)?\|[^|]+\|https?://\S+",
    flags=_re_guide_markers.IGNORECASE,
)


def _strip_guide_markers_from_text(text: str) -> str:
    """Remove stray ``__guide__|Label|URL`` (and Markdown-stripped
    ``guide|Label|URL``) markers from the bot response text.

    The marker is only legitimate inside ``quick_replies`` entries.
    When the LLM leaks it into the answer body, it shows up as
    raw text after Markdown normalisation — visually broken.

    Idempotent: safe to call multiple times. Whitespace cleanup
    afterwards collapses double-spaces that can remain after stripping
    a marker from a line.
    """
    if not text:
        return ""
    # Fast-path: skip regex if no marker-candidate substring is present.
    # Markdown can eat the surrounding underscores, so we check both
    # ``guide|`` (Markdown-cleaned) and ``guide__|`` (raw, surviving).
    low = text.lower()
    if "guide|" not in low and "guide__|" not in low:
        return text
    cleaned = _GUIDE_MARKER_RE.sub("", text)
    # Collapse multiple consecutive blanks and stranded line-ends
    cleaned = _re_guide_markers.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = _re_guide_markers.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()
