"""Paket AS-5b (Plan 2026-11-09 §5g, A5-6): Ablauf-Werkzeuge im Muster-Modus.

Ein Muster nennt ``ablauf-<id>`` in ``tools:``. ``phase3_modulate`` trennt den Namen von den
MCP-Werkzeugen (wie die UI-Module, ``ablauf_werkzeuge``); die Auswahl bietet das Werkzeug an, wenn
der Ablauf vorschlagbar ist (aktiv, Auslöser ``agent``, Voraussetzungen erfüllt). In der Schleife
des Musters läuft ein Aufruf virtuell in der Vorrunde: die Angaben geprüft wie jeder Start, der
Vorschlag im ``session_state`` — den Knopf setzt die Zusammenstellung wie im Agent-Modus. Wie dort
(A5-8): steht ``respond_to_user`` in derselben Runde, gibt es keinen Vorschlag mit Angaben.
"""

from __future__ import annotations

import json

import pytest

from boerdi.api.config_choices import _tools as tools_katalog
from boerdi.domain import pattern_engine as pe
from boerdi.domain.tool_pflicht import fehlende_pflichtwerkzeuge
from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN
from boerdi.services import config_loader
from boerdi.services import response_tool_selection as rts
from boerdi.services.ablauf import ausloeser, vorschlag
from tests.test_tool_loop import _resp_text, _resp_tools, _run_loop

_UUID = "0a1b2c3d-0000-4000-8000-000000000001"
_FELDER = [{"name": "sammlung", "typ": "nodeid", "pflicht": True,
            "beschreibung": {"de": "Die Sammlung"}}]
_SCHRITTE = [{"id": "a", "typ": "nachricht", "text": {"de": "Los."}}, {"id": "e", "typ": "ende"}]


def _roh(id_, art="agent", **mehr):
    return {"id": id_, "titel": {"de": f"Titel {id_}"}, "aktiv": True, "schritte": _SCHRITTE,
            "ausloeser": [{"art": art}]} | mehr


@pytest.fixture
def katalog(monkeypatch):
    eintraege: list = []
    monkeypatch.setattr(ausloeser, "_roh_liste", lambda: eintraege)
    return eintraege


# ── Trennung in phase3_modulate ────────────────────────────────────────────────────────────────


def _modulieren(monkeypatch, **muster) -> dict:
    monkeypatch.setattr(pe, "_load_config_tables", lambda: ({}, [], {"desktop": 6}, {}))
    monkeypatch.setattr(config_loader, "get_tone_modifier_for_persona", lambda _pid: {
        "tone": "neutral", "length_bias": 0.0, "formality": "wie_user",
        "card_text_mode": "minimal", "override": False})
    return pe.phase3_modulate(pe.PatternDef(id="M03", label="X", **muster), signals=[],
                              device="desktop", entities={}, persona_id="P-AND")


def test_ablauf_werkzeuge_stehen_neben_den_mcp_werkzeugen(monkeypatch):
    out = _modulieren(monkeypatch, tools=["search_wlo_content", "ablauf-baum"],
                      force_tool_use=True, requires_all_tools=True)
    assert "ablauf-baum" not in out["tools"] and "search_wlo_content" in out["tools"]
    assert out[vorschlag.MUSTER_KEY] == ["ablauf-baum"]
    # kein Pflichtwerkzeug: sonst verlangte die A1-Reflexion einen Vorschlag
    assert fehlende_pflichtwerkzeuge(out, ["search_wlo_content", "lookup_wlo_vocabulary",
                                           "get_node_details"]) == []


# ── Angebot ────────────────────────────────────────────────────────────────────────────────────


@pytest.fixture()
def _ohne_schnellantwort(monkeypatch):
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "0")


def _angebot(pattern_output: dict, degradation=False) -> list[str]:
    tools, *_ = rts._select_active_tools({"entities": {}}, pattern_output, None, None, False,
                                         degradation)
    return [t["function"]["name"] for t in tools]


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_genannt_und_vorschlagbar_wird_angeboten(katalog):
    katalog += [_roh("baum", start=_FELDER), _roh("ast"), _roh("knopf", art="knopf")]
    namen = _angebot({"tools": [], vorschlag.MUSTER_KEY: ["ablauf-baum", "ablauf-knopf",
                                                          "ablauf-weg"]})
    assert [n for n in namen if vorschlag.ist_ablauf_werkzeug(n)] == ["ablauf-baum"]


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_nicht_genannt_wird_nicht_angeboten(katalog):
    katalog.append(_roh("baum"))
    assert not any(vorschlag.ist_ablauf_werkzeug(n) for n in _angebot({"tools": []}))


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_die_degradation_nimmt_auch_die_ablaeufe(katalog):
    katalog.append(_roh("baum"))
    assert _angebot({"tools": [], vorschlag.MUSTER_KEY: ["ablauf-baum"]}, degradation=True) == []


# ── Schleife des Musters ───────────────────────────────────────────────────────────────────────


def _aufruf(name, args, kennung="c1"):
    return (kennung, name, json.dumps(args))


def _quittung(st, kennung):
    return next(m["content"] for m in st["messages"] if m.get("tool_call_id") == kennung)


def _angeboten(katalog_ids):
    return [w for w in vorschlag.werkzeuge("de") if vorschlag.kennung(
        w["function"]["name"]) in katalog_ids]


def test_ein_aufruf_wird_ein_vorschlag_ohne_mcp(monkeypatch, katalog):
    katalog.append(_roh("baum", start=_FELDER))
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ablauf-baum", {"sammlung": _UUID})]),
        _resp_text("Mit dem Knopf startest du den Ablauf für diese Sammlung."),
    ], active_tools=_angeboten({"baum"}))
    text, _karten, gerufen, _outs = result
    assert st["session_state"][vorschlag.SITZUNG_KEY] == [
        {"ablauf": "baum", "start": {"sammlung": _UUID}}]
    assert gerufen == [] and "Knopf" in text
    quittung = next(m["content"] for m in st["messages"] if m.get("tool_call_id") == "c1")
    assert quittung == vorschlag.QUITTUNG


def test_falsche_angaben_ergeben_keinen_vorschlag(monkeypatch, katalog):
    katalog.append(_roh("baum", start=_FELDER))
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ablauf-baum", {"sammlung": "x"})]),
        _resp_text("ok"),
    ], active_tools=_angeboten({"baum"}))
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)
    assert "typ:sammlung" in _quittung(st, "c1")


def test_nicht_angeboten_wird_abgewiesen(monkeypatch, katalog):
    katalog += [_roh("baum"), _roh("ast")]
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ablauf-ast", {})]),
        _resp_text("ok"),
    ], active_tools=_angeboten({"baum"}))
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)
    assert _quittung(st, "c1") == NICHT_ANGEBOTEN


def test_neben_der_antwort_kein_vorschlag_mit_angaben(monkeypatch, katalog):
    """A5-8: steht die Antwort in derselben Runde, sah sie die Quittung nie."""
    from boerdi.domain.antwort_werkzeug import antwort_werkzeug

    katalog.append(_roh("baum", start=_FELDER))
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("respond_to_user", {"text": "Hier."}),
                     _aufruf("ablauf-baum", {"sammlung": _UUID}, "c2")]),
    ], active_tools=[*_angeboten({"baum"}), antwort_werkzeug(2, 500)])
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)
    assert _quittung(st, "c2") == vorschlag.NEBEN_DER_ANTWORT


# ── Katalog fürs Studio ────────────────────────────────────────────────────────────────────────


def test_der_katalog_nennt_die_ablauf_werkzeuge(katalog):
    katalog += [_roh("baum"), _roh("knopf", art="knopf"), _roh("aus", aktiv=False)]
    werte = {c["value"]: c["label"] for c in tools_katalog()}
    assert "ablauf-baum" in werte and "Titel baum" in werte["ablauf-baum"]
    assert "ablauf-knopf" not in werte
    assert werte["ablauf-aus"].endswith("(aus)")


# ── Review AS-5b und Querschnitts-Review AS-5 ──────────────────────────────────────────────────


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_ein_genannter_ablauf_auf_platz_sieben_wird_angeboten(katalog):
    """Review AS-5b, Befund 1 (schwer): erst filtern, dann kürzen."""
    katalog += [_roh(f"a{i}") for i in range(7)]
    namen = _angebot({"tools": [], vorschlag.MUSTER_KEY: ["ablauf-a6"]})
    assert "ablauf-a6" in namen


def _angebot_mit(pattern_output: dict, **kw) -> list[str]:
    tools, *_ = rts._select_active_tools({"entities": {}}, pattern_output, None, None, False,
                                         False, **kw)
    return [t["function"]["name"] for t in tools]


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_ohne_moeglichen_knopf_kein_ablauf_werkzeug(katalog, monkeypatch):
    """Review AS-5b, Befund 4: ein Muster ohne Schnellantworten (``quick_replies_mode: none``),
    Chips des Gastgebers oder ein laufender KI-Schritt (Querschnitt, Befund 2) — die Quittung
    verspräche einen Knopf, den es nicht gibt."""
    katalog.append(_roh("baum"))
    po = {"tools": [], vorschlag.MUSTER_KEY: ["ablauf-baum"], "id": "M01"}
    assert "ablauf-baum" in _angebot_mit(po)
    assert "ablauf-baum" not in _angebot_mit(po, ohne_ablaeufe=True)
    monkeypatch.setattr(rts, "_qr_policy", lambda pid: ("none", None))
    assert "ablauf-baum" not in _angebot_mit(po)


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_eine_lesende_einbettung_im_muster(katalog):
    """Querschnitt, Befund 6: dieselbe Regel wie im Agent-Modus."""
    schreibt = [{"id": "a", "typ": "auftrag", "flow": "wlo/x", "argumente": {}, "schreibt": "t",
                 "bei_fehler": "e"}, {"id": "e", "typ": "ende"}]
    katalog.append(_roh("baum", schritte=schreibt))
    po = {"tools": [], vorschlag.MUSTER_KEY: ["ablauf-baum"]}
    assert "ablauf-baum" not in _angebot_mit(po, tool_mode="read-only")


def test_ein_ablauf_werkzeug_wird_nie_erzwungen(monkeypatch, katalog):
    """Review AS-5b, Befund 2: wie die UI-Module — sonst zwänge die erste Runde einen Vorschlag."""
    katalog.append(_roh("baum"))
    fake, _result, _st = _run_loop(monkeypatch, [_resp_text("ok")],
                                   active_tools=_angeboten({"baum"}),
                                   pattern_output={"force_tool_use": True})
    assert fake.calls[0].get("tool_choice") != "required"


def test_derselbe_abgewiesene_vorschlag_nimmt_die_ablauf_werkzeuge_weg(monkeypatch, katalog):
    """Review AS-5b, Befund 5: der zweite gleiche Fehlversuch — danach bietet die Runde keine
    Ablauf-Werkzeuge mehr an (wie der Stillstand im Agent-Modus, ohne den Zug zu beenden)."""
    katalog.append(_roh("baum", start=_FELDER))
    falsch = {"sammlung": "x"}
    fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ablauf-baum", falsch)]),
        _resp_tools([_aufruf("ablauf-baum", falsch, "c2")]),
        _resp_text("ok"),
    ], active_tools=_angeboten({"baum"}))
    namen = [t["function"]["name"] for t in fake.calls[2].get("tools") or []]
    assert not any(vorschlag.ist_ablauf_werkzeug(n) for n in namen)
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)


def test_ohne_angaben_neben_der_antwort_moeglich(monkeypatch, katalog):
    from boerdi.domain.antwort_werkzeug import antwort_werkzeug

    katalog.append(_roh("baum"))
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("respond_to_user", {"text": "Mit dem Knopf startest du ihn."}),
                     _aufruf("ablauf-baum", {}, "c2")]),
    ], active_tools=[*_angeboten({"baum"}), antwort_werkzeug(2, 500)])
    assert st["session_state"][vorschlag.SITZUNG_KEY] == [{"ablauf": "baum"}]


def test_hoechstens_ein_vorschlag_je_zug_im_muster(monkeypatch, katalog):
    katalog += [_roh("baum"), _roh("ast")]
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ablauf-baum", {}), _aufruf("ablauf-ast", {}, "c2")]),
        _resp_text("ok"),
    ], active_tools=_angeboten({"baum", "ast"}))
    assert st["session_state"][vorschlag.SITZUNG_KEY] == [{"ablauf": "baum"}]
    assert _quittung(st, "c2") == vorschlag.SCHON_VORGESCHLAGEN


def test_neben_einer_frage_kein_vorschlag_im_muster(monkeypatch, katalog):
    """Querschnitt, Befund 10."""
    katalog.append(_roh("baum"))
    frage = {"frage": "Welche Klasse?", "optionen": [{"id": "a", "label": "5"},
                                                     {"id": "b", "label": "6"}]}
    _fake, _result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf("ui_entscheidung", frage), _aufruf("ablauf-baum", {}, "c2")]),
        _resp_text("darf nie kommen"),
    ], active_tools=[*_angeboten({"baum"}), {"type": "function",
                                             "function": {"name": "ui_entscheidung"}}])
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)


def test_unter_der_fehlerblase_kein_ablauf_knopf(monkeypatch):
    """Review AS-5b, Befund 3: scheitert der Zug nach einem gemerkten Vorschlag, fällt er weg."""
    from boerdi.graph.nodes import respond as respond_mod
    from tests.test_respond_node import _ctx, _install, _Rec
    from tests.test_respond_node import _run as _respond

    rec = _Rec()
    _install(monkeypatch, rec)

    async def _gen(session, **kw):
        kw["session_state"][vorschlag.SITZUNG_KEY] = [{"ablauf": "baum"}]
        raise RuntimeError("LLM weg")

    monkeypatch.setattr(respond_mod, "generate_response", _gen)
    out = _respond(_ctx(qr_mode="speculative"))
    assert vorschlag.SITZUNG_KEY not in out.session_state



def test_scheitert_die_zweite_runde_bleibt_kein_knopf(monkeypatch, katalog):
    """Zweites Review AS-5, Befund 2: die Schleife gibt den Fehlertext zurück, ohne zu werfen —
    auch dann fällt der gemerkte Vorschlag weg (sonst stünde der Knopf unter der Fehlerblase).
    Das Skript hat nur eine Antwort: der zweite LLM-Aufruf scheitert."""
    katalog.append(_roh("baum"))
    _fake, _result, st = _run_loop(monkeypatch, [_resp_tools([_aufruf("ablauf-baum", {})])],
                                   active_tools=_angeboten({"baum"}))
    assert not st["session_state"].get(vorschlag.SITZUNG_KEY)
