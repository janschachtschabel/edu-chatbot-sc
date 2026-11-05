"""Drittes Review U2, Befund 2: der letzte Entwurf in späteren Zügen (Agent-Weg und Rahmen).

Der Antwort-Knoten merkt die geprüfte Antwort, gibt den gemerkten Entwurf als ``vorlage`` an die
Schleife (auch Züge später) und rahmt ihn kurz vor der Nachricht; einen erzeugten Entwurf merkt
er nach dem Lauf. ``erneut_zeigen`` zeigt ihn unverändert wieder als offenen Block.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain.ui_bloecke import neuer_block
from boerdi.graph.nodes.respond_agent import respond_agent
from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.services.agent_loop import AgentRun
from boerdi.ui_module import antwort, aufruf
from boerdi.ui_module import strukturentwurf_merken as merken
from boerdi.ui_module.namen import STRUKTURENTWURF
from tests.test_respond_agent import _ctx, _patch

_DATEN = {"titel": "Optik", "quelle": "ki", "knoten": [
    {"id": "k1", "titel": "Licht"}, {"id": "k2", "titel": "Farben"}]}


@pytest.mark.anyio
async def test_ein_spaeterer_zug_bekommt_den_gemerkten_entwurf_als_vorlage_und_rahmen(monkeypatch):
    seen: dict = {}
    _patch(monkeypatch, seen)
    ctx = _ctx(message="Vertiefe bitte Licht")
    merken.aus_antwort(ctx.session_state["entities"], {
        "modul": STRUKTURENTWURF, "daten": {**_DATEN, "uebernommen": True, "bearbeitet": False}})
    await respond_agent(ctx)
    lauf = seen["run_agent_loop"]
    assert lauf["modul_vorlage"]["knoten"][0]["titel"] == "Licht"
    letzte = lauf["messages"][-1]["content"]
    assert "[DEIN LETZTER ENTWURF" in letzte and letzte.endswith("Vertiefe bitte Licht")


@pytest.mark.anyio
async def test_ein_erzeugter_entwurf_wird_nach_dem_lauf_gemerkt(monkeypatch):
    seen: dict = {}
    block = neuer_block(STRUKTURENTWURF, 1, "abfragen", _DATEN, "t")
    _patch(monkeypatch, seen, lauf=AgentRun(text="Hier.", stop_reason="frage", iterations=1,
                                             ui_bloecke=[block]))
    ctx = _ctx(message="Entwirf Optik")
    await respond_agent(ctx)
    assert merken.vorlage(ctx.session_state["entities"])["titel"] == "Optik"


def test_mit_antwort_auf_den_entwurf_steht_kein_zweiter_rahmen():
    geprueft = {"block_id": "b1", "modul": STRUKTURENTWURF, "frage": "Entwurf „Optik“",
                "daten": {**_DATEN, "uebernommen": True, "bearbeitet": False}, "labels": []}
    rahmen = "[DEIN LETZTER ENTWURF — x]\n- a\n[ENDE ENTWURF]"
    text = antwort.vorsatz(geprueft, None, letzter=rahmen)
    assert text.startswith("[ENTWURF DER PERSON") and "DEIN LETZTER ENTWURF" not in text


def test_ohne_mitgeschickten_entwurf_ersetzt_der_rahmen_das_unbekannt():
    offen = {"block_id": "b1", "modul": STRUKTURENTWURF, "frage": "Entwurf „Optik“", "anzahl": 2}
    rahmen = "[DEIN LETZTER ENTWURF — x]\n- Licht\n[ENDE ENTWURF]"
    assert antwort.vorsatz(None, offen, letzter=rahmen) == rahmen
    assert "Seinen Stand kennst du nicht" in antwort.vorsatz(None, offen)


async def test_erneut_zeigen_ergibt_den_entwurf_unveraendert_ohne_llm(monkeypatch):
    async def kein_llm(*_a, **_k):
        raise AssertionError("kein LLM-Aufruf")

    monkeypatch.setattr(dienst, "llm_json", lambda _z: kein_llm)
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True,
                                                   "erneut_zeigen": True},
                                 aufruf.Umgebung(vorlage=dict(_DATEN)))
    assert erg.block is not None and erg.block.status == "offen"
    assert [k["titel"] for k in erg.block.daten["knoten"]] == ["Licht", "Farben"]


async def test_erneut_zeigen_ohne_vorlage_ist_ein_fehler():
    erg = await aufruf.asynchron(STRUKTURENTWURF, {"thema": "Optik", "erneut_zeigen": True},
                                 aufruf.Umgebung())
    assert erg.block is None and erg.text.startswith("Fehler:")


def test_der_muster_weg_nimmt_den_gemerkten_entwurf(monkeypatch):
    from boerdi.services import tool_loop_module
    from tests.test_agent_loop import _tool_call
    from tests.test_ui_strukturentwurf_agent import _aufrufe

    gesehen: dict = {}

    async def attrappe(name, args, umgebung=None):
        gesehen["vorlage"] = umgebung.vorlage
        from boerdi.ui_module.datenquelle import Ergebnis
        return Ergebnis(None, "Fehler: x", None)

    monkeypatch.setattr(tool_loop_module, "asynchron", attrappe)
    state = {"entities": {}}
    merken.aus_antwort(state["entities"], {"modul": STRUKTURENTWURF, "daten": dict(_DATEN)})
    asyncio.run(tool_loop_module.nimm_module_an(
        _aufrufe(_tool_call(STRUKTURENTWURF, {"thema": "Optik", "vorlage": True})),
        [STRUKTURENTWURF], state, [], tools_called=[], outcomes=[]))
    assert gesehen["vorlage"]["titel"] == "Optik"
