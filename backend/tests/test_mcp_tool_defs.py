"""Charakterisierungs-Pins für den Tool-Definitions-Leaf des MCP-Pakets.

1:1-Port aus ALT ``tests/test_mcp_tool_defs.py``: statische Tool-Schemas
(``TOOL_DEFINITIONS``, ``_TOOL_ARG_MODELS``, ``_JSON_CAPABLE_TOOLS``) + die reine
Validierung (``validate_tool_args``), ohne geteilten Zustand. Deviation ggü. ALT:
Import aus ``boerdi.services.mcp.tool_defs`` (in ALT lief er über die
``mcp_client``-Re-Export-Fassade, die im Neubau erst mit 5-1 entsteht).
"""

from __future__ import annotations

from boerdi.services.mcp.tool_args import (
    _JSON_CAPABLE_TOOLS,
    _TOOL_ARG_MODELS,
    validate_tool_args,
)
from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS


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


# Die REIHENFOLGE ist tragend, nicht kosmetisch: ``_select_active_tools``
# reicht ``list(TOOL_DEFINITIONS)`` unverändert an den LLM-Aufruf durch, der
# Katalog geht also genau so in den Prompt. Eine Umsortierung ist deshalb keine
# Formatierung, sondern eine Verhaltensänderung — sie kippte schon einmal zwei
# fremde Tests (siehe Docstring von ``response_tool_selection``). Alle übrigen
# Prüfungen hier arbeiten mit ``set(...)`` und würden das nicht bemerken.
#
# Der Pin schlägt ABSICHTLICH auch bei einem neuen Werkzeug an: wer eines
# ergänzt, soll die Einfügeposition bewusst wählen und hier nachtragen, statt
# sie dem Zufall des Anhängens zu überlassen.
_TOOL_ORDER = [
    "get_wlo_content_text",
    "get_collection_stats",
    "get_node_breadcrumb",
    "get_compendium_text",
    "lookup_wlo_publishers",
    "search_wlo_within_collection",
    "get_related_content",
    "get_node_collections",
    "search_skill",
    "get_skill",
    "search_wlo_collections",
    "search_wlo_content",
    "search_wlo_topic_pages",
    "search_wlo_all",
    "get_topic_page_content",
    "get_collection_contents",
    "get_node_details",
    "lookup_wlo_vocabulary",
    "get_subject_portals",
    "browse_collection_tree",
    "wlo_health_check",
    "get_nodes_details",
    "get_skill_registry",
    "get_url_text",
    "get_wikipedia_summary",
    "wlo_auth_status",
]


def test_tool_definitions_order_is_pinned():
    assert [td["function"]["name"] for td in TOOL_DEFINITIONS] == _TOOL_ORDER


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


def test_compendium_text_bietet_auch_den_buendel_abruf():
    """Vertragswechsel V6 (2026-08-20), vorher bewusst Einzelform.

    Die alte Begründung — der Export-Filter strippe nur leere Strings, eine
    leere Liste ginge als ``nodeIds: []`` mit raus — ist seit V4 hinfällig
    (leere Listen werden gestrippt). Und der Anwendungsfall existiert jetzt:
    Lückenanalyse über Geschwister-Sammlungen in EINEM Aufruf (M19,
    MCP-Hinweis 6). ``nodeId`` bleibt Pflicht; ``nodeIds`` ergänzt weitere —
    der Server vereinigt beide Angaben.
    """
    props = _tool("get_compendium_text")["parameters"]["properties"]
    assert "nodeId" in props
    assert "nodeIds" in props


def test_compendium_text_haelt_ein_buendel():
    out = validate_tool_args(
        "get_compendium_text", {"nodeId": "a", "nodeIds": ["b", "c"]})
    assert out == {"nodeId": "a", "nodeIds": ["b", "c"]}


def test_publishers_lookup_can_be_scoped():
    props = _tool("lookup_wlo_publishers")["parameters"]["properties"]
    for p in ("query", "discipline", "educationalContext", "maxResults"):
        assert p in props, p


def test_compendium_text_keeps_a_single_node():
    assert validate_tool_args("get_compendium_text", {"nodeId": "abc"}) == {"nodeId": "abc"}


def test_compendium_text_nennt_den_merker_als_ausloeser():
    # Bis 2026-08-16 nannte die Beschreibung als Anlass einen „gekuerzten
    # 'Kompendium: …'-Auszug" im Sammlungsergebnis. Den gibt es nicht mehr: die
    # Kombi-Redaktion laesst den Kompendiumstext weg und setzt stattdessen
    # ``hasCompendium``. Ein Ausloeser, den das Modell nie zu sehen bekommt,
    # ist keiner — die Beschreibung muss den echten nennen.
    beschreibung = _tool("get_compendium_text")["description"]
    assert "hasCompendium" in beschreibung
    assert "Auszug" not in beschreibung


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
    """Die Gegenprobe zum Test darueber: der W10-Reparaturschritt bleibt heil.
    Die Grenze ist seit 2026-08-21 die Server-Obergrenze 200000, nicht mehr
    unsere alte 50000er-Kopie."""
    out = validate_tool_args("get_url_text", {"url": "https://e.org/", "maxChars": 999999})
    assert out["maxChars"] == 200000


def test_url_text_ohne_maxchars_schickt_den_parameter_nicht_mit():
    """Kern des Befunds der Plugin-Entwickler (2026-08-21): unser Feld-Default
    8000 reiste bei JEDEM Aufruf mit — fremde Seiten kamen also mit 8000 statt
    59 398 Zeichen an. Ohne Angabe darf nichts mitgehen, dann gilt die
    Server-Vorgabe 200000."""
    out = validate_tool_args("get_url_text", {"url": "https://e.org/"})
    assert "maxChars" not in out


def test_url_text_laesst_die_volle_server_grenze_durch():
    out = validate_tool_args("get_url_text", {"url": "https://e.org/", "maxChars": 200000})
    assert out["maxChars"] == 200000


def test_werkzeugbeschreibungen_nennen_die_200000er_vorgabe():
    """Die KI kann nicht wissen, wie lang eine Seite ist — sie erfährt die
    Vorgabe nur aus der Beschreibung. Stand bis 2026-08-21 dort „500-50000,
    Standard 8000", bestellte sie systematisch zu klein."""
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS

    for name in ("get_url_text", "get_wlo_content_text"):
        beschr = next(
            t["function"]["parameters"]["properties"]["maxChars"]["description"]
            for t in TOOL_DEFINITIONS if t["function"]["name"] == name
        )
        assert "200000" in beschr, name
        assert "50000" not in beschr and "8000" not in beschr, name


# ── MCP-Server-Update 2026-08-18/20: query, context, skillContext ──────────
# Die Fähigkeiten existierten serverseitig, waren aber unerreichbar: das
# Modell kann nur senden, was die Definition deklariert. Gemessen am
# deployten Server: get_skill_registry(f35c17d1) = 28 Skills/~14 KB, mit
# context="Stunde planen" = 1 Skill/~2 KB; get_compendium_text ohne query
# bis ~21 KB, mit query ~5 KB (Messung der MCP-Entwickler).

def _params(name: str) -> dict:
    from boerdi.services.mcp.tool_defs import TOOL_DEFINITIONS
    defn = next(t for t in TOOL_DEFINITIONS if t["function"]["name"] == name)
    return defn["function"]["parameters"]["properties"]


def test_kompendium_deklariert_die_suchanfrage():
    assert "query" in _params("get_compendium_text")


def test_registry_deklariert_den_kontext():
    assert "context" in _params("get_skill_registry")


def test_die_fuenf_sammlungs_werkzeuge_deklarieren_skillContext():
    for name in ("get_collection_contents", "search_wlo_within_collection",
                 "get_node_details", "get_topic_page_content",
                 "get_related_content"):
        assert "skillContext" in _params(name), name


def test_validierung_laesst_die_neuen_argumente_durch():
    """Deklariert UND validierbar — ein Parameter, den ``validate_tool_args``
    still verwirft, ist genau die halbe Fähigkeit, die dieser Block anmahnt."""
    from boerdi.services.mcp.tool_args import validate_tool_args

    faelle = [
        ("get_compendium_text", {"nodeId": "n", "query": "Lehrplan Thüringen"}, "query"),
        ("get_skill_registry", {"collectionId": "c", "context": "Stunde planen"}, "context"),
        ("get_collection_contents", {"collectionId": "c", "skillContext": "X"}, "skillContext"),
        ("search_wlo_within_collection",
         {"nodeId": "c", "query": "q", "skillContext": "X"}, "skillContext"),
        ("get_node_details", {"nodeId": "n", "skillContext": "X"}, "skillContext"),
        ("get_related_content", {"nodeId": "n", "skillContext": "X"}, "skillContext"),
    ]
    for werkzeug, args, feld in faelle:
        raus = validate_tool_args(werkzeug, args)
        assert raus.get(feld) == args[feld], f"{werkzeug}: {feld} kam nicht durch"


# ── V3 (2026-08-20): Lizenzfilter — der Server kennt license an drei Suchen ─

def test_content_search_keeps_the_license_filter():
    out = validate_tool_args("search_wlo_content", {"query": "Optik", "license": "OER"})
    assert out.get("license") == "OER"


def test_within_collection_search_keeps_the_license_filter():
    out = validate_tool_args(
        "search_wlo_within_collection", {"nodeId": "c1", "license": "CC BY 4.0"})
    assert out.get("license") == "CC BY 4.0"


def test_collection_search_drops_the_license_filter():
    # search_wlo_collections kennt serverseitig kein ``license``
    # (``additionalProperties: false``) — mitreisen hieße Server-Fehler.
    out = validate_tool_args("search_wlo_collections", {"query": "Optik", "license": "OER"})
    assert "license" not in out


def test_search_tools_offer_the_license_filter():
    fuer = {d["function"]["name"]: d["function"]["parameters"]["properties"]
            for d in TOOL_DEFINITIONS}
    for name in ("search_wlo_content", "search_wlo_all", "search_wlo_within_collection"):
        assert "license" in fuer[name], name
    assert "license" not in fuer["search_wlo_collections"]


# ── V4 (2026-08-20): excludeNodeIds — der dokumentierte Weg für Folgeseiten ─

def test_search_models_keep_exclude_node_ids():
    for tool, extra in (("search_wlo_content", {"query": "x"}),
                        ("search_wlo_collections", {"query": "x"}),
                        ("search_wlo_within_collection", {"nodeId": "c1"})):
        out = validate_tool_args(tool, {**extra, "excludeNodeIds": ["a", "b"]})
        assert out.get("excludeNodeIds") == ["a", "b"], tool


def test_leere_liste_reist_nicht_mit():
    # ``_export_non_empty`` strippt seit V4 auch leere Listen — sonst ginge
    # der Default ``[]`` mit JEDEM Aufruf zum Server.
    out = validate_tool_args("search_wlo_content", {"query": "x"})
    assert "excludeNodeIds" not in out


def test_search_tools_offer_exclude_node_ids():
    fuer = {d["function"]["name"]: d["function"]["parameters"]["properties"]
            for d in TOOL_DEFINITIONS}
    for name in ("search_wlo_content", "search_wlo_all",
                 "search_wlo_collections", "search_wlo_within_collection"):
        assert "excludeNodeIds" in fuer[name], name


# ── V2 (2026-08-20): Kontext nur auf ausdrücklichen Wunsch ──────────────────

def _props(name):
    return next(d["function"]["parameters"]["properties"]
                for d in TOOL_DEFINITIONS if d["function"]["name"] == name)


def test_skillcontext_beschreibungen_identisch_und_mit_regel():
    """Der Text steht 5× wörtlich kopiert (Datei-Konvention: Inline-Literale)
    — dieser Wächter hält die Kopien deckungsgleich und pinnt die Regel:
    nur auf ausdrücklichen Wunsch, sonst voller Katalog."""
    traeger = ("get_collection_contents", "search_wlo_within_collection",
               "get_node_details", "get_topic_page_content", "get_related_content")
    texte = {_props(n)["skillContext"]["description"] for n in traeger}
    assert len(texte) == 1
    assert texte.pop().startswith("Nur setzen")


def test_registry_context_beschreibung_traegt_die_regel():
    assert _props("get_skill_registry")["context"]["description"].startswith("Nur setzen")


def test_compendium_buendel_ist_auf_neun_begrenzt():
    """Review-Befund 1 (2026-08-20): get_compendium_text ist im Langform-Pfad
    NIE gedeckelt, und der Server-Deckel gilt je Kompendium — 25 auf einmal
    multiplizierten ihn auf >100 KB Prompt. 1+9 deckt die Lückenanalyse."""
    from annotated_types import MaxLen

    from boerdi.api.schemas import CompendiumTextArgs
    assert MaxLen(9) in CompendiumTextArgs.model_fields["nodeIds"].metadata


def _vorgehen_text() -> str:
    from pathlib import Path

    return (Path(__file__).parents[2] / "docs" / "skills" / "vorgehen.md").read_text(
        encoding="utf-8")


def test_vorgehen_md_nennt_nur_existierende_werkzeuge():
    """Wächter für den Master-Skill (docs/skills/vorgehen.md): jeder als
    Backtick-Code genannte Name mit Unterstrich muss ein Werkzeug des Katalogs
    oder ein virtuelles Werkzeug des Chat-Zuges sein. Ein Tippfehler dort ist
    ein Phantom-Werkzeug im wichtigsten Prompt-Dokument — das Modell ruft es,
    bekommt einen Fehler und rät weiter (gemessen 2026-08-16 bei den
    erfundenen get_skill-IDs)."""
    import re

    text = _vorgehen_text()
    from boerdi.services.mcp.tool_defs_curation import CURATION_TOOL_DEFINITIONS

    genannt = {t for t in re.findall(r"`([a-z][a-z0-9_]+)`", text) if "_" in t}
    katalog = {d["function"]["name"]
               for d in (*TOOL_DEFINITIONS, *CURATION_TOOL_DEFINITIONS)}
    virtuell = {"wissen_suchen", "liefere_ergebnis"}
    # ``search_skill`` nennt der Skill nur, um es zu VERNEINEN („existiert
    # nicht") — die Nennung ist gewollt, das Werkzeug bleibt draußen.
    unbekannt = genannt - katalog - virtuell - {"search_skill"}
    assert not unbekannt, unbekannt


def test_vorgehen_md_traegt_die_kernbegriff_suchregel():
    """Y1 (2026-08-20, Live-Befund Repo-Einbettung): das Modell reichte den
    ganzen Nutzersatz als ``query`` durch ("ich suche nur arbeitsblätter zu
    optik") — Ranking verwässert, und der Satz landet in den Such-Links der
    Oberfläche. Die Regel „query = Kernbegriff, Materialart/Fach/Stufe in die
    Filter" muss im Finden-Teil des Master-Skills stehen und dort bleiben."""
    text = _vorgehen_text()
    finden = text.split("## Finden", 1)[1]
    assert "Kernbegriff" in finden
    assert 'query: "Optik"' in finden
    assert 'learningResourceType: "Arbeitsblatt"' in finden
    # Z1: alle drei Filter-Dimensionen beim Namen — das Modell soll wissen,
    # WOHIN Fach und Stufe gehoeren, nicht nur, dass sie nicht in die query.
    assert "discipline" in finden
    assert "educationalContext" in finden


def test_query_beschreibungen_lehren_den_kernbegriff_nicht_den_satz():
    """Z1 (2026-08-20): die ``query``-Beispiele von search_wlo_content
    ("Bruchrechnung Grundschule") und search_wlo_all ("Bruchrechnung Klasse 7")
    machten dem Modell das Stopfen von Stufe/Typ in den Suchbegriff aktiv VOR —
    die Such-Links der Trefferanzeige trugen dann den ganzen Wortschwall. Die
    Beschreibung muss den Kernbegriff lehren und die drei Filter-Dimensionen
    (Fach -> discipline, Stufe -> educationalContext, Typ ->
    learningResourceType) beim Namen nennen."""
    for name in ("search_wlo_content", "search_wlo_all"):
        props = _props(name)
        q = props["query"]["description"]
        assert "Kernbegriff" in q, name
        for dimension in ("discipline", "educationalContext", "learningResourceType"):
            assert dimension in q, (name, dimension)
        assert "Bruchrechnung Grundschule" not in q, name
        assert "Bruchrechnung Klasse 7" not in q, name
