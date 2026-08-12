"""Characterization tests for services/lp_fast_path.py::run_lp_fast_path (P4-5).

ALT origin: ``chat_turn_routing._route_pattern`` learning-path fast-path body
(Z. 282-597, the ``if _has_lp_intent and _thema:`` block). Integration-only in
ALT → these pin the observable contract (routed flag + produced response/cards/
tools/new_state/qr fields + session_state side effects) and the P1/P2/P3 +
generation paths. Logic fidelity itself is proven by the AST-diff gate; these
catch the wiring (import swaps, no-op removals) and the return contract.

The I/O boundaries (``call_mcp_tool``/``parse_wlo_cards``/
``generate_learning_path_text``/``generate_quick_replies``) are faked at the
module; the pure diversity + QR-policy helpers run for real.
"""

import json
from types import SimpleNamespace

import pytest

from boerdi.obs.usage import new_accumulator
from boerdi.services import lp_fast_path
from boerdi.services.lp_fast_path import run_lp_fast_path


def _req(message: str, locale: str = "de-DE"):
    # ``environment`` gehoert zum ChatRequest-Vertrag; der Fast-Path liest seit
    # C1-f2a das ``locale`` daraus. Kein ``getattr``-Notausgang im Produktivcode
    # — die Attrappe folgt dem Vertrag.
    return SimpleNamespace(message=message, environment=SimpleNamespace(locale=locale))


class _Cls:
    """Classification stub — the body reads ``.entities`` + ``.model_dump()``."""

    def __init__(self, entities=None):
        self.entities = entities or {}

    def model_dump(self):
        return {"entities": dict(self.entities)}


@pytest.fixture
def patch_gen(monkeypatch):
    """Default fakes: LLM generators + non-speculative QR-policy + inert MCP.

    call_mcp_tool/parse_wlo_cards default to empty so no test hits the network;
    the P2/P3 tests override them via ``_patch_mcp``.
    """
    async def _fake_lp(**kwargs):
        _fake_lp.kwargs = kwargs
        return "**Lernpfad: Test**\nSchritt 1: los"

    _fake_lp.kwargs = None

    async def _fake_qr(**kwargs):
        return ["q1", "q2"]

    async def _fake_mcp(tool_name, args):
        return ""

    monkeypatch.setattr(lp_fast_path, "generate_learning_path_text", _fake_lp)
    monkeypatch.setattr(lp_fast_path, "generate_quick_replies", _fake_qr)
    monkeypatch.setattr(lp_fast_path, "call_mcp_tool", _fake_mcp)
    monkeypatch.setattr(lp_fast_path, "parse_wlo_cards", lambda text: [])
    monkeypatch.setattr(lp_fast_path, "_qr_policy", lambda pid: ("exact", 4))
    monkeypatch.setattr(lp_fast_path, "_qr_default_count", lambda: 4)
    return _fake_lp


def _patch_mcp(monkeypatch, parsed_by_tool):
    """Fake call_mcp_tool (echoes tool name) + parse_wlo_cards (dispatch on it)."""
    async def _fake_mcp(tool_name, args):
        return f"MCP::{tool_name}"

    def _fake_parse(text):
        for tool, cards in parsed_by_tool.items():
            if tool in text:
                return [dict(c) for c in cards]
        return []

    monkeypatch.setattr(lp_fast_path, "call_mcp_tool", _fake_mcp)
    monkeypatch.setattr(lp_fast_path, "parse_wlo_cards", _fake_parse)


class TestNotRouted:
    async def test_no_intent(self, patch_gen):
        res = await run_lp_fast_path(
            has_lp_intent=False, thema="Bruchrechnung", req=_req("x"),
            classification=_Cls(), session_state={"entities": {}},
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is False
        assert res.response_text is None
        assert res.wlo_cards_raw is None
        assert res.new_state == "S1"

    async def test_no_thema(self, patch_gen):
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="", req=_req("Lernpfad"),
            classification=_Cls(), session_state={"entities": {}},
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is False


class TestPriorities:
    async def test_priority1_from_session_contents(self, patch_gen):
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "Bruchrechnung",
                "_last_contents": json.dumps([
                    {"node_id": "n1", "title": "Video A",
                     "learning_resource_types": ["video"], "description": "d", "url": "u"},
                ]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Bruchrechnung", req=_req("Erstelle einen Lernpfad"),
            classification=_Cls({}), session_state=ss,  # no new thema → no topic-switch
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert res.response_text.startswith("**Lernpfad")
        assert res.new_state == "S3"
        assert "generate_learning_path (aus Einzelinhalten)" in res.tools_called
        assert len(res.wlo_cards_raw) == 1
        # canvas markers set for follow-up edits
        assert ss["entities"]["_canvas_material_type"] == "lernpfad"
        assert ss["entities"]["_canvas_topic"] == "Bruchrechnung"

    async def test_priority2_from_session_collections(self, patch_gen, monkeypatch):
        _patch_mcp(monkeypatch, {
            "get_collection_contents": [{"node_id": "m1", "title": "Mat 1"}],
        })
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "Photosynthese",
                "_last_collections": json.dumps([{"node_id": "c1", "title": "Sammlung X"}]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Photosynthese", req=_req("Lernpfad daraus"),
            classification=_Cls({}), session_state=ss,  # no new thema → no topic-switch
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert any("get_collection_contents" in t for t in res.tools_called)
        assert "generate_learning_path" in res.tools_called

    async def test_priority3_search_and_fetch(self, patch_gen, monkeypatch):
        _patch_mcp(monkeypatch, {
            "search_wlo_collections": [{"node_id": "col1", "title": "Eiszeit-Sammlung"}],
            "get_collection_contents": [
                {"node_id": f"m{i}", "title": f"Mat{i}"} for i in range(1, 5)
            ],
        })
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Eiszeit"}}
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Eiszeit", req=_req("Lernpfad zur Eiszeit"),
            classification=_Cls({"thema": "Eiszeit"}), session_state=ss,
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert any("search_wlo_collections" in t for t in res.tools_called)
        # per-topic skipCount advanced for the next request
        assert ss["entities"]["_lp_skip_eiszeit"] == 3

    async def test_priority3_thin_candidates_fallback(self, patch_gen, monkeypatch):
        _patch_mcp(monkeypatch, {
            "search_wlo_collections": [{"node_id": "col1", "title": "Dünn"}],
            "get_collection_contents": [{"node_id": "m1", "title": "Mat1"}],  # 1 unique < 4
            "search_wlo_content": [
                {"node_id": f"c{i}", "title": f"Content{i}"} for i in range(2, 5)
            ],
        })
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Nische"}}
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Nische", req=_req("Lernpfad Nische"),
            classification=_Cls({"thema": "Nische"}), session_state=ss,
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert any("search_wlo_content" in t for t in res.tools_called)

    async def test_no_contents_not_routed(self, patch_gen, monkeypatch):
        _patch_mcp(monkeypatch, {})  # every parse returns []
        ss = {"persona_id": "P-LEHR", "entities": {"thema": "Leer"}}
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Leer", req=_req("Lernpfad Leer"),
            classification=_Cls({"thema": "Leer"}), session_state=ss,
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is False
        assert res.new_state == "S1"  # unchanged when nothing routes


class TestTopicSwitchAndReset:
    async def test_topic_switch_forces_fresh_search(self, patch_gen, monkeypatch):
        # _last_contents mentions a DIFFERENT topic → new thema not in haystack →
        # fresh P3 search instead of reusing the stale session item.
        _patch_mcp(monkeypatch, {
            "search_wlo_collections": [{"node_id": "col1", "title": "Eiszeit-Sammlung"}],
            "get_collection_contents": [
                {"node_id": f"m{i}", "title": f"Mat{i}"} for i in range(1, 5)
            ],
        })
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "Eiszeit",
                "_last_contents": json.dumps([{"node_id": "old", "title": "Altes Thema"}]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="Eiszeit", req=_req("Lernpfad Eiszeit"),
            classification=_Cls({"thema": "Eiszeit"}), session_state=ss,
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert any("search_wlo_collections" in t for t in res.tools_called)

    async def test_reset_note_when_all_used(self, patch_gen):
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "X",
                "_last_contents": json.dumps([{"node_id": "n1", "title": "A"}]),
                # n1 already used → forces reset; old1/old2 must be cleared by it
                "_lp_used_node_ids": json.dumps(["old1", "old2", "n1"]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="X", req=_req("Lernpfad X"),
            classification=_Cls({}), session_state=ss,  # no new thema → no topic-switch
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        assert "Auswahl jetzt wiederholt" in res.response_text
        # reset clears the accumulated used-ids ("[]"), then _add_used_lp_ids
        # immediately re-adds only THIS path's id → old1/old2 gone, n1 remains.
        assert json.loads(ss["entities"]["_lp_used_node_ids"]) == ["n1"]


class TestGenerationSideEffects:
    async def test_speculative_qr_task_started(self, patch_gen, monkeypatch):
        monkeypatch.setattr(lp_fast_path, "_qr_policy", lambda pid: ("speculative", 3))
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "X",
                "_last_contents": json.dumps([{"node_id": "n1", "title": "A"}]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="X", req=_req("Lernpfad X"),
            classification=_Cls({}), session_state=ss,  # no new thema → no topic-switch
            pattern_output={}, usage_acc={}, new_state="S1",
        )
        assert res.qr_mode == "speculative"
        assert res.qr_max == 3
        assert res.qr_spec_task is not None
        result = await res.qr_spec_task  # drain the task
        assert result == ["q1", "q2"]

    async def test_merkposten_erreicht_den_lp_generator(self, patch_gen):
        """K1b-Naht: der Fast-Path FÜHRT den Merkposten (Parameter Z. 95) und
        gab ihn an die spekulative QR-Erzeugung weiter — aber nicht an den
        Lernpfad-Generator selbst, den teuersten Aufruf dieses Pfades."""
        fake_lp = patch_gen
        acc = new_accumulator()
        ss = {"persona_id": "P-LEHR", "entities": {
            "thema": "X", "_last_contents": json.dumps([{"node_id": "n1", "title": "A"}])}}

        await run_lp_fast_path(
            has_lp_intent=True, thema="X", req=_req("Lernpfad X"),
            classification=_Cls({}), session_state=ss,
            pattern_output={}, usage_acc=acc, new_state="S1",
        )

        assert fake_lp.kwargs["usage_acc"] is acc

    async def test_card_text_link_filter_applied(self, patch_gen, monkeypatch):
        # pattern_output card_text_link_required=True → cards filtered to those
        # whose node_id is mentioned in the response text.
        async def _fake_lp(**kwargs):
            return "Lernpfad mit n1 erwähnt"

        monkeypatch.setattr(lp_fast_path, "generate_learning_path_text", _fake_lp)
        ss = {
            "persona_id": "P-LEHR",
            "entities": {
                "thema": "X",
                "_last_contents": json.dumps([
                    {"node_id": "n1", "title": "A"},
                    {"node_id": "n2", "title": "B"},
                ]),
            },
        }
        res = await run_lp_fast_path(
            has_lp_intent=True, thema="X", req=_req("Lernpfad X"),
            classification=_Cls({}), session_state=ss,  # no new thema → no topic-switch
            pattern_output={"card_text_link_required": True}, usage_acc={}, new_state="S1",
        )
        assert res.routed is True
        kept_ids = {c["node_id"] for c in res.wlo_cards_raw}
        assert kept_ids == {"n1"}  # only n1 is mentioned in the text
