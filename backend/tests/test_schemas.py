"""P0-5: schema port parity with ALT app/models/schemas.py (spec §5.1).

The import from ``boerdi.api.schemas`` doubles as the re-export contract:
ALT exposed everything from one module; the facade must keep that surface.
"""

import pytest
from pydantic import ValidationError

from boerdi.api.schemas import (
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
    assert set(ChatResponse.model_fields) == {
        "session_id", "content", "cards", "follow_up", "quick_replies", "debug",
        "page_action", "pagination", "query_metas", "web_links",
        "inline_documents", "topic_page", "display_rules", "tour",
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
