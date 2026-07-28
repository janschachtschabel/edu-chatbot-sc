"""Behaviour pins for ``domain/url_helpers`` (whole-module verbatim port of ALT
``chat_url_helpers.py``): the two stateless, offline URL helpers that run after the
bot answer is produced.

``_extract_web_links_from_text`` pulls markdown/HTML links out of the answer text
into a structured ``web_links`` box, stripping them from the prose, while excluding
links that already belong to a card or point at a single material (video/PDF/
edu-sharing render path). ``_rewrite_external_urls_to_repo`` swaps external provider
URLs for their repo render URL in guide mode.

Pure string/regex/urlparse logic — no boundaries to mock. The pins nail each
function's branches; expected values are traced against the ALT source.
"""

from __future__ import annotations

from boerdi.domain import url_helpers as uh


# ── _extract_web_links_from_text ────────────────────────────────
def test_fast_path_returns_text_unchanged_when_no_link_pattern():
    text = "Das ist einfacher Text ohne Links."
    cleaned, links = uh._extract_web_links_from_text(text)
    assert cleaned == text
    assert links == []


def test_empty_and_none_text_yield_empty_box():
    assert uh._extract_web_links_from_text("") == ("", [])
    assert uh._extract_web_links_from_text(None) == ("", [])


def test_inline_markdown_link_promoted_and_replaced_by_label():
    text = "Schau dir [Bruchrechnung](https://example.org/bruch) an."
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == [{"title": "Bruchrechnung", "url": "https://example.org/bruch"}]
    assert "https://example.org/bruch" not in cleaned
    assert "Bruchrechnung" in cleaned


def test_bullet_markdown_link_line_removed_and_promoted():
    text = "Hier:\n- [Titel](https://example.org/x)\nEnde"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == [{"title": "Titel", "url": "https://example.org/x"}]
    assert "https://example.org/x" not in cleaned
    assert "- [Titel]" not in cleaned
    assert "Hier:" in cleaned and "Ende" in cleaned


def test_inline_html_anchor_promoted_and_replaced_by_label():
    text = 'Siehe <a href="https://example.org/page">Seite</a> dort'
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == [{"title": "Seite", "url": "https://example.org/page"}]
    assert "Seite" in cleaned
    assert "<a" not in cleaned


def test_card_url_stripped_from_text_but_excluded_from_box():
    text = "Mehr: [Sammlung](https://repo.example/coll/1)"
    cards = [{"link": "https://repo.example/coll/1"}]
    cleaned, links = uh._extract_web_links_from_text(text, cards=cards)
    assert links == []
    assert "https://repo.example/coll/1" not in cleaned
    assert "Sammlung" in cleaned


def test_card_url_from_object_card_is_excluded():
    card = type("Card", (), {"link": "https://repo.example/c/9"})()
    text = "X [Y](https://repo.example/c/9)"
    cleaned, links = uh._extract_web_links_from_text(text, cards=[card])
    assert links == []
    assert "Y" in cleaned


def test_material_video_url_excluded_from_box():
    text = "Guck [hier](https://www.youtube.com/watch?v=abc123)"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == []
    assert "youtube.com" not in cleaned
    assert "hier" in cleaned


def test_material_file_extension_url_excluded_from_box():
    text = "Doc [PDF](https://example.org/file.pdf)"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == []
    assert "file.pdf" not in cleaned


def test_material_edu_sharing_render_path_excluded_from_box():
    text = "[X](https://server/edu-sharing/components/render/abc)"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == []


def test_max_links_caps_the_box_but_all_urls_are_stripped():
    text = "\n".join(f"- [L{i}](https://example.org/{i})" for i in range(7))
    cleaned, links = uh._extract_web_links_from_text(text, max_links=3)
    assert len(links) == 3
    assert links[0] == {"title": "L0", "url": "https://example.org/0"}
    for i in range(7):
        assert f"https://example.org/{i}" not in cleaned


def test_duplicate_url_recorded_once_keeps_first_label():
    text = "[A](https://example.org/x) und [B](https://example.org/x)"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == [{"title": "A", "url": "https://example.org/x"}]
    assert "A" in cleaned and "B" in cleaned


def test_keep_bullet_labels_keeps_the_line_and_replaces_link_with_label():
    text = "- Material: [Titel](https://example.org/m)"
    cleaned, links = uh._extract_web_links_from_text(text, keep_bullet_labels=True)
    assert links == [{"title": "Titel", "url": "https://example.org/m"}]
    assert "- Material: Titel" in cleaned
    assert "https://example.org/m" not in cleaned


def test_bullet_removal_collapses_triple_blank_and_strips():
    text = "- [A](https://example.org/a)\n\n\n\nUnten"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == [{"title": "A", "url": "https://example.org/a"}]
    assert cleaned == "Unten"


def test_empty_label_is_not_recorded():
    # ``[](url)`` has no label → inline regex needs >=1 char in ``[...]``; the
    # link is left untouched and nothing is boxed.
    text = "Text [](https://example.org/nolabel) mehr"
    cleaned, links = uh._extract_web_links_from_text(text)
    assert links == []


# ── _rewrite_external_urls_to_repo ──────────────────────────────
def test_rewrite_noop_when_guide_mode_off():
    text = "Link https://youtube.com/x hier"
    cards = [{"url": "https://youtube.com/x", "link": "https://repo/y"}]
    assert uh._rewrite_external_urls_to_repo(text, cards, guide_mode=False) == text


def test_rewrite_empty_text_returns_empty_string():
    assert uh._rewrite_external_urls_to_repo("", [{"url": "a", "link": "b"}], True) == ""


def test_rewrite_empty_cards_returns_text():
    assert uh._rewrite_external_urls_to_repo("hi", [], True) == "hi"


def test_rewrite_dict_card_external_to_repo():
    text = "Guck https://youtube.com/watch?v=z hier"
    cards = [{"url": "https://youtube.com/watch?v=z", "link": "https://repo.example/render/1"}]
    out = uh._rewrite_external_urls_to_repo(text, cards, guide_mode=True)
    assert out == "Guck https://repo.example/render/1 hier"


def test_rewrite_object_card_external_to_repo():
    card = type("Card", (), {"url": "https://vimeo.com/1", "link": "https://repo/v"})()
    text = "See https://vimeo.com/1 now"
    out = uh._rewrite_external_urls_to_repo(text, [card], guide_mode=True)
    assert out == "See https://repo/v now"


def test_rewrite_falls_back_to_www_variant():
    # card ext carries ``www.``; the text uses the bare host → the www-stripped
    # variant must still be rewritten.
    text = "Guck https://youtube.com/x hier"
    cards = [{"url": "https://www.youtube.com/x", "link": "https://repo.example/r"}]
    out = uh._rewrite_external_urls_to_repo(text, cards, guide_mode=True)
    assert out == "Guck https://repo.example/r hier"


def test_rewrite_uses_wlo_url_when_link_absent():
    text = "a https://ext.org/x b"
    cards = [{"url": "https://ext.org/x", "wlo_url": "https://repo/w"}]
    out = uh._rewrite_external_urls_to_repo(text, cards, guide_mode=True)
    assert out == "a https://repo/w b"


def test_rewrite_noop_when_external_equals_repo():
    text = "x https://same.org/a y"
    cards = [{"url": "https://same.org/a", "link": "https://same.org/a"}]
    assert uh._rewrite_external_urls_to_repo(text, cards, guide_mode=True) == text
