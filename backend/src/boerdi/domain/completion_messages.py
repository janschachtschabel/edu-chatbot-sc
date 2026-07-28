"""Completion bubbles — ported 1:1 from ALT
``app/routers/chat_completion_messages.py``: heading extraction from canvas/
learning-path markdown (``_extract_headings`` with local ``_is_meta`` filter)
and the chat-bubble texts for created canvas materials
(``_canvas_completion_message``) and finished learning paths
(``_lp_completion_message``). Stateless, offline (``re`` imported
function-locally, as in the original) -> pure ``domain/``.
"""

from __future__ import annotations


def _extract_headings(markdown: str, topic: str, levels: str = "##") -> list[str]:
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
    META_PATTERNS = (
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
    )
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
    formality: str = "",
) -> str:
    """Build a rich chat-bubble text when a canvas-material is created.

    Welle E v4+++ (2026-05-26, eval-bd3a): ``formality`` durchgereicht, damit
    die Ankündigungs-Bubble bei P-ENT/P-RED/P-LEH siezt — vorher hartkodiert
    "Ich habe **dir** … du kannst es …" auch bei `formality=siezen`.
    """
    import re as _re
    _form = (formality or "").strip().lower()
    _siezen = _form in ("sie", "siezen", "formal", "foermlich")
    sections = _extract_headings(markdown, topic)
    if _siezen:
        lines = [f"Ich habe Ihnen ein **{label}** zum Thema *{topic}* erstellt."]
    else:
        lines = [f"Ich habe dir ein **{label}** zum Thema *{topic}* erstellt."]

    # Has the extractor only returned meta headings (e.g. ["Lösungen"]) —
    # that means the document is task-driven (Arbeitsblatt/Quiz). Count
    # numbered tasks instead so the preview is meaningful.
    META_ONLY_SET = {"lösungen", "loesungen", "quellen", "hinweise"}
    only_meta = bool(sections) and all(
        s.strip().lower() in META_ONLY_SET for s in sections
    )

    if sections and not only_meta:
        lines.append("")
        lines.append("Abschnitte:")
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
            lines.append(f"Enthält **{task_count} Aufgaben**" + (
                " mit Lösungen." if any(s.strip().lower() in META_ONLY_SET for s in (sections or [])) else "."
            ))
        elif sections:
            # Even meta-only: show them rather than nothing
            lines.append("")
            lines.append("Abschnitte:")
            for i, s in enumerate(sections[:5], 1):
                lines.append(f"{i}. **{s}**")

    lines.append("")
    if canvas_enabled:
        if _siezen:
            lines.append(
                "Sie sehen es rechts im Canvas — ich kann es direkt anpassen, "
                "wenn Sie z.B. \"machen Sie die Aufgaben einfacher\" oder "
                "\"fügen Sie Lösungen hinzu\" schreiben."
            )
        else:
            lines.append(
                "Du siehst es rechts im Canvas — ich kann es direkt anpassen, "
                "wenn du z.B. \"mach die Aufgaben einfacher\" oder \"füge Lösungen "
                "hinzu\" schreibst."
            )
    else:
        # Inline-Modus: das Material landet unter dieser Bubble im Chat-
        # Verlauf statt im Canvas. Print-Button vom Frontend angeboten
        # (siehe `boerdi:printable-canvas`-Sentinel).
        if _siezen:
            lines.append(
                "Das Material steht direkt unter dieser Nachricht — Sie können "
                "es mit dem Druck-Button als PDF speichern. Geben Sie bitte "
                "Bescheid, falls Sie Anpassungen wünschen (z.B. *\"machen Sie "
                "die Aufgaben einfacher\"* oder *\"fügen Sie Lösungen hinzu\"*)."
            )
        else:
            lines.append(
                "Das Material steht direkt unter dieser Nachricht — du kannst "
                "es mit dem Druck-Button als PDF speichern. Sag mir gerne, was "
                "angepasst werden soll (z.B. *\"mach die Aufgaben einfacher\"* "
                "oder *\"füge Lösungen hinzu\"*)."
            )
    return "\n".join(lines)


def _lp_completion_message(
    topic: str, markdown: str, canvas_enabled: bool = True,
) -> str:
    """Build a rich chat-bubble text for a completed learning path.

    The full path lives in the canvas — but the chat bubble needs more than
    a terse "guck im canvas"-pointer. Extract the H2/H3-Überschriften (Phasen)
    from the markdown so the user sees the roadmap inline.
    """
    phases = _extract_headings(markdown, topic)
    if canvas_enabled:
        lines = [
            f"Ich habe dir den **Lernpfad zu *{topic}*** im Canvas rechts aufgebaut."
        ]
    else:
        # Inline-Modus: Lernpfad landet direkt im Chat-Verlauf, Print-Button
        # vom Frontend angeboten (siehe `**Lernpfad:`-intrinsic marker plus
        # `boerdi:printable-canvas`-Sentinel).
        lines = [
            f"Ich habe dir den **Lernpfad zu *{topic}*** direkt unter dieser "
            f"Nachricht aufgebaut."
        ]
    if phases:
        lines.append("")
        lines.append("Er ist in diese Phasen gegliedert:")
        for i, p in enumerate(phases, 1):
            lines.append(f"{i}. **{p}**")
    lines.append("")
    if canvas_enabled:
        lines.append(
            "Du kannst ihn im Canvas drucken, als Markdown speichern oder mir "
            "sagen, was angepasst werden soll (z.B. *\"mach ihn für Klasse 5 "
            "einfacher\"* oder *\"füge einen Schritt zur Sicherung hinzu\"*)."
        )
    else:
        lines.append(
            "Du kannst ihn mit dem Druck-Button unten als PDF speichern oder "
            "mir sagen, was angepasst werden soll (z.B. *\"mach ihn für "
            "Klasse 5 einfacher\"* oder *\"füge einen Schritt zur Sicherung "
            "hinzu\"*)."
        )
    return "\n".join(lines)
