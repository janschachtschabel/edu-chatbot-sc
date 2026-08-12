"""Characterization pins for services/turn_links._finalize_links_and_metas (verbatim
port of ALT chat_turn_links._finalize_links_and_metas, turn phases P27-P28).

Only the true boundaries are mocked: the query-meta accumulator (get_query_metas),
the repo-base-url config read (get_repo_base_url), and the MCP vocabulary helpers
(_ensure_label_cache/_fuzzy_lookup/_label_to_uri_cache in services/mcp/arg_resolvers).
The pure rewriters (_resolve_wanted_content_types, _extract_web_links_from_text) run
for real. asyncio_mode=auto runs the async tests without a marker.

Module-level boundaries are patched ON this module; the vocab helpers are imported
in-function from arg_resolvers, so they are patched at that source module.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from boerdi.api.schemas import WloCard
from boerdi.services.turn_links import _finalize_links_and_metas

MOD = "boerdi.services.turn_links"
AR = "boerdi.services.mcp.arg_resolvers"


def _card(node_id, title="", node_type="content", topic_pages=None, lrt=None):
    return WloCard(
        node_id=node_id, title=title, node_type=node_type,
        topic_pages=topic_pages or [],
        learning_resource_types=lrt or [],
    )


async def _call(monkeypatch, *, winner=None, pattern_output=None, message="",
                classification=None, tools_called=None, effective="M06",
                cards=None, response_text="", query_metas=None, repo="https://repo.example",
                mock_vocab=False, vocab_map=None, locale="de-DE"):
    """Invoke the finalizer with the boundaries stubbed. Returns the 7-tuple + tracer."""
    from boerdi.api.schemas import ChatRequest, Environment
    monkeypatch.setattr(f"{MOD}.get_query_metas", Mock(return_value=list(query_metas or [])))
    monkeypatch.setattr(f"{MOD}.get_repo_base_url", Mock(return_value=repo))
    if mock_vocab or vocab_map is not None:
        monkeypatch.setattr(f"{AR}._ensure_label_cache", AsyncMock(return_value=None))
        monkeypatch.setattr(f"{AR}._fuzzy_lookup", Mock(return_value=None))
        monkeypatch.setattr(f"{AR}._label_to_uri_cache", dict(vocab_map or {}))
    req = ChatRequest(session_id="s1", message=message,
                      environment=Environment(locale=locale))
    tracer = Mock()
    out = await _finalize_links_and_metas(
        req, session_state={"entities": {}}, classification_dict=classification or {"entities": {}},
        winner=winner, pattern_output=pattern_output or {}, tracer=tracer,
        tools_called=tools_called or [], _effective_pattern_id=effective,
        cards=list(cards or []), response_text=response_text,
    )
    return out, tracer


def _ids(cards):
    return [c.node_id if hasattr(c, "node_id") else c.get("node_id") for c in cards]


async def test_off_topic_filter_drops_non_matching_cards(monkeypatch):
    cards = [_card("a", "Klimawandel Grundlagen"), _card("b", "Photosynthese Zellen")]
    (out, _tr) = await _call(monkeypatch, winner=None, message="Klimawandel Unterricht",
                             cards=cards, response_text="Text.")
    kept = _ids(out[0])
    assert "a" in kept       # title token overlaps the search signal
    assert "b" not in kept   # no overlap → dropped by the off-topic filter


async def test_topic_page_card_bypasses_off_topic_filter(monkeypatch):
    cards = [_card("tp", "Nachhaltigkeit", node_type="collection",
                   topic_pages=[{"url": "u"}])]
    (out, _tr) = await _call(monkeypatch, winner=None, message="Klimawandel",
                             cards=cards, response_text="Text.")
    assert "tp" in _ids(out[0])   # topic-page cards are always kept


async def test_type_focus_strips_collections_and_rewrites_text(monkeypatch):
    cards = [_card("c1", "Mathe Video", lrt=["Video"]),
             _card("coll", "Mathe Sammlung", node_type="collection")]
    (out, _tr) = await _call(
        monkeypatch, winner=SimpleNamespace(id="M06"), message="Videos zu Mathe",
        classification={"entities": {"medientyp": "Video", "thema": "Mathe"}},
        cards=cards, response_text="Hier sind ein paar Videos.", mock_vocab=True)
    new_cards, new_text = out[0], out[1]
    assert "coll" not in _ids(new_cards)          # collections stripped in type-focus
    assert "schau" in new_text and "Suche unten" in new_text  # honest Such-CTA text
    assert out[6] == "Videos"                     # _type_focus_label


async def test_type_focus_skipped_for_non_search_pattern(monkeypatch):
    cards = [_card("c1", "Mathe Video"), _card("coll", "Mathe Sammlung", node_type="collection")]
    (out, _tr) = await _call(
        monkeypatch, winner=SimpleNamespace(id="M03"), message="Videos zu Mathe",
        classification={"entities": {"medientyp": "Video"}},
        cards=cards, response_text="Originaltext.")
    assert out[1] == "Originaltext."   # non-M05/M06 → type-focus rewriter does not fire
    assert out[6] == ""                # no type-focus label


async def test_type_focus_skipped_when_degraded(monkeypatch):
    cards = [_card("c1", "Mathe Video")]
    (out, _tr) = await _call(
        monkeypatch, winner=SimpleNamespace(id="M06"), message="Videos zu Mathe",
        classification={"entities": {"medientyp": "Video"}},
        pattern_output={"degradation": True, "missing_slots": ["thema"]},
        cards=cards, response_text="Rückfrage: welches Thema?")
    assert out[1] == "Rückfrage: welches Thema?"  # degraded → rewriters suspend
    assert out[6] == ""


async def test_web_links_extraction_plain_text(monkeypatch):
    (out, _tr) = await _call(monkeypatch, winner=None, message="Frage",
                             cards=[], response_text="Nur Text ohne Links.")
    assert out[2] == "Nur Text ohne Links."   # _final_text unchanged
    assert out[3] == []                        # _web_links empty


async def test_query_metas_mapped_and_traced(monkeypatch):
    metas = [{"toolName": "search_wlo_content", "queryType": "content",
              "searchTerm": "Mathe", "criteria": [], "pagination": {},
              "repositoryUrl": "r", "searchUrl": "http://s"}]
    (out, tracer) = await _call(monkeypatch, winner=None, message="Frage",
                                cards=[], response_text="x", query_metas=metas)
    assert out[4] == metas                       # _raw_metas passthrough
    entries = out[5]
    assert len(entries) == 1 and entries[0].search_term == "Mathe"
    assert tracer.record.call_args.args[0] == "query_meta"   # traced


async def test_synthetic_fallback_meta_when_cards_but_no_signal(monkeypatch):
    cards = [_card("a", "Klima")]
    (out, _tr) = await _call(
        monkeypatch, winner=None, message="Klimawandel",
        classification={"entities": {"thema": "Klimawandel"}},
        cards=cards, response_text="Text.", query_metas=[], repo="https://repo.x")
    synth = [m for m in out[5] if m.tool_name == "synthetic_fallback"]
    assert len(synth) == 1
    assert synth[0].search_term == "Klimawandel"   # from classification thema
    assert synth[0].repository_url == "https://repo.x"


# ── C1-f2b3: Sprache des Type-Focus-Suchverweises ──────────────────
# Der Verweis ersetzt die LLM-Antwort KOMPLETT. Seit C1-f1 ist diese
# Antwort bei ``locale="en-*"`` englisch — der Ersatzsatz war es nicht.
#
# Der deutsche Wortlaut ist ALT-verbatim und wird hier byte-genau
# festgehalten, samt des fehlenden schliessenden Anfuehrungszeichens
# hinter dem Thema (ALT-Befund, siehe C1-Plan — nicht stumm repariert).
_CTA_DE_TOPIC = (
    "Für Videos zu „Klima schau in die Suche unten — dort findest du "
    "die gefilterten Treffer."
)
_M06 = SimpleNamespace(id="M06")


async def test_type_focus_cta_german_is_alt_verbatim(monkeypatch):
    (out, _tr) = await _call(
        monkeypatch, winner=_M06, message="hast du Videos?",
        classification={"entities": {"thema": "Klima"}},
        response_text="Hier sind ein paar Videos.", mock_vocab=True)
    assert out[1] == _CTA_DE_TOPIC


async def test_type_focus_cta_english(monkeypatch):
    """Englische Nachricht erreicht den Pfad wirklich: ``videos`` ist in
    beiden Sprachen dasselbe Wort, ``_extract_wanted_content_types``
    trifft also auch auf Englisch."""
    (out, _tr) = await _call(
        monkeypatch, locale="en-GB", winner=_M06,
        message="do you have videos?",
        classification={"entities": {"thema": "Climate"}},
        response_text="Here are a few videos.", mock_vocab=True)
    assert "Für" not in out[1] and "Suche" not in out[1]
    assert out[1] == (
        "For Videos on “Climate” check the search below — that is where "
        "you will find the filtered results."
    )


async def test_type_focus_cta_english_without_topic(monkeypatch):
    (out, _tr) = await _call(
        monkeypatch, locale="en-GB", winner=_M06,
        message="do you have videos?",
        response_text="Here are a few videos.", mock_vocab=True)
    assert out[1] == (
        "For Videos on this topic check the search below — that is where "
        "you will find the filtered results."
    )


async def test_type_focus_label_is_translated(monkeypatch):
    (de, _t1) = await _call(
        monkeypatch, winner=_M06,
        classification={"entities": {"medientyp": "Arbeitsblatt", "thema": "Klima"}},
        response_text="Text.", mock_vocab=True)
    (en, _t2) = await _call(
        monkeypatch, locale="en-GB", winner=_M06,
        classification={"entities": {"medientyp": "Arbeitsblatt", "thema": "Climate"}},
        response_text="Text.", mock_vocab=True)
    assert de[6] == "Arbeitsblätter"
    assert en[6] == "Worksheets"


async def test_type_focus_vocab_lookup_stays_german(monkeypatch):
    """Das Typ-Label ist Anzeigetext UND Suchbegriff fuer das deutsche
    WLO-Vokabular (``_vocab_uri_for("lrt", …)``). Mit dem uebersetzten
    Label traefe der Lookup nie — der Typ-Filter fiele still aus der
    Such-URL, und der Verweis ``schau in die Suche unten`` zeigte auf
    eine ungefilterte Suche."""
    (out, _tr) = await _call(
        monkeypatch, locale="en-GB", winner=_M06,
        classification={"entities": {"medientyp": "Arbeitsblatt", "thema": "Climate"}},
        response_text="Text.",
        vocab_map={"lrt": {"arbeitsblätter": "http://uri/ab"}})
    tf = [m for m in out[5] if m.query_type == "type-focus-synth"]
    assert len(tf) == 1
    assert "filters=" in tf[0].search_url     # LRT-URI gefunden → Filter gesetzt
    assert tf[0].criteria[0]["values"] == ["http://uri/ab"]


# ── C1-f2b4: Anti-Halluzinations-Waechter ueber der eigenen Ausgabe ──
# Der Waechter liest den Antworttext, den WIR gerade erzeugt haben, und
# ersetzt Behauptungen ueber Sammlungen/Themenseiten, die im UI gar nicht
# sichtbar sind. Seit C1-f1 ist dieser Text bei ``locale="en-*"`` englisch
# — die deutschen Muster griffen dort nie.
#
# Der Waechter braucht: Such-Pattern (M05/M06), einen gelaufenen Such-Tool-
# Aufruf (sonst Offer-Mode-Skip) und leere Karten (0 Sammlungen sichtbar).
# ``message`` darf KEIN Typ-Wort enthalten, sonst ersetzt der Type-Focus-
# Rewriter den Text schon vorher komplett.
_SEARCHED = ["search_wlo_content"]


async def _watch(monkeypatch, text, *, locale="de-DE", tools=None, message="Klima"):
    (out, _tr) = await _call(
        monkeypatch, locale=locale, winner=_M06, message=message,
        tools_called=_SEARCHED if tools is None else tools,
        cards=[], response_text=text)
    return out[1]


async def test_watchdog_collection_claim_german_is_alt_verbatim(monkeypatch):
    """ALT-Wortlaut byte-genau: das Determinativ direkt vor dem Nomen wird
    mitgeschluckt, ein davorstehendes Zahlwort bleibt stehen."""
    assert await _watch(monkeypatch, "Hier sind zwei passende Sammlungen.") == (
        "Hier sind zwei passende Treffer in der Suche."
    )


async def test_watchdog_topic_page_claim_german_is_alt_verbatim(monkeypatch):
    assert await _watch(monkeypatch, "Ich zeige dir passende Themenseiten.") == (
        "Ich zeige dir passende Treffer in der Suche."
    )


async def test_watchdog_delivery_claim_german_is_alt_verbatim(monkeypatch):
    """Der Liefer-Satz wird als GANZER Satz ersetzt — inklusive des
    abschliessenden Leerzeichens, das ALT im Ersatztext mitfuehrt."""
    assert await _watch(monkeypatch, "Ich habe dir etwas rausgesucht.") == (
        "Schau in die verlinkte Suche unten — dort findest du passende "
        "Treffer zum Thema. "
    )


async def test_watchdog_skips_offer_mode_without_search_tool(monkeypatch):
    """Kein Such-Tool gelaufen → die Erwaehnung ist ein Angebot fuer den
    naechsten Zug, keine Halluzination ueber diesen. Text bleibt."""
    text = "Ich kann nach passenden Sammlungen suchen."
    assert await _watch(monkeypatch, text, tools=[]) == text


async def test_watchdog_collection_claim_english(monkeypatch):
    assert await _watch(
        monkeypatch, "Here are two matching collections.", locale="en-GB",
        message="climate",
    ) == "Here are two matching results in the search."


async def test_watchdog_topic_page_claim_english(monkeypatch):
    assert await _watch(
        monkeypatch, "I am showing you the topic pages.", locale="en-GB",
        message="climate",
    ) == "I am showing you matching results in the search."


async def test_watchdog_delivery_claim_english(monkeypatch):
    assert await _watch(
        monkeypatch, "I have put together a few things for you.",
        locale="en-GB", message="climate",
    ) == (
        "Look at the linked search below — that is where you will find "
        "matching results on this topic. "
    )


async def test_watchdog_english_still_catches_german_product_terms(monkeypatch):
    """``Themenseite`` ist ein WLO-Produktbegriff. Der f2a-Hinweis laesst
    Eigennamen bewusst unuebersetzt, das Modell kann ihn also mitten im
    englischen Satz stehen lassen — dann muss der englische Waechter ihn
    trotzdem fassen, sonst behauptet die Antwort sichtbare Boxen, die es
    nicht gibt."""
    assert await _watch(
        monkeypatch, "Here are the Themenseiten on this topic.", locale="en-GB",
        message="climate",
    ) == "Here are matching results in the search on this topic."


async def test_watchdog_german_unaffected_by_english_patterns(monkeypatch):
    """Gegenprobe: die englischen Woerter duerfen den deutschen Text
    nicht anfassen (die Kataloge sind getrennt, nicht vereinigt)."""
    text = "Hier sind Collections zum Thema."
    assert await _watch(monkeypatch, text) == text
