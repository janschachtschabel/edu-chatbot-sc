"""Der Kontext-Simulator der Demo-Seiten (2026-08-13).

Der Nutzer wollte „eine Möglichkeit der Übergabe eines Triggers, um zu
simulieren, dass ich auf einer Sammlung, Themenseite, Einzelinhalt, Suche oder
sonstigen URL stehe". Die Wahl reist im Query-String und wird SERVERSEITIG ins
Element geschrieben — also ist sie eine Eingabe von aussen, die in HTML landet.
Die Prüfung am Rand ist deshalb kein Zierrat, und dieser Test ist ihr Beleg.
"""

from __future__ import annotations

import json
import re

import pytest

from boerdi.api import widget_demo_context as ctx

UUID = "aa0ecc77-1111-2222-3333-444455556666"


# ── Was die Auswahl überhaupt anbieten darf ──────────────────────────────


def test_every_kind_maps_onto_a_field_the_backend_reads():
    # Die Schlüssel stammen aus `services/page_context.py` (Kopf-Docstring) bzw.
    # dem Detektor (`page-context-detector.ts`, DetectedContext). Ein Feld, das
    # dort nicht vorkommt, käme im Backend nie an — die Simulation liefe ins
    # Leere, und zwar lautlos.
    bekannt = {
        "topic_page_slug", "collection_id", "node_id", "search_query", "page_url",
    }
    assert {k.field for k in ctx.KINDS} == bekannt


def test_page_kinds_are_the_ones_the_backend_classifies():
    # `page_kind` aus DetectedContext: topic | collection | content | subject |
    # search | other. `subject` fehlt bewusst — ein Fachportal löst weder
    # Begrüssung noch Kontext-Aktionen aus (dieselbe Begründung wie in
    # `studio/views/preview-embed.ts`), es anzubieten verspräche eine Wirkung.
    assert {k.page_kind for k in ctx.KINDS} == {
        "topic", "collection", "content", "search", "other",
    }


# ── Prüfung am Rand ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("kind", "wert"),
    [
        ("collection", UUID),
        ("content", UUID),
        ("topic", "eiszeit"),
        ("search", "Dreiecke berechnen"),
        ("url", "https://beispiel.de/seite"),
    ],
)
def test_a_valid_value_becomes_a_page_context(kind, wert):
    gebaut = ctx.build_context(kind, wert)
    assert gebaut and gebaut["page_kind"]
    # Herkunft mitgeschickt, damit Demo-Sitzungen in den Auswertungen
    # unterscheidbar bleiben — der Detektor schreibt dort `url:/themenseite`.
    assert gebaut["detection_source"].startswith("demo:")


@pytest.mark.parametrize(
    ("kind", "wert"),
    [
        ("collection", "keine-uuid"),
        ("content", "12345"),
        ("topic", "Kein Slug mit Leerzeichen"),
        ("topic", "a"),                      # zu kurz
        ("search", "x"),                     # zu kurz
        ("search", "y" * 500),               # über dem Deckel
        ("url", "javascript:alert(1)"),      # kein http(s)
        ("url", "ftp://beispiel.de"),
        ("url", "https://beispiel.de/" + "p" * 3000),
        ("unbekannt", UUID),                 # kein solcher Typ
        ("collection", ""),                  # leer
        ("", UUID),                          # kein Typ gewählt
    ],
)
def test_an_invalid_value_yields_no_context_at_all(kind, wert):
    # Kein halber Kontext: ein `page_kind` ohne auflösbare ID liesse das Backend
    # nichts finden, die Begrüssung bliebe aus, und die Seite sähe aus, als sei
    # die Konfiguration kaputt.
    assert ctx.build_context(kind, wert) is None
    assert ctx.element_attributes(kind, wert) == {}


def test_a_url_context_carries_the_host_as_well():
    # Das Backend entscheidet „eigene Seite oder fremde" am Hostnamen
    # (DetectedContext.page_host). Ohne ihn wäre „ich stehe auf einer fremden
    # Adresse" genau die Simulation, die nicht funktioniert.
    gebaut = ctx.build_context("url", "https://fremde.example.org/a/b?c=d")
    assert gebaut == {
        "page_kind": "other",
        "page_url": "https://fremde.example.org/a/b?c=d",
        "page_host": "fremde.example.org",
        "detection_source": ctx.DETECTION_SOURCE,
    }


# ── Was am Element landet ────────────────────────────────────────────────


def test_the_element_gets_the_context_and_the_detector_switched_off():
    attrs = ctx.element_attributes("collection", UUID)
    # `auto-context="false"` aus demselben Grund wie in der Studio-Vorschau:
    # sonst trüge der Detektor `page_url`/`page_host` der DEMO-Seite bei, und
    # das Backend entschiede „eigene Seite oder fremde" gegen eine Adresse, die
    # mit dem simulierten Typ nichts zu tun hat.
    assert attrs["auto-context"] == "false"
    # Roh, nicht maskiert: maskiert wird in `widget_demo_html._element`, und die
    # Zusicherung dazu steht dort, wo das Attribut entsteht
    # (`test_widget_router.test_a_hostile_query_value_cannot_break_out_…`).
    assert json.loads(attrs["page-context"]) == {
        "page_kind": "collection",
        "collection_id": UUID,
        "detection_source": ctx.DETECTION_SOURCE,
    }


# ── Das Bedienfeld ───────────────────────────────────────────────────────


def test_the_panel_offers_every_kind_and_preselects_the_current_one():
    html = ctx.panel("topic", "eiszeit")
    for kind in ctx.KINDS:
        assert f'value="{kind.id}"' in html
    assert '<option value="topic" selected>' in html
    assert 'value="eiszeit"' in html


def test_the_panel_escapes_a_rejected_value_it_shows_back():
    # Ein abgelehnter Wert bleibt im Feld stehen (sonst tippt man ihn neu) —
    # also geht er durch die Maskierung, obwohl er die Prüfung nicht bestand.
    html = ctx.panel("topic", '"><script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


@pytest.mark.parametrize("kind", [k.id for k in ctx.KINDS])
def test_every_kind_can_say_what_it_expected(kind):
    # Für den abgelehnten Wert schlägt `panel()` einen Halbsatz nach, was DIESER
    # Typ erwartet hätte. Fehlte er für einen Typ, endete ein ungültiger
    # Query-String in einem KeyError — HTTP 500 auf einem öffentlichen Pfad, und
    # zwar nur bei falscher Eingabe, also genau dort, wo niemand hinsieht.
    # Deshalb über jeden Typ, nicht über die Tabelle: was hier zählt, ist die
    # Antwort, nicht wie sie zustande kommt.
    ungueltig = "x" * 500  # keine UUID, kein Slug, über allen Deckeln, kein http
    html = ctx.panel(kind, ungueltig)
    assert 'role="alert"' in html


def test_the_panel_says_when_a_value_was_refused():
    # Stumm zu verwerfen wäre die schlechteste Variante: die Seite sähe aus wie
    # immer, und man suchte den Fehler beim Chatbot.
    assert 'role="alert"' in ctx.panel("collection", "keine-uuid")
    assert 'role="alert"' not in ctx.panel("collection", UUID)
    assert 'role="alert"' not in ctx.panel("", "")


def test_the_panel_carries_no_inline_event_handler():
    # Dieselbe Linie wie im Attribut-Pult: ein Formular, das der Browser selbst
    # abschickt (GET auf die eigene Adresse) braucht kein Skript — und was kein
    # Skript hat, kann keines ausführen.
    html = ctx.panel("", "")
    assert not re.search(r"\son[a-z]+=", html)
