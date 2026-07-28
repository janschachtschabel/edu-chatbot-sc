"""Charakterisierungs-Tests für ``services/outcome_service.py``.

KEIN ALT-Unit-Test → frisch geschrieben (wie state_machine 4-4c). Pinnt
``call_with_outcome`` (Status/item_count-Heuristik/Latency/Fehlerpfad) +
``adjust_confidence`` + ``derive_state_hint``. ``call_mcp_tool`` wird am
outcome_service-Modul gefaked (kein Netz, keine DB).
"""

from __future__ import annotations

import asyncio

from boerdi.api.schemas import ToolOutcome
from boerdi.services import outcome_service as os_


def _wire_call(monkeypatch, result=None, exc=None):
    async def fake(tool, args):
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(os_, "call_mcp_tool", fake)


# ═══ call_with_outcome ═════════════════════════════════════════════════════
def test_call_with_outcome_success_zaehlt_nodeids(monkeypatch):
    _wire_call(monkeypatch, '{"results":[{"nodeId":"a"},{"nodeId":"b"}]}')
    result, outcome = asyncio.run(
        os_.call_with_outcome("search_wlo_content", {"query": "x"}))
    assert outcome.tool == "search_wlo_content"
    assert outcome.status == "success"
    assert outcome.item_count == 2  # 2× "nodeId"
    assert outcome.latency_ms >= 0
    assert result.startswith("{")


def test_call_with_outcome_nicht_such_tool_ist_eins(monkeypatch):
    _wire_call(monkeypatch, "irgendein markdown ohne knoten")
    _, outcome = asyncio.run(os_.call_with_outcome("lookup_wlo_vocabulary", {}))
    assert outcome.status == "success"
    assert outcome.item_count == 1  # Nicht-Such-Tool → 1


def test_call_with_outcome_search_bullet_fallback(monkeypatch):
    # Search-Tool ohne "nodeId" → count("- ")-Fallback (or-Kurzschluss).
    _wire_call(monkeypatch, "- treffer eins\n- treffer zwei\n- drei")
    _, outcome = asyncio.run(os_.call_with_outcome("search_wlo_collections", {}))
    assert outcome.item_count == 3


def test_call_with_outcome_leer_ist_empty(monkeypatch):
    _wire_call(monkeypatch, "   ")
    result, outcome = asyncio.run(os_.call_with_outcome("search_wlo_content", {}))
    assert outcome.status == "empty"
    assert outcome.item_count == 0
    assert result == "   "  # roher Result bleibt (nur Status ist empty)


def test_call_with_outcome_exception_ist_error(monkeypatch):
    _wire_call(monkeypatch, exc=RuntimeError("boom " * 60))  # str >200 Zeichen
    result, outcome = asyncio.run(os_.call_with_outcome("search_wlo_content", {}))
    assert outcome.status == "error"
    assert result == ""
    assert len(outcome.error) == 200  # str(e)[:200]
    assert outcome.latency_ms >= 0


# ═══ adjust_confidence ═════════════════════════════════════════════════════
def test_adjust_confidence_deltas_und_clamp():
    b = 0.5
    assert round(os_.adjust_confidence(b, [ToolOutcome(status="error")]), 2) == 0.3
    assert round(os_.adjust_confidence(b, [ToolOutcome(status="empty")]), 2) == 0.4
    assert round(
        os_.adjust_confidence(b, [ToolOutcome(status="success", item_count=2)]), 2) == 0.55
    assert round(os_.adjust_confidence(b, [ToolOutcome(status="timeout")]), 2) == 0.35
    # success mit item_count=0 → kein Bonus
    assert round(
        os_.adjust_confidence(b, [ToolOutcome(status="success", item_count=0)]), 2) == 0.5
    # Clamp unten: viele Errors → 0.0 (nicht negativ)
    assert os_.adjust_confidence(0.1, [ToolOutcome(status="error")] * 3) == 0.0
    # Clamp oben: viele Success → 1.0
    assert os_.adjust_confidence(
        0.99, [ToolOutcome(status="success", item_count=1)] * 5) == 1.0


# ═══ derive_state_hint ═════════════════════════════════════════════════════
def test_derive_state_hint_leer():
    assert os_.derive_state_hint([]) == ""


def test_derive_state_hint_alle_fehlgeschlagen_clarification():
    outs = [
        ToolOutcome(status="error"),
        ToolOutcome(status="empty"),
        ToolOutcome(status="timeout"),
    ]
    assert os_.derive_state_hint(outs) == "state-clarification"


def test_derive_state_hint_erfolg_S3():
    outs = [ToolOutcome(status="error"), ToolOutcome(status="success", item_count=3)]
    assert os_.derive_state_hint(outs) == "S3"


def test_derive_state_hint_success_ohne_items_neutral():
    # success aber item_count=0 → weder all-failed noch successful → ""
    assert os_.derive_state_hint([ToolOutcome(status="success", item_count=0)]) == ""
