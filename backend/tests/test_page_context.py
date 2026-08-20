"""R6: Charakterisierungs-Tests für services/page_context — Port von ALT
tests/test_page_context_service.py (verbatim; nur Imports + MCP-Patch-Ziel
angepasst). Reine sync-Funktionen: JSON-Parsing, Cache-Frische, Kontext-
Signatur und die Prompt-Block-Renderer (``render_raw_for_prompt`` /
``render_for_prompt``) plus der async Netz-Resolver (``resolve_page_context``,
MCP an der Boundary gefakt — NEU-Konvention: ``setattr(module, 'call_mcp_tool')``).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time

from boerdi.services import page_context as p
from boerdi.services.context_facts import empty_marker


# ── _safe_json ──────────────────────────────────────────────────────────
def test_safe_json_valid_and_invalid():
    assert p._safe_json('{"a": 1}') == {"a": 1}
    assert p._safe_json("[1, 2]") == [1, 2]
    assert p._safe_json("kein json") is None
    assert p._safe_json("") is None


# ── Cache-Logik ─────────────────────────────────────────────────────────
def test_get_cached_empty_state_is_none():
    assert p.get_cached({}) is None


def test_cached_is_fresh_empty_state_is_false():
    assert p._cached_is_fresh({}, "irgendeine-signatur") is False


def test_context_signature_is_deterministic():
    pc = {"title": "Bruchrechnen", "url": "https://wlo.de/x"}
    assert p._current_context_signature(pc) == p._current_context_signature(pc)


# ── render_raw_for_prompt (Heuristik-Block) ─────────────────────────────
def test_render_raw_none_and_empty_return_empty():
    assert p.render_raw_for_prompt(None) == ""
    assert p.render_raw_for_prompt({}) == ""            # kein page_text
    assert p.render_raw_for_prompt({"page_text": "   "}) == ""   # nur Whitespace


def test_render_raw_with_page_text_builds_block():
    out = p.render_raw_for_prompt({
        "page_text": "Bruchrechnen üben mit Arbeitsblättern.",
        "page_kind": "topic",
        "detection_source": "dom",
    })
    assert out.startswith("## Inhalt der aktuellen Seite (Heuristik)")
    assert "Seitentyp: Themenseite" in out          # page_kind='topic' → Label
    assert "Bruchrechnen üben" in out               # Seitentext enthalten
    assert "Erkennungs-Quelle: dom" in out


def test_render_for_prompt_none_returns_empty():
    assert p.render_for_prompt(None) == ""


# ── Ausbau 2026-07-05: Wert-Asserts + async resolve_page_context ───────────
def _state_with(meta):
    return {"entities": {"_page_metadata": meta}}


def test_signature_exact_join():
    assert p._current_context_signature({"node_id": "a", "collection_id": "b"}) == "a|b||"
    assert p._current_context_signature({}) == "|||"


def test_get_cached_requires_title():
    assert p.get_cached({"entities": {"_page_metadata": {"title": "T"}}})["title"] == "T"
    assert p.get_cached({"entities": {"_page_metadata": {"title": ""}}}) is None


def test_cached_fresh_true_for_recent_matching():
    st = _state_with({"_signature": "sig", "_resolved_at": time.time(), "unresolved": False})
    assert p._cached_is_fresh(st, "sig") is True


def test_cached_fresh_false_for_wrong_signature():
    st = _state_with({"_signature": "other", "_resolved_at": time.time()})
    assert p._cached_is_fresh(st, "sig") is False


def test_cached_fresh_false_when_stale():
    st = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 10_000, "unresolved": False}
    )
    assert p._cached_is_fresh(st, "sig") is False


def test_cached_fresh_unresolved_uses_short_ttl():
    fresh = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 100, "unresolved": True}
    )
    stale = _state_with(
        {"_signature": "sig", "_resolved_at": time.time() - 200, "unresolved": True}
    )
    assert p._cached_is_fresh(fresh, "sig") is True
    assert p._cached_is_fresh(stale, "sig") is False


def test_extract_empty_returns_blank():
    out = p._extract_node_fields("")
    assert out["title"] == "" and out["disciplines"] == []


def test_extract_mcp_v2_json():
    raw = json.dumps({
        "nodeId": "abc", "title": "Bruchrechnung", "description": "Ein Kurs",
        "keywords": ["Brüche"], "disciplines": ["Mathematik"],
        "educationalContexts": ["Sekundarstufe I"], "learningResourceTypes": ["Video"],
        "url": "https://x/render",
    })
    out = p._extract_node_fields(raw)
    assert out["title"] == "Bruchrechnung"
    assert out["disciplines"] == ["Mathematik"]
    assert out["educational_contexts"] == ["Sekundarstufe I"]
    assert out["learning_resource_types"] == ["Video"]
    assert out["url"] == "https://x/render"


def test_extract_legacy_ccm_json():
    raw = json.dumps({"properties": {
        "cm:title": ["Titel X"],
        "ccm:taxonid_DISPLAYNAME": ["Mathematik"],
        "cclom:general_keyword": ["k1", "k2"],
    }})
    out = p._extract_node_fields(raw)
    assert out["title"] == "Titel X"
    assert out["disciplines"] == ["Mathematik"]
    assert out["keywords"] == ["k1", "k2"]


def test_extract_markdown_key_value():
    raw = "Titel: Photosynthese\nBeschreibung: Wie Pflanzen wachsen\nFächer: Biologie, Chemie\nURL: https://x"
    out = p._extract_node_fields(raw)
    assert out["title"] == "Photosynthese"
    assert out["description"] == "Wie Pflanzen wachsen"
    assert out["disciplines"] == ["Biologie", "Chemie"]
    assert out["url"] == "https://x"


def test_render_empty_when_no_title():
    assert p.render_for_prompt({"title": ""}) == ""


def test_render_collection_page_with_ids_and_filter():
    meta = {
        "title": "Bruchrechnung", "description": "desc", "disciplines": ["Mathe"],
        "educational_contexts": ["Sek I"], "keywords": ["k"], "learning_resource_types": ["Video"],
        "url": "https://x",
    }
    pc = {"page_kind": "collection", "collection_id": "C1", "search_query": "brüche"}
    out = p.render_for_prompt(meta, pc)
    assert "Sammlung (edu-sharing)" in out
    assert "Titel: Bruchrechnung" in out
    assert "Fächer: Mathe" in out
    assert "Sammlungs-ID (collection_id): C1" in out
    assert "get_collection_contents" in out
    assert "brüche" in out


def test_render_zeigt_bestand_und_skillkatalog():
    """Nutzer-Vorgabe 2026-08-14: Bestandszahl UND Skillkatalog gehören in
    BEIDE Engines, „pattern und agent loop".

    Beide lesen ihren Seitenblock aus dieser Funktion — die Muster-Engine über
    ``response_prompt_builder``, die Agent-Schleife über ``prompt_block``. Sie
    ist damit die eine Naht, an der beide gleichzeitig versorgt werden; zwei
    Einspeisungen wären zwei Orte, an denen es auseinanderläuft.

    Die Übersicht trägt nur TITEL — keine Inhalte, keine ``nodeId``
    (Nutzer-Klarstellung 2026-08-14). Die Rechnung dahinter steht im Docstring
    von ``_bestands_zeilen``; den Weg zum Volltext nennt der Block selbst, und
    genau darauf prüft die letzte Zusicherung unten.
    """
    meta = {
        "title": "Geometrische Optik",
        "context_facts": {
            "materials": 35, "sub_collections": 4, "skills": 28,
            "skill_titles": ["Stunde planen", "Dokumentieren"],
        },
    }
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})
    assert "35" in out and "Materialien" in out
    assert "28" in out
    assert "Stunde planen" in out and "Dokumentieren" in out
    # Der zweistufige Weg zum Volltext MUSS benannt sein — ohne nodeId in der
    # Übersicht käme das Modell sonst nicht an die Anleitung. WELCHE zwei
    # Schritte das sind, prüft der Wächter darunter.
    assert "get_skill" in out


def test_der_block_nennt_den_weg_den_das_modell_auch_gehen_kann():
    """Befund 2026-08-15: er nannte einen, den es nicht gehen kann.

    Der Hinweis stand auf ``search_skill`` → ``get_skill``. ``search_skill`` ist
    aber seit 2026-08-13 aus jedem Pfad genommen (``agent_tools.AUS_DEM_KATALOG``
    für die Agent-Schleife, ``_NICHT_UEBER_PATTERN`` für die Muster) — der Block
    entstand einen Tag später und nahm die Entscheidung nicht auf. Damit wies er
    das Modell auf ein Werkzeug, das in keiner Werkzeugliste steht, und der
    erreichbare Weg (``get_skill_registry`` mit der Sammlungs-ID, die derselbe
    Block wenige Zeilen später nennt) kam gar nicht vor.

    Der Agent-Lauf überstand das, weil ``respond_agent`` die Registry vorab in
    die Kette holt; der Mustermodus hat keinen Vorabruf und lief ins Leere —
    genau der Befund des Nutzers („beim pattern modus passiert dies oft nicht").

    Beide Richtungen sind gepinnt: kein stillgelegtes Werkzeug, und die zwei,
    die den Weg tragen, ausdrücklich. ``get_skill`` wird dabei mit einer
    Wortgrenze gesucht — sonst genügte ``get_skill_registry`` der Zusicherung.
    """
    import re

    from boerdi.services.agent_tools import AUS_DEM_KATALOG

    meta = {"title": "Geometrische Optik",
            "context_facts": {"skills": 28, "skill_titles": ["Stunde planen"]}}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})

    for stillgelegt in AUS_DEM_KATALOG:
        assert stillgelegt not in out, (
            f"Der Seitenblock weist auf {stillgelegt} — kein Pfad reicht es dem "
            "Modell.")
    assert "get_skill_registry" in out
    assert re.search(r"get_skill(?!_)", out), (
        "Der zweite Schritt fehlt — die Registry allein liefert nur Titel und "
        "nodeIds, nicht den Wortlaut der Anleitung.")
    # Und die ID, mit der der erste Schritt überhaupt aufrufbar ist.
    assert "C1" in out


def test_der_block_sagt_den_vorrang_vor_den_mitgelieferten_vorlagen_an():
    """Nutzer-Regel 2026-08-16: „skills stehen dabei über den mustern die der
    chatbot von haus aus mitbringt. wenn es ein muster für die gleiche ausgabe
    aus dem skill und eines aus dem bot gibt - sollte er den skill nutzen".

    Der Block nannte den Weg zur Anleitung, aber nicht ihren Rang. Damit stand
    Aussage gegen Aussage: hier eine freigegebene Anleitung, dort eine
    mitgelieferte Vorlage im selben Prompt — und keine Regel, welche gewinnt.
    Der Routing-Teil dieser Regel sitzt in ``domain/skill_precedence``; dies
    hier ist der Teil, den das Modell liest.

    Geprüft wird die **Aussage**, nicht ihr Wortlaut: der Rang („vor") und der
    ausdrückliche Gleichstands-Fall (eine eigene Vorlage für dieselbe Ausgabe),
    denn genau der war der Befund.
    """
    meta = {"title": "Geometrische Optik",
            "context_facts": {"skills": 28, "skill_titles": ["Stunde planen"]}}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})

    assert "VOR" in out, "Der Rang der Anleitungen steht nicht im Block."
    assert "Vorlage" in out, (
        "Der Gleichstands-Fall fehlt — genau er war der Befund: der Bot hatte "
        "eine eigene Vorlage für dieselbe Ausgabe und nahm sie.")


def test_der_bestandsabschnitt_laesst_sich_abschalten():
    """Review-Befund 2026-08-14: ``render_for_prompt`` hat DREI Verbraucher,
    nicht zwei — auch der Klassifikator (``classify_prompt.py:244``) liest ihn.

    Der wählt ein Muster und ruft keine Skills auf; der Katalog war dort
    gemessene +2 232 Zeichen je Zug. Schwerer wiegt: es formt seinen Prompt,
    und genau dafür verlangt der Plan einen Golden-Lauf. Also abschaltbar —
    Vorgabe bleibt AN, damit die zwei gewollten Verbraucher nichts tun müssen.
    """
    meta = {
        "title": "Geometrische Optik",
        "context_facts": {"materials": 35, "skills": 28,
                          "skill_titles": ["Stunde planen"]},
    }
    pc = {"page_kind": "collection", "collection_id": "C1"}
    mit = p.render_for_prompt(meta, pc)
    ohne = p.render_for_prompt(meta, pc, include_stock=False)
    assert "Bestand dieser Sammlung" in mit
    assert "Bestand dieser Sammlung" not in ohne
    assert "Stunde planen" not in ohne
    # Der Rest des Blocks bleibt — abgeschaltet wird der Bestand, nicht die Seite.
    assert "Titel: Geometrische Optik" in ohne
    assert "Sammlungs-ID (collection_id): C1" in ohne


def test_render_ohne_bestandsfakten_bleibt_wie_bisher():
    """Gegenprobe: ohne die Fakten darf kein leerer Abschnitt entstehen —
    eine Überschrift ohne Inhalt liest sich wie ein Ausfall."""
    out = p.render_for_prompt({"title": "T"}, {"page_kind": "collection"})
    assert "Bestand" not in out
    assert "Skill" not in out


def test_der_leer_vermerk_erscheint_nie_im_prompt():
    """Der Vermerk „hier kam nichts" wohnt IM Faktenobjekt (``_leer_seit``),
    damit der Knoten ihn ohne zweites Feld datieren kann.

    Der Preis dafür ist genau dieses Risiko: er läuft durch dieselbe Naht wie
    echte Fakten. Beide Leser dürfen ihn nicht sehen — hier der Renderer, in
    ``test_context_greeting`` der Begrüßungssatz.
    """
    out = p.render_for_prompt({"title": "T", "context_facts": empty_marker()},
                              {"page_kind": "collection"})
    assert "_leer_seit" not in out
    assert "Bestand dieser Sammlung" not in out
    assert "Freigegebene Anleitungen" not in out


def test_render_kappt_einen_sehr_grossen_skillkatalog():
    """Der Block läuft in JEDEN Zug auf einer Sammlungsseite. 28 Einträge sind
    gemessene 2 kB; ohne Deckel wächst das mit dem Katalog unbegrenzt."""
    titel = [f"Skill {i}" for i in range(200)]
    meta = {"title": "T", "context_facts": {"skills": 200, "skill_titles": titel}}
    out = p.render_for_prompt(meta, {"page_kind": "collection"})
    assert "Skill 0" in out
    assert f"Skill {p.MAX_SKILL_ENTRIES - 1}" in out      # bis zum Deckel vollständig
    assert f"Skill {p.MAX_SKILL_ENTRIES}" not in out
    assert "Skill 199" not in out
    assert "weitere" in out          # die Kappung wird benannt, nicht verschwiegen


def test_der_skillkatalog_passt_auf_eine_a4_seite():
    """Nutzer-Vorgabe 2026-08-14: „nur die Übersicht … nicht mehr als eine A4
    Seite … die registry bitte vollständig rein geben — kann man ab 100 kappen".

    Beide Zahlen gehen nur in EINER Form zusammen, an der echten Registry
    nachgemessen (28 Einträge, Titel im Schnitt 30,6 Zeichen): nur Titel
    ergeben bei 100 Einträgen 3 361 Zeichen — eine A4-Seite. Mit ``nodeId``
    wären es 7 161, also gut zwei. Deshalb trägt die Übersicht keine IDs; den
    Volltext holt das Modell gezielt über ``get_skill_registry`` →
    ``get_skill``.
    """
    titel = [f"Anleitung Nummer {i} zu einem Thema" for i in range(p.MAX_SKILL_ENTRIES)]
    abschnitt = "\n".join(p._bestands_zeilen(
        {"skills": len(titel), "skill_titles": titel}))
    assert len(abschnitt) <= p.MAX_SKILL_CHARS, (
        f"Übersicht {len(abschnitt)} Zeichen — mehr als eine A4-Seite")
    assert "weitere" in abschnitt      # was nicht passt, wird benannt

    # Die ECHTE Registry (28 Einträge, Titel im Schnitt 30,6 Zeichen) passt
    # vollständig — der Deckel ist ein Netz, keine Alltagsgrenze.
    echt = [f"Anleitung {i} zum Thema" for i in range(28)]
    voll = "\n".join(p._bestands_zeilen({"skills": 28, "skill_titles": echt}))
    assert "weitere" not in voll
    assert echt[-1] in voll


def test_render_unresolved_adds_hint_and_truncates_desc():
    meta = {"title": "T", "description": "D" * 500, "unresolved": True}
    out = p.render_for_prompt(meta)
    assert "Aktuelle Seite" in out
    assert "nicht geladen" in out          # Unresolved-Hinweis
    assert "…" in out                      # Beschreibung gekürzt


def test_render_raw_includes_fields_and_snippet():
    pc = {
        "page_text": "Sichtbarer Seiteninhalt zum Thema Wasserkreislauf.",
        "page_kind": "topic", "topic_page_slug": "wasser",
        "search_query": "kreislauf", "detection_source": "dom",
    }
    out = p.render_raw_for_prompt(pc)
    assert "Themenseite-Slug: wasser" in out
    assert "Aktiver Suchbegriff: kreislauf" in out
    assert "Wasserkreislauf" in out


def test_render_raw_truncates_long_text():
    out = p.render_raw_for_prompt({"page_text": "x" * 2000})
    assert "…" in out
    assert "x" * 2000 not in out


def _patch_mcp(monkeypatch, fn):
    monkeypatch.setattr(p, "call_mcp_tool", fn)


def test_resolve_empty_context_returns_none():
    assert asyncio.run(p.resolve_page_context({}, {})) is None
    assert asyncio.run(p.resolve_page_context(None, {})) is None


def test_resolve_no_signature_uses_document_title():
    state = {}
    meta = asyncio.run(p.resolve_page_context({"document_title": "Nur Titel"}, state))
    assert meta["source"] == "document_title_only"
    assert meta["title"] == "Nur Titel"
    assert meta["unresolved"] is True
    assert state["entities"]["_page_metadata"]["title"] == "Nur Titel"


def test_resolve_no_signature_no_title_returns_none():
    assert asyncio.run(p.resolve_page_context({"search_query": "x"}, {})) is None


def test_resolve_node_id_path_success(monkeypatch):
    async def fake_call(tool, args):
        assert tool == "get_node_details"
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Bruchrechnung",
            "disciplines": ["Mathematik"], "educationalContexts": ["Sek I"],
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context({"node_id": "abc-123"}, state))
    assert meta["title"] == "Bruchrechnung"
    assert meta["source"] == "get_node_details"
    assert meta["unresolved"] is False
    assert meta["disciplines"] == ["Mathematik"]
    assert state["entities"]["_page_metadata"]["title"] == "Bruchrechnung"


def test_resolve_mcp_error_falls_back_to_title(monkeypatch):
    async def fake_call(tool, args):
        return "MCP error: upstream down"

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "abc-123", "document_title": "Seite X"}, {}))
    assert meta["source"] == "fallback_title"
    assert meta["title"] == "Seite X"
    assert meta["unresolved"] is True


def test_resolve_returns_cached_when_fresh(monkeypatch):
    called = {"n": 0}

    async def fake_call(tool, args):
        called["n"] += 1
        return "MCP error"

    _patch_mcp(monkeypatch, fake_call)
    sig = p._current_context_signature({"node_id": "abc"})
    state = _state_with(
        {"title": "Cached", "_signature": sig, "_resolved_at": time.time(), "unresolved": False}
    )
    meta = asyncio.run(p.resolve_page_context({"node_id": "abc"}, state))
    assert meta["title"] == "Cached"
    assert called["n"] == 0  # frischer Cache → kein MCP-Call


# ── T7/T8: kompendialer Text + Volltext (2026-07-10 Seitenkontext) ─────────

def test_extract_surfaces_compendium_and_textcontent():
    raw = json.dumps({
        "nodeId": "c1", "title": "Optik", "disciplines": ["Physik"],
        "compendiumText": "Die Optik ist ein Teilgebiet der Physik.",
        "textContent": "Langer Volltext des Materials.",
    })
    out = p._extract_node_fields(raw)
    assert out["compendium_text"] == "Die Optik ist ein Teilgebiet der Physik."
    assert out["text_content"] == "Langer Volltext des Materials."


def test_extract_no_compendium_fields_are_blank():
    raw = json.dumps({"nodeId": "c1", "title": "X", "disciplines": ["Y"]})
    out = p._extract_node_fields(raw)
    assert out["compendium_text"] == ""
    assert out["text_content"] == ""


def test_resolve_content_page_requests_textcontent(monkeypatch):
    seen = {}

    async def fake_call(tool, args):
        seen["args"] = args
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Material", "disciplines": [],
            "textContent": "Volltext hier", "compendiumText": "Komp",
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "abc", "page_kind": "content"}, state))
    assert seen["args"].get("includeTextContent") is True
    assert meta["text_content"] == "Volltext hier"


def test_resolve_collection_page_omits_textcontent(monkeypatch):
    seen = {}

    async def fake_call(tool, args):
        seen["args"] = args
        return json.dumps({
            "nodeId": args["nodeId"], "title": "Sammlung", "disciplines": [],
            "compendiumText": "Kompendialer Text",
        })

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"collection_id": "C1", "page_kind": "collection"}, state))
    assert "includeTextContent" not in seen["args"]
    assert meta["compendium_text"] == "Kompendialer Text"


def test_render_includes_compendium_block_and_curation_hint():
    meta = {"title": "Optik", "compendium_text": "Sollinhalt der Sammlung."}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})
    assert "Kompendium" in out
    assert "Sollinhalt der Sammlung." in out
    assert "Lücken" in out  # Kuratier-Instruktion (Soll-vs-Ist) nur bei vorhandenem Kompendium


def test_render_compendium_trims_to_budget():
    meta = {"title": "X", "compendium_text": "K" * 5000}
    out = p.render_for_prompt(meta, {"page_kind": "collection"})
    assert "…" in out
    assert "K" * 4001 not in out  # auf ~4000er-Budget gekürzt


def test_render_includes_textcontent_block_for_content():
    meta = {"title": "Material", "text_content": "Voller Text des Materials."}
    out = p.render_for_prompt(meta, {"page_kind": "content", "node_id": "N1"})
    assert "Voller Text des Materials." in out


def test_render_includes_publisher_filter_line():
    meta = {"title": "Suchergebnisse"}
    pc = {"page_kind": "search", "search_filters": {"publisher": ["Serlo"]}}
    out = p.render_for_prompt(meta, pc)
    assert "Serlo" in out


def test_render_without_compendium_or_textcontent_is_unchanged():
    meta = {"title": "T", "disciplines": ["Mathe"]}
    out = p.render_for_prompt(meta, {"page_kind": "collection", "collection_id": "C1"})
    assert "Kompendium" not in out
    assert "Volltext" not in out


# ── prompt_block: darf keinen Zug kosten, aber auch nicht still ausfallen ──


def test_ein_fehler_im_seitenblock_kostet_keinen_zug(monkeypatch, caplog):
    """``prompt_block`` faengt alles — der Block ist Zusatzwissen, nicht die
    Aufgabe. Lautlos darf der Ausfall trotzdem nicht sein.

    Faellt er aus, ist der Agent wieder blind fuer die Seite (Befund B-2, den
    P4 gerade behoben hat) — und das ist von „diese Seite hat keinen Kontext"
    nicht zu unterscheiden. Auf ``debug`` sieht das im Betrieb niemand; der
    Nachbar im selben Paket (``agent_prefetch``) meldet denselben Fall als
    WARNING.
    """
    def _kaputt(*_a, **_k):
        raise RuntimeError("Renderer kaputt")

    monkeypatch.setattr(p, "render_for_prompt", _kaputt)
    with caplog.at_level(logging.WARNING, logger=p.__name__):
        assert p.prompt_block({}, {"page_kind": "collection", "collection_id": "C1"}) == ""
    assert [r for r in caplog.records if r.levelno >= logging.WARNING], (
        "der Ausfall wurde nicht gemeldet"
    )


# ── V1 (2026-08-20): MCP-Deploy — Details-JSON trägt nur noch das Signal ────
# Gemessen live: der Optik-Treffer kam mit ``hasCompendium: true`` und OHNE
# ``compendiumText``; get_node_details liefert im JSON denselben Stand. Ohne
# Nachladen wäre der Kompendium-Block des Seitenkontexts seit dem Deploy leer.

def test_hascompendium_signal_loest_nachladen_aus(monkeypatch):
    calls = []

    async def fake_call(tool, args):
        calls.append((tool, dict(args)))
        if tool == "get_node_details":
            return json.dumps({
                "nodeId": args["nodeId"], "title": "Optik",
                "disciplines": ["Physik"], "hasCompendium": True,
            })
        assert tool == "get_compendium_text"
        return "## Optik\nDie Optik ist ein Teilgebiet der Physik."

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context({"collection_id": "c-optik"}, {}))
    assert "Teilgebiet der Physik" in meta["compendium_text"]
    assert ("get_compendium_text", {"nodeId": "c-optik"}) in calls


def test_ohne_signal_kein_nachladen(monkeypatch):
    calls = []

    async def fake_call(tool, args):
        calls.append(tool)
        return json.dumps({"nodeId": args["nodeId"], "title": "Arbeitsblatt",
                           "disciplines": ["Mathematik"]})

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context({"node_id": "m-1"}, {}))
    assert meta["compendium_text"] == ""
    assert calls == ["get_node_details"]


def test_inline_text_gewinnt_kein_zweitaufruf(monkeypatch):
    """Alte Server-Stände liefern den Text noch inline — dann kein Nachladen."""
    calls = []

    async def fake_call(tool, args):
        calls.append(tool)
        return json.dumps({"nodeId": args["nodeId"], "title": "Optik",
                           "disciplines": ["Physik"], "hasCompendium": True,
                           "compendiumText": "Inline-Text."})

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context({"collection_id": "c-1"}, {}))
    assert meta["compendium_text"] == "Inline-Text."
    assert calls == ["get_node_details"]


def test_nachlade_fehler_laesst_den_kontext_bestehen(monkeypatch):
    async def fake_call(tool, args):
        if tool == "get_node_details":
            return json.dumps({"nodeId": args["nodeId"], "title": "Optik",
                               "disciplines": ["Physik"], "hasCompendium": True})
        return "MCP error: upstream down"

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context({"collection_id": "c-1"}, {}))
    assert meta["title"] == "Optik"
    assert meta["unresolved"] is False
    assert meta["compendium_text"] == ""


# ── Z2 (2026-08-20): gescheiterte Aufloesung verschluckt die Node-ID nicht ──
# Live-Befund (edu-sharing Prueftisch, anonymer Bot): die Seite reicht eine
# node_id, get_node_details scheitert an den Leserechten, und der GANZE
# Seitenblock verschwand — das Modell fragte den Nutzer nach der ID, die
# laengst vorlag.


def test_resolve_unaufloesbare_node_id_liefert_meta_statt_none(monkeypatch):
    async def fake_call(tool, args):
        return "MCP-Fehler: 403 Forbidden"

    _patch_mcp(monkeypatch, fake_call)
    monkeypatch.setattr(p, "is_mcp_error", lambda raw: True)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "765efba2-x", "page_kind": "content"}, state))
    assert meta is not None
    assert meta["unresolved"] is True
    assert meta["node_id"] == "765efba2-x"
    assert meta["title"]                       # Block braucht einen Titel
    assert state["entities"]["_page_metadata"]["node_id"] == "765efba2-x"


def test_resolve_unaufloesbar_behaelt_document_title(monkeypatch):
    async def fake_call(tool, args):
        return ""

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "abc-1", "document_title": "Redaktion - edu-sharing"}, state))
    assert meta["title"] == "Redaktion - edu-sharing"
    assert meta["unresolved"] is True
    assert meta["node_id"] == "abc-1"


def test_render_unaufgeloest_nennt_id_und_warnt_vor_nachfrage():
    meta = {"title": "Redaktion - edu-sharing", "unresolved": True,
            "node_id": "765efba2-x"}
    out = p.render_for_prompt(meta, {"page_kind": "content",
                                     "node_id": "765efba2-x"})
    assert "Node-ID: 765efba2-x" in out
    assert "NICHT" in out and "Leserechte" in out
    # Der Ausweg steht dabei: Transkript/Text erbitten oder Anmeldung.
    assert "Transkript" in out or "Anmeldung" in out


def test_render_aufgeloestes_meta_traegt_keinen_unresolved_hinweis():
    meta = {"title": "Bruchrechnung", "unresolved": False}
    out = p.render_for_prompt(meta, {"page_kind": "content", "node_id": "n-1"})
    assert "Leserechte" not in out


def test_render_unaufgeloest_mit_seitentext_liefert_den_text_statt_transkript_bitte():
    """EK1 (2026-08-20, Live-Befund Prüftisch): der Rahmen liefert den sichtbaren
    Seitentext mit, aber seit Z2 ist der unaufgelöste Block nie leer — der
    ``or``-Rückfall auf ``render_raw_for_prompt`` griff nicht mehr, und die
    Z2-Note bat um ein Transkript, das im Request längst stand. Liegt
    ``page_text`` vor, gehört er in den Block, und die Note zeigt auf ihn."""
    meta = {"title": "Redaktion - edu-sharing", "unresolved": True, "node_id": "n-1"}
    pc = {"page_kind": "content", "node_id": "n-1",
          "page_text": "Kategorie des Inhalts Person Gordon Bunshaft Lebensdaten"}
    out = p.render_for_prompt(meta, pc)
    assert "Gordon Bunshaft" in out          # der Text steht im Block
    assert "Sichtbarer Text" in out
    assert "Transkript" not in out           # keine Bitte um längst Vorhandenes
    assert "Leserechte" in out               # die ehrliche Ansage bleibt


def test_render_unaufgeloest_ohne_seitentext_bittet_weiter_um_transkript():
    meta = {"title": "X", "unresolved": True, "node_id": "n-1"}
    out = p.render_for_prompt(meta, {"page_kind": "content", "node_id": "n-1"})
    assert "Transkript" in out or "Anmeldung" in out


def test_render_aufgeloest_ignoriert_den_heuristischen_seitentext():
    """Aufgelöst schlägt Heuristik: der Bestand liefert ``text_content``, der
    DOM-Harvest wäre daneben nur Rauschen (und doppelte Prompt-Kosten)."""
    meta = {"title": "Bruchrechnung", "unresolved": False, "text_content": "Echter Text."}
    pc = {"page_kind": "content", "node_id": "n-1", "page_text": "DOM-Harvest"}
    out = p.render_for_prompt(meta, pc)
    assert "DOM-Harvest" not in out


def test_render_unaufgeloester_seitentext_haelt_das_budget():
    # 3000 wie ``text_content``: der Seitentext ist hier die EINZIGE Inhalts-
    # quelle, und auf dem Prüftisch liegen vor dem Metadaten-Formular ~1800
    # Zeichen Listen-Harvest — ein 1500er-Budget schnitte genau das Wertvolle ab.
    meta = {"title": "X", "unresolved": True, "node_id": "n-1"}
    out = p.render_for_prompt(
        meta, {"page_kind": "content", "node_id": "n-1", "page_text": "T" * 5000})
    assert "T" * 3001 not in out
    assert "T" * 2500 in out


def test_render_editorial_traegt_erschliessungs_rahmen():
    """EK2: auf dem Prüftisch ist die Überschrift die Situation (Erschließung),
    nicht „Inhaltsseite" — und eine Regelzeile sagt dem Modell, was hier
    gefragt ist: Hinweise zum Inhalt, Sammlungs-Vorschläge, Metadaten-Hilfe."""
    meta = {"title": "Redaktion - edu-sharing", "unresolved": True, "node_id": "n-1"}
    out = p.render_for_prompt(meta, {"page_kind": "editorial", "node_id": "n-1"})
    assert "Erschließung" in out
    assert "Sammlung" in out


def test_resolve_editorial_holt_den_volltext(monkeypatch):
    seen = {}

    async def fake_call(tool, args):
        seen["args"] = args
        return ""

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    asyncio.run(p.resolve_page_context(
        {"node_id": "n-1", "page_kind": "editorial"}, state))
    assert seen["args"].get("includeTextContent") is True


def test_render_ohne_id_nimmt_den_seitentext_trotzdem_auf():
    """EK3 (Review-Befund B, 2026-08-20): fremde Seiten haben KEINE auflösbare
    ID — der Resolver baut aus dem Tab-Titel ein Minimal-Meta, und weil ein Meta
    mit Titel den Block nie leer lässt, griff auch dort der ``or``-Rückfall auf
    ``render_raw_for_prompt`` nicht mehr. Der geerntete Seitentext lag ungenutzt
    im Request, während das Modell blind urteilte oder einen Werkzeug-Rundlauf
    für Text zahlte, den es schon hatte. Die Rechte-Note gehört NICHT dazu: auf
    einer fremden Seite fehlen keine Leserechte, sie ist einfach kein WLO-Objekt.
    """
    meta = {"title": "Gordon Bunshaft – Wikipedia", "unresolved": True}
    pc = {"page_kind": "external", "page_host": "de.wikipedia.org",
          "page_text": "Gordon Bunshaft war ein US-amerikanischer Architekt."}
    out = p.render_for_prompt(meta, pc)
    assert "Sichtbarer Text" in out
    assert "US-amerikanischer Architekt" in out
    assert "Leserechte" not in out       # keine Rechte-Erklärung ohne ID
    assert "Transkript" not in out


def test_render_ohne_id_und_ohne_seitentext_bleibt_stumm():
    meta = {"title": "Irgendeine Seite", "unresolved": True}
    out = p.render_for_prompt(meta, {"page_kind": "external",
                                     "page_host": "example.org"})
    assert "Sichtbarer Text" not in out
    assert "Irgendeine Seite" in out     # der Block selbst bleibt


def test_resolve_akzeptiert_title_als_alias_fuer_document_title(monkeypatch):
    """EK8 (Live-Befund Prüftisch 2026-08-21): der Repo-Rahmen sendet den
    Seitentitel als ``title``, nicht als ``document_title`` — das Widget setzt
    letzteres nur aus der EIGENEN Erkennung. Ohne Alias fiel der Titel durch,
    und der Gruß/Prompt zitierte den Z2-Platzhalter „Seite mit nicht
    auflösbarem Inhalt" als wäre er der Seitenname."""
    async def fake_call(tool, args):
        return ""

    _patch_mcp(monkeypatch, fake_call)
    state = {}
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "n-1", "title": "Redaktion - edu-sharing"}, state))
    assert meta["title"] == "Redaktion - edu-sharing"
    assert meta["unresolved"] is True


def test_resolve_document_title_schlaegt_den_alias(monkeypatch):
    # Beide gesetzt: das ausdrücklich benannte Feld gewinnt.
    async def fake_call(tool, args):
        return ""

    _patch_mcp(monkeypatch, fake_call)
    meta = asyncio.run(p.resolve_page_context(
        {"node_id": "n-1", "document_title": "Eigenes Feld",
         "title": "Alias"}, {}))
    assert meta["title"] == "Eigenes Feld"


def test_resolve_ohne_ids_nutzt_den_title_alias():
    # Der signaturlose Minimal-Rückfall (nur Titel, keine ID) kennt den Alias
    # ebenfalls — fremde Seiten mit Rahmen-Kontext bekommen sonst gar kein Meta.
    meta = asyncio.run(p.resolve_page_context(
        {"title": "Gordon Bunshaft – Wikipedia"}, {}))
    assert meta is not None
    assert meta["title"] == "Gordon Bunshaft – Wikipedia"
