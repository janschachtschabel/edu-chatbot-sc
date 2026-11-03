"""Review U1 gesamt (2026-11-03): Befunde zu allen Backend-Änderungen der UI-Module.

Je Befund ein Block; die Nummern sind die der Änderungsnotiz
``docs/aenderungen/2026-11-03-review-u1-gesamt.md``.
"""

from __future__ import annotations

import json

import pytest

from boerdi.services.mcp import arg_resolvers
from boerdi.ui_module import datenquelle
from tests.test_ui_themenbaum import THEMENBAUM, WERKZEUG, _payload

# ── Befund 2: der Themenbaum zeigt das genannte Unterthema, nicht das Fachportal ──

_PORTALE = {"results": [
    {"nodeId": "aaaaaaaa-1111-4111-8111-111111111111", "title": "Mathematik"},
    {"nodeId": "bbbbbbbb-2222-4222-8222-222222222222", "title": "Physik"},
]}
_UNTERTHEMA = "cccccccc-3333-4333-8333-333333333333"


@pytest.fixture
def server(monkeypatch):
    """Der Transport unter dem MCP-Client: Portalliste und Baum; hält fest, was hinausging."""
    from boerdi.services.mcp import client

    gesendet: list[tuple[str, dict]] = []

    async def call_tool(name, args, url=None):
        gesendet.append((name, dict(args)))
        antwort = _PORTALE if name == "get_subject_portals" else _payload()
        return {"result": {"content": [{"type": "text", "text": json.dumps(antwort)}]}}

    monkeypatch.setattr(client.transport, "call_tool", call_tool)
    monkeypatch.setattr(client, "_cache_get", lambda _schluessel: None)
    yield gesendet
    arg_resolvers.set_request_hints({})


def _baum_aufrufe(gesendet: list[tuple[str, dict]]) -> list[dict]:
    return [args for name, args in gesendet if name == WERKZEUG]


@pytest.mark.anyio
async def test_ein_unterthema_bleibt_trotz_fach_hinweis_stehen(server):
    arg_resolvers.set_request_hints({"fach": "Physik"})
    block, _text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"nodeId": _UNTERTHEMA})
    assert block is not None
    (args,) = _baum_aufrufe(server)
    assert args["nodeId"] == _UNTERTHEMA


@pytest.mark.anyio
async def test_ein_genanntes_fach_bekommt_keine_kennung_aus_dem_hinweis(server):
    arg_resolvers.set_request_hints({"fach": "Mathematik"})
    block, _text, _outcome = await datenquelle.aufruf(THEMENBAUM, {"subject": "Physik"})
    assert block is not None
    (args,) = _baum_aufrufe(server)
    assert args["subject"] == "Physik" and not args.get("nodeId")


# ── Befund 3: die offene Frage fällt nie der Obergrenze von fünf Blöcken zum Opfer ──

_FRAGE_ARGS = {"frage": "Welche Klasse?",
               "optionen": [{"id": "a", "label": "Klasse 5"}, {"id": "b", "label": "Klasse 6"}]}


def _anzeige(i: int):
    from boerdi.domain import ui_bloecke

    return ui_bloecke.neuer_block("ui_test", 1, "anzeigen", {"i": i}, f"t{i}")


def _frage():
    from boerdi.domain import ui_bloecke

    return ui_bloecke.neuer_block("ui_entscheidung", 1, "abfragen", dict(_FRAGE_ARGS), "?")


def test_die_regeln_behalten_die_frage_und_lassen_anzeigen_weg():
    from boerdi.domain import ui_bloecke

    frage = _frage()
    bloecke = [*(_anzeige(i) for i in range(6)), frage]
    behalten = ui_bloecke.regeln_anwenden(bloecke)
    assert [b.block_id for b in behalten] == [*(b.block_id for b in bloecke[:4]), frage.block_id]
    assert ui_bloecke.regeln_anwenden(behalten) == behalten          # idempotent


def test_die_regeln_ohne_frage_bleiben_bei_fuenf():
    from boerdi.domain import ui_bloecke

    assert len(ui_bloecke.regeln_anwenden([_anzeige(i) for i in range(7)])) == 5


def test_drei_dokumente_vorschau_zwei_baeume_und_frage_die_frage_bleibt(monkeypatch):
    """Der Befund: 3 Dokumente + Schreib-Vorschau + 2 Bäume + Frage — die Frage ist gemerkt
    (``_offene_frage``) und muss darum auch gezeigt werden."""
    from tests.test_turn_persist import _GELIEFERT, _run2

    baum = [_anzeige(1), _anzeige(2)]
    frage = _frage()
    resp, _sp = _run2(
        monkeypatch, ui_bloecke=[*baum, frage],
        gelieferte_dokumente=[dict(_GELIEFERT), {**_GELIEFERT, "title": "Zwei"},
                              {**_GELIEFERT, "title": "Drei"}],
        session_state={"turn_count": 4, "entities": {}, "_write_preview": "Titel: X"})
    module = [b.modul for b in resp.ui.ui_bloecke]
    assert module == ["ui_inhaltsrahmen"] * 4 + ["ui_entscheidung"]
    assert resp.ui.ui_bloecke[-1].block_id == frage.block_id


def _dok(i: int, call_id: str):
    from tests.test_agent_loop import _tool_call

    return _tool_call("ui_inhaltsrahmen", {"titel": f"Dok {i}", "art": "stundenplanung",
                                           "markdown": f"# Dok {i}\n\nInhalt."}, call_id)


def test_agent_nimmt_nur_so_viele_anzeigen_an_wie_platz_ist(monkeypatch):
    """3 Dokumente + 1 Baum füllen die vier Anzeige-Plätze; der zweite Baum wird nicht geholt,
    die Frage bekommt ihren Platz."""
    from boerdi.domain import ui_bloecke
    from tests.test_agent_loop import _lauf, _resp_tools, _tool_call
    from tests.test_ui_themenbaum import _Rufer

    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    _fake, run, msgs = _lauf(monkeypatch, [_resp_tools([
        _dok(1, "d1"), _dok(2, "d2"), _dok(3, "d3"),
        _tool_call(THEMENBAUM, {"subject": "Mathe"}, "b1"),
        _tool_call(THEMENBAUM, {"subject": "Physik"}, "b2"),
        _tool_call("ui_entscheidung", _FRAGE_ARGS, "f1"),
    ])])
    assert len(rufer.calls) == 1
    assert [b.modul for b in run.ui_bloecke] == [THEMENBAUM, "ui_entscheidung"]
    antwort = {m["tool_call_id"]: m["content"] for m in msgs if m.get("role") == "tool"}
    assert antwort["b2"] == ui_bloecke.GENUG_BLOECKE


def test_muster_nimmt_nur_so_viele_anzeigen_an_wie_platz_ist(monkeypatch):
    from boerdi.domain import ui_bloecke
    from boerdi.services.tool_loop_module import MODUL_BLOECKE_KEY
    from tests.test_agent_loop import _resp_tools, _tool_call
    from tests.test_tool_loop import _run_loop
    from tests.test_ui_themenbaum import _Rufer

    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    _fake, _result, st = _run_loop(monkeypatch, [_resp_tools([
        _dok(1, "d1"), _dok(2, "d2"), _dok(3, "d3"),
        _tool_call(THEMENBAUM, {"subject": "Mathe"}, "b1"),
        _tool_call(THEMENBAUM, {"subject": "Physik"}, "b2"),
        _tool_call("ui_entscheidung", _FRAGE_ARGS, "f1"),
    ])])
    assert len(rufer.calls) == 1
    bloecke = st["session_state"][MODUL_BLOECKE_KEY]
    assert [b.modul for b in bloecke] == [THEMENBAUM, "ui_entscheidung"]
    antwort = {m["tool_call_id"]: m["content"] for m in st["messages"] if m.get("role") == "tool"}
    assert antwort["b2"] == ui_bloecke.GENUG_BLOECKE


# ── Befund 4: Werte, die nur das System setzt, nimmt ein Modul-Aufruf nicht an ──


def _probe_mit_systemwert(monkeypatch, tmp_path, *, nur_system: list[str]):
    from boerdi.ui_module import katalog, werkzeuge
    from tests.test_ui_modul_katalog import _manifest, _schreibe

    m = _manifest(agent=True, eingabe={
        "type": "object", "required": ["text", "stufe"],
        "properties": {"text": {"type": "string"},
                       "stufe": {"type": "string", "enum": ["normal", "intern"],
                                 "x-nur-system": nur_system}}},
                  beispiele=[{"titel": "Kurz", "daten": {"text": "Hallo", "stufe": "normal"}}])
    kat = katalog.lade(_schreibe(tmp_path, m))
    monkeypatch.setattr(werkzeuge, "_agent_module", lambda: kat)
    return werkzeuge


def test_ein_systemwert_vom_modell_wird_abgewiesen(monkeypatch, tmp_path):
    werkzeuge = _probe_mit_systemwert(monkeypatch, tmp_path, nur_system=["intern"])
    block, fehler = werkzeuge.modul_aufruf_annehmen("ui_probe", {"text": "a", "stufe": "intern"})
    assert block is None and "stufe" in (fehler or "")
    block, fehler = werkzeuge.modul_aufruf_annehmen("ui_probe", {"text": "a", "stufe": "normal"})
    assert block is not None and fehler is None


def test_nur_systemwerte_heisst_das_modell_kann_keinen_setzen(monkeypatch, tmp_path):
    """Sieht die KI keine Aufzählung (alle Werte gehören dem System), darf die Prüfung trotzdem
    keinen beliebigen Wert durchlassen."""
    werkzeuge = _probe_mit_systemwert(monkeypatch, tmp_path, nur_system=["normal", "intern"])
    block, _fehler = werkzeuge.modul_aufruf_annehmen("ui_probe", {"text": "a", "stufe": "intern"})
    assert block is None


# ── Befund 5 und 11: die Direktaktion nimmt nur Knoten-Kennungen und führt das Modul ──

_KNOTEN = "bbbb2222-0000-4000-8000-000000000001"


def _aktion(monkeypatch, kennung):
    import asyncio

    from boerdi.services import themenbaum_aktion
    from tests.test_preflight_node import _SESSION
    from tests.test_ui_themenbaum import _Rufer
    from tests.test_ui_themenbaum_aktion import _req, _SaveSpy

    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    monkeypatch.setattr(themenbaum_aktion, "save_message", _SaveSpy())
    resp = asyncio.run(themenbaum_aktion.handle_show_collection_tree(
        _SESSION, _req(collection_id=kennung, title="Algebra"), {}, blocked_tools=[]))
    return resp, rufer


@pytest.mark.parametrize("kennung", ["-userhome-", "-inbox-", "Mathematik", "bbbb-2222"])
def test_die_direktaktion_nimmt_keine_sonderkennungen(monkeypatch, kennung):
    resp, rufer = _aktion(monkeypatch, kennung)
    assert rufer.calls == [] and resp.ui.ui_bloecke == []


def test_die_direktaktion_fuehrt_das_modul_wie_die_schleifen(monkeypatch):
    resp, rufer = _aktion(monkeypatch, _KNOTEN)
    assert [args["nodeId"] for _w, args in rufer.calls] == [_KNOTEN]
    assert resp.debug.tools_called == [THEMENBAUM]


# ── Befund 6: jede Antwort geht nach den Regeln hinaus, auch ohne abgeleitete Blöcke ──


def test_die_antwort_gilt_nach_den_regeln_auch_ohne_links_und_karten():
    from boerdi.api import publikum
    from boerdi.api.schemas import ChatResponse, DebugInfo
    from boerdi.api.schemas_ui import UiInfo

    zwei_fragen = [_frage(), _frage(), *(_anzeige(i) for i in range(6))]
    resp = ChatResponse(session_id="bb-1", content="x", debug=DebugInfo(pattern="ACTION: x"),
                        ui=UiInfo(ui_bloecke=zwei_fragen))
    aus = publikum.antwort_fuer(resp, intern=False)
    assert [b.block_id for b in aus.ui.ui_bloecke] == [
        zwei_fragen[0].block_id, *(b.block_id for b in zwei_fragen[2:6])]


# ── Befund 7: die Textfassungen bauen sichere Markdown-Links ──


def test_md_link_maskiert_klammern_und_prueft_die_adresse():
    from boerdi.ui_module.abgeleitet import md_link

    assert md_link("a]b[c", "https://x.de/p") == r"[a\]b\[c](https://x.de/p)"
    assert md_link("Seite", "https://x.de/a b(1)") == "[Seite](https://x.de/a%20b%281%29)"
    assert md_link("Böse", "javascript:alert(1)") == "Böse"
    assert md_link("", "ftp://x") == ""


def test_die_trefferliste_verlinkt_nur_http_adressen():
    from boerdi.ui_module.abgeleitet import trefferliste_block

    block = trefferliste_block([{"node_id": "n1", "title": "Klick [hier]",
                                 "url": "javascript:alert(1)"}], [], None, "")
    assert block is not None
    assert "javascript" not in block.text and r"Klick \[hier\]" in block.text
    such = trefferliste_block([], [{"search_term": "Optik ]", "search_url": "data:x"}], None, "")
    assert such is not None and "data:" not in such.text


def test_die_linkbox_maskiert_den_titel():
    from boerdi.ui_module.abgeleitet import linkbox_block

    block = linkbox_block([{"title": "a](javascript:x)", "url": "https://x.de/"}])
    assert block is not None and block.text == r"- [a\](javascript:x)](https://x.de/)"


def test_der_themenbaum_maskiert_den_titel_statt_ihn_umzuschreiben():
    from boerdi.ui_module import themenbaum

    zeile = themenbaum._zeile({"titel": "Mengen [A]", "url": "https://x.de/s"}, "")
    assert zeile == r"- [Mengen \[A\]](https://x.de/s)"


# ── Befund 12: unter einer offenen Frage sind keine Schnellantworten zu erwarten ──


def test_der_qr_check_entfaellt_unter_einer_offenen_frage():
    from tests.test_golden_ui_module import _FRAGE, _antwort, rg

    frage = _antwort(_FRAGE)
    frage["quick_replies"] = []
    assert rg.check_golden_turn({}, frage, {})["checks"]["qr"] is None
    # ``qr: false`` bleibt eine Aussage — auch unter einer Frage.
    assert rg.check_golden_turn({"qr": False}, frage, {})["checks"]["qr"] is True
    # Ohne Frage gilt wie bisher „mindestens eine“.
    ohne = _antwort()
    ohne["quick_replies"] = []
    assert rg.check_golden_turn({}, ohne, {})["checks"]["qr"] is False
    beantwortet = _antwort({**_FRAGE, "status": "beantwortet"})
    beantwortet["quick_replies"] = []
    assert rg.check_golden_turn({}, beantwortet, {})["checks"]["qr"] is False
