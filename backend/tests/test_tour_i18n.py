"""domain.tour_i18n — Webseiten-Tour in der Sprache des Zuges (C1-g2d).

Die Wahl passiert EINMAL an der Knoten-Grenze, nicht an den ~15 Lesestellen in
``domain/tour``: die Zustandsmaschine ist ein 1:1-Port und soll es bleiben.
Getestet wird deshalb genau diese Umformung — plus die zwei Eigenschaften, die
sie nicht kaputt machen darf: deutsche Züge bleiben unverändert, und das
Gruppen-Matching greift weiter auf deutschen Text.
"""

from __future__ import annotations

from boerdi.domain import tour as tour_domain
from boerdi.domain.tour_i18n import localize

_CFG = {
    "enabled": True,
    "base_host": "https://wlo.test",
    "home_path": "/home/",
    "contact_hub": "/mitmachen/",
    "start_label": "Web-Tour starten",
    "trigger_phrases": ["web-tour", "start the tour"],
    "intro": "Willkommen zur Tour!",
    "intro_en": "Welcome to the tour!",
    "nudge": "Du bist woanders.",
    "nudge_en": "You are somewhere else.",
    "explore": "Schau dich um.",
    "explore_en": "",
    "entry": {"solutions": "Mitten drin, {group}!", "solutions_en": "Right in it, {group}!"},
    "groups": [
        {
            "id": "lehrkraft",
            "label": "Lehrkraft",
            "label_en": "Teacher",
            "synonyms": ["lehrkraft", "unterrichte"],
            "page": "/home/oer-community/",
            "angebote": [
                {"label": "Fachportale", "label_en": "Subject portals", "path": "/fachportale/"},
                {"label": "Nur Deutsch", "path": "/nur-deutsch/"},
            ],
        },
    ],
    "content_sublinks": [
        {"label": "Was ist OER?", "label_en": "What is OER?", "path": "/bildungsinhalte/oer/"},
    ],
    "contact_links": [{"label": "FAQ", "label_en": "FAQ", "path": "/mitmachen/faq/"}],
    "steps": {
        "intro": {"nav_label": "Zur Startseite", "nav_label_en": "To the home page"},
        "group": {
            "text": "Als was bist du unterwegs?",
            "text_en": "What brings you here?",
            "unsure_label": "Bin mir nicht sicher",
            "unsure_label_en": "Not sure",
        },
        "solutions": {
            "text": "Lösungen für {group}",
            "text_en": "Solutions for {group}",
            "angebote_label": "Für {group} relevant",
            "angebote_label_en": "Relevant for {group}",
            "nav_label": "Weiter zur Anfrage",
            "nav_label_en": "On to the enquiry",
        },
    },
}


def test_german_turn_returns_the_config_unchanged():
    """Der deutsche Weg darf kein Byte kosten — und auch keine Kopie."""
    assert localize(_CFG, "de") is _CFG


def test_english_turn_picks_the_maintained_english_texts():
    cfg = localize(_CFG, "en")

    assert cfg["intro"] == "Welcome to the tour!"
    assert cfg["nudge"] == "You are somewhere else."
    assert cfg["entry"]["solutions"] == "Right in it, {group}!"
    assert cfg["steps"]["intro"]["nav_label"] == "To the home page"
    assert cfg["steps"]["group"]["unsure_label"] == "Not sure"
    assert cfg["steps"]["solutions"]["angebote_label"] == "Relevant for {group}"
    assert cfg["groups"][0]["label"] == "Teacher"
    assert cfg["groups"][0]["angebote"][0]["label"] == "Subject portals"
    assert cfg["content_sublinks"][0]["label"] == "What is OER?"
    assert cfg["contact_links"][0]["label"] == "FAQ"


def test_unmaintained_english_falls_back_to_german_per_key():
    """Leer heißt „nicht gepflegt" — nie „leerer Text"."""
    cfg = localize(_CFG, "en")

    assert cfg["explore"] == "Schau dich um."                     # explore_en ist leer
    assert cfg["groups"][0]["angebote"][1]["label"] == "Nur Deutsch"  # gar kein label_en


def test_paths_and_ids_survive_the_localization():
    """Der Ankunfts-Vergleich läuft über Pfade — die dürfen sich nie ändern."""
    cfg = localize(_CFG, "en")

    assert cfg["base_host"] == "https://wlo.test"
    assert cfg["home_path"] == "/home/"
    assert cfg["groups"][0]["id"] == "lehrkraft"
    assert cfg["groups"][0]["page"] == "/home/oer-community/"
    assert cfg["groups"][0]["angebote"][0]["path"] == "/fachportale/"
    assert cfg["content_sublinks"][0]["path"] == "/bildungsinhalte/oer/"
    assert tour_domain.detect_entry("/home/", cfg) == ("group", "")
    assert tour_domain.detect_entry("/fachportale/", cfg) == ("solutions", "lehrkraft")


def test_the_original_config_is_not_mutated():
    """Der Prozess-Cache liefert dieselbe Instanz an jeden Zug."""
    localize(_CFG, "en")

    assert _CFG["intro"] == "Willkommen zur Tour!"
    assert _CFG["groups"][0]["label"] == "Lehrkraft"
    assert _CFG["groups"][0]["angebote"][0]["label"] == "Fachportale"


def test_group_matching_answers_to_both_languages():
    """Die Synonyme bleiben deutsch — deshalb ist das Matching eine VEREINIGUNG.

    Der englische Chip trägt die englische Beschriftung und muss treffen; wer
    trotzdem deutsch tippt, trifft weiterhin über die (unübersetzten) Synonyme.
    """
    cfg = localize(_CFG, "en")

    assert (tour_domain.match_group("Teacher", cfg) or {}).get("id") == "lehrkraft"
    assert (tour_domain.match_group("Lehrkraft", cfg) or {}).get("id") == "lehrkraft"


def test_render_produces_an_english_step_end_to_end():
    cfg = localize(_CFG, "en")
    out = tour_domain.render("solutions", cfg, "lehrkraft")

    assert "Solutions for Teacher" in out["text"]
    assert "**Relevant for Teacher:**" in out["text"]
    assert "[Subject portals](https://wlo.test/fachportale/)" in out["text"]
    assert out["quick_replies"] == [
        "__guide__|On to the enquiry|https://wlo.test/mitmachen/"
    ]
