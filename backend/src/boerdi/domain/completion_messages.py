"""Completion bubbles — ported 1:1 from ALT
``app/routers/chat_completion_messages.py``: heading extraction from canvas/
learning-path markdown (``_extract_headings`` with local ``_is_meta`` filter)
and the chat-bubble texts for created canvas materials
(``_canvas_completion_message``) and finished learning paths
(``_lp_completion_message``). Stateless, offline (``re`` imported
function-locally, as in the original) -> pure ``domain/``.

**C1-f2b2 — the language reaches here as a parameter.** The bubbles are the
bot's own voice, so their sentences moved into ``i18n/bot_text``. The meta-
heading filter below moved with them, but as *patterns*, not prose: it reads
the markdown **we ourselves generated**, whose language has been the user's
since C1-f2a. With the German patterns only, an English worksheet's
"## Solutions" was never recognised as a meta section and became the single
visible entry in the preview.
"""

from __future__ import annotations

from typing import Final

from boerdi.i18n import DEFAULT, Locale, bot_text

# Meta headings — "how to use / solutions / sources" titles that describe no
# content. Patterns, not sentences, hence not in the catalogue: they are
# matched against our own markdown, not shown to anyone. The German entry is
# ALT-verbatim.
_META_PATTERNS: Final[dict[Locale, tuple[str, ...]]] = {
    "de": (
        r"wie\s+liest\s+man",
        r"^lösungen?$",
        r"^loesungen?$",
        r"^quellen(angabe)?$",
        r"^hinweise?$",
        r"^anhang$",
        r"^glossar$",  # only when it's a meta-ref, not the main content
        r"^weiterführende",
        r"^weiterfu[eh]hrende",
        r"^literaturverzeichnis$",
    ),
    "en": (
        r"how\s+to\s+(?:read|use)",
        r"^solutions?$",
        r"^answers?$",
        r"^answer\s+key$",
        r"^sources?$",
        r"^references?$",
        r"^notes?$",
        r"^appendix$",
        r"^glossary$",
        r"^further\s+reading",
        r"^bibliography$",
    ),
}

# Headings that mark a task-driven document (worksheet/quiz): when the
# extractor returns only these, count the numbered tasks instead of listing
# sections. Lower-case, compared verbatim.
_META_ONLY: Final[dict[Locale, frozenset[str]]] = {
    "de": frozenset({"lösungen", "loesungen", "quellen", "hinweise"}),
    "en": frozenset({"solutions", "answers", "answer key", "sources", "notes"}),
}


def _extract_headings(
    markdown: str, topic: str, levels: str = "##", lang: Locale = DEFAULT,
) -> list[str]:
    """Extract H2 (or H2+H3) headings from the markdown, skipping duplicate
    or wrapper headings that just echo the topic and filtering out meta-
    sections like "Wie liest man diese Übersicht?" / "Lösungen" that would
    otherwise become the single visible section and make the chat preview
    look empty.
    """
    import re as _re
    # Try H2 first — if few, also include H3
    h2 = _re.findall(rf"^{levels}\s+(.+?)\s*$", markdown or "", flags=_re.MULTILINE)
    if len(h2) < 2:
        h2 = _re.findall(r"^#{2,3}\s+(.+?)\s*$", markdown or "", flags=_re.MULTILINE)

    # If still too few, extract bold-bullet "**Hauptast**"-pattern from list
    # structures (common in Strukturübersicht / Glossar where headings are
    # nested instead of H2'd).
    if len(h2) < 2:
        bullet_bold = _re.findall(
            r"^\s*[-*+]\s+\*\*(.+?)\*\*",
            markdown or "", flags=_re.MULTILINE,
        )
        if bullet_bold:
            h2 = bullet_bold

    # Strip markdown syntax and trailing punctuation
    cleaned = [h.strip().strip("*_`").strip() for h in h2]
    tl = (topic or "").strip().lower()

    # Meta-sections: filter unless they're the only thing we have. These
    # are "how to use / solutions / meta" titles that don't describe content.
    META_PATTERNS = _META_PATTERNS.get(lang, _META_PATTERNS[DEFAULT])
    def _is_meta(h: str) -> bool:
        hl = h.strip().strip("*_`").lower()
        return any(_re.search(p, hl) for p in META_PATTERNS)

    non_meta = [h for h in cleaned if h and h.lower() != tl and not _is_meta(h)]
    meta = [h for h in cleaned if h and h.lower() != tl and _is_meta(h)]

    # Prefer non-meta sections; only fall back to meta when we'd otherwise
    # have nothing.
    out = non_meta if non_meta else meta
    return out[:6]


def _canvas_completion_message(
    label: str, topic: str, markdown: str, canvas_enabled: bool = True,
    formality: str = "", lang: Locale = DEFAULT,
) -> str:
    """Build a rich chat-bubble text when a canvas-material is created.

    Welle E v4+++ (2026-05-26, eval-bd3a): ``formality`` durchgereicht, damit
    die Ankündigungs-Bubble bei P-ENT/P-RED/P-LEH siezt — vorher hartkodiert
    "Ich habe **dir** … du kannst es …" auch bei `formality=siezen`.

    ``lang`` picks the catalogue; ``formality`` still selects the du/Sie key,
    which English simply answers with the same sentence twice.
    """
    import re as _re
    _form = (formality or "").strip().lower()
    _siezen = _form in ("sie", "siezen", "formal", "foermlich")
    _anrede = "sie" if _siezen else "du"
    sections = _extract_headings(markdown, topic, lang=lang)
    lines = [bot_text(lang, f"completion.canvas.lead.{_anrede}",
                      label=label, topic=topic)]

    # Has the extractor only returned meta headings (e.g. ["Lösungen"]) —
    # that means the document is task-driven (Arbeitsblatt/Quiz). Count
    # numbered tasks instead so the preview is meaningful.
    META_ONLY_SET = _META_ONLY.get(lang, _META_ONLY[DEFAULT])
    only_meta = bool(sections) and all(
        s.strip().lower() in META_ONLY_SET for s in sections
    )

    if sections and not only_meta:
        lines.append("")
        lines.append(bot_text(lang, "completion.sections"))
        for i, s in enumerate(sections[:5], 1):
            lines.append(f"{i}. **{s}**")
    else:
        # Count numbered tasks at start-of-line ("1.", "2.", ...) — a robust
        # signal for Arbeitsblatt/Quiz/Übung documents.
        numbered = _re.findall(
            r"^\s*(\d{1,2})\.\s+\S",
            markdown or "",
            flags=_re.MULTILINE,
        )
        # Filter out the numbered "Lösungen"-list at the end by counting only
        # unique consecutive numbering from 1
        task_count = 0
        prev = 0
        for n in numbered:
            try:
                ni = int(n)
            except ValueError:
                continue
            if ni == prev + 1:
                task_count += 1
                prev = ni
            elif ni == 1:
                # restart of numbering (e.g. solutions section) — stop counting tasks
                break
        if task_count >= 2:
            lines.append("")
            _with_sol = any(
                s.strip().lower() in META_ONLY_SET for s in (sections or [])
            )
            lines.append(bot_text(
                lang,
                "completion.tasksWithSolutions" if _with_sol else "completion.tasks",
                count=task_count,
            ))
        elif sections:
            # Even meta-only: show them rather than nothing
            lines.append("")
            lines.append(bot_text(lang, "completion.sections"))
            for i, s in enumerate(sections[:5], 1):
                lines.append(f"{i}. **{s}**")

    lines.append("")
    if canvas_enabled:
        lines.append(bot_text(lang, f"completion.canvas.outro.{_anrede}"))
    else:
        # Inline-Modus: das Material landet unter dieser Bubble im Chat-
        # Verlauf statt im Canvas. Print-Button vom Frontend angeboten
        # (siehe `boerdi:printable-canvas`-Sentinel).
        lines.append(bot_text(lang, f"completion.inline.outro.{_anrede}"))
    return "\n".join(lines)


def _lp_completion_message(
    topic: str, markdown: str, canvas_enabled: bool = True,
    lang: Locale = DEFAULT,
) -> str:
    """Build a rich chat-bubble text for a completed learning path.

    The full path lives in the canvas — but the chat bubble needs more than
    a terse "guck im canvas"-pointer. Extract the H2/H3-Überschriften (Phasen)
    from the markdown so the user sees the roadmap inline.
    """
    phases = _extract_headings(markdown, topic, lang=lang)
    # Inline-Modus: Lernpfad landet direkt im Chat-Verlauf, Print-Button
    # vom Frontend angeboten (siehe `**Lernpfad:`-intrinsic marker plus
    # `boerdi:printable-canvas`-Sentinel).
    _where = "canvas" if canvas_enabled else "inline"
    lines = [bot_text(lang, f"completion.lp.lead.{_where}", topic=topic)]
    if phases:
        lines.append("")
        lines.append(bot_text(lang, "completion.lp.phases"))
        for i, p in enumerate(phases, 1):
            lines.append(f"{i}. **{p}**")
    lines.append("")
    lines.append(bot_text(lang, f"completion.lp.outro.{_where}"))
    return "\n".join(lines)
