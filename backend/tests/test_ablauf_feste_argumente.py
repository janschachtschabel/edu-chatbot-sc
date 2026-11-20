"""Plan 2026-11-19, A2 (E4, Befund S2b): feste Argumente am KI-Schritt.

``agent.feste_argumente`` (je Werkzeug ein Objekt) setzt der Server in JEDEN Aufruf des Werkzeugs
in diesem Schritt — anders als ``vorbelegen`` geht hier der Ablauf vor der KI. So entwirft der
Dokument-Schritt nie frei, wenn die KI ``aus_dokument`` vergisst. Die Prüfung kennt das Feld: nur
Werkzeuge des Schritts, nur UI-Module mit Dienst, nur Argumente (und Werte) ihres Schemas.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

from boerdi.api.schemas_debug import ToolOutcome
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import pruefung, treiber
from boerdi.ui_module import aufruf
from boerdi.ui_module.datenquelle import Ergebnis
from boerdi.ui_module.namen import STRUKTURENTWURF

_SEEDS = Path(__file__).resolve().parents[1] / "seeds" / "06-ablaeufe"


def _ablauf(**agent: Any) -> AblaufArea:
    return AblaufArea.model_validate({"id": "tb", "titel": {"de": "TB"}, "schritte": [
        {"id": "entwurf", "typ": "agent", "text": {"de": "Los?"},
         "agent": {"werkzeuge": [STRUKTURENTWURF], **agent}},
        {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})


def _befunde(ablauf: AblaufArea) -> list[str]:
    return [b for b in pruefung.pruefe(ablauf) if "feste_argumente" in b]


# ── Modell ───────────────────────────────────────────────────────────────────────────────────────

def test_leer_ist_nicht_gesetzt_und_aendert_die_fassung_nicht():
    leer = _ablauf(feste_argumente={})
    assert leer.schritte[0].agent.feste_argumente is None
    assert treiber.fassung(leer) == treiber.fassung(_ablauf())
    gesetzt = _ablauf(feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})
    assert gesetzt.schritte[0].agent.feste_argumente == {STRUKTURENTWURF: {"aus_dokument": True}}


# ── Dienst: der Ablauf geht vor der KI ───────────────────────────────────────────────────────────

def _rufe(args: dict, **umgebung: Any) -> Ergebnis:
    async def los():
        ende = asyncio.get_running_loop().time() + 60
        return await aufruf.asynchron(STRUKTURENTWURF, args,
                                      aufruf.Umgebung(frist_ende=ende, **umgebung))
    return asyncio.run(los())


@pytest.mark.parametrize("args", [{"thema": "Optik"}, {"thema": "Optik", "aus_dokument": False}])
def test_ein_aufruf_ohne_aus_dokument_erreicht_den_dienst_mit_aus_dokument(args):
    # Ohne Dokument der Sitzung antwortet der Dienst ``kein_dokument`` — der Beweis, dass er
    # ``aus_dokument: true`` bekam (ohne entwürfe er frei).
    erg = _rufe(args, feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})
    assert erg.block is None and erg.outcome.error == "kein_dokument"


def test_feste_argumente_gehen_auch_der_vorbelegung_vor():
    erg = _rufe({"thema": "Optik"}, vorbelegung={"thema": "Optik", "tiefe": 1},
                feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})
    assert erg.outcome.error == "kein_dokument"


def test_feste_argumente_eines_anderen_werkzeugs_gelten_nicht(monkeypatch):
    from boerdi.services import strukturentwurf_dienst as dienst

    async def erzeugen(auftrag, **k):
        return dienst.Erzeugt(None, "test")

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    erg = _rufe({"thema": "Optik"}, feste_argumente={"ui_upload": {"aus_dokument": True}})
    assert erg.outcome.error == "test"


# ── Weg dorthin: Muster und Agent ────────────────────────────────────────────────────────────────

def test_der_muster_weg_reicht_sie_durch(monkeypatch):
    from boerdi.services import tool_loop_module

    gesehen: dict = {}

    async def asynchron(name, args, umgebung=None):
        gesehen["umgebung"] = umgebung
        return Ergebnis(None, "t", ToolOutcome(tool=name, status="error", error="test"))

    monkeypatch.setattr(tool_loop_module, "asynchron", asynchron)
    feste = {STRUKTURENTWURF: {"aus_dokument": True}}
    state = {tool_loop_module.FESTE_KEY: feste}
    asyncio.run(tool_loop_module._ergebnis(
        STRUKTURENTWURF, '{"thema": "Karate"}', [STRUKTURENTWURF], state,
        tool_loop_module.Vorrunde(), [], [], 0, None))
    assert gesehen["umgebung"].feste_argumente == feste


def test_der_agent_weg_reicht_sie_durch(monkeypatch):
    from boerdi.services import agent_loop
    from tests.test_agent_loop import _lauf, _resp_text, _resp_tools, _tool_call

    gesehen: dict = {}

    async def asynchron(name, args, umgebung=None):
        gesehen["umgebung"] = umgebung
        return Ergebnis(None, "t", ToolOutcome(tool=name, status="error", error="test"))

    monkeypatch.setattr(agent_loop, "modul_asynchron", asynchron)
    feste = {STRUKTURENTWURF: {"aus_dokument": True}}
    _lauf(monkeypatch, [_resp_tools([_tool_call(STRUKTURENTWURF, {"thema": "Optik"})]),
                        _resp_text("Fertig.")], modul_feste=feste)
    assert gesehen["umgebung"].feste_argumente == feste


# ── Prüfung ──────────────────────────────────────────────────────────────────────────────────────

def test_gueltige_feste_argumente_ergeben_keinen_befund():
    assert _befunde(_ablauf(feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})) == []


def test_ein_werkzeug_ausserhalb_des_schritts_ist_ein_befund():
    [b] = _befunde(_ablauf(feste_argumente={"ui_upload": {"ziel": "x"}}))
    assert "ui_upload" in b


def test_ein_unbekanntes_argument_ist_ein_befund():
    [b] = _befunde(_ablauf(feste_argumente={STRUKTURENTWURF: {"aus_dokumentt": True}}))
    assert "aus_dokumentt" in b and "aus_dokument" in b


def test_ein_falscher_wert_ist_ein_befund():
    [b] = _befunde(_ablauf(feste_argumente={STRUKTURENTWURF: {"aus_dokument": "ja"}}))
    assert "aus_dokument" in b


def test_ein_werkzeug_ohne_dienst_ist_ein_befund():
    ablauf = AblaufArea.model_validate({"id": "tb", "titel": {"de": "TB"}, "schritte": [
        {"id": "suche", "typ": "agent", "text": {"de": "Los?"},
         "agent": {"werkzeuge": ["search_wlo_all"],
                   "feste_argumente": {"search_wlo_all": {"query": "x"}}}},
        {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]})
    [b] = _befunde(ablauf)
    assert "search_wlo_all" in b


def test_die_befunde_gibt_es_auf_englisch():
    ablauf = _ablauf(feste_argumente={STRUKTURENTWURF: {"aus_dokumentt": True}})
    [b] = [b for b in pruefung.pruefe(ablauf, "en") if "feste_argumente" in b]
    assert b.startswith("Step entwurf:")


# ── Seeds ────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("datei", "schritt", "argumente"), [
    ("themenbaum.yaml", "entwurf_dokument", {"aus_dokument": True}),
    ("themenbaum.yaml", "entwurf_inhalte", {"aus_inhalten": True}),
    ("themenbaum_aus_inhalten.yaml", "entwurf", {"aus_inhalten": True}),
])
def test_die_seeds_entwerfen_dort_nie_frei(datei, schritt, argumente):
    ablauf = AblaufArea.model_validate(yaml.safe_load((_SEEDS / datei).read_text("utf-8")))
    [s] = [s for s in ablauf.schritte if s.id == schritt]
    assert s.agent.feste_argumente == {STRUKTURENTWURF: argumente}
    assert _befunde(ablauf) == []
    # Review A, MINOR 6: „nochmal“ nach ``voruebergehend`` zehrt das Budget nicht auf
    assert s.agent.zuege == 5


# ── Abnahme S2: die Scan-PDF im WLO-Weg ─────────────────────────────────────────────────────────

def test_scan_im_wlo_weg_kein_freier_entwurf_sondern_kein_lesbarer_text():
    """Die KI ruft ohne ``aus_dokument``; der Schritt setzt es, und die Scan-PDF (WLO hat keinen
    Volltext, ``not_extracted``) ergibt den Satz „kein lesbarer Text“ — keinen freien Entwurf."""
    from boerdi.services.dokumente.stand import OhneVolltext
    from boerdi.ui_module.dienst_fehler import FEHLER

    async def lader():
        return OhneVolltext((("Unterricht planen.pdf", "not_extracted"),))

    erg = _rufe({"thema": "Unterricht planen in der beruflichen Bildung"}, dokument=lader,
                feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})
    assert erg.block is None and erg.outcome.error == "volltext_fehlt"
    assert erg.text.startswith(FEHLER["volltext_fehlt_datei"].split("{namen}")[0])
    assert "Scan" in erg.text


# ── Review Paket A, MAJOR 1: feste Argumente gelten nur für neue Entwürfe ──────────────────────

_VORLAGE = {"titel": "Physik", "quelle": "dokument", "thema": "Physik",
            "knoten": [{"id": "k1", "titel": "Optik"}, {"id": "k2", "titel": "Mechanik"}]}


def test_mit_vorlage_wird_vertieft_statt_neu_entworfen(monkeypatch):
    from boerdi.services import strukturentwurf_dienst as dienst

    gesehen: dict = {}

    async def erzeugen(auftrag, **k):
        gesehen.update(k, auftrag=auftrag)
        return dienst.Erzeugt(None, "test")

    monkeypatch.setattr(dienst, "erzeugen", erzeugen)
    erg = _rufe({"thema": "Physik", "vorlage": True, "vertiefen": ["Optik"]}, vorlage=_VORLAGE,
                feste_argumente={STRUKTURENTWURF: {"aus_dokument": True}})
    assert erg.outcome.error == "test"                     # nicht ``dokument_vorlage``
    assert gesehen["vorlage"] == _VORLAGE and gesehen["dokument"] is None
    assert gesehen["auftrag"].vertiefen == ("Optik",)


def test_mit_vorlage_zeigt_erneut_zeigen_den_entwurf_wieder():
    erg = _rufe({"thema": "Physik", "vorlage": True, "erneut_zeigen": True}, vorlage=_VORLAGE,
                feste_argumente={STRUKTURENTWURF: {"aus_inhalten": True}})
    assert erg.block is not None and erg.outcome.status == "success"


# ── Review A, MINOR 9: die Verdrahtung in den Knoten ────────────────────────────────────────────

_FESTE = {STRUKTURENTWURF: {"aus_dokument": True}}


def _ki_ablauf() -> AblaufArea:
    return _ablauf(feste_argumente=_FESTE)


def test_der_muster_knoten_legt_die_festen_argumente_ab_und_raeumt_auf(monkeypatch):
    from boerdi.services import tool_loop_module
    from tests.test_respond_node import _ctx, _install, _Rec, _run, respond_mod

    ablauf = _ki_ablauf()
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx()
    gesehen: dict = {}

    async def generate(session, **kw):
        gesehen["feste"] = ctx.session_state.get(tool_loop_module.FESTE_KEY)
        return ("ANTWORT", [], [], [])

    monkeypatch.setattr(respond_mod, "generate_response", generate)
    monkeypatch.setattr(respond_mod.ki_schritt, "fuer_zug",
                        lambda state, sid, safety: (ablauf, ablauf.schritte[0]))
    _run(ctx)
    assert gesehen["feste"] == _FESTE
    assert tool_loop_module.FESTE_KEY not in ctx.session_state          # nur für diesen Zug


@pytest.mark.anyio
async def test_der_agent_knoten_reicht_die_festen_argumente_an_die_schleife(monkeypatch):
    from tests.test_respond_agent import _ctx, _patch, agent_mod, respond_agent

    ablauf = _ki_ablauf()
    monkeypatch.setattr(agent_mod.ki_schritt, "aktueller",
                        lambda state, sid: (ablauf, ablauf.schritte[0]))
    seen: dict = {}
    _patch(monkeypatch, seen)
    await respond_agent(_ctx())
    assert seen["run_agent_loop"]["modul_feste"] == _FESTE


# ── Review A, NIT 11: widersprüchliche feste Argumente ──────────────────────────────────────────

def test_aus_dokument_und_aus_inhalten_zugleich_ist_ein_befund():
    [b] = _befunde(_ablauf(feste_argumente={
        STRUKTURENTWURF: {"aus_dokument": True, "aus_inhalten": True}}))
    assert "aus_dokument" in b and "aus_inhalten" in b


@pytest.mark.parametrize("argument", [
    {"vorlage": True}, {"vertiefen": ["Optik"]}, {"erneut_zeigen": True}])
def test_vorlage_vertiefen_und_erneut_zeigen_sind_nie_fest(argument):
    [b] = _befunde(_ablauf(feste_argumente={STRUKTURENTWURF: argument}))
    assert next(iter(argument)) in b


def test_werte_mit_verweis_ins_schema_werden_geprueft():
    """Zweites Review A, NIT 10: ein Argument mit ``$ref`` (``#/$defs/…``) wird gegen das Teilschema
    MIT den ``$defs`` des Werkzeugs geprüft — allein gelöst, fände der Verweis nichts."""
    from boerdi.services.ablauf import pruefung_feste

    module = {"ui_x": {"dienst": {"parameter": {
        "type": "object", "properties": {"stufe": {"$ref": "#/$defs/stufe"}},
        "$defs": {"stufe": {"enum": ["Primarstufe"]}}}}}}

    def schritt(wert):
        return AblaufArea.model_validate({"id": "tb", "titel": {"de": "TB"}, "schritte": [
            {"id": "s", "typ": "agent", "text": {"de": "Los?"},
             "agent": {"werkzeuge": ["ui_x"], "feste_argumente": {"ui_x": {"stufe": wert}}}},
            {"id": "ende", "typ": "ende", "text": {"de": "Ende."}}]}).schritte[0]

    assert pruefung_feste.befunde(schritt("Primarstufe"), module, "de") == []
    [b] = pruefung_feste.befunde(schritt("Mond"), module, "de")
    assert "stufe" in b
