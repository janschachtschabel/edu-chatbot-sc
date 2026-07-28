"""Charakterisierungs-Tests für die Web-Tour-State-Machine — Port von ALT
``tests/test_tour_service.py``. Das Modul zog von ``app/services/tour_service.py``
nach ``boerdi.domain.tour`` (reine Domäne, framework-frei; Regel 4).

Reine Funktionen: URL-/Marker-Helfer + cfg-getriebene Gruppen-/Entry-/Render-
Logik. ``tour`` ist rein bzgl. seines ``cfg``-Arguments → alle Verträge werden
gegen eine synthetische Mini-Config ``CFG`` gepinnt (deterministisch, ohne
YAML-Abhängigkeit).

Adaptation (dokumentiert, keine Schwächung): ALTs 4 „echte-Config"-Smoke-Tests
riefen ``load_website_tour_config()`` nur als bequeme Fixture; ihre Assertions
sind config-AGNOSTISCH (``/``→intro-Kurzschluss, Unbekannt-Schritt-Fallback-
Form, Gibberish→None). Sie sind hier gegen ``CFG`` ausgedrückt (in die
synthetischen Tests gefaltet), statt die 30-Zeilen-``seed+bind_store``-Fixture
aus ``test_config_loader_surface.py`` zu duplizieren. Die reale
``website-tour.yaml`` ↔ ``tour`` Integration bleibt über den Loader-Surface-Test
(``load_website_tour_config``→dict) und die P4-6-Golden-Tour-Flows abgedeckt.
"""

from __future__ import annotations

from boerdi.domain import tour as ts

# ── Reine URL-/Marker-Helfer (kein cfg, exakte Golden-Werte) ────────────


def test_norm_path_adds_leading_and_strips_trailing_slash():
    assert ts._norm_path("foo/") == "/foo"
    assert ts._norm_path("/foo") == "/foo"


def test_norm_path_strips_host_query_fragment():
    assert ts._norm_path("https://wp-test.example/home/?x=1#frag") == "/home"
    assert ts._norm_path("/") == "/"  # Root behält den einen Slash


def test_full_url_joins_host_and_path():
    assert ts._full_url("https://wlo.de", "/x") == "https://wlo.de/x"


def test_md_link_format():
    assert ts._md_link("Label", "https://wlo.de", "/x") == "[Label](https://wlo.de/x)"


def test_nav_qr_uses_guide_marker_format():
    # ``__guide__|Label|URL`` — das Marker-Format, das der Guide-QR-Injector erwartet.
    assert ts._nav_qr("Weiter", "https://wlo.de", "/x") == "__guide__|Weiter|https://wlo.de/x"


# ── Synthetische Mini-Config: exakte Branch-Werte ohne YAML-Abhängigkeit ──
CFG = {
    "base_host": "https://wlo.de",
    "home_path": "/home/",
    "content_hub": "/bildungsinhalte/",
    "contact_hub": "/mitmachen/",
    "intro": "Willkommen!",
    "nudge": "Falsche Seite.",
    "explore": "Stöber ruhig.",
    "entry": {"solutions": "Hallo {group}!"},
    "steps": {
        "intro": {"nav_label": "Zur Startseite"},
        "group": {"text": "Wer bist du?", "unsure_text": "Kein Stress.",
                  "unsure_label": "Weiß nicht"},
        "group_page": {"text": "Seite für {group}", "nav_label": "Zur {group}-Seite"},
        "content": {"text": "Inhalte", "nav_label": "Zu den Inhalten"},
        "solutions": {"text": "Lösungen für {group}", "angebote_label": "Für dich",
                      "sublinks_label": "Stöbern", "nav_label": "Weiter"},
        "contact": {"text": "Mach mit", "links_label": "Weiter"},
    },
    "groups": [
        {"id": "lehrer", "label": "Lehrkräfte", "synonyms": ["lehrer", "unterricht"],
         "page": "/fuer-lehrkraefte/", "angebote": [{"label": "Material", "path": "/material/"}]},
        {"id": "schueler", "label": "Schülerinnen", "synonyms": ["schüler"],
         "page": "/fuer-schueler/", "angebote": []},
    ],
    "content_sublinks": [{"label": "Fächer", "path": "/faecher/"}],
    "contact_links": [{"label": "Kontakt", "path": "/kontakt/"}],
}


def test_match_group_matches_label_synonym_and_rejects_gibberish():
    assert ts.match_group("Lehrkräfte", CFG)["id"] == "lehrer"       # exakt = label
    assert ts.match_group("ich bin lehrer", CFG)["id"] == "lehrer"   # Synonym als Teilstring
    assert ts.match_group("", CFG) is None
    # (gefaltet aus ALTs echte-Config-Smoke) Gibberish trifft keine Gruppe.
    assert ts.match_group("völlig zusammenhangloser text ohne trigger", CFG) is None


def test_detect_entry_all_branches():
    assert ts.detect_entry("/", CFG) == ("intro", "")                # Root-Kurzschluss
    assert ts.detect_entry("/home/", CFG) == ("group", "")           # A
    assert ts.detect_entry("/fuer-lehrkraefte/", CFG) == ("solutions", "lehrer")  # B1
    assert ts.detect_entry("/material/", CFG) == ("solutions", "lehrer")          # C1 Rückwärts
    assert ts.detect_entry("/mitmachen/", CFG) == ("contact", "")    # D1
    assert ts.detect_entry("/mitmachen/anfrage", CFG) == ("contact", "")  # D2 Unterseite
    assert ts.detect_entry("/random/page", CFG) == ("intro", "")     # Fallback
    # (gefaltet) Rückgabe ist immer ein (str, str)-Tupel.
    entry, gid = ts.detect_entry("/irgendeine/seite", CFG)
    assert isinstance(entry, str) and isinstance(gid, str)


def test_expected_per_step():
    assert ts.expected("intro", "", CFG) == ("/home", [], "group")
    assert ts.expected("group", "", CFG) == (None, ["/home"], "group_page")
    assert ts.expected("group_page", "lehrer", CFG) == ("/fuer-lehrkraefte", [], "content")
    assert ts.expected("content", "", CFG) == ("/bildungsinhalte", [], "solutions")
    adv, expl, nxt = ts.expected("solutions", "lehrer", CFG)
    assert adv == "/mitmachen" and nxt == "contact"
    assert set(expl) == {"/material", "/faecher", "/fuer-lehrkraefte"}
    assert ts.expected("bogus", "", CFG) == (None, [], None)


def test_render_returns_text_qr_final_shape():
    # (gefaltet aus ALTs echte-Config-Smoke) Der Render-Vertrag: 3 Keys mit Typen.
    r = ts.render("group", CFG)
    assert set(r.keys()) == {"text", "quick_replies", "final"}
    assert isinstance(r["text"], str)
    assert isinstance(r["quick_replies"], list)
    assert isinstance(r["final"], bool)


def test_render_group_lists_all_group_labels_and_unsure():
    r = ts.render("group", CFG)
    assert r["text"] == "Wer bist du?"
    assert "Lehrkräfte" in r["quick_replies"] and "Schülerinnen" in r["quick_replies"]
    assert "Weiß nicht" in r["quick_replies"]
    # unsure prependet den Zusatztext.
    assert ts.render("group", CFG, kind="unsure")["text"].startswith("Kein Stress.")


def test_render_nudge_and_explore_use_cfg_text_plus_nav():
    nudge = ts.render("content", CFG, "lehrer", kind="nudge")
    assert nudge["text"] == "Falsche Seite." and nudge["final"] is False
    assert nudge["quick_replies"][0].startswith(ts.GUIDE_QR_PREFIX)
    explore = ts.render("solutions", CFG, "lehrer", kind="explore")
    assert explore["text"] == "Stöber ruhig."


def test_render_entry_solutions_greets_group_and_lists_angebote():
    r = ts.render("solutions", CFG, "lehrer", kind="entry")
    assert "Hallo Lehrkräfte!" in r["text"]               # {group} ersetzt
    assert "[Material](https://wlo.de/material/)" in r["text"]


def test_render_solutions_normal_has_sublinks_and_angebote():
    r = ts.render("solutions", CFG, "lehrer")
    assert "Lösungen für Lehrkräfte" in r["text"]
    assert "[Fächer](https://wlo.de/faecher/)" in r["text"]
    assert "[Material](https://wlo.de/material/)" in r["text"]
    assert r["quick_replies"][0].startswith(ts.GUIDE_QR_PREFIX)


def test_render_contact_is_final_without_quick_replies():
    r = ts.render("contact", CFG)
    assert r["final"] is True
    assert r["quick_replies"] == []
    assert "[Kontakt](https://wlo.de/kontakt/)" in r["text"]


def test_render_group_page_and_content_fill_group_and_nav():
    gp = ts.render("group_page", CFG, "lehrer")
    assert gp["text"] == "Seite für Lehrkräfte"
    assert gp["quick_replies"][0] == "__guide__|Zur Lehrkräfte-Seite|https://wlo.de/fuer-lehrkraefte/"
    content = ts.render("content", CFG)
    assert content["text"] == "Inhalte"
    assert content["quick_replies"][0] == "__guide__|Zu den Inhalten|https://wlo.de/bildungsinhalte/"


def test_render_unknown_step_falls_back_to_intro():
    # (gefaltet aus ALTs render("S1", cfg)-Smoke) Unbekannter Schritt → Intro-Fallback.
    r = ts.render("S1", CFG)
    assert r["text"] == "Willkommen!"
    assert r["final"] is False
