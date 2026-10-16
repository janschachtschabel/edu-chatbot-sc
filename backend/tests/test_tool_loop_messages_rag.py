"""Der RAG-Vorabruf bucht seine Dauer in den Debug-Block (Plan 2026-09-30, T8).

RAG läuft ohne eigenen LLM-Aufruf (Einbettung + Datenbank) und taucht deshalb
in ``per_phase`` nicht auf — gemessen 0,4–1,8 s je Zug. Er steht als Schritt
``respond.rag`` in ``zeiten_ms``.
"""

from __future__ import annotations

import asyncio

from boerdi.obs import usage
from boerdi.services import tool_loop_messages as tlm
from boerdi.services.rag import retrieval


def test_der_rag_vorabruf_bucht_seine_dauer(monkeypatch):
    async def _rag(session, message, **kwargs):
        return "WLO ist eine Bildungsplattform."

    monkeypatch.setattr(retrieval, "get_rag_context", _rag)
    monkeypatch.setattr(retrieval, "get_retrieval_settings", lambda: {
        "top_k": 5, "min_score": 0.3, "max_chars_per_area": None})
    acc: dict = {}
    usage.bind_turn_usage(acc)
    try:
        asyncio.run(tlm._assemble_messages(
            None, "Was ist WLO?", [], {}, "M15", {},
            ["WLO"], {"WLO": {"mode": "always"}}, [], None, None, None,
            "SYSTEM", False, None, True,
        ))
    finally:
        usage.bind_turn_usage(None)

    assert acc["zeiten_ms"]["respond.rag"] >= 0



def _abruf_mit(monkeypatch, rag_einbettung):
    gesehen: dict = {}

    async def _rag(session, message, **kwargs):
        gesehen.update(kwargs)
        return "WLO ist eine Bildungsplattform."

    monkeypatch.setattr(retrieval, "get_rag_context", _rag)
    monkeypatch.setattr(retrieval, "get_retrieval_settings", lambda: {
        "top_k": 5, "min_score": 0.3, "max_chars_per_area": None})
    asyncio.run(tlm._assemble_messages(
        None, "Was ist WLO?", [], {}, "M15", {},
        ["WLO"], {"WLO": {"mode": "always"}}, [], None, None, None,
        "SYSTEM", False, None, True, rag_einbettung=rag_einbettung,
    ))
    return gesehen


def test_der_vorab_gerechnete_vektor_erreicht_den_abruf(monkeypatch):
    """T1 (Paket 7): die Einbettung lief neben der Klassifikation."""
    gesehen = _abruf_mit(monkeypatch, ("Was ist WLO?", [0.3]))
    assert gesehen["query_emb"] == [0.3]


def test_ein_vektor_zu_anderem_text_wird_nicht_genommen(monkeypatch):
    gesehen = _abruf_mit(monkeypatch, ("Etwas anderes", [0.3]))
    assert gesehen["query_emb"] is None
