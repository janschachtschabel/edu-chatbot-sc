"""Review U1-d2 (2026-11-03): Befunde zur Entscheidung im Muster-Modus.

* Befund 1: Ein Modul-Werkzeug allein erzwingt in der ersten Runde keinen Werkzeugaufruf.
* Befund 2: Der Klassifikator sieht die Frage des vorigen Zugs (gerahmt) vor der Nachricht.
* Befund 3: Die Werkzeug-Treue der Auswertung zählt nur MCP-Werkzeuge eines Musters.
* Befund 4: Module ohne Wirkung in ``tools:`` (Inhaltsrahmen, abgeleitete) weist das Muster ab.
* Befund 5: Im Fehlerweg von ``respond`` fallen die Blöcke weg, keine Frage bleibt offen.
* Befund 8: Die Krisen-Sperrliste schlägt nur MCP-Werkzeuge vor.
* Befund 9: Eine Runde mit abfragendem Modul ist die Antwort (Phase ``response``).
* Befund 11: Der Schlüssel der Modul-Blöcke im ``session_state`` ist nicht der Debug-Schlüssel.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from boerdi.api.schemas import ChatRequest, ClassificationResult, SafetyDecision
from boerdi.domain import ui_bloecke
from boerdi.domain.config_models.patterns import PatternFrontmatter
from boerdi.graph import state as state_mod
from boerdi.graph.nodes import assess as assess_mod
from boerdi.graph.nodes.assess import assess
from boerdi.services import config_loader
from boerdi.services.eval.metrics import _aggregate_classification_metrics
from boerdi.services.tool_loop_module import MODUL_BLOECKE_KEY
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UI_WERKZEUGE_KEY
from tests.test_respond_node import _ctx, _install, _Rec
from tests.test_respond_node import _run as _respond
from tests.test_tool_loop import _resp_text, _resp_tools, _run_loop
from tests.test_ui_antwort import _offen
from tests.test_ui_entscheidung_muster import (
    _ARGS,
    ENTSCHEIDUNG,
    _angebot,
    _aufruf,
    _frage_block,
)

_SUCHE = {"type": "function", "function": {"name": "search_wlo_content"}}


# ── Befund 1: ein Modul allein erzwingt keinen Werkzeugaufruf ──────────────


def test_nur_ein_modul_im_angebot_erzwingt_keinen_aufruf(monkeypatch):
    """Rückfrage-Muster ohne Schnellantworten: übrig bleibt nur das Modul. „required“ zwänge die
    KI in die Auswahl-Frage — sie soll frei zwischen Frage und Prosa wählen."""
    po = {"tools": [], UI_WERKZEUGE_KEY: [ENTSCHEIDUNG], "output_mode": "clarify",
          "format_follow_up": "none"}
    assert _angebot(po, ui_module=[ENTSCHEIDUNG]) == [ENTSCHEIDUNG]
    fake, result, _st = _run_loop(monkeypatch, [_resp_text("Welche Klasse?")],
                                  active_tools=[{"type": "function",
                                                 "function": {"name": ENTSCHEIDUNG}}])
    assert fake.calls[0]["tool_choice"] is None
    assert result[0] == "Welche Klasse?"


def test_mit_einem_echten_werkzeug_bleibt_der_zwang(monkeypatch):
    fake, _result, _st = _run_loop(monkeypatch, [_resp_text("ok")], active_tools=[
        {"type": "function", "function": {"name": ENTSCHEIDUNG}}, _SUCHE])
    assert fake.calls[0]["tool_choice"] == "required"


# ── Befund 2: der Klassifikator sieht die Frage ────────────────────────────


def _klassifikator_eingaben(monkeypatch) -> list[str]:
    gesehen: list[str] = []

    async def _safety(*_a, **_kw):
        return SafetyDecision(risk_level="low")

    async def _classify(message, *_a, **_kw):
        gesehen.append(message)
        return ClassificationResult()

    monkeypatch.setattr(assess_mod, "assess_safety", _safety)
    monkeypatch.setattr(assess_mod, "classify_input", _classify)
    return gesehen


async def _keine_erinnerung(_session_id: str) -> list[dict]:
    return []


def _assess_ctx(message: str, *, ui_antwort=None, geschlossen=None) -> state_mod.TurnContext:
    ctx = state_mod.TurnContext(req=ChatRequest(session_id="s1", message=message))
    ctx.session_state = {"persona_id": "P-AND", "state_id": "S1"}
    ctx.ui_antwort = ui_antwort
    ctx.geschlossene_frage = geschlossen
    return ctx


def test_der_klassifikator_sieht_frage_und_gewaehlte_antwort(monkeypatch):
    gesehen = _klassifikator_eingaben(monkeypatch)
    antwort = {"block_id": "b" * 16, "modul": ENTSCHEIDUNG, "frage": "Welche Klasse?",
               "daten": {"gewaehlt": ["a"]}, "labels": ["Klasse 5"]}
    asyncio.run(assess(_assess_ctx("Klasse 5", ui_antwort=antwort, geschlossen=_offen()),
                       _keine_erinnerung))
    [eingabe] = gesehen
    assert eingabe.startswith("[ANTWORT AUF DEINE FRAGE")
    assert "„Welche Klasse?“" in eingabe and "Klasse 5 (a)" in eingabe
    assert eingabe.endswith("\n\nKlasse 5")          # die Nachricht bleibt zuletzt


def test_der_klassifikator_sieht_die_uebergangene_frage(monkeypatch):
    gesehen = _klassifikator_eingaben(monkeypatch)
    asyncio.run(assess(_assess_ctx("die zweite", geschlossen=_offen()), _keine_erinnerung))
    [eingabe] = gesehen
    assert eingabe.startswith("[DEINE LETZTE FRAGE") and "2. Klasse 6" in eingabe
    assert eingabe.endswith("\n\ndie zweite")


def test_ohne_frage_klassifiziert_er_die_nachricht_allein(monkeypatch):
    gesehen = _klassifikator_eingaben(monkeypatch)
    asyncio.run(assess(_assess_ctx("Hallo"), _keine_erinnerung))
    assert gesehen == ["Hallo"]


# ── Befund 3: Werkzeug-Treue nur über MCP-Werkzeuge ────────────────────────


def test_die_werkzeug_treue_zaehlt_keine_module(monkeypatch):
    monkeypatch.setattr(config_loader, "load_pattern_definitions", lambda: [
        {"id": "M-UI", "tools": [ENTSCHEIDUNG]},
        {"id": "M-MIX", "tools": ["search_wlo_content", ENTSCHEIDUNG]},
    ])
    conv = {"persona_id": "", "intent_id": "", "turns": [
        {"user": "x", "debug": {"pattern": "M-UI (z)", "tools_called": []}, "judge": {}},
        {"user": "y", "debug": {"pattern": "M-MIX (z)",
                                "tools_called": ["search_wlo_content"]}, "judge": {}},
    ]}
    out = _aggregate_classification_metrics([conv])
    assert out["tool_compliance_total"] == 1
    assert out["tool_compliance_rate"] == 1.0
    assert out["tool_compliance_per_pattern"] == {"M-MIX": {"ok": 1, "total": 1}}


# ── Befund 4: Module ohne Wirkung in ``tools:`` ────────────────────────────


@pytest.mark.parametrize("name", ["ui_linkbox", "ui_trefferliste", "ui_inhaltsrahmen"])
def test_ein_modul_ohne_wirkung_in_tools_wird_abgewiesen(name):
    with pytest.raises(ValidationError, match=name):
        PatternFrontmatter.model_validate({"tools": ["search_wlo_content", name]})


def test_modul_werkzeuge_und_unbekannte_namen_bleiben_erlaubt():
    """Unbekannte Namen weist das Muster wie bisher nicht ab (fremde Server, spätere Werkzeuge)."""
    fm = PatternFrontmatter.model_validate(
        {"tools": [ENTSCHEIDUNG, "search_wlo_content", "noch_unbekannt"]})
    assert fm.tools == [ENTSCHEIDUNG, "search_wlo_content", "noch_unbekannt"]
    assert PatternFrontmatter.model_validate({"tools": None}).tools is None


# ── Befund 5: der Fehlerweg von ``respond`` ────────────────────────────────


def test_im_fehlerweg_fallen_die_bloecke_weg(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    from boerdi.graph.nodes import respond as respond_mod

    async def _gen(session, **kw):
        kw["session_state"][MODUL_BLOECKE_KEY] = [_frage_block()]
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr(respond_mod, "generate_response", _gen)
    out = _respond(_ctx(qr_mode="speculative"))
    assert out.ui_bloecke == []
    assert MODUL_BLOECKE_KEY not in out.session_state
    assert OFFENE_FRAGE not in out.session_state["entities"]
    assert out.qr_mode == "speculative"


# ── Befund 8: die Krisen-Sperrliste schlägt nur MCP-Werkzeuge vor ──────────


def test_die_krisen_sperrliste_zeigt_auf_den_mcp_katalog():
    from boerdi.domain.config_models.base_governance import SafetyConfigArea

    props = SafetyConfigArea.model_json_schema()["properties"]
    assert props["crisis_blocked_tools"]["items"]["x-catalog"] == "mcp_tools"


def test_der_mcp_katalog_nennt_keine_module(monkeypatch):
    from boerdi.api import config_choices
    from boerdi.services.mcp import fremdwerkzeuge

    monkeypatch.setattr(config_choices.cl, "get_enabled_mcp_servers",
                        lambda: [{"id": "wlo", "enabled": True, "tools": ["search_wlo_all"]}])
    monkeypatch.setattr(fremdwerkzeuge, "definitionen", lambda: [])
    assert [e["value"] for e in config_choices._mcp_tools()] == ["search_wlo_all"]
    assert [e["value"] for e in config_choices._tools()] == [
        "search_wlo_all", ENTSCHEIDUNG, "ui_strukturentwurf",            # U2: der Entwurf
        "ui_themenbaum"]                                                 # U1-e: auch der Themenbaum
    assert "mcp_tools" in config_choices.CATALOG_NAMES


# ── Befund 9: eine Frage-Runde ist die Antwort ─────────────────────────────


def test_eine_frage_runde_bucht_als_antwort(monkeypatch):
    from boerdi.obs import usage as usage_mod

    acc = usage_mod.new_accumulator()
    u = SimpleNamespace(prompt_tokens=10, completion_tokens=5, prompt_tokens_details=None)
    _run_loop(monkeypatch, [_resp_tools([_aufruf(ENTSCHEIDUNG, _ARGS)], usage=u)],
              usage_acc=acc)
    assert acc["per_phase"]["response"]["calls"] == 1
    assert "tool_loop" not in acc["per_phase"]


# ── Befund 11: eigener Schlüssel für die Blöcke des Zugs ───────────────────


def test_der_zug_schluessel_ist_nicht_der_debug_schluessel():
    assert MODUL_BLOECKE_KEY != ui_bloecke.DEBUG_KEY
