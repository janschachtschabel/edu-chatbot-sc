"""Charakterisierungs-Pins für den Tool-Definitions-Leaf des MCP-Pakets.

1:1-Port aus ALT ``tests/test_mcp_tool_defs.py``: statische Tool-Schemas
(``TOOL_DEFINITIONS``, ``_TOOL_ARG_MODELS``, ``_JSON_CAPABLE_TOOLS``) + die reine
Validierung (``validate_tool_args``), ohne geteilten Zustand. Deviation ggü. ALT:
Import aus ``boerdi.services.mcp.tool_defs`` (in ALT lief er über die
``mcp_client``-Re-Export-Fassade, die im Neubau erst mit 5-1 entsteht).
"""

from __future__ import annotations

from boerdi.services.mcp.tool_defs import (
    _JSON_CAPABLE_TOOLS,
    _TOOL_ARG_MODELS,
    TOOL_DEFINITIONS,
    validate_tool_args,
)


# ── validate_tool_args ──────────────────────────────────────────────────
def test_unknown_tool_passes_args_through_unchanged():
    assert validate_tool_args("__unknown__", {"a": 1, "b": ""}) == {"a": 1, "b": ""}


def test_known_tool_applies_defaults():
    # search_wlo_content → SearchWloArgs setzt maxResults=5 als Default.
    assert validate_tool_args("search_wlo_content", {"query": "mathe"}) == {
        "query": "mathe", "maxResults": 5,
    }


def test_known_tool_empty_args_stay_empty():
    assert validate_tool_args("wlo_health_check", {}) == {}


def test_explicit_false_bool_arg_is_preserved():
    # NOTE: Fix 2026-07-10 (C7) — der Export-Filter darf explizite False/0-Werte
    # NICHT droppen. Früher fraß ``v != 0`` (wegen ``False == 0`` in Python) auch
    # Bool-False, z.B. get_subject_portals.includeContentCounts=False (leerer
    # educationalContext bleibt korrekt weg-gefiltert).
    out = validate_tool_args("get_subject_portals", {"includeContentCounts": False})
    assert out == {"includeContentCounts": False}


# ── statische Definitionen ──────────────────────────────────────────────
def test_tool_definitions_shape():
    assert isinstance(TOOL_DEFINITIONS, list) and TOOL_DEFINITIONS
    for td in TOOL_DEFINITIONS:
        assert td.get("type") == "function"
        assert td["function"]["name"]
    names = {td["function"]["name"] for td in TOOL_DEFINITIONS}
    assert "search_wlo_collections" in names


# ── W4-1: was wir dem LLM über die Tools sagen, muss stimmen ────────────
def _tool(name: str) -> dict:
    return next(t["function"] for t in TOOL_DEFINITIONS if t["function"]["name"] == name)


def test_collection_search_does_not_offer_unknown_user_role_param():
    # Gegen das Server-Schema geprüft (2026-07-30): ``search_wlo_collections``
    # kennt query/parentNodeId/educationalContext/discipline/excludeNodeIds/
    # maxResults/outputFormat — KEIN userRole. Ein Parameter, den wir dem Modell
    # anbieten und der Server stumm verwirft, kostet Tokens und erzeugt beim
    # Modell die falsche Annahme, die Eingrenzung habe gewirkt. Dieselbe
    # Fehlerklasse wie ``discipline`` bei den Themenseiten (W2-2).
    assert "userRole" not in _tool("search_wlo_collections")["parameters"]["properties"]


def test_content_search_keeps_user_role_param():
    # Gegenprobe: dort gibt es ihn im Server-Schema wirklich.
    assert "userRole" in _tool("search_wlo_content")["parameters"]["properties"]


def test_collection_search_description_does_not_equate_collections_with_topic_pages():
    # W3 hat gemessen: Sammlungen sind NICHT Themenseiten — nur ein Bruchteil
    # trägt eine Seiten-Konfiguration, und dafür gibt es ein eigenes Tool. Die
    # Gleichsetzung schickte das Modell mit der Themenseiten-Frage in die
    # Sammlungs-Suche.
    beschreibung = _tool("search_wlo_collections")["description"]
    assert "= Themenseiten" not in beschreibung
    assert "search_wlo_topic_pages" in beschreibung


def test_json_capable_tools_is_frozenset_with_known_member():
    assert isinstance(_JSON_CAPABLE_TOOLS, frozenset)
    assert "search_wlo_content" in _JSON_CAPABLE_TOOLS


def test_content_text_tool_is_offered_to_the_model():
    # W5-3b: ohne Eintrag in TOOL_DEFINITIONS kann das Modell den Volltext gar
    # nicht anfordern — genau das fehlte für „zeig mir den Inhalt".
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    assert "get_wlo_content_text" in names


def test_content_text_tool_offers_max_chars():
    props = _tool("get_wlo_content_text")["parameters"]["properties"]
    assert "nodeId" in props
    assert "maxChars" in props


def test_content_text_tool_is_requested_as_json():
    # W5-3a: Der Server kann für dieses Tool JSON (content-text.ts:36) und legt
    # dort ``reason``/``source``/``truncated`` hinein. In Markdown fehlen sie —
    # dann ist „kein Volltext" nicht von „Material ist gesperrt" zu trennen.
    assert "get_wlo_content_text" in _JSON_CAPABLE_TOOLS


def test_tool_arg_models_covers_registered_tools():
    assert isinstance(_TOOL_ARG_MODELS, dict)
    assert "search_wlo_content" in _TOOL_ARG_MODELS
    assert "wlo_health_check" in _TOOL_ARG_MODELS


# ── W9a: vier Einordnungs-Werkzeuge des neuen Servers ───────────────────
# Schemata am 2026-08-01 per ``tools/list`` VOM SERVER geholt, nicht abgetippt —
# W4-1 hatte gezeigt, dass abgetippte Kopien driften.
_W9A_TOOLS = (
    "get_collection_stats",
    "get_node_breadcrumb",
    "get_compendium_text",
    "lookup_wlo_publishers",
)


def test_w9a_tools_are_offered_to_the_model():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    fehlend = [n for n in _W9A_TOOLS if n not in names]
    assert not fehlend, f"nicht angeboten: {fehlend}"


def test_w9a_tools_have_an_argument_model():
    # Ohne Modell reicht ``validate_tool_args`` die Roh-Argumente des Modells
    # ungeprüft an den Server durch — genau da entstehen still ignorierte Filter.
    fehlend = [n for n in _W9A_TOOLS if n not in _TOOL_ARG_MODELS]
    assert not fehlend, f"ohne Argument-Modell: {fehlend}"


def test_w9a_tools_stay_on_markdown():
    # Bewusst NICHT in _JSON_CAPABLE_TOOLS: wir parsen diese Antworten nicht,
    # das Modell liest sie direkt. Markdown ist dafür lesbarer und kürzer.
    drin = [n for n in _W9A_TOOLS if n in _JSON_CAPABLE_TOOLS]
    assert not drin, f"unnötig auf JSON gestellt: {drin}"


def test_collection_stats_requires_a_node_id():
    props = _tool("get_collection_stats")["parameters"]["properties"]
    assert "nodeId" in props
    assert _tool("get_collection_stats")["parameters"]["required"] == ["nodeId"]


def test_compendium_text_offers_one_node_at_a_time():
    # Der Server kann auch ``nodeIds`` (Mehrfach-Abruf). Wir bieten es dem
    # Modell BEWUSST nicht an: der Export-Filter in ``validate_tool_args``
    # entfernt nur leere Strings, eine leere Liste ginge als ``nodeIds: []``
    # mit raus. Ein Kompendium je Aufruf kostet einen Roundtrip mehr und
    # spart eine Sonderbehandlung — Bündelung ist eine Optimierung, die kein
    # Anwendungsfall verlangt.
    props = _tool("get_compendium_text")["parameters"]["properties"]
    assert "nodeId" in props
    assert "nodeIds" not in props


def test_publishers_lookup_can_be_scoped():
    props = _tool("lookup_wlo_publishers")["parameters"]["properties"]
    for p in ("query", "discipline", "educationalContext", "maxResults"):
        assert p in props, p


def test_compendium_text_keeps_a_single_node():
    assert validate_tool_args("get_compendium_text", {"nodeId": "abc"}) == {"nodeId": "abc"}


# ── W9c: Server-Fakten in die Beschreibungen, Fähigkeiten anbieten ──────
def test_every_offered_parameter_is_accepted_by_its_argument_model():
    """Ein angebotener Parameter, den das Modell nicht kennt, verschwindet STILL.

    ``validate_tool_args`` baut das Pydantic-Modell und exportiert dessen Felder
    — was das Modell nicht deklariert, fällt beim ``model_dump`` heraus, ohne
    Fehler. Das LLM sähe den Parameter in der Werkzeug-Beschreibung, füllte ihn
    aus, und der Server bekäme ihn nie. Diese Richtung muss lückenlos sein.
    """
    unbekannt = {}
    for t in TOOL_DEFINITIONS:
        name = t["function"]["name"]
        modell = _TOOL_ARG_MODELS.get(name)
        if modell is None:
            continue
        angeboten = set((t["function"]["parameters"].get("properties") or {}).keys())
        fehlt = sorted(angeboten - set(modell.model_fields))
        if fehlt:
            unbekannt[name] = fehlt
    assert not unbekannt, f"Parameter würden still verworfen: {unbekannt}"


def test_node_details_can_fetch_the_quick_text_variant():
    # W9c: ``includeTextContent`` liefert nachweislich Text (live 2026-08-01:
    # 2444 bzw. 4011 Zeichen). Die Beschreibung sagt dazu, dass
    # get_wlo_content_text der bessere Weg ist, wenn der Text WIRKLICH gebraucht
    # wird — dieses Feld hat keinen Rückfall auf die verlinkte Seite.
    props = _tool("get_node_details")["parameters"]["properties"]
    assert "includeTextContent" in props


def test_node_details_does_not_promise_the_parent_collections():
    """``includeParents`` bleibt draußen — der Server liefert es nicht.

    Live geprüft 2026-08-01 an vier Materialien, darunter zwei, die
    nachweislich in „Biologie-Breakouts" liegen: ``parents`` kam jedes Mal als
    leere Liste. Der Server dokumentiert die Fähigkeit („useful to find which
    Sammlung a content item is in"), erfüllt sie aber nicht. Angeboten hätte das
    Modell dem Nutzer „liegt in keiner Sammlung" geantwortet — eine falsche
    Auskunft ist schlimmer als eine fehlende.
    """
    props = _tool("get_node_details")["parameters"]["properties"]
    assert "includeParents" not in props


def test_node_details_does_not_offer_the_raw_uris():
    # ``includeRaw`` liefert die ccm:*/cclom:*-Roh-URIs — ein Debug-Werkzeug.
    # Im Modell-Kontext wäre es nur Ballast, der die Antwortlänge frisst.
    props = _tool("get_node_details")["parameters"]["properties"]
    assert "includeRaw" not in props


def test_collection_tree_accepts_a_subject_name_instead_of_a_node_id():
    # Der Server löst einen Fachportal-Namen („Mathematik") selbst auf. Ohne
    # diesen Parameter braucht „zeig mir die Unterthemen von Mathematik" erst
    # einen get_subject_portals-Aufruf — ein vermeidbarer Netz-Roundtrip.
    t = _tool("browse_collection_tree")
    assert "subject" in t["parameters"]["properties"]
    assert "required" not in t["parameters"], "nodeId darf nicht mehr Pflicht sein"


def test_topic_page_content_can_resolve_a_topic_in_one_call():
    # Der Server nimmt einen Themennamen direkt und sucht die Themenseite selbst
    # (dieselbe Zusammenlegung, die W5-1 im M16-Resolver schon nutzt). Unsere
    # Beschreibung verlangte vorher „erst search_wlo_topic_pages" — ein
    # vermeidbarer zweiter Aufruf pro Themenseiten-Anfrage.
    props = _tool("get_topic_page_content")["parameters"]["properties"]
    assert "query" in props


def test_search_all_flags_that_only_the_content_total_is_real():
    # Wahrhaftigkeit: laut Server ist nur ``content.total`` die echte
    # Backend-Trefferzahl; ``collections.total``/``topicPages.total`` sind bloß
    # die angezeigte Anzahl. Ohne diesen Hinweis nennt der Bot dem Nutzer eine
    # Gesamtzahl, die es so nicht gibt.
    beschr = _tool("search_wlo_all")["description"]
    assert "content.total" in beschr


def test_collection_tree_warns_about_truncated_branches():
    # Wahrhaftigkeit: der Server deckelt Breite und Tiefe und markiert gekappte
    # Zweige mit ``hasMoreChildren``. Ohne diesen Hinweis stellt das Modell eine
    # unvollständige Auswahl als vollständig dar.
    beschr = _tool("browse_collection_tree")["description"]
    assert "hasMoreChildren" in beschr


# ── W9b: die zwei Karten-Werkzeuge ──────────────────────────────────────
_W9B_TOOLS = ("search_wlo_within_collection", "get_related_content")


def test_w9b_tools_are_offered_to_the_model():
    names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
    fehlend = [n for n in _W9B_TOOLS if n not in names]
    assert not fehlend, f"nicht angeboten: {fehlend}"


def test_w9b_tools_have_an_argument_model():
    fehlend = [n for n in _W9B_TOOLS if n not in _TOOL_ARG_MODELS]
    assert not fehlend, f"ohne Argument-Modell: {fehlend}"


def test_w9b_tools_are_requested_as_json():
    # Anders als die W9a-Werkzeuge PARSEN wir diese Antworten (sie werden zu
    # Karten). Nur der JSON-Envelope trägt die label-aufgelösten Felder.
    fehlend = [n for n in _W9B_TOOLS if n not in _JSON_CAPABLE_TOOLS]
    assert not fehlend, f"nicht auf JSON gestellt: {fehlend}"


def test_within_collection_requires_the_collection():
    t = _tool("search_wlo_within_collection")
    assert t["parameters"]["required"] == ["nodeId"]
    assert "query" in t["parameters"]["properties"]


def test_related_content_requires_the_seed_node():
    t = _tool("get_related_content")
    assert t["parameters"]["required"] == ["nodeId"]


def test_publishers_lookup_caps_max_results():
    # Server-Default 20. Ein Modell, das 500 anfordert, würde die Antwort und
    # damit den Kontext des nächsten Zuges sprengen.
    out = validate_tool_args("lookup_wlo_publishers", {"maxResults": 500})
    assert out["maxResults"] <= 50, out


# ── W10: Obergrenzen müssen greifen, nicht nur dastehen ─────────────────
# Befund 2026-08-01: ``Field(le=…)`` war auf allen Bestands-Werkzeugen reine
# Dekoration. ``validate_tool_args`` fängt die ValidationError ab und reicht die
# ROHEN Argumente weiter — ein ``maxResults: 100`` gegen ``le=20`` landete also
# ungebremst beim Server. Genau der Fall, für den die Grenze existiert.
def test_ueberschrittene_obergrenze_wird_geklemmt_statt_durchgereicht():
    out = validate_tool_args("search_wlo_content", {"query": "mathe", "maxResults": 100})
    assert out["maxResults"] == 20, out


def test_klemmen_greift_auch_ueber_den_alten_namen_maxItems():
    """Der Alias läuft durch den Pre-Validator; pydantic meldet im Fehler den
    KANONISCHEN Namen (gemessen 2026-08-01) — die Reparatur trifft ihn deshalb."""
    out = validate_tool_args("search_wlo_collections", {"query": "x", "maxItems": 100})
    assert out["maxResults"] == 20, out
    assert "maxItems" not in out


def test_unterschrittene_untergrenze_wird_ebenso_geklemmt():
    out = validate_tool_args("get_collection_contents", {"nodeId": "n", "skipCount": -5})
    assert out["skipCount"] == 0, out


def test_zwei_verletzte_grenzen_in_einem_aufruf_werden_beide_geklemmt():
    out = validate_tool_args(
        "browse_collection_tree", {"nodeId": "n", "depth": 9, "maxResults": 999}
    )
    assert (out["depth"], out["maxResults"]) == (2, 100), out


def test_fehlendes_pflichtfeld_faellt_weiter_auf_die_rohargumente_zurueck():
    """Nur Grenzverletzungen werden repariert. Ein fehlendes Pflichtfeld kann die
    Reparatur nicht erfinden — dort bleibt der bisherige Fail-Open-Pfad."""
    assert validate_tool_args("get_collection_contents", {"query": "x"}) == {"query": "x"}


def test_nicht_zahliger_wert_faellt_weiter_auf_die_rohargumente_zurueck():
    roh = {"maxResults": "viele"}
    assert validate_tool_args("search_wlo_content", roh) == roh


def test_die_beiden_w9b_werkzeuge_klemmen_weiterhin():
    """W9a/W9b hatten je einen handgeschriebenen Klemm-Validator, weil die
    deklarative Grenze nicht trug. Der generische Reparaturschritt ersetzt sie —
    diese Pins halten das Verhalten über den Umbau fest."""
    innerhalb = validate_tool_args(
        "search_wlo_within_collection", {"nodeId": "n", "maxResults": 500}
    )
    verwandt = validate_tool_args("get_related_content", {"nodeId": "n", "maxResults": 500})
    assert (innerhalb["maxResults"], verwandt["maxResults"]) == (20, 20)


# ── W10/C: der statische Werkzeug-Prompt darf nichts Unbekanntes nennen ──
def test_der_werkzeug_prompt_nennt_nur_werkzeuge_die_es_wirklich_gibt():
    """``render_tools_block`` ist ALT-verbatim und zählt die MCP-Werkzeuge
    NAMENTLICH auf — statisch, unabhängig von der aktiven Tool-Liste des Musters.
    Wird eines umbenannt oder entfernt, verspricht der Prompt dem Modell etwas,
    das der Katalog nicht mehr kennt, ohne dass irgendwo etwas auffiele.
    """
    import re

    from boerdi.services.response_prompt_tools_text import render_tools_block

    block = render_tools_block({}, None, None, "de")
    genannt = set(re.findall(r"^- ([a-z_]+):", block, re.MULTILINE))
    bekannt = {t["function"]["name"] for t in TOOL_DEFINITIONS} | {"query_knowledge"}
    assert genannt, "Regex greift nicht mehr — der Block hat sein Format geändert"
    assert not (genannt - bekannt), (
        f"Der Prompt nennt Werkzeuge, die es nicht gibt: {sorted(genannt - bekannt)}"
    )


# ── R5 (2026-08-11): was die Grenzen WIRKLICH leisten ────────────────────
# ``validate_tool_args`` repariert nur ``ge``/``le``; jeder andere Fehler faellt
# auf die ROHEN Argumente zurueck. Damit war ``max_length`` Dekoration und
# ``extra="forbid"`` sogar irrefuehrend: die erfundene Angabe reiste weiter.
# Diese drei Pins halten fest, was gilt — der erste war der Fix, die beiden
# anderen halten die verbleibende Fail-Open-Kante sichtbar.


def test_erfundene_angabe_an_einem_argumentlosen_werkzeug_verschwindet():
    """``wlo_auth_status`` nimmt ein leeres Objekt. Eine erfundene Angabe darf
    den Server nicht erreichen — sonst kuendigt unsere Validierung etwas an,
    das sie nicht einloest."""
    assert validate_tool_args("wlo_auth_status", {"erfunden": "x"}) == {}


def test_zu_lange_zeichenkette_reist_unveraendert_weiter():
    """Bewusst NICHT geklemmt: eine auf 2000 Zeichen gekuerzte Adresse waere
    eine ANDERE Adresse. Der Server lehnt sie ab; unsere Grenze dokumentiert
    seine und erzeugt die Protokollzeile. Gepinnt, damit niemand mehr eine
    Kappung annimmt."""
    lang = "https://e.org/" + "a" * 3000
    assert validate_tool_args("get_url_text", {"url": lang})["url"] == lang


def test_zahlgrenzen_klemmen_weiterhin():
    """Die Gegenprobe zum Test darueber: der W10-Reparaturschritt bleibt heil."""
    out = validate_tool_args("get_url_text", {"url": "https://e.org/", "maxChars": 99999})
    assert out["maxChars"] == 50000
