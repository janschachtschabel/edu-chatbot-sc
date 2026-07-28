"""Behavior pins for services/prefetch._fallback_inline_search (verbatim-body port of
ALT chat_prefetch._fallback_inline_search). The MCP boundary (call_mcp_tool) and the
parser are mocked at their source modules — the function imports them in-function, so
patching the source binds the mock. asyncio_mode=auto runs the async tests directly.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

from boerdi.services.prefetch import _fallback_inline_search

CT = "boerdi.services.mcp.client.call_mcp_tool"
PC = "boerdi.services.mcp.parsers.parse_wlo_cards"


async def test_builds_args_and_returns_parsed_cards(monkeypatch):
    ct = AsyncMock(return_value="RAW")
    pc = Mock(return_value=[{"node_id": "n1"}])
    monkeypatch.setattr(CT, ct)
    monkeypatch.setattr(PC, pc)
    out = await _fallback_inline_search("Photosynthese", {})
    assert out == [{"node_id": "n1"}]
    ct.assert_awaited_once_with("search_wlo_content", {"query": "Photosynthese", "maxResults": 5})
    pc.assert_called_once_with("RAW")


async def test_adds_discipline_and_context_filters(monkeypatch):
    ct = AsyncMock(return_value="RAW")
    monkeypatch.setattr(CT, ct)
    monkeypatch.setattr(PC, Mock(return_value=[]))
    await _fallback_inline_search("q", {"fach": "Mathematik", "stufe": "Sekundarstufe I"})
    args = ct.await_args.args[1]
    assert args["discipline"] == "Mathematik"
    assert args["educationalContext"] == "Sekundarstufe I"


async def test_empty_raw_returns_empty_and_skips_parse(monkeypatch):
    ct = AsyncMock(return_value="")
    pc = Mock()
    monkeypatch.setattr(CT, ct)
    monkeypatch.setattr(PC, pc)
    assert await _fallback_inline_search("q", {}) == []
    pc.assert_not_called()


async def test_parse_returning_none_yields_empty(monkeypatch):
    monkeypatch.setattr(CT, AsyncMock(return_value="RAW"))
    monkeypatch.setattr(PC, Mock(return_value=None))
    assert await _fallback_inline_search("q", {}) == []


async def test_exception_is_swallowed_returns_empty(monkeypatch):
    monkeypatch.setattr(CT, AsyncMock(side_effect=RuntimeError("boom")))
    assert await _fallback_inline_search("q", {}) == []


async def test_non_dict_entities_add_no_filters(monkeypatch):
    ct = AsyncMock(return_value="RAW")
    monkeypatch.setattr(CT, ct)
    monkeypatch.setattr(PC, Mock(return_value=[]))
    await _fallback_inline_search("q", None)
    args = ct.await_args.args[1]
    assert "discipline" not in args and "educationalContext" not in args


async def test_blank_filter_values_are_ignored(monkeypatch):
    ct = AsyncMock(return_value="RAW")
    monkeypatch.setattr(CT, ct)
    monkeypatch.setattr(PC, Mock(return_value=[]))
    await _fallback_inline_search("q", {"fach": "  ", "stufe": ""})
    args = ct.await_args.args[1]
    assert "discipline" not in args and "educationalContext" not in args
