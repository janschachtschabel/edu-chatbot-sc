"""P0-5: schema port parity with ALT app/models/schemas.py (spec §5.1).

The import from ``boerdi.api.schemas`` doubles as the re-export contract:
ALT exposed everything from one module; the facade must keep that surface.
"""

import pytest
from pydantic import ValidationError

from boerdi.api.schemas import (
    MAX_RESULT_SCHEMA_CHARS,
    ChatRequest,
    ChatResponse,
    ClassificationResult,
    CollectionContentsArgs,
    CollectionTreeArgs,
    ConfigFile,
    ContextSnapshot,
    DebugInfo,
    Environment,
    HealthCheckArgs,
    InlineDocument,
    LookupVocabularyArgs,
    MemoryEntry,
    NodeDetailsArgs,
    NodesDetailsArgs,
    PageAction,
    PaginationInfo,
    PolicyDecision,
    QueryMetaEntry,
    RagDocument,
    RagQuery,
    RagResult,
    SafetyDecision,
    SearchTopicPagesArgs,
    SearchWloArgs,
    SessionState,
    SubjectPortalsArgs,
    SwimlaneBox,
    ToolOutcome,
    TopicPageView,
    TraceEntry,
    WebLink,
    WloCard,
)

ALL_MODELS = [
    ChatRequest, ChatResponse, ClassificationResult, CollectionContentsArgs,
    CollectionTreeArgs, ConfigFile, ContextSnapshot, DebugInfo, Environment,
    HealthCheckArgs, InlineDocument, LookupVocabularyArgs, MemoryEntry,
    NodeDetailsArgs, NodesDetailsArgs, PageAction, PaginationInfo,
    PolicyDecision, QueryMetaEntry, RagDocument, RagQuery, RagResult,
    SafetyDecision, SearchTopicPagesArgs, SearchWloArgs, SessionState,
    SubjectPortalsArgs, SwimlaneBox, ToolOutcome, TopicPageView, TraceEntry,
    WebLink, WloCard,
]


@pytest.mark.parametrize("model", ALL_MODELS, ids=lambda m: m.__name__)
def test_model_json_schema_buildable(model) -> None:
    schema = model.model_json_schema()
    assert schema.get("type") == "object" or "properties" in schema


def test_chat_response_field_parity_spec_5_1() -> None:
    # Zwei Zusätze gegenüber §5.1, beide rein additiv mit Vorgabe „nichts":
    #
    # ``prepared_write`` (E3, 2026-08-12): im eingebetteten Betrieb beschreibt der
    # MCP-Server eine bestätigte Änderung, statt sie zu schreiben, und das Widget
    # setzt sie mit der Anmeldung der Seite ab. Bewusst KEIN weiterer
    # ``page_action``-Typ: der Platz ist einzeln und schon von Canvas/Guide belegt.
    #
    # ``result`` + ``result_stop_reason`` (Nutzer-Entscheid 2026-08-14): erklärt
    # der Gastgeber ein ``Environment.result_schema``, bekommt er das Ergebnis des
    # Zuges maschinenlesbar. Der Ende-Grund gehört DAZU und nicht ins Protokoll —
    # ein an der Frist abgeschnittener Lauf sähe sonst aus wie einer, der fertig
    # geworden ist. Ohne Schema bleiben beide leer; jede Bestands-Antwort sieht
    # aus wie zuvor.
    #
    # ``auth_invalid`` (Paket 10, Kurzaudit A-3): der MCP-Server hat den
    # Zugangsblock des Zuges abgewiesen; das Widget räumt ihn und bietet die
    # Anmeldung neu an. Vorgabe ``False``.
    #
    # ``ui`` (Paket 18C/D, Phase 3): der öffentliche Teil des Debug-Blocks
    # (``api/schemas_ui``), zusätzlich — ab Phase 4 liest das Widget nur noch dort.
    assert set(ChatResponse.model_fields) == {
        "session_id", "content", "cards", "follow_up", "quick_replies", "debug",
        "page_action", "pagination", "query_metas", "web_links",
        "inline_documents", "topic_page", "display_rules", "tour",
        "prepared_write", "result", "result_stop_reason", "auth_invalid", "ui",
    }


def test_environment_defaults_spec_5_1() -> None:
    env = Environment()
    assert env.page == "/"
    assert env.page_context == {}
    assert env.device == "desktop"
    assert env.locale == "de-DE"
    assert env.session_duration == 0
    assert env.referrer == "direkt"
    assert env.guide_mode is True
    assert env.host == ""
    assert env.ai_content_enabled is None  # deprecated, tolerated
    assert env.tour_action is None
    assert env.page_event is None


def test_result_schema_ist_gedeckelt() -> None:
    """``result_schema`` reist WÖRTLICH in die Werkzeug-Parameter und damit in
    jeden Modellaufruf der Schleife (bis zu ``max_iterations``). ``/api/chat``
    ist der ÖFFENTLICHE Router ohne Anmeldung — der Deckel gehört deshalb an den
    Rand, nicht an den Verbraucher.

    Abgelehnt statt gekürzt, anders als beim Nachbarn ``page_context``: ein
    halbes Schema ist ein ANDERES Schema. Der Gastgeber bekäme Ergebnisse in
    einer Form, die er nie verlangt hat, und merkte es nicht.
    """
    Environment(result_schema={"type": "object"})
    Environment(result_schema=None)
    with pytest.raises(ValidationError):
        Environment(result_schema={"type": "object", "x": "a" * MAX_RESULT_SCHEMA_CHARS})


def test_result_schema_deckel_liegt_bei_200000(monkeypatch) -> None:
    """Angehoben von 10000 auf 200000 (Nutzer-Entscheid 2026-08-18).

    Anders als bei ``message`` und ``host_instruction`` bleibt hier EIN Deckel
    stehen: das Schema reist woertlich in die Werkzeug-Parameter und damit in
    jeden Modellaufruf der Schleife, und ein absurd grosses Schema ist nie ein
    Wunsch, sondern ein Fehler. 200000 Zeichen sind fuer eine Struktur so viel
    Platz, dass die Grenze in der Praxis nicht mehr vorkommt.
    """
    assert MAX_RESULT_SCHEMA_CHARS == 200000
    gross = Environment(result_schema={"type": "object", "x": "a" * 100_000})
    assert gross.result_schema is not None


def test_result_schema_nimmt_nur_objekte() -> None:
    # Eine Liste ist kein JSON-Schema-Objekt; ``dict[str, Any]`` weist sie ab.
    with pytest.raises(ValidationError):
        Environment(result_schema=[{"type": "object"}])  # type: ignore[arg-type]


@pytest.mark.parametrize("kaputt", [
    {"type": "intger"},
    {"type": "object", "properties": {"a": {"$ref": "https://example.org/s.json"}}},
])
def test_result_schema_muss_ein_gueltiges_schema_sein(kaputt) -> None:
    """Paket 4, A3: Das Ergebnis wird jetzt gegen das Schema geprüft. Ein
    kaputtes Schema oder ein Verweis nach draußen fällt deshalb schon am Rand
    auf (422), statt mitten im Lauf. Für den Agent-Endpunkt gilt dasselbe; sein
    Größendeckel bleibt bewusst offen (siehe ``MAX_RESULT_SCHEMA_CHARS``)."""
    from boerdi.api.schemas_agent import AgentRequest

    with pytest.raises(ValidationError):
        Environment(result_schema=kaputt)
    with pytest.raises(ValidationError):
        AgentRequest(instruction="Bewerte", result_schema=kaputt)
    # Ein gültiges geht an beiden Stellen durch.
    gut = {"type": "object", "properties": {"score": {"type": "integer"}}}
    assert Environment(result_schema=gut).result_schema == gut
    assert AgentRequest(instruction="Bewerte", result_schema=gut).result_schema == gut


def test_chat_request_message_ohne_zeichendeckel() -> None:
    """Deckel entfernt (Nutzer-Entscheid 2026-08-18) — er lag bei 10000.

    Er war nie die Grenze der Anfragegroesse: ``environment.page_context`` ist
    ein freies ``dict`` ohne jede Schranke und stand die ganze Zeit daneben
    offen. Was den Missbrauch begrenzt, ist das Rate-Limit, nicht dieses Feld.
    """
    lang = ChatRequest(session_id="bb-x", message="a" * 50_000)
    assert len(lang.message) == 50_000
    req = ChatRequest(session_id="bb-x", message="hi")
    assert req.action is None
    assert req.action_params == {}
    assert req.canvas_state is None
    assert isinstance(req.environment, Environment)


def test_wlo_card_defaults() -> None:
    card = WloCard()
    assert card.node_type == "content"
    assert card.preview_is_icon is False
    assert card.file_size == 0
    assert (card.url, card.wlo_url, card.download_url, card.content_url,
            card.guide_url, card.link) == ("", "", "", "", "", "")
    assert card.topic_pages == []


def test_classification_result_defaults() -> None:
    c = ClassificationResult()
    assert (c.persona_id, c.intent_id, c.next_state, c.turn_type) == (
        "P-AND", "I03", "S1", "initial")
    assert c.persona_confidence == 0.8
    assert c.pattern_id_hint is None
    assert c.tool_id_hint is None


def test_debug_info_defaults() -> None:
    d = DebugInfo()
    assert d.confidence == 1.0
    assert d.token_usage == {}
    assert d.safety is None and d.policy is None and d.context is None
    assert d.trace == [] and d.outcomes == []


def test_search_args_legacy_aliases() -> None:
    args = SearchWloArgs(
        query="brüche",
        educationalLevel="sek1",
        resourceType="arbeitsblatt",
        maxItems=7,
        license="cc",
        skipCount=5,
    )
    assert args.educationalContext == "sek1"
    assert args.learningResourceType == "arbeitsblatt"
    assert args.maxResults == 7
    dumped = args.model_dump()
    assert "license" not in dumped and "skipCount" not in dumped


def test_collection_contents_legacy_max_items() -> None:
    args = CollectionContentsArgs(nodeId="n1", maxItems=9)
    assert args.maxResults == 9
    assert args.skipCount == 0


def test_lookup_vocabulary_legacy_field() -> None:
    assert LookupVocabularyArgs(field="discipline").vocabulary == "discipline"
    assert LookupVocabularyArgs(vocabulary="lrt").vocabulary == "lrt"


# ── Paket 9 (Review Paket 7, CRITICAL 2 / MINOR 14 / V3): Eingang begrenzen ──
@pytest.mark.parametrize("sid", [
    "bb-0f8fad5b-d9cb-469f-a165-70867728950e", "eval-1a2b3c4d5e6f",
    "loadtest-1a2b3c4d-s0-12", "studio-0f8fad5b-d9cb-469f-a165-70867728950e",
    "a" * 128, "s_1",
])
def test_echte_sitzungskennungen_gehen_durch(sid) -> None:
    assert ChatRequest(session_id=sid, message="hallo").session_id == sid


@pytest.mark.parametrize("sid", [
    "", "a" * 129, "__lauf:aufbewahrung", "x y", "bb-ä", "../etc", "a\nb",
])
def test_andere_sitzungskennungen_werden_abgewiesen(sid) -> None:
    """Dieselbe Form wie an der offenen Lesestelle (``api/sessions``). Eine
    Kennung ist zugleich der Schlüssel der Sitzungssperre: ``__lauf:aufbewahrung``
    blockierte sonst den Löschlauf (Lease-Raum geteilt)."""
    with pytest.raises(ValidationError):
        ChatRequest(session_id=sid, message="hallo")


def test_seitenkontext_wird_am_eintritt_gedeckelt() -> None:
    """Ein Suchbegriff mit zwei Megabyte lief ungebremst durch Entschärfung,
    Klassifikator und beide Prompt-Wege. Gekürzt statt abgewiesen: der
    Seitenkontext ist Zusatzwissen, kein Auftrag — der Zug soll laufen."""
    from boerdi.services.page_context import TEXT_PROMPT_BUDGET

    env = Environment(page_context={
        "search_query": "q" * 100_000,
        "page_url": "https://x.de/" + "p" * 5000,
        "page_text": "t" * 300_000,
        "page_kind": "collection",
        "widget": True,
        "zahl": 3,
        "search_filters": {"publisher": ["v" * 1000] * 100},
        "tief": {"a": {"b": {"c": {"d": "zu tief"}}}},
    })
    pc = env.page_context
    assert len(pc["search_query"]) == 500
    assert len(pc["page_url"]) == 2048
    # Eins über dem Budget, damit ``_trim_text`` das Kürzen noch bemerkt („…“).
    assert len(pc["page_text"]) == TEXT_PROMPT_BUDGET + 1
    assert pc["page_kind"] == "collection" and pc["widget"] is True and pc["zahl"] == 3
    assert len(pc["search_filters"]["publisher"]) == 50
    assert all(len(v) == 500 for v in pc["search_filters"]["publisher"])
    assert pc["tief"] == {"a": {"b": {}}}


def test_ein_gewoehnlicher_seitenkontext_bleibt_wortgleich() -> None:
    pc = {"node_id": "0f8fad5b-d9cb-469f-a165-70867728950e", "page_kind": "content",
          "search_query": "Photosynthese", "search_filters": {"publisher": ["Serlo"]},
          "page_text": "Titel\nText", "page_host": "wirlernenonline.de"}
    assert Environment(page_context=pc).page_context == pc
