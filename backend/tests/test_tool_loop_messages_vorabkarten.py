"""Paket 18E, 2.3: Ein Parserfehler verwarf die Vorab-Karten still.

Vorfall 2026-08-16: ``search_wlo_all`` lieferte 12 Treffer, im Chat standen 0 Karten — die
Ursache war eine eigene Parser-Kopie. Seither gilt eine Weiche; scheitert sie, steht
Werkzeugname und Fehlerart im Log (nie der Werkzeugtext).
"""

from __future__ import annotations

import asyncio
import logging

from boerdi.services import tool_loop_messages as tlm


def _kaputt(_name: str, _text: str) -> list[dict]:
    raise ValueError("unerwartete Form")


def _zusammenbauen(prefetched_tool=None, prefetched_extras=None) -> tuple:
    return asyncio.run(tlm._assemble_messages(
        None, "Was gibt es zur Optik?", [], {}, "M05", {},
        [], {}, [], prefetched_tool, prefetched_extras, None,
        "SYSTEM", False, None, False,
    ))


def test_parserfehler_beim_vorabruf_meldet_sich(monkeypatch, caplog):
    monkeypatch.setattr(tlm, "parse_cards_for_tool", _kaputt)

    with caplog.at_level(logging.WARNING, logger=tlm.__name__):
        _zusammenbauen(prefetched_tool={
            "name": "search_wlo_all", "arguments": {}, "result_text": "Optik-Treffer"})

    meldungen = [r.getMessage() for r in caplog.records]
    assert any("search_wlo_all" in m and "ValueError" in m for m in meldungen), meldungen
    assert not any("Optik" in m for m in meldungen)


def test_parserfehler_bei_den_extras_meldet_sich(monkeypatch, caplog):
    monkeypatch.setattr(tlm, "parse_cards_for_tool", _kaputt)

    with caplog.at_level(logging.WARNING, logger=tlm.__name__):
        _zusammenbauen(prefetched_extras=[
            {"name": "get_collection_contents", "arguments": {}, "result_text": "Optik"}])

    meldungen = [r.getMessage() for r in caplog.records]
    assert any("get_collection_contents" in m and "ValueError" in m for m in meldungen), \
        meldungen
