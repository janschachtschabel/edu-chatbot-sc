"""Charakterisierungs-Tests für die MCP-Response-Parser (``services/mcp/parsers/``).

Port aus ALT ``tests/test_mcp_parsers.py``. Die Parser sind reine Funktionen
(JSON/Text → Card-Dicts), ohne geteilten Zustand — nur ``config_loader`` für
Repo-URLs (env-getrieben, kein PG). Diese Tests pinnen Feld-Mapping, Envelope-
Erkennung, Placeholder-Titel und Varianten-Dedup.

Importiert wird bewusst über die **Paket-Fassade** ``…mcp.parsers``, nicht aus den
Untermodulen: sie ist die öffentliche Fläche, und diese Tests waren bei der
W11-Zerlegung (2026-08-01) der Beleg, dass sie unverändert geblieben ist.
"""

from __future__ import annotations

import json

from boerdi.services.mcp.parsers import (
    _first_json_object,
    _topic_page_display_title,
    parse_content_text,
    parse_search_all_cards,
    parse_topic_page_swimlanes,
    parse_total_count,
    parse_wikipedia_summary,
    parse_wlo_cards,
    parse_wlo_topic_page_cards,
)


# ── parse_content_text (W5-3a) ──────────────────────────────────────────
# Vertrag aus ``src/apps/outputSchemas.ts:70`` des Servers: nodeId, title, text,
# source ('repository'|'external-extraction'|'none'), sourceUrl, charCount,
# truncated, reason (nur im Leerfall). Der Volltext ist die Grundlage für
# „Inhalt anzeigen" — ohne ``reason`` kann der Bot nicht unterscheiden, ob ein
# Material aus Rechtegründen verschlossen ist (daran ändert kein Retry etwas)
# oder ob die Extraktion scheiterte.
def test_content_text_reads_full_envelope():
    raw = json.dumps({
        "nodeId": "n1", "title": "Bruchrechnung", "text": "# Aufgabe 1\nKürze …",
        "source": "repository", "sourceUrl": None,
        "charCount": 4200, "truncated": False,
    })
    out = parse_content_text(raw)
    assert out["text"].startswith("# Aufgabe 1")
    assert out["title"] == "Bruchrechnung"
    assert out["source"] == "repository"
    assert out["truncated"] is False
    assert out["reason"] == ""


def test_content_text_surfaces_access_denied_reason():
    raw = json.dumps({
        "nodeId": "n1", "title": "Geschütztes Material", "text": "",
        "source": "none", "sourceUrl": None, "charCount": 0,
        "truncated": False, "reason": "access_denied",
    })
    out = parse_content_text(raw)
    assert out["reason"] == "access_denied"
    assert out["text"] == ""


def test_content_text_marks_truncation():
    raw = json.dumps({
        "nodeId": "n1", "title": "Langer Text", "text": "x" * 100,
        "source": "repository", "sourceUrl": "https://example.org/a",
        "charCount": 41000, "truncated": True,
    })
    out = parse_content_text(raw)
    assert out["truncated"] is True
    assert out["char_count"] == 41000
    assert out["source_url"] == "https://example.org/a"


def test_content_text_markdown_answer_is_not_mistaken_for_a_result():
    # v1-Server / outputFormat=markdown: kein Envelope. Dann ist das Ergebnis
    # leer statt halb geraten — der Aufrufer soll den Leerfall behandeln.
    out = parse_content_text("# Titel\n\nQuelle: WLO-Repository\n\nText …")
    assert out["text"] == ""
    assert out["reason"] == "no_envelope"


def test_content_text_empty_input_is_empty_result():
    assert parse_content_text("")["text"] == ""


# ── parse_wikipedia_summary ─────────────────────────────────────────────
# Vertrag live vom Server geholt (2026-08-01, ``outputFormat="json"``):
#   Treffer : {"query": str, "found": true,
#              "summary": {"title", "extract", "url", "lang"}}
#   Fehlschlag: {"query": str, "found": false, "summary": null}
# Ohne ``outputFormat="json"`` antwortet das Werkzeug in Markdown — daraus Titel
# und URL zurückzuraten wäre eine Fehlerquelle in Unterrichtsmaterial, deshalb
# ist der Nicht-Envelope-Fall ein sauberer Leerfall.
def test_wikipedia_summary_reads_envelope():
    raw = json.dumps({
        "query": "Bruchrechnen", "found": True,
        "summary": {
            "title": "Bruchrechnung",
            "extract": "Im engeren Sinn bezeichnet Bruchrechnung das Rechnen …",
            "url": "https://de.wikipedia.org/wiki/Bruchrechnung",
            "lang": "de",
        },
    })
    out = parse_wikipedia_summary(raw)
    assert out["title"] == "Bruchrechnung"
    assert out["extract"].startswith("Im engeren Sinn")
    assert out["url"] == "https://de.wikipedia.org/wiki/Bruchrechnung"


def test_wikipedia_summary_not_found_is_empty():
    raw = json.dumps({"query": "Qwertzuiop", "found": False, "summary": None})
    out = parse_wikipedia_summary(raw)
    assert out["title"] == ""
    assert out["extract"] == ""
    assert out["url"] == ""


def test_wikipedia_summary_markdown_answer_is_not_mistaken_for_a_result():
    out = parse_wikipedia_summary("# Photosynthese\n\nDie Photosynthese ist …")
    assert out["extract"] == ""


def test_wikipedia_summary_empty_input_is_empty_result():
    assert parse_wikipedia_summary("")["extract"] == ""


# ── search_wlo_all + Envelope-Toleranz (W9b) ────────────────────────────
_SEARCH_ALL = json.dumps({
    "query": "Photosynthese",
    "content": {"total": 2, "count": 2, "results": [
        {"nodeId": "c1", "title": "Arbeitsblatt"},
        {"nodeId": "c2", "title": "Video"},
    ]},
    "collections": {"total": 1, "count": 1, "results": [
        {"nodeId": "k1", "title": "Sammlung Bio"},
    ]},
    # Live gemessen 2026-08-01 (Anfrage „Mathematik"): der topicPages-Topf von
    # ``search_wlo_all`` ist eine gewöhnliche FormattedNode-Liste mit ``nodeId``
    # und ``topicPageUrl`` — NICHT die ``collectionId``+``variants``-Form, die
    # ``search_wlo_topic_pages`` liefert. Zwei Werkzeuge, zwei Antwortformen.
    "topicPages": {"total": 1, "count": 1, "results": [
        {"nodeId": "t1", "title": "Mathematik", "nodeType": "collection",
         "topicPageUrl": "https://wlo.example/t1"},
    ]},
})


def test_search_all_splits_three_pots():
    out = parse_search_all_cards(_SEARCH_ALL)
    assert len(out["content"]) == 2
    assert len(out["collections"]) == 1
    assert len(out["topic_pages"]) == 1


def test_envelope_without_total_still_yields_cards():
    # ``get_related_content`` liefert (live gemessen 2026-08-01)
    # {seedNodeId, seedTitle, disciplines, educationalContexts, results} — echte
    # Karten, aber OHNE ``total``/``count``. Die alte Heuristik verlangte eines
    # von beiden und verwarf die Antwort komplett.
    raw = json.dumps({
        "seedNodeId": "s1", "seedTitle": "Artikelübersicht Pflanzen",
        "disciplines": ["Biologie"], "educationalContexts": ["Sekundarstufe I"],
        "results": [
            {"nodeId": "r1", "title": "Zellatmung"},
            {"nodeId": "r2", "title": "Blattaufbau"},
        ],
    })
    karten = parse_wlo_cards(raw)
    assert [k["title"] for k in karten] == ["Zellatmung", "Blattaufbau"]


def test_a_dict_without_results_is_still_not_an_envelope():
    # Die Lockerung darf nicht dazu führen, dass irgendein JSON-Objekt als
    # Kartenliste durchgeht.
    assert parse_wlo_cards(json.dumps({"nodeId": "x", "text": "kein Envelope"})) == []


# ── parse_total_count ───────────────────────────────────────────────────
def test_total_count_gesamt():
    assert parse_total_count("Gesamt: 42 Materialien") == 42


def test_total_count_ergebnisse_suffix():
    assert parse_total_count("17 Ergebnisse gefunden") == 17


def test_total_count_found():
    assert parse_total_count("Found 5 results") == 5


def test_total_count_no_match_is_zero():
    assert parse_total_count("kein Zähler hier") == 0


# W2-1: der einzige Konsument (``direct_actions._handle_browse_collection``)
# ruft ``get_collection_contents`` — ein Tool aus ``_JSON_CAPABLE_TOOLS``, das
# also IMMER den JSON-Envelope liefert, nie Prosa. Die Regex-Kette griff dort
# nie (``{"total": 42`` matcht weder ``Total[:\s]+`` noch ``\d+\s+Ergebnisse``),
# der Pager zeigte deshalb "von <Seitengröße>" statt der echten Gesamtzahl.
def test_total_count_reads_json_envelope():
    envelope = json.dumps({"total": 42, "count": 5, "results": [{"nodeId": "n1"}]})
    assert parse_total_count(envelope) == 42


def test_total_count_json_envelope_without_total_falls_back_to_zero():
    assert parse_total_count(json.dumps({"count": 5, "results": []})) == 0


def test_total_count_prefers_json_over_prose_digits():
    # Beschreibungstexte in den Ergebnissen dürfen die Gesamtzahl nicht kapern.
    envelope = json.dumps({
        "total": 7,
        "results": [{"nodeId": "n1", "description": "Gesamt: 999 Übungen im Heft"}],
    })
    assert parse_total_count(envelope) == 7


# ── parse_wlo_cards (v2-JSON-Envelope) ──────────────────────────────────
_V2_ENVELOPE = json.dumps({
    "total": 2, "count": 2,
    "results": [
        {"nodeId": "n-content-1", "title": "Bruchrechnen", "nodeType": "content",
         "description": "Ein Arbeitsblatt", "disciplines": ["Mathematik"]},
        {"nodeId": "n-coll-1", "title": "Sammlung Algebra", "nodeType": "collection"},
    ],
})


# ── Die Nutzlast trägt einen zweiten Block hinter sich ──────────────────
#
# Der MCP-Server hängt seit dem Skill-Umbau (Quelltext gelesen 2026-08-15,
# Deploy steht noch aus) die Freigabeliste der ANGEFRAGTEN Sammlung als eigenen
# ``content``-Block an — ``tools/shared.ts::subjectRegistryText``, aufgerufen von
# ``get_collection_contents``, ``search_wlo_within_collection``,
# ``get_related_content`` und ``get_topic_page_content``. Sie steht bewusst
# NICHT im JSON: dort ist der erste Block die Nutzlast, und deutsche Prosa daran
# geklebt ließe ``JSON.parse`` brechen.
#
# Unser Client hängt alle Textblöcke aneinander (``client.py``:
# ``"\n".join(texts)``) — worauf der Server sich ausdrücklich verlässt. Beim
# Parser kommt damit **JSON plus Prosa** an.
#
# Gemessen vor dem Fix: ``parse_wlo_cards`` 2 → **0** Karten,
# ``parse_total_count`` 4 → **0**. Drei kartenliefernde Werkzeuge hätten ihre
# Karten verloren, sobald der Server aktualisiert wird.
_ZWEITER_BLOCK = (
    "Für die angefragte Sammlung f35c17d1 sind diese Skills freigegeben:\n"
    "Skill-Registry: Skillkatalog Physik Optik (nodeId: 247da7a9) — 28 "
    "freigegebene Skills, alle hier gelistet; Beschreibungen und "
    "Redaktionshinweise mit get_skill_registry\n"
    "  Skill: Stunde planen (nodeId: 5b29f470) — laden mit get_skill"
)


def test_karten_ueberleben_einen_zweiten_textblock():
    karten = parse_wlo_cards(_V2_ENVELOPE + "\n" + _ZWEITER_BLOCK)
    assert [k["node_id"] for k in karten] == ["n-content-1", "n-coll-1"]


def test_die_gesamtzahl_ueberlebt_einen_zweiten_textblock():
    assert parse_total_count(_V2_ENVELOPE + "\n" + _ZWEITER_BLOCK) == 2


# ── Ein einzelner Knoten statt einer Liste ──────────────────────────────
#
# ``get_node_details`` legt im TEXT-Block einen flachen Knoten ab —
# ``{...formatted, renderUrl, parents?, raw?, textContent?}`` — und den Umschlag
# nur in ``structuredContent``, das unser Client nicht liest
# (node-details.ts:131-158, Quelltext gelesen 2026-08-15).
#
# Das ist auf der Server-Seite Absicht und von vier Tests dort festgenagelt
# (``payload.parents``, ``payload.raw``, ``payload.compendiumText`` auf oberster
# Ebene); der Vertrag des Repos verlangt nur, dass ein Text-Block DA ist, nicht
# dass er ``structuredContent`` gleicht. Also passt sich diese Seite an.
#
# Gemessen vor dem Fix: 1 → **0** Karten, obwohl ``get_node_details`` in
# ``CARD_YIELDING_TOOLS`` steht.
_FLACHER_KNOTEN = json.dumps({
    "nodeId": "f35c17d1", "title": "Geometrische Optik", "description": "",
    "nodeType": "collection", "topicPageUrl": "",
    "renderUrl": "https://example.invalid/render/f35c17d1",
})


def test_ein_einzelner_knoten_gilt_als_ergebnis_von_eins():
    karten = parse_wlo_cards(_FLACHER_KNOTEN)
    assert [k["node_id"] for k in karten] == ["f35c17d1"]
    assert karten[0]["node_type"] == "collection"


def test_die_toleranz_greift_nur_bei_einem_echten_knoten():
    """Sonst läse jedes Objekt mit einer ``nodeId`` als Karte.

    Die Signatur eines ``FormattedNode`` ist das PAAR aus ``nodeId`` und einem
    bekannten ``nodeType`` — eine Auskunft wie ``{"nodeId": …, "fileCount": …}``
    trägt zwar eine ID, ist aber keine Karte.
    """
    assert parse_wlo_cards(json.dumps({"nodeId": "n1", "fileCount": 12})) == []
    assert parse_wlo_cards(json.dumps({"nodeType": "collection"})) == []
    assert parse_wlo_cards(json.dumps({"registry": {"entries": []}})) == []


def test_der_zweite_block_kapert_die_gesamtzahl_nicht():
    """Der Rückfall darf den W2-1-Schutz nicht aufweichen.

    ``parse_total_count`` liest den Umschlag und NICHT die Ziffern im Fließtext
    — sonst wäre „28 freigegebene Skills" im angehängten Block ein Kandidat für
    die Trefferzahl.
    """
    assert parse_total_count(_V2_ENVELOPE + "\n" + _ZWEITER_BLOCK) != 28


def test_parse_wlo_cards_maps_fields_and_types():
    cards = parse_wlo_cards(_V2_ENVELOPE)
    assert len(cards) == 2
    a, b = cards
    assert a["node_id"] == "n-content-1"
    assert a["title"] == "Bruchrechnen"
    assert a["node_type"] == "content"
    assert a["disciplines"] == ["Mathematik"]
    # content-Node → render-Permalink; collection → collections-Browse-URL
    assert "/edu-sharing/components/render/n-content-1" in a["wlo_url"]
    assert "/edu-sharing/components/collections?id=n-coll-1" in b["wlo_url"]
    assert b["node_type"] == "collection"


def test_parse_wlo_cards_non_json_returns_empty():
    assert parse_wlo_cards("das ist kein JSON") == []


def test_parse_wlo_cards_empty_returns_empty():
    assert parse_wlo_cards("") == []


def test_parse_wlo_cards_without_total_is_still_an_envelope():
    # GEÄNDERT in W9b (2026-08-01). Vorher pinnte dieser Test „ohne total/count
    # ist es kein v2-Envelope → []". Diese Annahme ist an der Wirklichkeit
    # gescheitert: ``get_related_content`` antwortet mit
    # {seedNodeId, seedTitle, disciplines, educationalContexts, results} und
    # KEINEM Zähler — live gemessen. Die alte Regel warf drei einwandfreie
    # Karten weg. Entscheidend ist der Eintrag mit ``nodeId``, nicht der Kopf.
    payload = json.dumps({"results": [{"nodeId": "x", "title": "T"}]})
    assert [k["node_id"] for k in parse_wlo_cards(payload)] == ["x"]


def test_parse_wlo_cards_skips_results_without_nodeid():
    payload = json.dumps({"total": 1, "results": [{"title": "ohne id"}]})
    assert parse_wlo_cards(payload) == []


def test_der_envelope_leser_setzt_node_type_immer():
    """``node_type`` ist nach dem Parsen IMMER gesetzt — auch ohne ``nodeType``.

    Diese Invariante trägt eine Löschung vom 2026-08-16: an vier Stellen stand
    ein ``c.setdefault("node_type", …)``, der einen fehlenden Schlüssel
    nachtragen sollte. Er konnte nie greifen, weil hier ein Vorgabewert gesetzt
    wird (Z. „nodeType or content"), und wurde deshalb entfernt. Fällt dieser
    Test, ist die Vorgabe weg — dann sind die entfernten Schutzzeilen plötzlich
    wieder nötig, und die Aufrufer bekämen Karten ohne Typ.
    """
    payload = json.dumps({"total": 2, "results": [
        {"nodeId": "ohne", "title": "kein nodeType im Ergebnis"},
        {"nodeId": "mit", "title": "Sammlung", "nodeType": "collection"},
    ]})
    ohne, mit = parse_wlo_cards(payload)
    assert "node_type" in ohne and ohne["node_type"] == "content"
    assert mit["node_type"] == "collection"


# ── parse_wlo_topic_page_cards ──────────────────────────────────────────
def test_topic_page_cards_basic():
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "Mathematik", "collectionId": "c-1",
            "topicPageUrl": "https://wlo/themenseite/c-1",
            "educationalContexts": ["Sek I"], "variants": [],
        }],
    })
    cards = parse_wlo_topic_page_cards(payload)
    assert len(cards) == 1
    assert cards[0]["title"] == "Mathematik"


def test_topic_page_cards_placeholder_title_becomes_readable():
    # PAGE_VARIANT_<uuid> ist ein Platzhalter → lesbares Label mit Bildungsstufe.
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "PAGE_VARIANT_037c4c53-abc", "collectionId": "c-2",
            "topicPageUrl": "https://wlo/x", "educationalContexts": ["Sek II"],
            "variants": [],
        }],
    })
    cards = parse_wlo_topic_page_cards(payload)
    assert cards[0]["title"] == "Themenseite (Sek II)"


def test_topic_page_cards_non_envelope_returns_empty():
    assert parse_wlo_topic_page_cards("kein JSON") == []
    assert parse_wlo_topic_page_cards("") == []


# ── parse_search_all_cards / parse_topic_page_swimlanes: Envelope-Robustheit ─
def test_search_all_non_envelope_returns_empty_buckets():
    # Ist-Verhalten: drei leere Buckets statt Fehler.
    assert parse_search_all_cards("kein JSON") == {
        "content": [], "collections": [], "topic_pages": [],
    }


def test_swimlanes_non_envelope_returns_empty_shape():
    # Ist-Verhalten: dict mit leeren Feldern (NICHT eine Liste).
    assert parse_topic_page_swimlanes("kein JSON") == {
        "variant_title": "", "topic_page_url": "", "swimlanes": [], "reason": "",
    }


# W2-3: Der Server begründet den Leerfall seit 2026-07-27 selbst
# (``no_match`` | ``node_not_found`` | ``no_page_config_ref`` | ``no_variant`` |
# ``empty_config``) und lässt das Feld bei Erfolg weg.
def test_swimlanes_forwards_server_reason():
    raw = json.dumps({
        "variantId": "", "collectionId": "c1", "variantTitle": "",
        "topicPageUrl": None, "swimlaneCount": 0, "swimlanes": [],
        "reason": "no_page_config_ref",
    })
    assert parse_topic_page_swimlanes(raw)["reason"] == "no_page_config_ref"


# W5-1: Der Server legt den lesbaren Namen in ``collectionTitle``;
# ``variantTitle`` trägt den technischen Varianten-Namen („Fachportalstartseite"
# für JEDE Fachportal-Themenseite). Live gemessen 2026-07-30: Mathematik, Chemie
# und Nachhaltigkeit kommen alle drei mit variantTitle="Fachportalstartseite"
# zurück. Bisher verdeckte der Kandidaten-Titel aus der Suche das; auf dem
# Ein-Call-Pfad (query=Thema) gibt es den nicht mehr.
def test_swimlanes_prefers_collection_title_over_variant_title():
    raw = json.dumps({
        "variantTitle": "Fachportalstartseite", "collectionTitle": "Mathematik",
        "topicPageUrl": "u", "swimlanes": [],
    })
    assert parse_topic_page_swimlanes(raw)["variant_title"] == "Mathematik"


def test_swimlanes_falls_back_to_variant_title_without_collection_title():
    raw = json.dumps({"variantTitle": "Seiten-Variante 1", "swimlanes": []})
    assert parse_topic_page_swimlanes(raw)["variant_title"] == "Seiten-Variante 1"


def test_swimlanes_reason_empty_when_server_omits_it():
    raw = json.dumps({"variantTitle": "T", "topicPageUrl": "u", "swimlanes": []})
    assert parse_topic_page_swimlanes(raw)["reason"] == ""


# ── Ausbau 2026-07-05: Happy-Paths + Helfer ────────────────────────────────
def test_total_count_total_and_treffer_prefix():
    assert parse_total_count("Total: 9") == 9
    assert parse_total_count("Treffer: 3 gefunden") == 3
    # Bare "Found 12"/"Gefunden 7" (ohne "results"-Suffix) → dritte Regex-Stufe.
    assert parse_total_count("Found 12") == 12
    assert parse_total_count("Gefunden 7") == 7


# ── _first_json_object (balancierter Extraktor) ────────────────────────────
def test_first_json_object_extracts_balanced():
    assert _first_json_object('prefix {"a": 1} suffix') == '{"a": 1}'


def test_first_json_object_ignores_braces_in_strings():
    assert _first_json_object('{"a": "}{"}') == '{"a": "}{"}'


def test_first_json_object_none_when_absent():
    assert _first_json_object("kein objekt hier") is None


# ── _topic_page_display_title (Placeholder-Erkennung) ──────────────────────
def test_display_title_clean_passthrough():
    assert _topic_page_display_title("Mathematik", "c1", ["Sek I"]) == "Mathematik"


def test_display_title_uuid_placeholder_no_ctx():
    assert _topic_page_display_title(
        "037c4c53-1234-1234-1234-123456789abc", "c1", None) == "Themenseite"


def test_display_title_equals_collection_id_with_ctx():
    assert _topic_page_display_title("c1", "c1", ["Grundschule"]) == "Themenseite (Grundschule)"


def test_display_title_variant_prefix_empty_ctx():
    assert _topic_page_display_title("variant_5", "c1", []) == "Themenseite"


# ── parse_wlo_topic_page_cards: Varianten + Dedup ──────────────────────────
def test_topic_page_cards_variants_dedup_and_clean_label():
    payload = json.dumps({
        "total": 1,
        "results": [{
            "title": "Physik", "collectionId": "c-9",
            "topicPageUrl": "https://wlo/tp/c-9", "educationalContexts": ["Sek I"],
            "variants": [
                {"variantId": "v1", "targetGroup": "teacher",
                 "targetGroupLabel": "Lehrkräfte", "topicPageUrl": "https://wlo/tp/teacher"},
                # funktional identisch → collapse
                {"variantId": "v2", "targetGroup": "teacher",
                 "targetGroupLabel": "Lehrkräfte", "topicPageUrl": "https://wlo/tp/teacher"},
                # uninformatives Label → "Themenseite"
                {"variantId": "v3", "targetGroup": "student",
                 "targetGroupLabel": "nicht gesetzt", "topicPageUrl": "https://wlo/tp/student"},
            ],
        }],
    })
    tps = parse_wlo_topic_page_cards(payload)[0]["topic_pages"]
    assert len(tps) == 2  # v1 & v2 kollabiert
    assert {tp["url"] for tp in tps} == {"https://wlo/tp/teacher", "https://wlo/tp/student"}
    student = next(tp for tp in tps if tp["target_group"] == "student")
    assert student["label"] == "Themenseite"  # "nicht gesetzt" → Fallback


# ── parse_search_all_cards: Happy-Path + Fragment-Fallback ─────────────────
def test_search_all_three_buckets():
    payload = json.dumps({
        "query": "bruch",
        "content": {"total": 1, "count": 1,
                    "results": [{"nodeId": "ct1", "title": "Content", "nodeType": "content"}]},
        "collections": {"total": 1, "count": 1,
                        "results": [{"nodeId": "co1", "title": "Coll", "nodeType": "collection"}]},
        "topicPages": {"total": 1, "count": 1,
                       "results": [{"nodeId": "tp1", "title": "TP", "nodeType": "collection"}]},
    })
    out = parse_search_all_cards(payload)
    assert [c["node_id"] for c in out["content"]] == ["ct1"]
    assert [c["node_id"] for c in out["collections"]] == ["co1"]
    assert [c["node_id"] for c in out["topic_pages"]] == ["tp1"]


def test_search_all_markiert_den_themenseiten_topf_als_themenseiten():
    # Der Server setzt im ``topicPages``-Topf ``nodeType='collection'`` und
    # liefert KEINE ``variants`` — die Karten sahen deshalb aus wie gewöhnliche
    # Sammlungen. ``_is_themenseite_card`` (``domain/cards/build``:211) erkannte
    # sie nicht: sie landeten in der Sammlungs-Box statt in der Themenseiten-Box
    # und teilten sich deren Deckel (Vorgabe 3). Live gemessen 2026-08-16 an
    # „Optik": drei Sammlungen, Themenseiten-Box leer — bei einer vierten wäre
    # die gesuchte Sammlung wieder ganz herausgefallen.
    payload = json.dumps({
        "topicPages": {"total": 1, "count": 1, "results": [
            {"nodeId": "tp1", "title": "Optik", "nodeType": "collection",
             "topicPageUrl": "https://wlo.example/tp?collectionId=tp1"},
        ]},
    })
    karte = parse_search_all_cards(payload)["topic_pages"][0]
    assert karte["node_type"] == "topic_page"
    assert [v["url"] for v in karte["topic_pages"]] == \
        ["https://wlo.example/tp?collectionId=tp1"]


def test_search_all_leitet_die_themenseiten_adresse_ab_wenn_sie_fehlt():
    # Ohne ``topicPageUrl`` baut der dedizierte Parser sie aus der cid
    # (``topic_pages.py``:182). Dieselbe Regel hier — sonst hinge die Erkennung
    # an einem Feld, das der Server weglassen darf.
    payload = json.dumps({
        "topicPages": {"total": 1, "count": 1, "results": [
            {"nodeId": "tp2", "title": "Wellenoptik", "nodeType": "collection"},
        ]},
    })
    karte = parse_search_all_cards(payload)["topic_pages"][0]
    assert karte["node_type"] == "topic_page"
    assert karte["topic_pages"][0]["url"].endswith("topic-pages?collectionId=tp2")


def test_search_all_laesst_die_anderen_toepfe_unberuehrt():
    # Gegenprobe: NUR der Themenseiten-Topf wird markiert. Sammlungen und
    # Inhalte behalten den Typ des Servers und bekommen keine Varianten.
    payload = json.dumps({
        "content": {"total": 1, "count": 1, "results": [
            {"nodeId": "c1", "title": "Video", "nodeType": "content"}]},
        "collections": {"total": 1, "count": 1, "results": [
            {"nodeId": "s1", "title": "Sammlung", "nodeType": "collection"}]},
    })
    out = parse_search_all_cards(payload)
    assert out["content"][0]["node_type"] == "content"
    assert out["collections"][0]["node_type"] == "collection"
    assert not out["collections"][0].get("topic_pages")


def test_search_all_with_trailing_text_uses_fragment():
    env = json.dumps({
        "content": {
            "total": 1,
            "results": [{"nodeId": "x", "title": "T", "nodeType": "content"}],
        },
    })
    out = parse_search_all_cards(env + "\n\n[meta trailing text]")
    assert [c["node_id"] for c in out["content"]] == ["x"]


# ── parse_topic_page_swimlanes: Happy-Path ─────────────────────────────────
def test_swimlanes_happy_path_maps_items_to_cards():
    payload = json.dumps({
        "variantTitle": "Sek I Variante", "topicPageUrl": "https://wlo/tp", "swimlaneCount": 1,
        "swimlanes": [{
            "heading": "Videos", "type": "container", "hasMore": True,
            "items": [{"nodeId": "n1", "title": "Video 1", "nodeType": "content"}],
        }],
    })
    out = parse_topic_page_swimlanes(payload)
    assert out["variant_title"] == "Sek I Variante"
    assert out["topic_page_url"] == "https://wlo/tp"
    assert len(out["swimlanes"]) == 1
    sl = out["swimlanes"][0]
    assert (sl["heading"], sl["type"], sl["has_more"]) == ("Videos", "container", True)
    assert [c["node_id"] for c in sl["cards"]] == ["n1"]


# ── Skill-Hinweis an der Karte (Nutzer-Vorgabe 2026-08-14) ───────────────
# Der MCP haengt ``skillRegistry`` ungefragt an Sammlungstreffer (gemessen an
# ``search_wlo_collections`` und ``search_wlo_all``). Bisher landete das nur im
# Prompt; sichtbar war es allein im Seitenkontext. Die Karte traegt die Zahl,
# damit die Kachel es auch bei einer Suche zeigen kann.

def test_karte_traegt_die_anzahl_freigegebener_skills():
    import json as _json

    from boerdi.services.mcp.parsers import parse_wlo_cards

    envelope = _json.dumps({"total": 1, "count": 1, "results": [{
        "nodeId": "9e7ae956-e9df-430f-bace-f3db4b910013",
        "title": "Optik", "nodeType": "collection",
        "skillRegistry": {"nodeId": "d84d54c4", "entries": [
            {"nodeId": "s1", "title": "Stunde planen"},
            {"nodeId": "s2", "title": "Pruefung erstellen"},
            {"nodeId": "s3", "title": "Dokumentieren"},
        ]},
    }]})
    karten = parse_wlo_cards(envelope)
    assert karten[0]["skill_count"] == 3


def test_karte_ohne_registry_meldet_null():
    import json as _json

    from boerdi.services.mcp.parsers import parse_wlo_cards

    envelope = _json.dumps({"total": 1, "count": 1, "results": [{
        "nodeId": "13c03c9b", "title": "Elektromagnetische Wellen",
        "nodeType": "collection",
    }]})
    assert parse_wlo_cards(envelope)[0]["skill_count"] == 0


def test_themenseiten_karte_traegt_das_feld_ebenfalls():
    """Zweiter kartenbauender Parser, gleiche Regel.

    Gemessen 2026-08-14 am echten Server: DERSELBE Knoten
    (``9e7ae956…``, „Optik") kommt über ``search_wlo_collections`` MIT
    ``skillRegistry`` (28 Eintraege) und über ``search_wlo_topic_pages`` OHNE.
    Das Feld fehlt also am Werkzeug, nicht an der Sammlung — die Luecke gehoert
    in den MCP-Server. Hier steht die Regel trotzdem, aus zwei Gruenden: heute
    liefert sie ehrlich 0 statt eines fehlenden Feldes, und wenn der Server
    nachzieht, traegt die Themenseiten-Kachel den Hinweis ohne weitere Aenderung.

    Der haeufige Fall ist ohnehin schon abgedeckt: laeuft im selben Zug auch die
    Sammlungssuche, erbt die Themenseiten-Karte die Zahl ueber ``_build_cards``
    (dieselbe node_id) — siehe ``test_skill_count_wird_vom_reicheren_partner_
    geerbt``.
    """
    import json as _json

    from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards

    envelope = _json.dumps({"total": 1, "count": 1, "results": [{
        "collectionId": "9e7ae956-e9df-430f-bace-f3db4b910013",
        "title": "Optik",
        "variants": [{"variantId": "v1", "url": "https://x/tp", "targetGroup": "teacher"}],
        "skillRegistry": {"nodeId": "d84d54c4", "entries": [
            {"nodeId": "s1", "title": "Stunde planen"},
            {"nodeId": "s2", "title": "Pruefung erstellen"},
        ]},
    }]})
    karten = parse_wlo_topic_page_cards(envelope)
    assert karten and karten[0]["skill_count"] == 2


def test_themenseiten_karte_ohne_registry_meldet_null():
    # Der heutige Normalfall am echten Server.
    import json as _json

    from boerdi.services.mcp.parsers import parse_wlo_topic_page_cards

    envelope = _json.dumps({"total": 1, "count": 1, "results": [{
        "collectionId": "bf729405-18ff-440b-9d5b-dd466ff563c3",
        "title": "Wellenoptik",
        "variants": [{"variantId": "v1", "url": "https://x/tp"}],
    }]})
    karten = parse_wlo_topic_page_cards(envelope)
    assert karten and karten[0]["skill_count"] == 0
