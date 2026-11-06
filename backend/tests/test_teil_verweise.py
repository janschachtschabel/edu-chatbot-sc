"""Paket V2: ``{"$teil": "<name>"}`` in Werkzeug-Argumenten — der Wert kommt aus dem Vorgang.

Die KI nennt nur den Namen; das Backend setzt den Teil ein, bevor das Werkzeug (und eine
Schreib-Vorschau) es sieht. Unbekannte Teile, falsche Formen und zu tiefe Verschachtelung werden
abgewiesen statt still durchgereicht.
"""

from __future__ import annotations

import asyncio

from boerdi.services import teil_verweise

_TEILE = {"draft": {"titel": "Optik", "knoten": [{"id": "k1", "titel": "Licht"}]},
          "structure": {"struktur": {"name": "P"}}}


async def _lader(name):
    return _TEILE.get(name)


def _ein(args, lader=_lader):
    return asyncio.run(teil_verweise.einsetzen(args, lader))


def test_ein_verweis_wird_durch_den_wert_ersetzt_auch_verschachtelt():
    args, fehlt = _ein({"struktur": {"$teil": "draft"}, "liste": [{"$teil": "structure"}], "n": 3})
    assert fehlt == []
    assert args == {"struktur": _TEILE["draft"], "liste": [_TEILE["structure"]], "n": 3}


def test_ohne_verweis_bleiben_die_argumente_dasselbe_objekt():
    args = {"query": "Optik", "filter": {"a": 1}}
    neu, fehlt = _ein(args)
    assert neu is args and fehlt == []


def test_ein_fehlender_teil_wird_gemeldet():
    _, fehlt = _ein({"x": {"$teil": "document"}})
    assert fehlt == ["document"]


def test_ohne_vorgang_ist_jeder_verweis_ein_fehlender_teil():
    _, fehlt = _ein({"x": {"$teil": "draft"}}, lader=None)
    assert fehlt == ["draft"]


def test_nur_die_reine_form_ist_ein_verweis():
    args = {"a": {"$teil": "draft", "mehr": 1}, "b": {"$teil": 5}, "c": "$teil"}
    neu, fehlt = _ein(args)
    assert neu == args and fehlt == []


def test_ungueltige_namen_und_zu_tiefe_verschachtelung_werden_abgewiesen():
    _, fehlt = _ein({"x": {"$teil": "../geheim"}})
    assert fehlt == ["../geheim"]
    tief: dict = {"$teil": "draft"}
    for _ in range(teil_verweise.TIEFE + 2):
        tief = {"x": tief}
    neu, fehlt = _ein(tief)
    assert fehlt == [] and "$teil" in str(neu)          # zu tief: nicht aufgelöst, nicht gesucht


def test_der_fehlertext_nennt_die_teile():
    assert "document" in teil_verweise.fehlertext(["document"])


# ── Review V2: wer einen Teil bekommt, oberste Ebene, Kopie ──

def test_nur_werkzeuge_mit_vorschau_und_module_die_lesen_bekommen_teile():
    assert teil_verweise.darf("wlo_create_collection", "draft")          # Vorschau + Abnahme
    assert teil_verweise.darf("ui_strukturentwurf", "draft")             # Manifest: liest draft
    assert not teil_verweise.darf("ui_strukturentwurf", "geheim")
    assert not teil_verweise.darf("search_wlo_all", "structure")         # lesend, ohne Vorschau
    assert not teil_verweise.darf("fremd__suche", "structure")           # fremder MCP-Server


def test_ein_nicht_freigegebenes_ziel_bekommt_den_teil_nicht():
    neu, fehlt = asyncio.run(teil_verweise.einsetzen(
        {"query": {"$teil": "structure"}}, _lader, "fremd__suche"))
    assert fehlt == ["structure"] and neu["query"] == {"$teil": "structure"}


def test_die_oberste_ebene_ist_kein_verweis():
    args = {"$teil": "draft"}
    neu, fehlt = _ein(args)
    assert neu is args and fehlt == []


def test_eingesetzt_wird_eine_kopie():
    neu, _ = _ein({"x": {"$teil": "draft"}})
    neu["x"]["titel"] = "verändert"
    assert _TEILE["draft"]["titel"] == "Optik"


# ── Einbau in die Schleifen ──

def test_die_agent_schleife_gibt_einem_lesenden_werkzeug_keinen_teil(monkeypatch):
    from tests.test_agent_loop import _lauf, _OutcomeFake, _resp_text, _resp_tools, _tool_call

    werkzeug = _OutcomeFake()
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call("search_wlo_all", {"query": "Optik",
                                                   "kontext": {"$teil": "draft"}})]),
        _resp_text("ohne")], outcome=werkzeug, modul_teile=_lader)
    assert werkzeug.calls == []
    antworten = [m["content"] for m in msgs if m.get("role") == "tool"]
    assert any("draft" in a and a.startswith("Fehler") for a in antworten)


def test_die_muster_vorrunde_prueft_teile_fuer_module_wie_die_agent_schleife():
    """Review V2, Befund 2: beide Maschinen gleich — ein Modul ohne ``liest`` bekommt nichts."""
    from boerdi.services.tool_loop_module import TEIL_LADER_KEY, nimm_module_an
    from tests.test_ui_strukturentwurf_agent import _aufrufe, _tool_call

    state = {TEIL_LADER_KEY: _lader}
    msgs: list[dict] = []
    asyncio.run(nimm_module_an(
        _aufrufe(_tool_call("ui_entscheidung", {"frage": "x", "optionen": {"$teil": "draft"}})),
        ["ui_entscheidung"], state, msgs, tools_called=[], outcomes=[]))
    assert msgs[0]["content"].startswith("Fehler") and "draft" in msgs[0]["content"]


def test_ein_zu_grosser_teil_geht_nicht_an_ein_werkzeug_der_ki():
    """Querschnitts-Review 2026-11-06: bis 1 MB (Auftragsergebnis) lägen sonst im Abnahme-Merkposten
    der Sitzung und kämen mit der Vorschau zurück ans Modell."""
    gross = {"text": "x" * (teil_verweise.MAX_BYTES + 1)}

    async def lader(name):
        return gross if name == "volltext" else None

    neu, fehlt = asyncio.run(teil_verweise.einsetzen(
        {"inhalt": {"$teil": "volltext"}}, lader, "wlo_create_collection"))
    assert fehlt == ["volltext"] and neu["inhalt"] == {"$teil": "volltext"}


def test_der_treiber_eines_geprueften_ablaufs_bekommt_auch_grosse_teile():
    gross = {"text": "x" * (teil_verweise.MAX_BYTES + 1)}

    async def lader(name):
        return gross

    neu, fehlt = asyncio.run(teil_verweise.einsetzen({"inhalt": {"$teil": "volltext"}}, lader))
    assert fehlt == [] and neu["inhalt"] == gross
