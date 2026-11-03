"""Paket U1-f: Studio-Schalter der UI-Module — „aktiv“ und „für den Agenten“ (Plan §16).

Gespeichert in ``01-base/display-rules`` unter ``display_rules.ui_module`` als Ausschalt-Listen
(``aus``, ``agent_aus``). Geprüft wird hier der Weg durch den echten Lader (Speicher gebunden),
nicht über eine Attrappe des Laders: ein neuer Schlüssel wirkt erst, wenn der Lader ihn
zurückgibt (Falle ``config-loader-kuratiert-die-rueckgabe``).
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models import model_for
from boerdi.services import config_loader as cl
from boerdi.ui_module import schalter
from boerdi.ui_module.namen import ENTSCHEIDUNG, INHALTSRAHMEN, LINKBOX, THEMENBAUM, TREFFERLISTE
from boerdi.ui_module.werkzeuge import modul_werkzeuge

BEREICH = "01-base/display-rules"
ALLE = (ENTSCHEIDUNG, THEMENBAUM)


class _Store:
    def __init__(self, areas: dict[str, dict[str, Any]]) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


@pytest.fixture()
def bind():
    yield lambda ui_module: cl.bind_store(_Store(
        {BEREICH: {"display_rules": {"ui_module": ui_module}}} if ui_module is not None else {}))
    cl.bind_store(None)


def _doc(ui_module: Any) -> dict[str, Any]:
    return {"display_rules": {"ui_module": ui_module}}


# ── Modell (Prüfung beim Speichern im Studio) ──────────────────────────────
def test_das_modell_nimmt_ausschalt_listen_an() -> None:
    model_for(BEREICH).model_validate(_doc({"aus": [LINKBOX], "agent_aus": [ENTSCHEIDUNG]}))
    model_for(BEREICH).model_validate(_doc({}))


@pytest.mark.parametrize("liste", ["aus", "agent_aus"])
def test_der_inhaltsrahmen_ist_fest(liste: str) -> None:
    with pytest.raises(ValidationError, match="fest"):
        model_for(BEREICH).model_validate(_doc({liste: [INHALTSRAHMEN]}))


@pytest.mark.parametrize("name", ["Ui_Linkbox", "linkbox", "ui_x", ""])
def test_ein_name_ausserhalb_der_form_wird_abgewiesen(name: str) -> None:
    with pytest.raises(ValidationError):
        model_for(BEREICH).model_validate(_doc({"aus": [name]}))


def test_ein_name_doppelt_wird_abgewiesen() -> None:
    with pytest.raises(ValidationError, match="doppelt"):
        model_for(BEREICH).model_validate(_doc({"aus": [LINKBOX, LINKBOX]}))


# ── Lader ──────────────────────────────────────────────────────────────────
def test_ohne_eintrag_sind_alle_module_an(bind) -> None:
    bind(None)
    assert cl.load_ui_modul_schalter() == {"aus": frozenset(), "agent_aus": frozenset()}
    assert all(schalter.aktiv(n) and schalter.fuer_agent(n) for n in ALLE)


def test_der_lader_liest_die_listen_aus_dem_speicher(bind) -> None:
    bind({"aus": [LINKBOX], "agent_aus": [ENTSCHEIDUNG]})
    assert cl.load_ui_modul_schalter() == {"aus": frozenset({LINKBOX}),
                                           "agent_aus": frozenset({ENTSCHEIDUNG})}


def test_kaputter_bestand_bricht_nichts_und_der_inhaltsrahmen_bleibt_an(bind) -> None:
    # Am Validator vorbei (alte Sicherung, Rohtext): der Lader nimmt nur Texte.
    bind({"aus": "ui_linkbox", "agent_aus": [3, None, INHALTSRAHMEN]})
    assert cl.load_ui_modul_schalter() == {"aus": frozenset(),
                                           "agent_aus": frozenset({INHALTSRAHMEN})}
    # Der Lader liest nur; dass ein festes Modul an bleibt, entscheidet ``schalter``.
    assert schalter.aktiv(INHALTSRAHMEN) and schalter.fuer_agent(INHALTSRAHMEN)


def test_die_schalter_gehen_nicht_in_die_oeffentlichen_anzeige_regeln(bind) -> None:
    # ``load_display_rules_config`` reist in jeder Antwort mit — die Schalter gehören nicht dazu.
    bind({"aus": [LINKBOX]})
    assert "ui_module" not in cl.load_display_rules_config()


# ── Bedeutung ──────────────────────────────────────────────────────────────
def test_aus_heisst_auch_nicht_fuer_den_agenten(bind) -> None:
    bind({"aus": [ENTSCHEIDUNG]})
    assert not schalter.aktiv(ENTSCHEIDUNG)
    assert not schalter.fuer_agent(ENTSCHEIDUNG)


def test_agent_aus_laesst_das_modul_aktiv(bind) -> None:
    bind({"agent_aus": [ENTSCHEIDUNG]})
    assert schalter.aktiv(ENTSCHEIDUNG)
    assert not schalter.fuer_agent(ENTSCHEIDUNG)


def test_schaltbarkeit_je_modul() -> None:
    assert schalter.schaltbar(INHALTSRAHMEN) == {"aktiv": False, "agent": False}
    assert schalter.schaltbar(LINKBOX) == {"aktiv": True, "agent": False}
    assert schalter.schaltbar(TREFFERLISTE) == {"aktiv": True, "agent": False}
    assert schalter.schaltbar(ENTSCHEIDUNG) == {"aktiv": True, "agent": True}
    assert schalter.schaltbar(THEMENBAUM) == {"aktiv": True, "agent": True}


# ── Angebot der Modul-Werkzeuge ────────────────────────────────────────────
def _namen(werkzeuge: list[dict[str, Any]]) -> set[str]:
    return {w["function"]["name"] for w in werkzeuge}


_VERFUEGBAR = {"browse_collection_tree"}


def test_der_agent_bekommt_kein_abgeschaltetes_modul(bind) -> None:
    bind({"agent_aus": [ENTSCHEIDUNG], "aus": [THEMENBAUM]})
    assert _namen(modul_werkzeuge(ALLE, _VERFUEGBAR, fuer="agent")) == set()


def test_das_muster_bietet_ein_nur_fuer_den_agenten_abgeschaltetes_modul_weiter_an(bind) -> None:
    bind({"agent_aus": [ENTSCHEIDUNG]})
    assert _namen(modul_werkzeuge(ALLE, _VERFUEGBAR, fuer="muster")) == set(ALLE)


def test_das_muster_bietet_kein_inaktives_modul_an(bind) -> None:
    bind({"aus": [ENTSCHEIDUNG]})
    assert _namen(modul_werkzeuge(ALLE, _VERFUEGBAR, fuer="muster")) == {THEMENBAUM}


def test_ohne_schalter_bleibt_das_angebot_wie_bisher(bind) -> None:
    bind(None)
    assert _namen(modul_werkzeuge(ALLE, _VERFUEGBAR, fuer="agent")) == set(ALLE)


def test_fuer_ist_eine_pflichtangabe() -> None:
    with pytest.raises(TypeError):
        modul_werkzeuge(ALLE, _VERFUEGBAR)  # type: ignore[call-arg]


# ── Abgeleitete Blöcke (live und Verlauf) ─────────────────────────────────
_LINKS = [{"title": "WirLernenOnline", "url": "https://wirlernenonline.de/"}]


def _antwort(**mehr):
    from boerdi.api.schemas import ChatResponse, DebugInfo

    return ChatResponse(session_id="bb-12345678-1234", content="x",
                        debug=DebugInfo(pattern=mehr.pop("pattern", "M05")), **mehr)


def _module_live_und_verlauf() -> tuple[list[str], list[str]]:
    from boerdi.api import publikum
    from boerdi.api.schemas import WebLink
    from tests.test_ui_trefferliste_backend import _KARTEN, _META

    live = publikum.antwort_fuer(_antwort(web_links=[WebLink(**link) for link in _LINKS],
                                          cards=list(_KARTEN), query_metas=[_META]),
                                 intern=False)
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "M05", "_web_links": _LINKS, "_query_metas": [_META.model_dump()]},
        cards=[k.model_dump() for k in _KARTEN])
    return ([b.modul for b in live.ui.ui_bloecke], [b.modul for b in verlauf.ui_bloecke])


def test_ohne_schalter_entstehen_beide_abgeleiteten_bloecke(bind) -> None:
    bind(None)
    assert _module_live_und_verlauf() == ([TREFFERLISTE, LINKBOX], [TREFFERLISTE, LINKBOX])


@pytest.mark.parametrize(("aus", "bleibt"), [([TREFFERLISTE], [LINKBOX]),
                                             ([LINKBOX], [TREFFERLISTE]),
                                             ([TREFFERLISTE, LINKBOX], [])])
def test_ein_inaktives_abgeleitetes_modul_entsteht_weder_live_noch_im_verlauf(
        bind, aus, bleibt) -> None:
    bind({"aus": aus})
    assert _module_live_und_verlauf() == (bleibt, bleibt)


def test_agent_aus_aendert_an_abgeleiteten_bloecken_nichts(bind) -> None:
    bind({"agent_aus": [TREFFERLISTE, LINKBOX]})
    assert _module_live_und_verlauf() == ([TREFFERLISTE, LINKBOX], [TREFFERLISTE, LINKBOX])


def test_gespeicherte_bloecke_eines_inaktiven_moduls_bleiben_im_verlauf(bind) -> None:
    """Der Verlauf ist ein Protokoll (Plan §16, F-2): was gezeigt wurde, bleibt."""
    from boerdi.api import publikum
    from boerdi.domain import ui_bloecke

    optionen = [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}]
    frage = ui_bloecke.neuer_block(ENTSCHEIDUNG, 1, "abfragen",
                                   {"frage": "Welche Stufe?", "optionen": optionen},
                                   "Welche Stufe?\n\n1. A\n2. B")
    bind({"aus": [ENTSCHEIDUNG]})
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "AGENT", ui_bloecke.DEBUG_KEY: ui_bloecke.fuer_den_debug_block([frage])})
    assert [b.modul for b in verlauf.ui_bloecke] == [ENTSCHEIDUNG]


# ── Direktaktion „Unterthemen öffnen“ ─────────────────────────────────────
def test_ist_der_themenbaum_aus_baut_die_aktion_keinen_baum(bind, monkeypatch) -> None:
    import asyncio

    from boerdi.api.schemas import ChatRequest
    from boerdi.services import themenbaum_aktion
    from boerdi.ui_module import datenquelle
    from tests.test_ui_themenbaum import _Rufer
    from tests.test_ui_themenbaum_aktion import KNOTEN

    gespeichert: list[str] = []

    async def _save(session, session_id, role, content, cards=None, debug=None):
        gespeichert.append(content)

    rufer = _Rufer()
    monkeypatch.setattr(datenquelle, "_rufen", rufer)
    monkeypatch.setattr(themenbaum_aktion, "save_message", _save)
    bind({"aus": [THEMENBAUM]})
    req = ChatRequest(session_id="bb-1", message="Unterthemen von Algebra",
                      action="show_collection_tree",
                      action_params={"collection_id": KNOTEN, "title": "Algebra"})

    resp = asyncio.run(themenbaum_aktion.handle_show_collection_tree(
        None, req, {}, blocked_tools=[]))

    assert rufer.calls == [] and resp.ui.ui_bloecke == []
    assert "abgeschaltet" in resp.content and "Algebra" in resp.content
    assert resp.quick_replies == []          # ein zweiter Versuch hülfe nicht
    assert gespeichert == [resp.content]


# ── Studio: Werkzeug-Übersicht und Prompt-Vorschau ────────────────────────
def test_die_uebersicht_nennt_die_studio_sperre_nur_wenn_abgeschaltet(bind, monkeypatch) -> None:
    from boerdi.services import agent_tool_overview as ov
    from boerdi.services import agent_tools

    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    monkeypatch.setattr(ov, "load_policy_config", lambda: {})
    monkeypatch.setattr(ov, "load_rag_config", lambda: {})

    def zeile(name: str) -> dict:
        return next(t for t in ov.werkzeugliste()["tools"] if t["name"] == name)

    bind(None)
    assert zeile(ENTSCHEIDUNG)["offered"] is True
    assert {"code": "studio_off"} not in zeile(ENTSCHEIDUNG)["locks"]

    bind({"agent_aus": [ENTSCHEIDUNG]})
    abgeschaltet = zeile(ENTSCHEIDUNG)
    assert abgeschaltet["offered"] is False
    assert {"code": "studio_off"} in abgeschaltet["locks"]

    bind({"aus": [THEMENBAUM]})
    assert {"code": "studio_off"} in zeile(THEMENBAUM)["locks"]
    assert zeile(INHALTSRAHMEN)["locks"] == []      # fest: nie abgeschaltet


async def test_die_prompt_vorschau_nennt_nur_module_fuer_den_agenten(bind, monkeypatch) -> None:
    from boerdi.services import agent_prompt_preview as pv
    from boerdi.services import agent_tools

    async def _kein_block(_):
        return None

    monkeypatch.setattr(pv, "load_rag_config", lambda: {})
    monkeypatch.setattr(pv.master_skill, "prompt_block", _kein_block)
    monkeypatch.setattr(pv.master_skill, "zustand", lambda: {})
    monkeypatch.setattr(agent_tools, "has_auth_token", lambda: False)
    bind({"agent_aus": [ENTSCHEIDUNG]})

    module = (await pv.prompt_vorschau("de"))["tools"]["ui_module"]

    assert module["names"] == [THEMENBAUM]
    assert module["chars"] == len(json.dumps(modul_werkzeuge(
        [THEMENBAUM], verfuegbar={"browse_collection_tree"}, fuer="agent"), ensure_ascii=False))


# ── Studio-Endpunkt GET /api/config/ui-module ─────────────────────────────
_AUTH = {"X-Studio-Key": "k-studio-testkey"}


@pytest.fixture()
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from boerdi.main import create_app
    from boerdi.settings import get_settings

    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_der_katalog_nur_mit_studio_schluessel(client) -> None:
    assert client.get("/api/config/ui-module").status_code == 401


def test_der_katalog_nennt_jedes_modul_mit_manifest_und_schaltbarkeit(client) -> None:
    from boerdi.ui_module import katalog

    antwort = client.get("/api/config/ui-module", headers=_AUTH)
    assert antwort.status_code == 200
    daten = antwort.json()
    assert daten["bereich"] == BEREICH
    module = {m["name"]: m for m in daten["module"]}
    assert list(module) == sorted(katalog.katalog())
    for name, manifest in katalog.katalog().items():
        assert module[name]["manifest"] == manifest
        assert module[name]["schaltbar"] == schalter.schaltbar(name)
    assert module[INHALTSRAHMEN]["schaltbar"] == {"aktiv": False, "agent": False}
    assert module[LINKBOX]["abgeleitet"] is True
    assert module[ENTSCHEIDUNG]["abgeleitet"] is False
