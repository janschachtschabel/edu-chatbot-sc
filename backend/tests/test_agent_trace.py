"""AG-1 — die Spur der Agent-Schleife (Plan 2026-09-26 §8).

Bis hier kannte ein Zug nur Summen: Runden, Ende-Grund, echte Werkzeuge. Welche
Runde was gerufen hat, wie lange sie lief und was sie gekostet hat, ging
verloren, und die virtuellen Werkzeuge (``zeige_dokument``, ``liefere_ergebnis``
…) tauchten nirgends auf. Die Schleife führt deshalb je Runde einen Eintrag.

Argumente erscheinen nur mit ihren NAMEN: die Werte können Nutzerinhalt oder
einen Bestätigungs-Schlüssel tragen — dieselbe Linie wie bei den
Fortschritts-Ereignissen (``test_agent_loop``).
"""

from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from boerdi.obs.usage import new_accumulator
from tests.test_agent_loop import (
    _lauf,
    _resp_text,
    _resp_tools,
    _tool_call,
    _uhr,
    _usage,
)

# ── T1: je Runde ein Eintrag ─────────────────────────────────────────────


def test_jede_runde_hinterlaesst_einen_eintrag(monkeypatch):
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("search_wlo_content",
                                {"query": "geheim", "maxResults": 5})]),
        _resp_text("fertig"),
    ])
    assert [r["runde"] for r in run.runden] == [1, 2]
    assert run.runden[0]["werkzeuge"] == [
        {"name": "search_wlo_content", "argumente": ["maxResults", "query"]}]
    assert run.runden[1]["werkzeuge"] == []
    # Nur die Namen der Argumente: der Wert ist Nutzerinhalt.
    assert "geheim" not in json.dumps(run.runden, ensure_ascii=False)


def test_virtuelle_werkzeuge_stehen_in_der_spur(monkeypatch):
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([
            _tool_call("search_wlo_content", {"query": "a"}, "c1"),
            _tool_call("zeige_dokument", {"titel": "Plan", "markdown": "# Plan"}, "c2"),
        ]),
        _resp_text("fertig"),
    ])
    assert [w["name"] for w in run.runden[0]["werkzeuge"]] == [
        "search_wlo_content", "zeige_dokument"]
    # ``tools_called`` bleibt, was es war: die echten Werkzeuge. Die Spur
    # ergänzt, sie ersetzt nichts.
    assert run.tools_called == ["search_wlo_content"]


def test_token_je_runde(monkeypatch):
    acc = new_accumulator()
    # Ein früherer Schritt desselben Zugs (Safety) gehört keiner Runde.
    acc["prompt_tokens"] = 5000
    mit_cache = SimpleNamespace(
        prompt_tokens=200, completion_tokens=20,
        prompt_tokens_details=SimpleNamespace(cached_tokens=150))
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("search_wlo_content", {"query": "a"})],
                    usage=_usage(prompt=100, completion=10)),
        _resp_text("fertig", usage=mit_cache),
    ], usage_acc=acc, echter_transport=True)
    assert [(r["prompt_tokens"], r["cached_tokens"], r["completion_tokens"])
            for r in run.runden] == [(100, 0, 10), (200, 150, 20)]


def test_dauer_je_runde_aus_der_uhr(monkeypatch):
    # Uhr-Protokoll: der Start, dann je Runde EIN Wert — die Frist-Prüfung ist
    # zugleich Beginn dieser und Ende der vorigen Runde —, zum Schluss das
    # Laufende. Eine Runde dauert damit genau bis zur nächsten.
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("search_wlo_content", {"query": "a"})]),
        _resp_text("fertig"),
    ], clock=_uhr(0.0, 1.0, 3.5, 3.75))
    assert [r["dauer_ms"] for r in run.runden] == [2500, 250]


def _suche(q: str, cid: str):
    return _resp_tools([_tool_call("search_wlo_content", {"query": q}, cid)])


def _ausgang(grund: str) -> tuple[list, dict]:
    """Antworten und Lauf-Argumente, die genau diesen Ausgang erzwingen."""
    from boerdi.domain.config_models.engine import AgentLimits

    return {
        "text": ([_resp_text("fertig")], {}),
        "max_iterations": ([_suche("a", "c1"), _suche("b", "c2")],
                           {"limits": AgentLimits(max_iterations=2)}),
        "submit": ([_resp_tools([_tool_call("submit_result", {"text": "fertig"})])], {}),
        "empty": ([_resp_text("")], {}),
        "no_progress": ([_suche("a", "c1")], {}),
        "error": ([], {"raises": RuntimeError("boom")}),
        # Frist und Budget NACH einer Runde: die Runde schliesst dann oben in
        # der Schleife, nicht in ``schluss()``.
        "deadline": ([_suche("a", "c1"), _suche("b", "c2")],
                     {"limits": AgentLimits(deadline_s=10), "clock": _uhr(0.0, 0.0, 40.0)}),
        "token_budget": ([_resp_tools([_tool_call("search_wlo_content", {"query": "a"})],
                                      usage=_usage(prompt=900, completion=200)),
                          _suche("b", "c2")],
                         {"limits": AgentLimits(token_budget=1000),
                          "usage_acc": new_accumulator(), "echter_transport": True}),
    }[grund]


@pytest.mark.parametrize("grund", [
    "text", "max_iterations", "submit", "empty", "no_progress", "error", "deadline",
    "token_budget",
])
def test_keine_runde_bleibt_offen(monkeypatch, grund):
    """Jeder Ausgang schließt die letzte Runde — sonst fehlten ihr Dauer und
    Token, und genau die Runde, an der der Lauf endete, wäre die stumme. Alle
    acht Ausgänge, damit ein künftiges ``return`` an ``schluss()`` vorbei rot
    wird (Review 2026-09-26)."""
    antworten, kwargs = _ausgang(grund)
    _fake, run, _msgs = _lauf(monkeypatch, antworten, **kwargs)
    assert run.stop_reason == grund
    assert run.runden
    for runde in run.runden:
        assert set(runde) == {"runde", "werkzeuge", "dauer_ms", "prompt_tokens",
                              "cached_tokens", "completion_tokens"}


def test_auch_die_abgebrochene_runde_steht_in_der_spur(monkeypatch):
    """Der Stillstand fällt MITTEN in der Runde — gerufen hat das Modell
    trotzdem, und genau diesen Aufruf will man in der Spur sehen."""
    gleich = _resp_tools([_tool_call("search_wlo_content", {"query": "a"})])
    _fake, run, _msgs = _lauf(monkeypatch, [gleich])
    assert run.stop_reason == "no_progress"
    assert len(run.runden) == 2
    assert run.runden[1]["werkzeuge"][0]["name"] == "search_wlo_content"


def test_llm_fehler_hinterlaesst_eine_runde_ohne_werkzeug(monkeypatch):
    _fake, run, _msgs = _lauf(monkeypatch, [], raises=RuntimeError("boom"))
    assert run.stop_reason == "error"
    assert [r["werkzeuge"] for r in run.runden] == [[]]


def test_frist_vor_der_ersten_runde_hinterlaesst_keinen_eintrag(monkeypatch):
    """Frist und Token-Budget greifen VOR dem Aufruf — ohne Aufruf keine Runde."""
    from boerdi.domain.config_models.engine import AgentLimits

    _fake, run, _msgs = _lauf(monkeypatch, [_resp_text("nie")],
                              limits=AgentLimits(deadline_s=10),
                              clock=_uhr(0.0, 40.0))
    assert run.stop_reason == "deadline"
    assert run.runden == []


# -- T2: aus den Runden wird die Spur des Debug-Blocks ----------------------

_RUNDEN = [
    {"runde": 1,
     "werkzeuge": [{"name": "search_wlo_content", "argumente": ["query"]},
                   {"name": "zeige_dokument", "argumente": ["markdown", "titel"]}],
     "dauer_ms": 2500, "prompt_tokens": 100, "cached_tokens": 0, "completion_tokens": 10},
    {"runde": 2, "werkzeuge": [], "dauer_ms": 250,
     "prompt_tokens": 200, "cached_tokens": 150, "completion_tokens": 20},
]


def test_je_runde_eine_zeile_und_zum_schluss_das_ende():
    from boerdi.services.agent_trace import spur

    zeilen = spur(_RUNDEN, "text")
    assert [(z.step, z.label, z.duration_ms) for z in zeilen] == [
        ("agent_round", "Runde 1: search_wlo_content, zeige_dokument", 2500),
        ("agent_round", "Runde 2: ohne Werkzeug", 250),
        ("agent_stop", "Ende: text", 2750),
    ]
    assert zeilen[0].data == _RUNDEN[0]
    assert zeilen[2].data == {"stop_reason": "text", "runden": 2}


def test_ohne_runde_bleibt_nur_das_ende():
    from boerdi.services.agent_trace import spur

    assert [(z.step, z.duration_ms, z.data) for z in spur([], "deadline")] == [
        ("agent_stop", 0, {"stop_reason": "deadline", "runden": 0})]


def test_die_spur_teilt_nichts_mit_dem_lauf():
    """Die Zeilen tragen Kopien: wer die Spur nachbearbeitet (Kuerzen fuer die
    Anzeige, Schwaerzen), darf den Lauf nicht mitveraendern."""
    from boerdi.services.agent_trace import spur

    zeilen = spur(_RUNDEN, "text")
    zeilen[0].data["werkzeuge"].clear()
    assert _RUNDEN[0]["werkzeuge"]


# -- T3: der Antwort-Knoten legt die Spur auf den Debug-Block ----------------


@pytest.mark.anyio
async def test_respond_agent_legt_die_spur_auf_den_debug_block(monkeypatch):
    from boerdi.graph.nodes.respond_agent import respond_agent
    from boerdi.services.agent_loop import AgentRun
    from tests.test_respond_agent import _ctx, _patch

    lauf = AgentRun(text="Antwort", stop_reason="text", iterations=2,
                    runden=copy.deepcopy(_RUNDEN))
    _patch(monkeypatch, {}, lauf=lauf)
    ctx = _ctx()
    await respond_agent(ctx)
    assert [z.step for z in ctx.debug.trace] == [
        "agent_round", "agent_round", "agent_stop"]
    assert ctx.debug.trace[-1].data == {"stop_reason": "text", "runden": 2}
