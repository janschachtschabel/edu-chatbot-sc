"""Characterization tests for domain/canvas/postprocess.py (P4-5 canvas leaf).

ALT origin: ``app/services/canvas_postprocess.py`` — the three pure Markdown
post-processing helpers used by ``generate_canvas_content``:
``_extract_h1_title`` / ``_strip_empty_sections`` / ``_strip_latex`` plus the
LaTeX regex constants. 100 % self-contained (only ``re``). Logic fidelity is
proven by the AST-diff gate against the ALT module; these pin the observable
behaviour (H1 extraction, hanging-section removal, LaTeX→plaintext).
"""

from boerdi.domain.canvas.postprocess import (
    _extract_h1_title,
    _strip_empty_sections,
    _strip_latex,
)


class TestExtractH1Title:
    def test_returns_first_h1_text(self):
        assert _extract_h1_title("# Photosynthese\n\nText") == "Photosynthese"

    def test_ignores_h2(self):
        assert _extract_h1_title("## Unterabschnitt\nText") is None

    def test_none_when_no_h1(self):
        assert _extract_h1_title("Nur Fließtext ohne Überschrift") is None

    def test_first_h1_wins_over_later(self):
        assert _extract_h1_title("Intro\n# Erste\n# Zweite") == "Erste"

    def test_empty_h1_returns_none(self):
        # "# " with nothing after → s[2:].strip() falsy → `or None`
        assert _extract_h1_title("# \nText") is None


class TestStripEmptySections:
    def test_empty_input_unchanged(self):
        assert _strip_empty_sections("") == ""

    def test_drops_hanging_h2_heading_at_eof(self):
        md = "## Inhalt\n\nEcht was hier.\n\n## Differenzierung:\n"
        out = _strip_empty_sections(md)
        assert "## Differenzierung:" not in out
        assert "## Inhalt" in out
        assert "Echt was hier." in out

    def test_keeps_heading_with_content(self):
        md = "## Aufgabe\n\nLöse die Gleichung.\n"
        assert "## Aufgabe" in _strip_empty_sections(md)

    def test_drops_bold_only_hanging_list_item(self):
        md = "- Erster echter Punkt\n- **Tipp für Lehrende:**\n"
        out = _strip_empty_sections(md)
        assert "**Tipp für Lehrende:**" not in out
        assert "Erster echter Punkt" in out

    def test_keeps_bold_list_item_with_body(self):
        md = "- **Hinweis:**\n  Erklärender Unterpunkt folgt.\n"
        out = _strip_empty_sections(md)
        assert "**Hinweis:**" in out

    def test_collapses_triple_blank_lines(self):
        md = "A\n\n\n\nB\n"
        assert "\n\n\n" not in _strip_empty_sections(md)

    def test_preserves_trailing_newline(self):
        assert _strip_empty_sections("Text\n").endswith("\n")


class TestStripLatex:
    def test_no_latex_returned_unchanged(self):
        s = "Ganz normaler Text ohne Mathe."
        assert _strip_latex(s) is s  # early-return identity

    def test_frac_simple(self):
        assert _strip_latex(r"\frac{1}{2}") == "1/2"

    def test_frac_complex_parenthesised(self):
        assert _strip_latex(r"\frac{a+1}{b}") == "(a+1)/b"

    def test_sqrt(self):
        assert _strip_latex(r"\sqrt{2}") == "Wurzel(2)"

    def test_operators(self):
        assert _strip_latex(r"3\cdot4") == "3*4"
        assert _strip_latex(r"3\times4") == "3·4"
        assert _strip_latex(r"6\div2") == "6:2"
        assert _strip_latex(r"a\pm b") == "a± b"

    def test_inline_dollar_math_stripped(self):
        assert _strip_latex("Formel $x^2$ hier") == "Formel x^2 hier"

    def test_currency_dollar_untouched(self):
        # space right after $ → pandoc rule → not inline math
        assert _strip_latex("Das kostet 5$ und 3$ zusammen") == \
            "Das kostet 5$ und 3$ zusammen"
