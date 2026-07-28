"""Port der ALT fetch_card_pool + run_pipeline_v2 Tests (P5-4-Tail).

MCP-Boundary gemockt (call_mcp_tool + parse_wlo_* der lazy-importierten Symbole);
run_pipeline_v2 läuft gegen die ECHTEN domain/cards-Stufen (normalize/select/links)
— damit zugleich ein Integrationstest der verketteten Pipeline.

Test-Anpassung ggü. ALT: die drei Fakes patchen die NEU-Leaf-Module
(`mcp.client`/`mcp.parsers`) statt der ALT-`mcp_client`-Fassade.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import card_pipeline as cp


@pytest.fixture
def mcp_fakes(monkeypatch):
    """Fakes für die lazy-importierten mcp-Symbole. Gibt die Liste der
    (tool, args)-Aufrufe zurück, damit Tests die Tool-Wahl + Args pinnen."""
    calls: list[tuple] = []

    async def _call(tool, args):
        calls.append((tool, args))
        return tool                       # raw = Tool-Name (deterministisch)

    monkeypatch.setattr("boerdi.services.mcp.client.call_mcp_tool", _call)
    monkeypatch.setattr(
        "boerdi.services.mcp.parsers.parse_wlo_cards",
        lambda raw: [{"node_id": "c-" + str(raw), "node_type": "content",
                      "learning_resource_types": ["Video"]}] if raw else [],
    )
    monkeypatch.setattr(
        "boerdi.services.mcp.parsers.parse_wlo_topic_page_cards",
        lambda raw: [{"node_id": "tp-" + str(raw), "node_type": "topic_page",
                      "topic_pages": [{"url": "x"}]}] if raw else [],
    )
    return calls


class TestFetchCardPool:
    def test_collection_contents_uses_nodeid(self, mcp_fakes):
        out = asyncio.run(cp.fetch_card_pool(
            query="x", intent_kind="collection-contents",
            collection_id="coll1", pool_size=9,
        ))
        assert [c["node_id"] for c in out] == ["c-get_collection_contents"]
        assert mcp_fakes[0] == ("get_collection_contents",
                                {"nodeId": "coll1", "maxResults": 9})

    def test_collection_contents_without_id_returns_empty(self, mcp_fakes):
        out = asyncio.run(cp.fetch_card_pool(
            query="x", intent_kind="collection-contents", pool_size=9,
        ))
        assert out == []
        assert mcp_fakes == []             # gar kein Tool-Call

    def test_type_focus_passes_lrt_and_discipline(self, mcp_fakes):
        out = asyncio.run(cp.fetch_card_pool(
            query="videos", intent_kind="type-focus", pool_size=9,
            learning_resource_type_uri="lrt:vid", discipline_uri="disc:1",
        ))
        tool, args = mcp_fakes[0]
        assert tool == "search_wlo_content"
        assert args["learningResourceType"] == "lrt:vid"
        assert args["discipline"] == "disc:1"
        assert args["maxResults"] == 9
        assert [c["node_id"] for c in out] == ["c-search_wlo_content"]

    def test_general_concatenates_tp_col_con_in_order(self, mcp_fakes):
        out = asyncio.run(cp.fetch_card_pool(
            query="x", intent_kind="general", pool_size=9,
        ))
        assert [c["node_id"] for c in out] == [
            "tp-search_wlo_topic_pages",
            "c-search_wlo_collections",
            "c-search_wlo_content",
        ]
        assert {t for t, _ in mcp_fakes} == {
            "search_wlo_topic_pages", "search_wlo_collections", "search_wlo_content",
        }


class TestRunPipelineV2:
    def test_prefetched_pool_skips_fetch(self, mcp_fakes):
        pool = [
            {"node_id": "C1", "node_type": "collection", "title": "Bruchrechnung"},
            {"node_id": "V1", "node_type": "content", "title": "Video",
             "url": "https://youtube.com/x"},
        ]
        res = asyncio.run(cp.run_pipeline_v2(
            user_message="Bruchrechnung", prefetched_pool=pool,
        ))
        assert res["intent_kind"] == "general"
        assert res["pool_size"] == 2
        assert res["normalized_size"] == 2
        assert res["final_size"] == len(res["cards"])
        assert all("link" in c for c in res["cards"])
        assert mcp_fakes == []             # prefetched → kein Fetch

    def test_prefetched_converts_pydantic_model(self):
        class _Model:
            def model_dump(self):
                return {"node_id": "M1", "node_type": "content",
                        "url": "https://x.de/y"}

        res = asyncio.run(cp.run_pipeline_v2(
            user_message="x", prefetched_pool=[_Model()],
        ))
        assert res["pool_size"] == 1
        assert res["cards"][0]["node_id"] == "M1"

    def test_without_prefetch_calls_fetch(self, mcp_fakes):
        res = asyncio.run(cp.run_pipeline_v2(
            user_message="Mathe", wanted_content_types={"video"},
        ))
        assert res["intent_kind"] == "type-focus"
        assert "search_wlo_content" in {t for t, _ in mcp_fakes}
        # Fake-Content hat learning_resource_types=["Video"] → überlebt den Filter.
        assert res["final_size"] == 1
