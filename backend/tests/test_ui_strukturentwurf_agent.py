"""Paket U2-c (Plan 2026-11-04, T-6/T-7/T-10): ``ui_strukturentwurf`` in der Agent-Schleife.

Der Entwurf ist abfragend und asynchron (Dienst): die Runde endet wie bei ``ui_entscheidung``
(``frage``), eine zweite Frage derselben Runde wird abgewiesen, BEVOR der Dienst Geld kostet. Der
Dienst bucht in den Zähler des Laufs und endet vor dessen Frist; der mitgeschickte Entwurf der
Person geht als ``vorlage`` mit. Keine echten LLM-Aufrufe.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from boerdi.services import strukturentwurf_dienst as dienst
from boerdi.ui_module.antwort import ZWEITE_FRAGE
from boerdi.ui_module.datenquelle import ANTWORT_VERWORFEN
from boerdi.ui_module.namen import ENTSCHEIDUNG, STRUKTURENTWURF
from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call

_DATEN = {"titel": "Optik", "quelle": "ki", "thema": "Optik",
          "knoten": [{"id": "k1", "titel": "Licht"}, {"id": "k2", "titel": "Farben"}]}
_FRAGE = {"frage": "Welches Fach?", "optionen": [{"id": "a", "label": "Physik"},
                                                  {"id": "b", "label": "Chemie"}]}


@pytest.fixture
def gesehen(monkeypatch):
    aufrufe: list[dict[str, Any]] = []
    ergebnis = {"wert": dienst.Erzeugt(dict(_DATEN))}

    async def attrappe(auftrag, *, llm, frist_ende, vorlage=None):
        aufrufe.append({"auftrag": auftrag, "frist_ende": frist_ende, "vorlage": vorlage,
                        "llm": llm})
        return ergebnis["wert"]

    def naht(usage_acc):
        async def rufe(*_a):  # pragma: no cover — die Attrappe oben ruft sie nie
            raise AssertionError
        rufe.zaehler = usage_acc  # type: ignore[attr-defined]
        return rufe

    monkeypatch.setattr(dienst, "erzeugen", attrappe)
    monkeypatch.setattr(dienst, "llm_json", naht)
    return aufrufe, ergebnis


def test_der_entwurf_beendet_die_runde_wie_eine_frage(monkeypatch, gesehen):
    zaehler: dict[str, Any] = {}
    _fake, run, msgs = _lauf(monkeypatch, [_resp_tools([
        _tool_call(STRUKTURENTWURF, {"thema": "Optik"}),
        _tool_call("respond_to_user", {"text": "Hier ist ein Entwurf zur Optik."}),
    ])], usage_acc=zaehler)
    assert run.stop_reason == "frage" and run.text == "Hier ist ein Entwurf zur Optik."
    [block] = run.ui_bloecke
    assert block.modul == STRUKTURENTWURF and block.art == "abfragen" and block.status == "offen"
    assert run.tools_called == [STRUKTURENTWURF]
    [aufruf] = gesehen[0]
    assert aufruf["llm"].zaehler is zaehler            # gebucht im Zähler des Laufs
    quittung = [m["content"] for m in msgs if m.get("role") == "tool"][0]
    assert quittung.startswith("OK: Der Entwurf „Optik“") and "Licht; Farben" in quittung


def test_eine_zweite_frage_wird_abgewiesen_bevor_der_dienst_laeuft(monkeypatch, gesehen):
    _fake, run, msgs = _lauf(monkeypatch, [_resp_tools([
        _tool_call(ENTSCHEIDUNG, _FRAGE),
        _tool_call(STRUKTURENTWURF, {"thema": "Optik"}),
    ])])
    assert run.stop_reason == "frage" and [b.modul for b in run.ui_bloecke] == [ENTSCHEIDUNG]
    assert gesehen[0] == []
    assert ZWEITE_FRAGE in [m["content"] for m in msgs if m.get("role") == "tool"]


def test_nach_dem_entwurf_ist_keine_zweite_frage_moeglich(monkeypatch, gesehen):
    _fake, run, msgs = _lauf(monkeypatch, [_resp_tools([
        _tool_call(STRUKTURENTWURF, {"thema": "Optik"}),
        _tool_call(ENTSCHEIDUNG, _FRAGE),
    ])])
    assert [b.modul for b in run.ui_bloecke] == [STRUKTURENTWURF]
    assert ZWEITE_FRAGE in [m["content"] for m in msgs if m.get("role") == "tool"]


def test_der_dienst_endet_vor_der_frist_des_laufs(monkeypatch, gesehen):
    import asyncio

    beginn: dict[str, float] = {}

    async def messe(auftrag, *, llm, frist_ende, vorlage=None):
        beginn["jetzt"] = asyncio.get_running_loop().time()
        gesehen[0].append({"frist_ende": frist_ende})
        return dienst.Erzeugt(dict(_DATEN))

    monkeypatch.setattr(dienst, "erzeugen", messe)
    from boerdi.domain.config_models.engine import AgentLimits
    _lauf(monkeypatch, [_resp_tools([_tool_call(STRUKTURENTWURF, {"thema": "Optik"})])],
          limits=AgentLimits(deadline_s=60))
    rest = gesehen[0][0]["frist_ende"] - beginn["jetzt"]
    assert 60 - 15 - 2 < rest <= 60 - 15                     # Reserve für den Begleitsatz


def test_die_vorlage_der_person_geht_an_den_dienst(monkeypatch, gesehen):
    vorlage = {**_DATEN, "uebernommen": False, "bearbeitet": True}
    _lauf(monkeypatch, [_resp_tools([_tool_call(STRUKTURENTWURF, {
        "thema": "Optik", "vorlage": True, "vertiefen": ["Licht"]})])], modul_vorlage=vorlage)
    assert gesehen[0][0]["vorlage"] is vorlage


def test_scheitert_der_entwurf_gilt_die_antwort_derselben_runde_nicht(monkeypatch, gesehen):
    gesehen[1]["wert"] = dienst.Erzeugt(None, "fehler")
    _fake, run, msgs = _lauf(monkeypatch, [
        _resp_tools([_tool_call(STRUKTURENTWURF, {"thema": "Optik"}),
                     _tool_call("respond_to_user", {"text": "Hier ist der Entwurf."})]),
        _resp_text("Der Entwurf ging leider nicht."),
    ])
    assert run.ui_bloecke == [] and run.text == "Der Entwurf ging leider nicht."
    werkzeug_texte = [m["content"] for m in msgs if m.get("role") == "tool"]
    assert werkzeug_texte[0].startswith("Fehler:") and ANTWORT_VERWORFEN in werkzeug_texte
    assert json.dumps(run.outcomes[0].model_dump())  # Ergebnis protokolliert
    assert run.outcomes[0].error == "fehler"


# ── Muster-Weg (Vorrunde der Muster-Schleife, T-16) ───────────────────────


def _aufrufe(*calls):
    return _resp_tools(list(calls)).choices[0].message.tool_calls


async def test_die_muster_vorrunde_ruft_den_dienst_mit_dem_zaehler(gesehen):
    from boerdi.services.tool_loop_module import MODUL_BLOECKE_KEY, nimm_module_an

    zaehler: dict[str, Any] = {}
    state: dict[str, Any] = {}
    msgs: list[dict] = []
    tools_called: list[str] = []
    vorrunde = await nimm_module_an(
        _aufrufe(_tool_call(STRUKTURENTWURF, {"thema": "Optik"})), [STRUKTURENTWURF], state, msgs,
        tools_called=tools_called, outcomes=[], usage_acc=zaehler)
    [block] = state[MODUL_BLOECKE_KEY]
    assert block.modul == STRUKTURENTWURF and not vorrunde.ohne_block
    assert gesehen[0][0]["llm"].zaehler is zaehler and gesehen[0][0]["vorlage"] is None
    assert tools_called == [STRUKTURENTWURF] and msgs[0]["content"].startswith("OK: Der Entwurf")


async def test_die_muster_vorrunde_weist_einen_zweiten_entwurf_ab(gesehen):
    from boerdi.services.tool_loop_module import nimm_module_an

    state: dict[str, Any] = {}
    msgs: list[dict] = []
    await nimm_module_an(
        _aufrufe(_tool_call(ENTSCHEIDUNG, _FRAGE),
                 _tool_call(STRUKTURENTWURF, {"thema": "Optik"}, "c2")),
        [ENTSCHEIDUNG, STRUKTURENTWURF], state, msgs, tools_called=[], outcomes=[])
    assert msgs[1]["content"] == ZWEITE_FRAGE and gesehen[0] == []
