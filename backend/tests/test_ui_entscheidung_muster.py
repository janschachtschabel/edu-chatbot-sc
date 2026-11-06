"""Paket U1-d2 (d2-1): die Entscheidung im Muster-Modus (U-F4).

Ein Muster darf Modul-Werkzeuge (``agent: true``) in ``tools:`` nennen. Angeboten werden sie nur,
wenn das Muster sie nennt UND das Widget sie meldet (``environment.ui_module``) — dieselbe Regel
wie im Agent-Modus. ``phase3_modulate`` trennt sie von den MCP-Werkzeugen (``ui_werkzeuge``):
Pflicht-Prüfung (A1), Kuratier-Absicht und Medientyp-Strip lesen weiter nur MCP-Namen. In der
Muster-Schleife läuft ein Modul-Aufruf virtuell (Vorrunde wie das Dokument); ein abfragender Block
beendet die Runde wie ``respond_to_user``. ``respond`` legt die Blöcke an den Zug, merkt sich die
offene Frage und setzt im Folgezug die geprüfte Antwort bzw. die Frage gerahmt vor die Nachricht.
"""

from __future__ import annotations

import json

import pytest

from boerdi.api.config_choices import _tools as tools_katalog
from boerdi.domain import pattern_engine as pe
from boerdi.domain.tool_pflicht import fehlende_pflichtwerkzeuge
from boerdi.domain.werkzeug_angebot import NICHT_ANGEBOTEN
from boerdi.i18n.bot_text import bot_text
from boerdi.services import config_loader
from boerdi.services import response_tool_selection as rts
from boerdi.services.tool_loop_module import MODUL_BLOECKE_KEY
from boerdi.ui_module.antwort import OFFENE_FRAGE
from boerdi.ui_module.namen import UI_WERKZEUGE_KEY
from boerdi.ui_module.werkzeuge import modul_aufruf_annehmen
from tests.test_respond_node import _ctx, _install, _Rec
from tests.test_respond_node import _run as _respond
from tests.test_tool_loop import _resp_text, _resp_tools, _run_assemble, _run_loop
from tests.test_ui_antwort import _offen

ENTSCHEIDUNG = "ui_entscheidung"
_ARGS = {"frage": "Welche Klasse?",
         "optionen": [{"id": "a", "label": "Klasse 5"}, {"id": "b", "label": "Klasse 6"}]}


# ── Trennung in phase3_modulate ────────────────────────────────────────────


def _modulieren(monkeypatch, **muster) -> dict:
    monkeypatch.setattr(pe, "_load_config_tables", lambda: ({}, [], {"desktop": 6}, {}))
    monkeypatch.setattr(config_loader, "get_tone_modifier_for_persona", lambda _pid: {
        "tone": "neutral", "length_bias": 0.0, "formality": "wie_user",
        "card_text_mode": "minimal", "override": False})
    return pe.phase3_modulate(pe.PatternDef(id="M03", label="X", **muster), signals=[],
                              device="desktop", entities={}, persona_id="P-AND")


def test_module_in_tools_stehen_neben_den_mcp_werkzeugen(monkeypatch):
    out = _modulieren(monkeypatch, tools=["search_wlo_content", ENTSCHEIDUNG, "ui_inhaltsrahmen"])
    assert ENTSCHEIDUNG not in out["tools"] and "ui_inhaltsrahmen" not in out["tools"]
    assert "search_wlo_content" in out["tools"]
    assert out[UI_WERKZEUGE_KEY] == [ENTSCHEIDUNG, "ui_inhaltsrahmen"]


def test_ohne_module_bleibt_die_ausgabe_wie_bisher(monkeypatch):
    out = _modulieren(monkeypatch, tools=["search_wlo_content"])
    assert UI_WERKZEUGE_KEY not in out


def test_ein_modul_ist_kein_pflichtwerkzeug(monkeypatch):
    """Sonst verlangte die A1-Reflexion das Modul — ein „KORREKTUR“-Zug für eine Rückfrage."""
    nur_modul = _modulieren(monkeypatch, tools=[ENTSCHEIDUNG], force_tool_use=True)
    assert fehlende_pflichtwerkzeuge(nur_modul, []) == []
    alle = _modulieren(monkeypatch, tools=["search_wlo_content", ENTSCHEIDUNG],
                       force_tool_use=True, requires_all_tools=True)
    # Gerufen sind nur MCP-Werkzeuge (die Suche samt ihren Helfern) — das Modul nicht, und doch
    # fehlt nichts (Review U1-d2, Befund 12: die Liste kommt nicht mehr aus der Ausgabe selbst).
    gerufen = ["search_wlo_content", "lookup_wlo_vocabulary", "get_node_details"]
    assert fehlende_pflichtwerkzeuge(alle, gerufen) == []


def test_ein_modul_ist_keine_kuratier_absicht(monkeypatch):
    out = _modulieren(monkeypatch, tools=[ENTSCHEIDUNG])
    assert rts._pattern_curates(out) is False
    assert out["tools"] == []


# ── Angebot: genannt UND gemeldet ──────────────────────────────────────────


@pytest.fixture()
def _ohne_schnellantwort(monkeypatch):
    monkeypatch.setenv("CHAT_INLINE_QUICK_REPLIES", "0")


def _angebot(pattern_output: dict, *, ui_module=None, degradation=False, tool_mode=None):
    tools, *_ = rts._select_active_tools({"entities": {}}, pattern_output, None, None, False,
                                         degradation, tool_mode=tool_mode, ui_module=ui_module)
    return [t["function"]["name"] for t in tools]


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_genannt_und_gemeldet_wird_angeboten():
    namen = _angebot({"tools": ["search_wlo_content"], UI_WERKZEUGE_KEY: [ENTSCHEIDUNG]},
                     ui_module=[ENTSCHEIDUNG, "ui_linkbox"])
    assert namen.count(ENTSCHEIDUNG) == 1
    assert "search_wlo_content" in namen


@pytest.mark.usefixtures("_ohne_schnellantwort")
@pytest.mark.parametrize("ui_module", [None, [], ["ui_linkbox"]])
def test_ohne_meldung_des_widgets_kein_modul(ui_module):
    namen = _angebot({"tools": [], UI_WERKZEUGE_KEY: [ENTSCHEIDUNG]}, ui_module=ui_module)
    assert ENTSCHEIDUNG not in namen


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_nicht_genannt_wird_nicht_angeboten():
    assert ENTSCHEIDUNG not in _angebot({"tools": ["search_wlo_content"]},
                                        ui_module=[ENTSCHEIDUNG])


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_der_inhaltsrahmen_bleibt_auf_seinem_weg():
    namen = _angebot({"tools": [], UI_WERKZEUGE_KEY: ["ui_inhaltsrahmen", "ui_linkbox"]},
                     ui_module=["ui_inhaltsrahmen", "ui_linkbox"])
    assert namen.count("ui_inhaltsrahmen") == 1
    assert "ui_linkbox" not in namen


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_auch_im_rueckfrage_muster_und_im_lesemodus():
    """M03 (``output_mode: clarify``) ist der natürliche Ort für eine Auswahl-Rückfrage."""
    po = {"tools": [], UI_WERKZEUGE_KEY: [ENTSCHEIDUNG], "output_mode": "clarify"}
    assert ENTSCHEIDUNG in _angebot(po, ui_module=[ENTSCHEIDUNG], tool_mode="read-only")


@pytest.mark.usefixtures("_ohne_schnellantwort")
def test_die_degradation_nimmt_auch_die_module():
    """Fehlt ein Pflicht-Slot, verlangt der Prompt eine reine Text-Rückfrage."""
    po = {"tools": [], UI_WERKZEUGE_KEY: [ENTSCHEIDUNG]}
    assert _angebot(po, ui_module=[ENTSCHEIDUNG], degradation=True) == []


# ── Muster-Schleife ────────────────────────────────────────────────────────


def _aufruf(name, args, kennung="c1"):
    return (kennung, name, json.dumps(args))


def _mit_prosa(text, calls):
    resp = _resp_tools(calls)
    resp.choices[0].message.content = text
    return resp


def _bloecke(st) -> list:
    return st["session_state"].get(MODUL_BLOECKE_KEY, [])


def test_eine_frage_beendet_die_runde_mit_block_und_prosa(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _mit_prosa("Kurz nachgefragt:", [_aufruf(ENTSCHEIDUNG, _ARGS)]),
        _resp_text("darf nie kommen"),
    ])
    text, _karten, gerufen, _outs = result
    assert text == "Kurz nachgefragt:"
    assert len(fake.calls) == 1
    [block] = _bloecke(st)
    assert (block.modul, block.status, block.daten) == (ENTSCHEIDUNG, "offen", _ARGS)
    assert gerufen == []                       # virtuell: kein MCP, kein Werkzeugeintrag
    quittung = next(m["content"] for m in st["messages"] if m.get("tool_call_id") == "c1")
    assert "nächsten Zug" in quittung


def test_falsche_argumente_gehen_als_ergebnis_zurueck(monkeypatch):
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf(ENTSCHEIDUNG, {"frage": "?", "optionen": []})]),
        _resp_text("Dann in Prosa."),
    ])
    assert result[0] == "Dann in Prosa." and len(fake.calls) == 2
    assert _bloecke(st) == []
    fehler = next(m["content"] for m in st["messages"] if m.get("tool_call_id") == "c1")
    assert "optionen" in fehler


def test_nicht_angeboten_laeuft_kein_modul(monkeypatch):
    _fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf(ENTSCHEIDUNG, _ARGS)]),
        _resp_text("Antwort ohne Frage."),
    ], active_tools=[{"type": "function", "function": {"name": "search_wlo_content"}}])
    assert result[0] == "Antwort ohne Frage."
    assert _bloecke(st) == []
    assert [m["content"] for m in st["messages"] if m.get("role") == "tool"] == [NICHT_ANGEBOTEN]


def test_respond_to_user_derselben_runde_liefert_den_text_ohne_schnellantworten(monkeypatch):
    """Die Antwort steht VOR der Frage — die Vorrunde nimmt das Modul trotzdem an."""
    antwort = {"text": "Eine Rückfrage.", "quick_replies": ["X", "Y"]}
    _fake, result, st = _run_loop(monkeypatch, [_resp_tools([
        _aufruf("respond_to_user", antwort, "c1"), _aufruf(ENTSCHEIDUNG, _ARGS, "c2"),
    ])], _inline_qr_enabled=True)
    assert result[0] == "Eine Rückfrage."
    assert len(_bloecke(st)) == 1
    # Unter einer offenen Frage keine Schnellantworten — ein Klick machte sie veraltet.
    assert "_inline_quick_replies" not in st["session_state"]


def test_eine_zweite_frage_derselben_runde_wird_abgewiesen(monkeypatch):
    _fake, _result, st = _run_loop(monkeypatch, [_resp_tools([
        _aufruf(ENTSCHEIDUNG, _ARGS, "c1"),
        _aufruf(ENTSCHEIDUNG, {**_ARGS, "frage": "Und welches Fach?"}, "c2"),
    ])])
    assert [b.daten["frage"] for b in _bloecke(st)] == ["Welche Klasse?"]
    zweite = next(m["content"] for m in st["messages"] if m.get("tool_call_id") == "c2")
    assert "eine Frage" in zweite


def test_nach_der_frage_laeuft_kein_echtes_werkzeug_derselben_runde(monkeypatch):
    from tests.test_tool_loop import _OutcomeFake

    out = _OutcomeFake()
    _fake, result, st = _run_loop(monkeypatch, [_resp_tools([
        _aufruf(ENTSCHEIDUNG, _ARGS, "c1"), _aufruf("search_wlo_content", {"query": "x"}, "c2"),
    ])], outcome=out)
    assert out.calls == [] and result[2] == []
    beantwortet = {m["tool_call_id"] for m in st["messages"] if m.get("role") == "tool"}
    assert beantwortet == {"c1", "c2"}


def test_die_frage_umgeht_die_pflicht_reflexion(monkeypatch):
    """Ein Muster mit Pflicht-Suche fragt erst nach — die Frage ist kein „Shortcut“."""
    fake, result, st = _run_loop(monkeypatch, [
        _resp_tools([_aufruf(ENTSCHEIDUNG, _ARGS)]),
        _resp_text("darf nie kommen"),
    ], pattern_output={"force_tool_use": True, "tools": ["search_wlo_content"]})
    assert len(fake.calls) == 1
    assert not any("KORREKTUR" in str(m.get("content")) for m in st["messages"])
    assert result[0] == ""


# ── Kette: der gerahmte Block im Folgezug ──────────────────────────────────


def test_der_vorsatz_steht_vor_der_nachricht_die_suche_bleibt_die_nachricht(monkeypatch):
    from tests.test_tool_loop import _RagCtx

    rag = _RagCtx(text="Wissen")
    messages, *_ = _run_assemble(
        monkeypatch, rag_ctx=rag, vorsatz="[BLOCK]",
        available_rag_areas=["a"], rag_config={"a": {"mode": "always"}})
    nutzer = [m["content"] for m in messages if m.get("role") == "user"]
    assert nutzer == ["[BLOCK]\n\nfinde material"]
    assert rag.calls[0]["query"] == "finde material"


def test_ohne_vorsatz_bleibt_die_nachricht(monkeypatch):
    messages, *_ = _run_assemble(monkeypatch)
    assert messages[-1] == {"role": "user", "content": "finde material"}


# ── Antwort-Knoten im Muster-Weg ───────────────────────────────────────────


def _frage_block():
    block, _ = modul_aufruf_annehmen(ENTSCHEIDUNG, _ARGS)
    assert block is not None
    return block


def _mit_bloecken(monkeypatch, rec, text, bloecke):
    """``generate_response`` legt Blöcke wie die Schleife im ``session_state`` ab."""
    _install(monkeypatch, rec)
    from boerdi.graph.nodes import respond as respond_mod

    async def _gen(session, **kw):
        rec.gen_kwargs = kw
        kw["session_state"][MODUL_BLOECKE_KEY] = list(bloecke)
        return text, [], [], []

    monkeypatch.setattr(respond_mod, "generate_response", _gen)


def test_eine_frage_wird_block_und_offene_frage_der_sitzung(monkeypatch):
    rec, block = _Rec(), _frage_block()
    _mit_bloecken(monkeypatch, rec, "Kurz nachgefragt:", [block])
    out = _respond(_ctx(qr_mode="speculative"))
    assert out.ui_bloecke == [block]
    assert MODUL_BLOECKE_KEY not in out.session_state
    assert out.session_state["entities"][OFFENE_FRAGE]["block_id"] == block.block_id
    assert out.qr_mode == "none"
    assert out.response_text == "Kurz nachgefragt:"


def test_eine_frage_ohne_prosa_bekommt_den_festen_satz(monkeypatch):
    rec = _Rec()
    _mit_bloecken(monkeypatch, rec, "", [_frage_block()])
    out = _respond(_ctx())
    assert out.response_text == bot_text("de", "agent.frage")


def test_ohne_frage_bleibt_keine_offene_frage_stehen(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    out = _respond(_ctx(qr_mode="speculative"))
    assert out.ui_bloecke == [] and OFFENE_FRAGE not in out.session_state["entities"]
    assert out.qr_mode == "speculative"


def test_das_widget_meldet_seine_module_auch_dem_muster_weg(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx()
    ctx.env = {**ctx.env, "ui_module": [ENTSCHEIDUNG]}
    _respond(ctx)
    assert rec.gen_kwargs["environment"]["ui_module"] == [ENTSCHEIDUNG]


def test_die_gepruefte_antwort_steht_gerahmt_vor_der_nachricht(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx(message="Klasse 5")
    ctx.geschlossene_frage = _offen()
    ctx.ui_antwort = {"block_id": "b" * 16, "modul": ENTSCHEIDUNG, "frage": "Welche Klasse?",
                      "daten": {"gewaehlt": ["a"]}, "labels": ["Klasse 5"]}
    _respond(ctx)
    vorsatz = rec.gen_kwargs["vorsatz"]
    assert vorsatz.startswith("[ANTWORT AUF DEINE FRAGE") and "Klasse 5 (a)" in vorsatz
    assert rec.gen_kwargs["message"] == "Klasse 5"


def test_ein_getippter_folgezug_kennt_frage_und_moeglichkeiten(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx(message="die zweite")
    ctx.geschlossene_frage = _offen()
    _respond(ctx)
    vorsatz = rec.gen_kwargs["vorsatz"]
    assert vorsatz.startswith("[DEINE LETZTE FRAGE") and "2. Klasse 6" in vorsatz


def test_ohne_frage_kein_vorsatz(monkeypatch):
    rec = _Rec()
    _install(monkeypatch, rec)
    _respond(_ctx())
    assert rec.gen_kwargs["vorsatz"] == ""


# ── Katalog im Studio ──────────────────────────────────────────────────────


def test_der_werkzeug_katalog_nennt_die_modul_werkzeuge(monkeypatch):
    from boerdi.api import config_choices
    from boerdi.services.mcp import fremdwerkzeuge

    monkeypatch.setattr(config_choices.cl, "get_enabled_mcp_servers", lambda: [])
    monkeypatch.setattr(fremdwerkzeuge, "definitionen", lambda: [])
    eintraege = {e["value"]: e for e in tools_katalog()}
    # U1-e: auch der Themenbaum; U2: der Strukturentwurf.
    assert set(eintraege) == {ENTSCHEIDUNG, "ui_themenbaum", "ui_strukturentwurf", "ui_upload"}
    assert "Entscheidung" in eintraege[ENTSCHEIDUNG]["label"]
