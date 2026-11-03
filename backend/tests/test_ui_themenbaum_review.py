"""Review U1-e: Befunde zum Themenbaum (`ui_themenbaum`) und seiner Datenquelle.

Je Befund ein Block; die Nummern sind die des Reviews (Plan §15, „Review-Befunde“).
"""

from __future__ import annotations

import asyncio
import json

import pytest

from boerdi.api.schemas import ChatResponse, SafetyDecision
from boerdi.domain.config_models.engine import AgentLimits
from boerdi.graph.nodes import preflight as pf_mod
from boerdi.graph.nodes.preflight import preflight
from boerdi.obs.usage import bind_turn_usage, new_accumulator
from boerdi.services import agent_tool_overview as ov
from boerdi.services import agent_tools, themenbaum_aktion
from boerdi.ui_module import datenquelle, katalog, themenbaum
from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call
from tests.test_preflight_node import (
    _SESSION,
    _ctx,
    _patch_db,
    _patch_handlers,
    _patch_safety,
    _Spy,
)
from tests.test_tool_loop import _run_loop
from tests.test_ui_themenbaum import THEMENBAUM, WERKZEUG, _knoten, _payload, _Rufer
from tests.test_ui_themenbaum_aktion import KNOTEN, _laufen, _req, save  # noqa: F401 — Fixture

RESPOND = "respond_to_user"


def _fehlschlag(monkeypatch, art: str = "transport") -> _Rufer:
    rufer = _Rufer("MCP error: weg", art)
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    return rufer


def _tool_inhalt(msgs: list[dict], call_id: str) -> str:
    return next(m["content"] for m in msgs if m.get("tool_call_id") == call_id)


# ── Befund 1: keine Antwort derselben Runde, wenn der Baum fehlt ─────────


def test_agent_verwirft_die_antwort_derselben_runde_ohne_baum(monkeypatch):
    """Antwort VOR dem Modul in derselben Runde: die Person läse „hier ist der Baum“ ohne Baum."""
    _fehlschlag(monkeypatch)
    fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(RESPOND, {"text": "Hier ist der Themenbaum."}, "c1"),
                     _tool_call(THEMENBAUM, {"subject": "Mathe"}, "c2")]),
        _resp_tools([_tool_call(RESPOND, {"text": "Der Baum lässt sich gerade nicht laden."},
                                "c3")]),
    ])

    assert run.text == "Der Baum lässt sich gerade nicht laden."
    assert run.ui_bloecke == [] and len(fake.calls) == 2
    # Die zweite Runde sieht den Fehler und erfährt, dass ihre Antwort nicht übernommen wurde.
    assert _tool_inhalt(msgs, "c1") == datenquelle.ANTWORT_VERWORFEN
    assert _tool_inhalt(msgs, "c2").startswith("Fehler")


def test_agent_am_iterationsdeckel_bleibt_es_beim_ehrlichen_ende(monkeypatch):
    """Letzte Runde: kein Text aus der verworfenen Antwort — ``respond_agent`` holt den Abschluss
    nach oder setzt den Deckel-Satz (``agent_abschluss``)."""
    _fehlschlag(monkeypatch)
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"}, "c1"),
                     _tool_call(RESPOND, {"text": "Hier ist der Themenbaum."}, "c2")]),
    ], limits=AgentLimits(max_iterations=1))
    assert run.stop_reason == "max_iterations" and run.text == ""


def test_agent_mit_baum_gilt_die_antwort_derselben_runde(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"}, "c1"),
                     _tool_call(RESPOND, {"text": "Hier ist der Themenbaum."}, "c2")]),
    ])
    assert run.text == "Hier ist der Themenbaum." and len(run.ui_bloecke) == 1
    assert len(fake.calls) == 1


def test_muster_verwirft_die_antwort_derselben_runde_ohne_baum(monkeypatch):
    _fehlschlag(monkeypatch)
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([("c1", RESPOND, json.dumps({"text": "Hier ist der Themenbaum."})),
                     ("c2", THEMENBAUM, json.dumps({"subject": "Mathe"}))]),
        _resp_text("Der Baum lässt sich gerade nicht laden."),
    ])
    assert result[0] == "Der Baum lässt sich gerade nicht laden."
    assert len(fake.calls) == 2
    assert _tool_inhalt(st["messages"], "c1") == datenquelle.ANTWORT_VERWORFEN
    assert _tool_inhalt(st["messages"], "c2").startswith("Fehler")


def test_muster_am_iterationsdeckel_faellt_auf_den_abschluss_zurueck(monkeypatch):
    """Jede Runde dasselbe: die Schleife endet ohne Text (``None``) — ``generate`` ruft dann
    ``_max_iterations_fallback``, nicht die verworfene Antwort."""
    _fehlschlag(monkeypatch)
    runde = _resp_tools([("c1", THEMENBAUM, json.dumps({"subject": "Mathe"})),
                         ("c2", RESPOND, json.dumps({"text": "Hier ist der Themenbaum."}))])
    fake, result, _st = _run_loop(monkeypatch, [runde] * 5)      # Deckel der Schleife: 5
    assert result is None and len(fake.calls) == 5


def test_muster_mit_baum_gilt_die_antwort_derselben_runde(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    fake, result, _st = _run_loop(monkeypatch, [
        _resp_tools([("c1", THEMENBAUM, json.dumps({"subject": "Mathe"})),
                     ("c2", RESPOND, json.dumps({"text": "Hier ist der Themenbaum."}))]),
    ])
    assert result[0] == "Hier ist der Themenbaum." and len(fake.calls) == 1


# ── Befund 2: mehr Themen oben, als der Baum zeigt ───────────────────────


def _oben(n: int) -> list[dict]:
    return [_knoten(f"o{i:02d}-0000", f"Thema {i}") for i in range(n)]


def test_die_vorgabe_holt_einen_knoten_mehr_als_der_baum_zeigt():
    """Der Server meldet nicht, ob es oben mehr gibt (``truncated`` gilt nur für Zweige) — der
    eine Knoten mehr beweist es (``collection-traversal.ts``)."""
    vorgaben = katalog.katalog()[THEMENBAUM]["datenquelle"]["vorgaben"]
    assert vorgaben["maxResults"] == themenbaum.HOECHSTENS_OBEN + 1


def test_31_knoten_oben_werden_30_und_eine_marke():
    daten = themenbaum.daten_aus(_payload(results=_oben(31), truncated=False), titel="Mathe")
    assert len(daten["knoten"]) == 30
    assert daten["wurzel_mehr"] is True
    assert "gekuerzt" not in daten                    # kein Zweig gekürzt
    assert not katalog.daten_fehler(katalog.katalog()[THEMENBAUM], daten)


def test_30_knoten_oben_sind_vollstaendig():
    daten = themenbaum.daten_aus(_payload(results=_oben(30), truncated=False))
    assert len(daten["knoten"]) == 30 and "wurzel_mehr" not in daten


def test_die_wurzel_bekommt_eine_adresse_in_wlo():
    daten = themenbaum.daten_aus(_payload(results=_oben(31)))
    assert daten["wurzel_url"].startswith(("https://", "http://"))
    assert daten["wurzel_url"].endswith("/edu-sharing/components/collections?id=aaaa-1111")


def test_quittung_und_textfassung_nennen_die_kuerzung_oben():
    daten = themenbaum.daten_aus(_payload(results=_oben(31), truncated=False), titel="Mathe")
    quittung = themenbaum.quittung(daten)
    assert "mehr Themen" in quittung
    assert "Thema 0" not in quittung and "o00-0000" not in quittung
    assert themenbaum.textfassung(daten).splitlines()[-1] == "- …"


# ── Befund 3: die Direktaktion fragt das Angebot ─────────────────────────


@pytest.mark.parametrize("sperre", ["sicherheit", "verborgen", "einbettung"])
def test_die_direktaktion_ruft_kein_gesperrtes_werkzeug(monkeypatch, save, sperre):  # noqa: F811
    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    gesperrt: list[str] = []
    req = _req(collection_id=KNOTEN, title="Algebra")
    if sperre == "sicherheit":
        gesperrt = [WERKZEUG]
    elif sperre == "verborgen":
        monkeypatch.setattr(agent_tools, "verborgene_werkzeuge", lambda: frozenset({WERKZEUG}))
    else:
        # Kein Modus nimmt ein lesendes Werkzeug — die Prüfung selbst muss den Modus fragen.
        monkeypatch.setattr(agent_tools, "erlaubt", lambda name, modus: name != WERKZEUG)
        req.environment.tool_mode = "read-only"

    resp = asyncio.run(themenbaum_aktion.handle_show_collection_tree(
        _SESSION, req, {}, blocked_tools=gesperrt))

    assert rufer.calls == [] and resp.ui.ui_bloecke == []
    assert "Algebra" in resp.content          # „Die Unterthemen von "Algebra" ließen sich …“


def test_der_verteiler_reicht_die_sperren_der_sicherheit_weiter(monkeypatch):
    _patch_handlers(monkeypatch)
    baum = _Spy(ChatResponse(session_id="bb-1", content="BAUM-OK"))
    monkeypatch.setattr(pf_mod, "handle_show_collection_tree", baum)
    _patch_db(monkeypatch)
    _patch_safety(monkeypatch, SafetyDecision(risk_level="low", blocked_tools=[WERKZEUG]))
    asyncio.run(preflight(_ctx("show_collection_tree", collection_id=KNOTEN), _SESSION))
    assert baum.calls[0]["kwargs"]["blocked_tools"] == [WERKZEUG]


# ── Befund 5: unerreichbar ist kein falsches Argument ────────────────────


@pytest.mark.anyio
@pytest.mark.parametrize("art", ["transport", "timeout", "auth"])
async def test_unerreichbar_sagt_nicht_wiederholen(monkeypatch, art):
    _fehlschlag(monkeypatch, art)
    ergebnis = await datenquelle.aufruf(THEMENBAUM, {"subject": "Mathe"})
    assert ergebnis.block is None
    assert "nicht erreichbar" in ergebnis.text and "nicht noch einmal" in ergebnis.text
    assert "Prüfe das Argument" not in ergebnis.text
    assert ergebnis.outcome.status == ("timeout" if art == "timeout" else "error")


@pytest.mark.anyio
async def test_eine_ablehnung_des_servers_bittet_um_ein_anderes_argument(monkeypatch):
    _fehlschlag(monkeypatch, "tool")
    ergebnis = await datenquelle.aufruf(THEMENBAUM, {"subject": "Xyz"})
    assert "Prüfe das Argument" in ergebnis.text
    assert ergebnis.outcome.status == "error"


# ── Befund 6: der Aufruf steht in Protokoll, Ergebnissen und Zeiten ──────


def test_agent_fuehrt_den_aufruf_der_datenquelle_im_protokoll(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    acc = new_accumulator()
    bind_turn_usage(acc)
    try:
        _fake, run, _msgs = _lauf(monkeypatch, [
            _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"})]),
            _resp_text("Hier die Themen."),
        ])
    finally:
        bind_turn_usage(None)
    assert run.tools_called == [THEMENBAUM]
    [outcome] = run.outcomes
    assert (outcome.tool, outcome.status, outcome.item_count) == (THEMENBAUM, "success", 2)
    assert "respond.werkzeuge" in acc["zeiten_ms"]


def test_agent_fuehrt_auch_den_fehlschlag(monkeypatch):
    _fehlschlag(monkeypatch, "timeout")
    _fake, run, _msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(THEMENBAUM, {"subject": "Mathe"})]),
        _resp_text("Ohne Baum."),
    ])
    assert run.tools_called == [THEMENBAUM]
    assert [o.status for o in run.outcomes] == ["timeout"]


def test_muster_fuehrt_den_aufruf_der_datenquelle_im_protokoll(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    _fake, result, _st = _run_loop(monkeypatch, [
        _resp_tools([("c1", THEMENBAUM, json.dumps({"subject": "Mathe"}))]),
        _resp_text("Hier die Themen."),
    ])
    _text, _karten, gerufen, outcomes = result
    assert gerufen == [THEMENBAUM]
    assert [(o.tool, o.status) for o in outcomes] == [(THEMENBAUM, "success")]


@pytest.mark.anyio
async def test_ein_leerer_baum_ist_ein_leeres_ergebnis(monkeypatch):
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer(json.dumps(_payload(results=[]))))
    ergebnis = await datenquelle.aufruf(THEMENBAUM, {"nodeId": "aaaa-1111"})
    assert ergebnis.block is not None
    assert (ergebnis.outcome.status, ergebnis.outcome.item_count) == ("empty", 0)


# ── Befund 8: die Werkzeugübersicht nennt die Datenquelle ────────────────


def _zeile(name: str) -> dict:
    return next(t for t in ov.werkzeugliste()["tools"] if t["name"] == name)


@pytest.fixture
def _ohne_quellen(monkeypatch):
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})


@pytest.mark.usefixtures("_ohne_quellen")
def test_die_uebersicht_nennt_das_werkzeug_der_datenquelle_als_bedingung():
    zeile = _zeile(THEMENBAUM)
    assert zeile["offered"] is True
    assert zeile["locks"] == [{"code": "widget_module"},
                              {"code": "data_source", "tool": WERKZEUG}]


@pytest.mark.usefixtures("_ohne_quellen")
def test_ist_das_werkzeug_abgeschaltet_fehlt_der_themenbaum_mit_grund(monkeypatch):
    aus = frozenset({WERKZEUG})
    monkeypatch.setattr(agent_tools, "verborgene_werkzeuge", lambda: aus)
    monkeypatch.setattr(ov, "verborgene_werkzeuge", lambda: aus)
    zeile = _zeile(THEMENBAUM)
    assert zeile["offered"] is False
    assert {"code": "data_source", "tool": WERKZEUG} in zeile["locks"]


# ── Befund 10/11: Werkzeug aus dem Manifest, Begleitsatz ohne Überschrift ─


def test_die_direktaktion_nimmt_das_werkzeug_aus_dem_manifest():
    assert themenbaum_aktion._werkzeug() == WERKZEUG


def test_der_begleitsatz_wiederholt_die_ueberschrift_des_blocks_nicht(monkeypatch, save):  # noqa: F811
    monkeypatch.setattr(datenquelle, "_rufen", _Rufer())
    resp = _laufen(_req(collection_id=KNOTEN, title="Algebra"))
    [block] = resp.ui.ui_bloecke
    assert block.daten["titel"] == "Algebra"          # der Block beschreibt sich selbst
    assert "Algebra" not in resp.content
