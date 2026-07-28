"""Pure canvas Markdown post-processing — ported 1:1 from ALT
``app/services/canvas_postprocess.py``: ``_extract_h1_title`` /
``_strip_empty_sections`` / ``_strip_latex`` plus the LaTeX regexes
(``_RE_FRAC`` ...). 100 % self-contained (only ``re``). The future
``services/canvas_service`` port composes these into
``generate_canvas_content``.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_h1_title(markdown: str) -> str | None:
    """Return the text of the first H1 header, if present."""
    for line in markdown.splitlines():
        s = line.strip()
        if s.startswith("# ") and not s.startswith("## "):
            return s[2:].strip() or None
    return None


# ---------------------------------------------------------------------------
# LaTeX → plaintext fallback (safety net when the LLM ignores the prompt rule)
# ---------------------------------------------------------------------------

_RE_FRAC = re.compile(r"\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
_RE_SQRT = re.compile(r"\\sqrt\s*\{([^{}]+)\}")
_RE_CDOT = re.compile(r"\\cdot")
_RE_TIMES = re.compile(r"\\times")
_RE_DIV = re.compile(r"\\div")
_RE_PM = re.compile(r"\\pm")
# Strip surrounding $...$ or \(...\) or \[...\] pairs from inline math.
# The $-delimiters only count as inline math when the opening $ is directly
# followed by non-space and the closing $ directly preceded by non-space
# (pandoc rule). That keeps valid "$x^2$" but leaves plain-text currency like
# "5$ und 3$" (space right after the $) untouched.
_RE_MATH_DOLLAR = re.compile(r"\$(?=\S)([^$\n]{1,200}?)(?<=\S)\$")
_RE_MATH_PAREN = re.compile(r"\\\(([^\n]{1,400}?)\\\)")
_RE_MATH_BRACK = re.compile(r"\\\[([^\n]{1,400}?)\\\]")
# Standalone LaTeX wrapper in round brackets: "(\frac{a}{b})" → "a/b"
_RE_PAREN_LATEX = re.compile(r"\(\s*(\\\w+\{[^)]*?)\s*\)")


def _strip_empty_sections(md: str) -> str:
    """Drop heading lines that have no content underneath.

    The LLM sometimes ends a document with a section header like
    '## Differenzierung:' or '5. **Tipp für Lehrende:**' but no
    follow-up content. Such hanging headers look broken in the canvas.

    This pass removes:
      - markdown H2/H3 headings whose section body is empty/whitespace
      - bold-only list items ('- **Hinweis:**' / '5. **Tipp:**') with
        nothing else after
      - trailing colon-only header lines at end-of-document
    """
    if not md:
        return md
    import re as _re

    lines = md.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)

    HEAD = _re.compile(r"^(#{2,3})\s+(.+?)\s*$")
    BOLD_LIST = _re.compile(r"^\s*([-*+]|\d+\.)\s+\*\*([^*]+?):?\*\*\s*$")

    while i < n:
        line = lines[i]
        m = HEAD.match(line)
        if m:
            # Look ahead: does the following block (until next heading or EOF)
            # contain non-whitespace, non-heading content?
            j = i + 1
            has_content = False
            while j < n:
                nxt = lines[j]
                if HEAD.match(nxt):
                    break
                if nxt.strip():
                    has_content = True
                    break
                j += 1
            if has_content:
                out.append(line)
            # else: drop the heading entirely (and any blank lines in between)
            i += 1
            continue

        m2 = BOLD_LIST.match(line)
        if m2:
            # Bold-only list item: keep it when real content follows (an
            # indented sub-bullet OR a flowing-text line acting as its body);
            # drop it only as a hanging label (nothing but blanks until EOF,
            # or a new heading next).
            j = i + 1
            has_body = False
            while j < n:
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                if not HEAD.match(nxt):
                    has_body = True
                break
            if has_body:
                out.append(line)
            i += 1
            continue

        out.append(line)
        i += 1

    cleaned = "\n".join(out)
    # Collapse 3+ blank lines that may now exist
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
    # Preserve a trailing newline when the original had one (splitlines drops
    # it) or when a dropped trailing section left one behind.
    keep_nl = md.endswith("\n") or cleaned.endswith("\n")
    return cleaned.rstrip() + ("\n" if keep_nl else "")


def _strip_latex(md: str) -> str:
    """Convert common LaTeX constructs to plain readable text.

    Covers the patterns the LLM produces most frequently when it ignores the
    'no LaTeX' prompt rule. Not a full LaTeX parser — intentionally conservative.
    """
    if not md or "\\" not in md and "$" not in md:
        return md

    out = md

    # Strip math-mode wrappers first so inner \frac etc. are caught by the
    # regexes below.
    out = _RE_MATH_DOLLAR.sub(lambda m: m.group(1), out)
    out = _RE_MATH_PAREN.sub(lambda m: m.group(1), out)
    out = _RE_MATH_BRACK.sub(lambda m: m.group(1), out)

    # Normalise "(\frac{a}{b})" into "(a/b)": keep the surrounding parens (only
    # inner padding is dropped) and let the _RE_FRAC pass do the conversion.
    out = _RE_PAREN_LATEX.sub(lambda m: f"({m.group(1)})", out)

    # \frac{a}{b}  →  a/b
    def _frac(m: re.Match) -> str:
        num = m.group(1).strip()
        den = m.group(2).strip()
        # Parenthesise complex expressions
        if re.search(r"[+\-*/ ]", num):
            num = f"({num})"
        if re.search(r"[+\-*/ ]", den):
            den = f"({den})"
        return f"{num}/{den}"
    # Run twice to catch single-level nesting after the first pass.
    prev = None
    while prev != out:
        prev = out
        out = _RE_FRAC.sub(_frac, out)

    # \sqrt{x}  →  Wurzel(x)
    out = _RE_SQRT.sub(lambda m: f"Wurzel({m.group(1).strip()})", out)

    out = _RE_CDOT.sub("*", out)
    out = _RE_TIMES.sub("·", out)
    out = _RE_DIV.sub(":", out)
    out = _RE_PM.sub("±", out)

    return out
