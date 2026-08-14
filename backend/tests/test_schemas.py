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
    assert set(ChatResponse.model_fields) == {
        "session_id", "content", "cards", "follow_up", "quick_replies", "debug",
        "page_action", "pagination", "query_metas", "web_links",
        "inline_documents", "topic_page", "display_rules", "tour",
        "prepared_write", "result", "result_stop_reason",
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


def test_result_schema_nimmt_nur_objekte() -> None:
    # Eine Liste ist kein JSON-Schema-Objekt; ``dict[str, Any]`` weist sie ab.
    with pytest.raises(ValidationError):
        Environment(result_schema=[{"type": "object"}])  # type: ignore[arg-type]


def test_chat_request_message_cap_10000() -> None:
    ChatRequest(session_id="bb-x", message="a" * 10000)
    with pytest.raises(ValidationError):
        ChatRequest(session_id="bb-x", message="a" * 10001)
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
