"""Characterization pins for the async orchestrator
``services/widget_postprocess._postprocess_response_for_widget_modes`` (verbatim
port of ALT ``chat_postprocess._postprocess_response_for_widget_modes``).

Strategy: only the true external boundaries are mocked — the MCP fallback search
(``_fallback_inline_search``), the card-pipeline-v2 curation (``run_pipeline_v2`` /
``summarize_pipeline_result``), the v2 feature toggle, and the display-rules config
loader. Every pure helper (``_widget_modes``, ``_resolve_wanted_content_types``,
``_card_matches_wanted_types``, ``_apply_widget_modes_postprocess``, ``_qr_policy``,
url-helpers) runs for real, so these pins exercise the orchestrator's live branches
end to end. asyncio_mode=auto runs the async tests without a marker.

Note: module-level names (``_apply_widget_modes_postprocess``, ``_fallback_inline_search``,
``card_pipeline_v2_enabled``) are patched ON the orchestrator module; in-function
imports (``run_pipeline_v2``, ``summarize_pipeline_result``, ``load_display_rules_config``)
are patched at their SOURCE module, since the function re-imports them at call time.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from boerdi.api.schemas import ChatRequest, ChatResponse, DebugInfo, Environment, WloCard
from boerdi.services.widget_postprocess import _postprocess_response_for_widget_modes

MOD = "boerdi.services.widget_postprocess"
DR = "boerdi.services.config_loader.load_display_rules_config"


def _req(message="Photosynthese Grundlagen", *, host="", guide_mode=True,
         action=None, page_context=None):
    env = Environment(guide_mode=guide_mode, host=host, page_context=page_context or {})
    return ChatRequest(session_id="s1", message=message, environment=env, action=action)


def _resp(*, content="Hallo.", cards=None, quick_replies=None, page_action=None,
          tour=None, debug=None):
    return ChatResponse(
        session_id="s1", content=content,
        cards=cards if cards is not None else [],
        quick_replies=quick_replies if quick_replies is not None else [],
        page_action=page_action, tour=tour,
        debug=debug if debug is not None else DebugInfo(),
    )


def _nid(c):
    return c.get("node_id") if isinstance(c, dict) else getattr(c, "node_id", None)


def _no_v2(monkeypatch):
    """v2 pipeline off + a deterministic display-rules loader (max_count 4)."""
    monkeypatch.setattr(f"{MOD}.card_pipeline_v2_enabled", Mock(return_value=False))
    monkeypatch.setattr(DR, Mock(return_value={"quick_replies": {"max_count": 4}}))


async def test_tour_response_is_returned_unchanged():
    resp = _resp(tour={"active": True, "step": "intro"})
    out = await _postprocess_response_for_widget_modes(_req(), resp)
    assert out is resp  # deterministic tour payload bypasses postprocess entirely


async def test_exception_in_postprocess_returns_original_resp(monkeypatch):
    _no_v2(monkeypatch)
    monkeypatch.setattr(f"{MOD}._apply_widget_modes_postprocess",
                        Mock(side_effect=RuntimeError("boom")))
    resp = _resp(content="x")
    out = await _postprocess_response_for_widget_modes(_req(), resp)
    assert out is resp  # postprocess must never propagate — returns input unchanged


async def test_happy_path_no_cards_preserves_content(monkeypatch):
    _no_v2(monkeypatch)
    resp = _resp(content="Wie kann ich helfen?", quick_replies=["A", "B"])
    out = await _postprocess_response_for_widget_modes(_req(), resp)
    assert out is not resp                      # went through model_copy
    assert out.content == "Wie kann ich helfen?"
    assert list(out.cards) == []
    assert "A" in out.quick_replies and "B" in out.quick_replies


async def test_universal_type_filter_drops_non_matching_cards(monkeypatch):
    _no_v2(monkeypatch)
    video = WloCard(node_id="v1", node_type="content",
                    learning_resource_types=["Video"], title="Vid")
    coll = WloCard(node_id="c1", node_type="collection", title="Sammlung")
    resp = _resp(content="Schau mal.", cards=[video, coll])
    out = await _postprocess_response_for_widget_modes(
        _req(message="Hast du Videos zu Photosynthese?"), resp)
    ids = [_nid(c) for c in out.cards]
    assert "v1" in ids       # video content card matches wanted={"video"}
    assert "c1" not in ids   # collection dropped by the universal medientyp filter


async def test_safety_net_injects_fallback_cards_on_delivery_claim(monkeypatch):
    _no_v2(monkeypatch)
    fb = AsyncMock(return_value=[{"node_id": "fb1", "node_type": "content",
                                  "title": "Fallback"}])
    monkeypatch.setattr(f"{MOD}._fallback_inline_search", fb)
    dbg = DebugInfo(phase3_modulations={"tools": ["search_wlo_content"],
                                        "sources": ["mcp"]})
    resp = _resp(content="Ich habe dir etwas rausgesucht.", cards=[], debug=dbg)
    out = await _postprocess_response_for_widget_modes(
        _req(message="Photosynthese Grundlagen"), resp)
    fb.assert_awaited_once()
    assert "fb1" in [_nid(c) for c in out.cards]


async def test_safety_net_skipped_for_rag_only_pattern(monkeypatch):
    _no_v2(monkeypatch)
    fb = AsyncMock(return_value=[{"node_id": "fb1"}])
    monkeypatch.setattr(f"{MOD}._fallback_inline_search", fb)
    dbg = DebugInfo(phase3_modulations={"tools": [], "sources": ["rag"]})
    resp = _resp(content="Das zeig ich dir direkt.", cards=[], debug=dbg)
    out = await _postprocess_response_for_widget_modes(
        _req(message="Was ist WirLernenOnline?"), resp)
    fb.assert_not_awaited()   # tools=[] → RAG-only pattern → no fallback search
    assert list(out.cards) == []


async def test_v2_curation_replaces_cards(monkeypatch):
    monkeypatch.setattr(f"{MOD}.card_pipeline_v2_enabled", Mock(return_value=True))
    monkeypatch.setattr(DR, Mock(return_value={"quick_replies": {"max_count": 4}}))
    v2run = AsyncMock(return_value={"intent_kind": "general",
                                    "cards": [{"node_id": "v2a", "node_type": "content"}]})
    monkeypatch.setattr("boerdi.services.card_pipeline.run_pipeline_v2", v2run)
    monkeypatch.setattr("boerdi.domain.cards.select.summarize_pipeline_result",
                        Mock(return_value="v2 summary"))
    orig = WloCard(node_id="orig1", node_type="content", title="Original")
    resp = _resp(content="Hier.", cards=[orig])
    out = await _postprocess_response_for_widget_modes(_req(message="Bruchrechnen"), resp)
    v2run.assert_awaited_once()
    ids = [_nid(c) for c in out.cards]
    assert "v2a" in ids       # v2 curation output replaces the v1 pool
    assert "orig1" not in ids


async def test_quick_reply_cap_enforced_from_display_rules(monkeypatch):
    monkeypatch.setattr(f"{MOD}.card_pipeline_v2_enabled", Mock(return_value=False))
    monkeypatch.setattr(DR, Mock(return_value={"quick_replies": {"max_count": 2}}))
    resp = _resp(content="Hallo.", quick_replies=["a", "b", "c", "d", "e"])
    out = await _postprocess_response_for_widget_modes(_req(), resp)
    assert len(out.quick_replies) <= 2   # empty pattern → _qr_policy None → global cap
