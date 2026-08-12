"""Tests for services/page_duplicate.find_existing_by_url (Seitenkontext-
Erweiterung, Aufgabe 2) — "is this page already in WLO?".

The behaviour was measured against the live staging MCP before it was written
(2026-08-11): searching ``search_wlo_content`` with a full URL that IS in the
holdings answers ``total: 1`` with exactly that node; a URL that is not answers
``total: 0`` with no noise. That is what makes the URL the strong signal and the
title the weaker fallback — M20 asks for both.

The dangerous direction is a FALSE hit: the bot would tell the editor "we
already have this" and withhold the offer to add it. So a hit is only accepted
when the returned node really carries that URL (resp. that exact title) — the
search ranking alone is not taken as proof.

``call_mcp_tool`` is patched on this module; the parser runs for real.
"""

from __future__ import annotations

import asyncio
import json

from boerdi.services import page_duplicate as m

URL = "https://www.geogebra.org/classic/ahzTeJKG"
TITLE = "Huygen'sches Prinzip und Snellius'sches Brechungsgesetz"


def _envelope(*nodes: dict) -> str:
    return json.dumps({"total": len(nodes), "count": len(nodes), "results": list(nodes)})


def _node(node_id: str = "n1", title: str = TITLE, url: str = URL) -> dict:
    return {"nodeId": node_id, "title": title, "url": url, "nodeType": "content"}


def _patch(monkeypatch, *answers: str) -> list[dict]:
    """Serve one canned answer per call; record the arguments."""
    seen: list[dict] = []
    queue = list(answers)

    async def fake_call(tool_name: str, arguments: dict) -> str:
        seen.append({"tool": tool_name, **arguments})
        return queue.pop(0) if queue else _envelope()

    monkeypatch.setattr(m, "call_mcp_tool", fake_call)
    return seen


def _find(url: str = URL, title: str = TITLE):
    return asyncio.run(m.find_existing_by_url(url, title))


# ── Treffer über die Adresse ────────────────────────────────────────
def test_treffer_ueber_die_adresse(monkeypatch):
    _patch(monkeypatch, _envelope(_node()))
    assert _find() == {"node_id": "n1", "title": TITLE, "matched_on": "url"}


def test_adressen_treffer_spart_die_zweite_suche(monkeypatch):
    seen = _patch(monkeypatch, _envelope(_node()))
    _find()
    assert len(seen) == 1
    assert seen[0]["query"] == URL


def test_abweichende_schreibweise_der_adresse_zaehlt_als_dieselbe(monkeypatch):
    # Nachgestellter Schrägstrich und Groß-/Kleinschreibung im Host sind
    # dieselbe Seite; der Pfad bleibt unangetastet (er IST unterscheidend).
    _patch(monkeypatch, _envelope(_node(url=URL + "/")))
    got = _find(url="https://WWW.GeoGebra.org/classic/ahzTeJKG")
    assert got is not None and got["matched_on"] == "url"


def test_anderer_pfad_ist_keine_dublette(monkeypatch):
    # Die Suche rankt unscharf. Ein Treffer, der eine ANDERE Adresse trägt,
    # darf nicht als Dublette durchgehen — sonst verschweigt der Bot das
    # Erschliessungs-Angebot für eine Seite, die es nicht gibt.
    _patch(
        monkeypatch,
        _envelope(_node(url="https://www.geogebra.org/classic/ANDERE")),
        _envelope(),  # Titel-Suche findet nichts
    )
    assert _find(title="Ein ganz anderer Titel") is None


# ── Treffer über den Titel ──────────────────────────────────────────
def test_treffer_ueber_den_titel_wenn_die_adresse_nichts_findet(monkeypatch):
    seen = _patch(monkeypatch, _envelope(), _envelope(_node(node_id="n2", url="https://woanders.de/x")))
    got = _find()
    assert got == {"node_id": "n2", "title": TITLE, "matched_on": "title"}
    assert [s["query"] for s in seen] == [URL, TITLE]


def test_titel_vergleich_ignoriert_rand_und_schreibweise(monkeypatch):
    _patch(monkeypatch, _envelope(), _envelope(_node(title="  " + TITLE.upper() + " ")))
    got = _find()
    assert got is not None and got["matched_on"] == "title"


def test_aehnlicher_titel_ist_keine_dublette(monkeypatch):
    # Der Titel-Zweig verlangt Gleichheit, nicht Ähnlichkeit: "Arbeitsblatt
    # Bruchrechnen" gibt es dutzendfach, ohne dass es Dubletten wären.
    _patch(monkeypatch, _envelope(), _envelope(_node(title=TITLE + " — Teil 2")))
    assert _find() is None


def test_ohne_titel_wird_nur_die_adresse_gesucht(monkeypatch):
    seen = _patch(monkeypatch, _envelope())
    assert _find(title="") is None
    assert len(seen) == 1


# ── kein Treffer / Fehler ───────────────────────────────────────────
def test_kein_treffer_ist_none(monkeypatch):
    _patch(monkeypatch, _envelope(), _envelope())
    assert _find() is None


def test_mcp_fehlertext_wird_nicht_als_treffer_gelesen(monkeypatch):
    _patch(monkeypatch, "MCP error: server unreachable", "MCP error: server unreachable")
    assert _find() is None


def test_ausnahme_kommt_nicht_nach_oben(monkeypatch):
    async def boom(tool_name: str, arguments: dict) -> str:
        raise RuntimeError("mcp down")

    monkeypatch.setattr(m, "call_mcp_tool", boom)
    # Die Meldung im Chat darf nicht an der Dublettenprüfung scheitern.
    assert _find() is None


def test_ohne_adresse_wird_gar_nicht_gesucht(monkeypatch):
    seen = _patch(monkeypatch)
    assert _find(url="  ") is None
    assert seen == []
