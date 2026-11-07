"""Paket M4, Review-Befunde (Plan 2026-11-07): was das Modell von den neuen Lese-Werkzeugen sieht.

- ``get_skill_registry`` mit ``task``: die gewählte Anleitung kommt ungekürzt an und läuft wie nach
  ``get_skill`` (Faden für den Folgezug, Ansage); bei ``ambiguous``/``none`` bleibt das Urteil des
  Servers vor dem gekürzten Katalog stehen.
- Zählung: eine Anfrage, die der Server nicht annähme, fällt einzeln weg — nie der ganze Aufruf,
  nie still ohne Filter.
- Übersicht und Zählung: Fehlzeilen vor dem Deckel, keine Teilantwort im Cache.
"""

from __future__ import annotations

import json

from boerdi.domain.tool_result_redaction import (
    _redact_search_content_for_llm,
    gewaehlte_anleitung,
    redigiere_strukturell,
)
from boerdi.services.mcp.tool_args import validate_tool_args
from boerdi.services.mcp.tool_cache import _ttl_for_tool, cache_gesperrt
from boerdi.services.safety.regex_gate import SPERRE_PERSOENLICH
from tests.test_mcp_client import mcp_state  # noqa: F401 — Fixture

_ANLEITUNG = "Ablauf in fünf Schritten. " * 600  # ~15 000 Zeichen, weit über dem Deckel

_GEFUNDEN = "\n".join([
    "Für „Stunde planen“ passt aus den 28 freigegebenen Skills: Stunde planen (nodeId: s-1). "
    "Die Anleitung steht unten.",
    "Den ganzen Katalog liefert get_skill_registry ohne task.",
    "",
    "# Stunde planen",
    "nodeId: s-1",
    "",
    "---",
    "",
    "### Einstieg",          # eine Gliederung im Skill-Text, die wie ein Katalog-Eintrag aussieht
    "nodeId: falsch",
    "",
    _ANLEITUNG,
])

_UNKLAR = "\n".join([
    "Zu „Arbeitsblatt“ passt keiner der 28 freigegebenen Skills eindeutig — die Wörter der "
    "Aufgabe unterscheiden sie nicht genug. Wähle einen und lade ihn mit get_skill.",
    "In Frage kommen, nach Übereinstimmung: Arbeitsblatt A (nodeId: a-1) · Arbeitsblatt B "
    "(nodeId: b-1)",
    "",
    "# Skill-Registry Optik",
    "Registry-Dokument: r-1 — Sammlung: c-1",
    "",
    "### Arbeitsblatt A",
    "nodeId: a-1",
    "Erstellt ein Arbeitsblatt.",
    "",
    "### Arbeitsblatt B",
    "nodeId: b-1",
    "Erstellt ein differenziertes Arbeitsblatt.",
    "",
    "Freitext der Registry " * 2000,
])


# ── get_skill_registry mit task ──────────────────────────────────────────────────────────

def test_die_gewaehlte_anleitung_kommt_ungekuerzt_an():
    assert _redact_search_content_for_llm("get_skill_registry", _GEFUNDEN, [], False) == _GEFUNDEN
    assert redigiere_strukturell("get_skill_registry", _GEFUNDEN) == _GEFUNDEN


def test_bei_unklarer_wahl_bleibt_das_urteil_vor_dem_katalog():
    for sicht in (_redact_search_content_for_llm("get_skill_registry", _UNKLAR, [], False),
                  redigiere_strukturell("get_skill_registry", _UNKLAR)):
        assert sicht.startswith("Zu „Arbeitsblatt“ passt keiner")
        assert "- a-1 — Arbeitsblatt A" in sicht and "- b-1 — Arbeitsblatt B" in sicht
        assert "Freitext der Registry" not in sicht


def test_ohne_task_bleibt_der_katalog_wie_er_war():
    katalog = _UNKLAR.split("\n\n", 1)[1]
    sicht = redigiere_strukturell("get_skill_registry", katalog)
    assert sicht.startswith("Freigegebene Skills dieser Sammlung: 2.")


def test_die_wahl_des_servers_wird_gelesen():
    assert gewaehlte_anleitung(_GEFUNDEN) == ("s-1", "Stunde planen")
    assert gewaehlte_anleitung(_UNKLAR) is None
    assert gewaehlte_anleitung("# Stunde planen\nnodeId: s-1\n\nAblauf") is None  # get_skill


def test_die_gewaehlte_anleitung_laeuft_im_musterweg(monkeypatch):
    from tests.test_tool_loop import _OutcomeFake, _resp_text, _resp_tools, _run_loop

    _fake, _result, state = _run_loop(
        monkeypatch,
        [_resp_tools([("c1", "get_skill_registry",
                       json.dumps({"collectionId": "c-1", "task": "Stunde planen"}))]),
         _resp_text("fertig")],
        outcome=_OutcomeFake({"get_skill_registry": _GEFUNDEN}),
        session_state={"turn_count": 3, "entities": {}})
    lauf = state["session_state"]["entities"]["_skill_lauf"]
    assert lauf["node_id"] == "s-1"


def test_die_gewaehlte_anleitung_laeuft_im_agentweg(monkeypatch):
    from tests.test_agent_loop import _lauf, _OutcomeFake, _resp_text, _resp_tools, _tool_call

    _, lauf, _msgs = _lauf(
        monkeypatch,
        [_resp_tools([_tool_call("get_skill_registry",
                                 {"collectionId": "c-1", "task": "Stunde planen"})]),
         _resp_text("Fertig.")],
        outcome=_OutcomeFake({"get_skill_registry": _GEFUNDEN}),
    )
    assert lauf.anleitungen == [{"node_id": "s-1", "titel": "Stunde planen"}]


def test_eine_aufgabe_wird_gekuerzt_statt_verworfen():
    out = validate_tool_args("get_skill_registry", {"collectionId": "c-1", "task": "x" * 400})
    assert out["task"] == "x" * 300


# ── Zählung ──────────────────────────────────────────────────────────────────────────────

def test_jede_anfrage_wird_einzeln_geprueft():
    out = validate_tool_args("count_wlo_content_matches", {"queries": [
        {"id": 1, "query": "Optik"},                                       # Zahl als Kennung
        {"id": "b", "query": "Linsen", "filters": None},                   # leerer Filter
        {"id": "c", "query": "Licht", "filters": {"subject": "Physik"}},   # Altname
        {"id": "d", "query": "Farben", "filters": {"license": "OER"}},     # fremder Schlüssel
        {"id": "e", "query": "x" * 501},                                   # zu lang
        {"id": "f", "query": "Spiegel", "filters": {"discipline": "y" * 201}},
    ]})
    assert out["queries"] == [
        {"id": "1", "query": "Optik"},
        {"id": "b", "query": "Linsen"},
        {"id": "c", "query": "Licht", "filters": {"discipline": "Physik"}},
    ]


def test_die_zaehlung_ist_bei_persoenlichen_daten_gesperrt():
    assert "count_wlo_content_matches" in SPERRE_PERSOENLICH


# ── Übersicht ────────────────────────────────────────────────────────────────────────────

def test_die_uebersicht_nimmt_nodeid_und_einen_teil_als_text():
    out = validate_tool_args("get_collection_overview", {"nodeId": "c-1", "include": "stats"})
    assert out["collectionId"] == "c-1" and out["include"] == ["stats"]
    assert "nodeId" not in out


def test_fehlzeilen_ueberleben_den_deckel():
    text = "\n".join(["## Optik", "nodeId: c-1",
                      "Untersammlungen: " + "; ".join(f"U{i} (3) — n-{i}" for i in range(2000)),
                      "Nicht geladen: stats (timeout) — der Rest ist vollständig."])
    sicht = _redact_search_content_for_llm("get_collection_overview", text, [], False)
    assert sicht.startswith("Nicht geladen: stats (timeout)")
    zaehlung = "\n".join([*(f"q{i}: 12 — z. B. Titel {i}" for i in range(400)),
                          "q9: nicht gezählt (unresolved_filter: Stufe unbekannt)"])
    assert _redact_search_content_for_llm(
        "count_wlo_content_matches", zaehlung, [], False).startswith("q9: nicht gezählt (")


def test_im_gruppiermodus_nennt_die_uebersicht_keine_einzelinhalte():
    text = "\n".join(["## Optik", "nodeId: c-1", "Inhalte (2 von 57):",
                      "- Linsen im Alltag", "  nodeId: m-1", "- Brechung", "  nodeId: m-2",
                      "Nicht geladen: skills (timeout) — der Rest ist vollständig."])
    sicht = _redact_search_content_for_llm("get_collection_overview", text, [], True)
    assert "Linsen im Alltag" not in sicht and "Inhalte: 57" in sicht
    assert "Nicht geladen: skills" in sicht


# ── Cache ────────────────────────────────────────────────────────────────────────────────

def test_die_skill_wahl_kommt_nie_aus_dem_cache():
    assert cache_gesperrt("get_skill_registry", {"collectionId": "c-1", "task": "x"})
    assert not cache_gesperrt("get_skill_registry", {"collectionId": "c-1"})
    assert _ttl_for_tool("get_collection_overview") == 180


def test_eine_teilantwort_kommt_nicht_in_den_cache(mcp_state, monkeypatch):  # noqa: F811
    import asyncio

    from boerdi.services.mcp import client
    from tests.test_mcp_client import _text_part, _wire_tool_url, _wire_transport

    _wire_tool_url(monkeypatch)
    teil = {"result": {"content": [_text_part("Nicht geladen: stats (timeout)")],
                       "structuredContent": {"missing": [{"part": "stats", "code": "timeout"}]}}}
    ganz = {"result": {"content": [_text_part("vollständig")],
                       "structuredContent": {"missing": []}}}
    _wire_transport(monkeypatch, [teil, ganz, ganz])
    erst = asyncio.run(client.call_mcp_tool("get_collection_overview", {"collectionId": "c-1"}))
    dann = asyncio.run(client.call_mcp_tool("get_collection_overview", {"collectionId": "c-1"}))
    assert "Nicht geladen" in erst and dann == "vollständig"
