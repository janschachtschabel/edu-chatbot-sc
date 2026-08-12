"""Characterization tests for domain/completion_messages.py (P4-5 canvas leaf).

ALT origin: ``app/routers/chat_completion_messages.py`` — the stateless, offline
chat-bubble builders for created materials: ``_extract_headings`` (shared) +
``_canvas_completion_message`` (Canvas-Create fast-path) + ``_lp_completion_message``
(LP direct action). ALT tested ``_extract_headings`` directly (test_chat_inline_docs.py)
and the canvas bubble via the pipeline; here the extractor tests are ported 1:1 and
the two bubble builders get direct characterization. Logic fidelity is proven by the
AST-diff gate.
"""

from boerdi.domain.completion_messages import (
    _canvas_completion_message,
    _extract_headings,
    _lp_completion_message,
)


# ── _extract_headings (ported 1:1 from ALT test_chat_inline_docs.py) ──────
class TestExtractHeadings:
    def test_h2_headings_topic_echo_and_meta_filtered(self):
        md = ("# Photosynthese\n## Photosynthese\n## Grundlagen\n"
              "## Ablauf\n## Lösungen\n")
        assert _extract_headings(md, "Photosynthese") == ["Grundlagen", "Ablauf"]

    def test_falls_back_to_h3_when_few_h2(self):
        md = "## Einführung\n### Teil A\n### Teil B\n"
        assert _extract_headings(md, "X") == ["Einführung", "Teil A", "Teil B"]

    def test_bullet_bold_fallback(self):
        md = "- **Hauptast 1** Beschreibung\n- **Hauptast 2**\n"
        assert _extract_headings(md, "X") == ["Hauptast 1", "Hauptast 2"]

    def test_meta_only_falls_back_to_meta(self):
        md = "## Lösungen\n## Hinweise\n"
        assert _extract_headings(md, "X") == ["Lösungen", "Hinweise"]

    def test_capped_at_six(self):
        md = "\n".join(f"## Abschnitt {i}" for i in range(1, 9))
        out = _extract_headings(md, "X")
        assert len(out) == 6
        assert out[0] == "Abschnitt 1"
        assert out[-1] == "Abschnitt 6"

    def test_empty_markdown(self):
        assert _extract_headings("", "X") == []
        assert _extract_headings(None, "X") == []

    def test_markdown_syntax_stripped_from_heading(self):
        md = "## **Fett** \n## `Code`\n"
        assert _extract_headings(md, "X") == ["Fett", "Code"]

    def test_single_h2_kept(self):
        md = "# Titel\n## Abschnitt\nText"
        assert _extract_headings(md, "Titel") == ["Abschnitt"]


# ── _canvas_completion_message ───────────────────────────────────────────
class TestCanvasCompletionMessage:
    def test_duzen_lead_default(self):
        out = _canvas_completion_message("Infoblatt", "Wasser", "## A\nText\n## B\nText")
        assert out.startswith(
            "Ich habe dir ein **Infoblatt** zum Thema *Wasser* erstellt.")

    def test_siezen_lead(self):
        out = _canvas_completion_message(
            "Infoblatt", "Wasser", "## A\nText", formality="siezen")
        assert out.startswith(
            "Ich habe Ihnen ein **Infoblatt** zum Thema *Wasser* erstellt.")

    def test_sections_listed(self):
        md = "## Grundlagen\nText\n## Ablauf\nText"
        out = _canvas_completion_message("Infoblatt", "X", md)
        assert "Abschnitte:" in out
        assert "1. **Grundlagen**" in out
        assert "2. **Ablauf**" in out

    def test_task_count_for_arbeitsblatt(self):
        # Only a meta heading (Lösungen) → the extractor returns meta-only, so the
        # builder falls back to counting the numbered tasks instead of listing
        # sections; the trailing "1." under ## Lösungen restarts numbering → stops.
        md = ("Ein Arbeitsblatt zu Brüchen.\n\n"
              "1. Erste Aufgabe\n2. Zweite Aufgabe\n3. Dritte Aufgabe\n\n"
              "## Lösungen\n1. Lösung eins\n")
        out = _canvas_completion_message("Arbeitsblatt", "Brüche", md)
        assert "Enthält **3 Aufgaben**" in out

    def test_canvas_enabled_intro(self):
        out = _canvas_completion_message("Infoblatt", "X", "## A\nText", canvas_enabled=True)
        assert "rechts im Canvas" in out

    def test_inline_intro_when_canvas_disabled(self):
        out = _canvas_completion_message("Infoblatt", "X", "## A\nText", canvas_enabled=False)
        assert "direkt unter dieser Nachricht" in out
        assert "Druck-Button" in out

    def test_siezen_inline_intro(self):
        out = _canvas_completion_message(
            "Infoblatt", "X", "## A\nText", canvas_enabled=False, formality="sie")
        assert "Sie können" in out


# ── _lp_completion_message ───────────────────────────────────────────────
class TestLpCompletionMessage:
    def test_canvas_lead_and_phases(self):
        md = "## Phase 1\nText\n## Phase 2\nText"
        out = _lp_completion_message("Bruchrechnung", md, canvas_enabled=True)
        assert out.startswith("Ich habe dir den **Lernpfad zu *Bruchrechnung***")
        assert "im Canvas rechts aufgebaut" in out
        assert "Er ist in diese Phasen gegliedert:" in out
        assert "1. **Phase 1**" in out

    def test_inline_lead_when_canvas_disabled(self):
        out = _lp_completion_message("X", "## Phase 1\nT\n## Phase 2\nT", canvas_enabled=False)
        assert "direkt unter dieser\nNachricht aufgebaut" in out or \
            "direkt unter dieser" in out
        assert "Druck-Button" in out

    def test_no_phases_no_section_block(self):
        out = _lp_completion_message("X", "nur fließtext ohne headings")
        assert "gegliedert" not in out


# ── C1-f2b2: Sprache der Blasen + der Meta-Filter ─────────────────────────
class TestEnglishBubbles:
    def test_canvas_bubble_english(self):
        out = _canvas_completion_message(
            "Worksheet", "Water", "## Basics\nText\n## Steps\nText", lang="en")
        assert out.startswith("I have created a **Worksheet** on *Water* for you.")
        assert "Sections:" in out
        assert "1. **Basics**" in out
        assert "canvas on the right" in out

    def test_canvas_bubble_english_ignores_formality(self):
        """Englisch kennt kein Sie — beide Höflichkeitsformen liefern denselben
        Satz. Die Schlüssel bleiben trotzdem getrennt, damit der Aufrufer nicht
        sprachabhängig verzweigen muss."""
        du = _canvas_completion_message("Worksheet", "X", "## A\nT", lang="en")
        sie = _canvas_completion_message(
            "Worksheet", "X", "## A\nT", formality="siezen", lang="en")
        assert du == sie

    def test_canvas_inline_outro_english(self):
        out = _canvas_completion_message(
            "Worksheet", "X", "## A\nT", canvas_enabled=False, lang="en")
        assert "right below this message" in out
        assert "print button" in out

    def test_canvas_task_count_english(self):
        md = ("A worksheet on fractions.\n\n"
              "1. First task\n2. Second task\n3. Third task\n\n"
              "## Solutions\n1. Solution one\n")
        out = _canvas_completion_message("Worksheet", "Fractions", md, lang="en")
        assert "Contains **3 exercises**" in out

    def test_lp_bubble_english(self):
        out = _lp_completion_message(
            "Fractions", "## Phase 1\nT\n## Phase 2\nT", lang="en")
        assert out.startswith("I have built the **learning path on *Fractions***")
        assert "It is structured into these phases:" in out
        assert "1. **Phase 1**" in out


class TestExtractHeadingsLanguage:
    def test_english_meta_headings_filtered(self):
        """Der Meta-Filter liest unser EIGENES Markdown. Seit C1-f2a ist das
        bei ``lang='en'`` englisch — mit den deutschen Mustern rutschte
        „Solutions" als einziger sichtbarer Abschnitt in die Vorschau."""
        md = "## Introduction\n## Basics\n## Solutions\n## Further reading\n"
        assert _extract_headings(md, "X", lang="en") == ["Introduction", "Basics"]

    def test_english_meta_only_falls_back_to_meta(self):
        md = "## Solutions\n## Notes\n"
        assert _extract_headings(md, "X", lang="en") == ["Solutions", "Notes"]

    def test_german_patterns_untouched_by_default(self):
        md = "## Grundlagen\n## Lösungen\n"
        assert _extract_headings(md, "X") == ["Grundlagen"]
