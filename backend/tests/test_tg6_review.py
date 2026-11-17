"""Plan 2026-11-16, Review TG-4–6: die Befunde am Ablauf „Themenbaum erstellen“ und seinen Diensten.

- **MAJOR 1:** Direktstart nur, wenn vor dem Auftrag eine Frage steht, die auch Nein sagen lässt.
- **MAJOR 2:** Der Start schließt freie Arbeit nur, wenn dort eine Ablage, ein Metadaten-Lauf oder
  ein offener Lauf liegt — sonst bleibt der Entwurf.
- **MAJOR 3:** Synonyme treffen an Fragen mit Freitext nur als ganze Wörter; die Führung bleibt.
- **MINOR 8:** „gründlich“ nur, wenn auch der Metadaten-Auftrag geht.
- **MINOR 12:** Verdrahtung im Muster-Weg, unlesbares Dokument im Zug.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest
import yaml

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services import arbeitsstand
from boerdi.services.ablauf import treiber, werkzeuge, zug_basis
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from tests.test_ablauf_zug import (
    _S,
    _starte,
    _wahlen,
    umgebung,  # noqa: F401 — Fixture
)

_SEEDS = pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"


def _seed(name: str = "themenbaum") -> AblaufArea:
    return AblaufArea.model_validate(yaml.safe_load(
        (_SEEDS / f"{name}.yaml").read_text(encoding="utf-8")))


# ── MAJOR 1: eine echte Rückfrage ────────────────────────────────────────────────────────────────

def _sprache(**frage) -> AblaufArea:
    """Die Probe des Reviews: „Welche Sprache?“ — beide Antworten führen zum schreibenden
    Auftrag."""
    return AblaufArea.model_validate({
        "id": "sprache", "titel": {"de": "Sprache"}, "voraussetzungen": ["anmeldung"],
        "ausloeser": [{"art": "agent", "modus": "direkt"}],
        "schritte": [
            {"id": "frage", "typ": "nachricht", "text": {"de": "Welche Sprache?"},
             "optionen": [{"id": "de", "label": {"de": "Deutsch"}, "ziel": "a"},
                          {"id": "en", "label": {"de": "Englisch"}, "ziel": "a"}], **frage},
            {"id": "a", "typ": "auftrag", "flow": "f/x", "repo_schreibt": True,
             "bei_fehler": "e"},
            {"id": "e", "typ": "ende", "text": {"de": "Fertig."}}]})


def test_major1_eine_frage_ohne_nein_ist_keine_zustimmung():
    ablauf = _sprache()
    assert werkzeuge.ablauf_schreibt_ungefragt(ablauf)
    assert any("modus direkt" in b for b in pruefe(ablauf))


def test_major1_mit_nein_daneben_ist_es_eine_rueckfrage():
    ablauf = _sprache()
    ablauf.schritte[0].optionen[1].ziel = "e"
    assert not werkzeuge.ablauf_schreibt_ungefragt(ablauf)
    # … aber nicht, wenn getippter Text ebenfalls zum Auftrag führt
    mit_text = _sprache(freitext={"ziel": "a", "schreibt": "sprache"})
    mit_text.schritte[0].optionen[1].ziel = "e"
    assert werkzeuge.ablauf_schreibt_ungefragt(mit_text)


def test_major1_themenbaum_erstellen_fragt_mit_nein():
    ablauf = _seed()
    frage = next(s for s in ablauf.schritte if s.id == "metadaten_frage")
    assert {o.ziel for o in frage.optionen} == {"metadaten", "lesen"}
    assert not werkzeuge.ablauf_schreibt_ungefragt(ablauf)


# ── MAJOR 3: Synonyme als ganze Wörter ───────────────────────────────────────────────────────────

@pytest.mark.parametrize(("text", "erwartet"), [
    ("Lerninhalte der Zellbiologie", None),
    ("Systematik der Pflanzen", None),
    ("Pflegedokumentation", None),
    ("Inhalte der Optik", None),
    ("aus meinem Lehrplan", "dokument"),
    ("Ein Dokument, bitte", "dokument"),
    ("aus meinen Ordnern", "ordner"),
    ("meine Dateien", "dateien"),
    ("aus meinen Materialien", "dateien"),
])
def test_major3_grundlage_trifft_nur_ganze_woerter(text, erwartet):
    grundlage = next(s for s in _seed().schritte if s.id == "grundlage")
    assert treiber.wahl_aus_text(grundlage, text, "de") == erwartet


def test_major3_ohne_freitext_bleibt_der_teilwort_treffer():
    """Die Führung (Gruppenwahl ohne Freitext, WF-2) trifft weiter per Teilwort."""
    s = Schritt.model_validate({"id": "g", "typ": "nachricht", "text": {"de": "?"},
                                "optionen": [{"id": "l", "label": {"de": "Lehrkraft"},
                                              "ziel": "g", "synonyme": ["lehr"]}]})
    assert treiber.wahl_aus_text(s, "Ich bin Lehrerin", "de") == "l"


def test_major3_andere_grundlage_im_fehlerweg():
    ohne = next(s for s in _seed().schritte if s.id == "ohne_daten")
    andere = next(o for o in ohne.optionen if o.id == "andere")
    assert andere.ziel == "grundlage" and "grundlage" in andere.verwirft


# ── MINOR 8: „gründlich“ nur mit Auftrag und freigegebenem Flow ──────────────────────────────────

def test_minor8_ohne_freigegebenen_flow_kein_gruendlicher_weg(monkeypatch):
    from boerdi.services.ablauf import auftrag_zug
    from boerdi.services.auftraege import client

    monkeypatch.setattr(zug_basis, "_wlo_ablage", lambda: True)
    monkeypatch.setattr(auftrag_zug, "starter", lambda: object())
    monkeypatch.setattr(client, "erlaubt", lambda flow: False)
    assert zug_basis._wlo_erschliessen() is False
    monkeypatch.setattr(client, "erlaubt", lambda flow: flow == zug_basis.METADATEN_FLOW)
    assert zug_basis._wlo_erschliessen() is True
    monkeypatch.setattr(auftrag_zug, "starter", lambda: None)        # ohne Anmeldung/Schlüssel
    assert zug_basis._wlo_erschliessen() is False


def test_minor8_bereit_meldet_erschliessen_nur_mit_ablage():
    async def nichts(_name):
        return None

    def bereit(ablage: bool, erschliessen: bool) -> dict:
        k = werkzeuge.DienstKontext(teile=nichts, wlo_ablage=lambda: ablage,
                                    wlo_erschliessen=lambda: erschliessen)
        return asyncio.run(werkzeuge.DIENSTE["bereitgestellt"]({}, k))

    assert bereit(True, True)["wlo_erschliessen"] is True
    assert bereit(True, False)["wlo_erschliessen"] is False
    assert bereit(False, True)["wlo_erschliessen"] is False


def test_minor8_ohne_erschliessen_fragt_der_ablauf_nicht():
    ablauf = _seed()
    weg = next(s for s in ablauf.schritte if s.id == "dateien_weg")
    regel = next(r for r in weg.weiter if r.dann == "wlo_frage")
    assert regel.wenn_wert.quelle == "teil.bereit.wlo_erschliessen"


def test_minor7_kestra_nur_fuer_inhalte():
    auftrag = next(s for s in _seed().schritte if s.id == "metadaten")
    assert auftrag.argumente["node_ids"]["wo"] == {"stand": "stored", "rolle": "inhalt"}


# ── MAJOR 2 und MINOR 12 im Zug (Harness aus ``test_ablauf_zug``) ────────────────────────────────

@pytest.fixture
def themenbaum(umgebung, monkeypatch):  # noqa: F811 — Fixture
    roh = yaml.safe_load((_SEEDS / "themenbaum.yaml").read_text(encoding="utf-8"))
    umgebung.katalog["wert"] = {"ablaeufe": [roh]}
    monkeypatch.setattr(zug_basis, "_wlo_ablage", lambda: False)
    monkeypatch.setattr(zug_basis, "_wlo_erschliessen", lambda: False)
    return umgebung


_ORDNER = {"aktion": "erfasst", "struktur": {"name": "Physik", "dateien": 0, "alle_dateien": 2,
                                           "kinder": [
    {"name": "Mechanik", "dateien": 1, "alle_dateien": 1, "kinder": []},
    {"name": "Optik", "dateien": 1, "alle_dateien": 1, "kinder": []}]},
    "zahlen": {"ordner": 3, "inhalte": 2}}
_ENTWURF = {"titel": "Physik", "quelle": "ordner", "knoten": [{"id": "k1", "titel": "Optik"}],
            "uebernommen": True, "bearbeitet": True}


def _frei(state, modul, daten):
    assert asyncio.run(arbeitsstand.uebernehmen(_S(), "sitzung-0123456789", state["entities"],
                                                {"modul": modul, "block_id": "b1",
                                                 "daten": daten}))


def test_major2_freie_arbeit_samt_entwurf_bleibt(themenbaum):
    state: dict = {"entities": {}}
    _frei(state, UPLOAD, _ORDNER)
    _frei(state, STRUKTURENTWURF, _ENTWURF)
    [v] = themenbaum.speicher.v.values()
    assert {"structure", "draft"} <= set(v.akte["teile"])
    antwort = _starte(state, "themenbaum")
    assert list(themenbaum.speicher.v) == [v.id]                  # kein neuer Vorgang
    gleich = themenbaum.speicher.v[v.id]
    assert gleich.status != "fertig" and "draft" in gleich.akte["teile"]
    assert _wahlen(antwort) == {"verwenden", "andere", "ohne"}     # die Ordner bietet er an


def test_major2_eine_alte_ablage_erzwingt_einen_frischen_vorgang(themenbaum):
    """N14: eine alte Ablage ginge sonst als „frisch hochgeladen“ an den Metadaten-Flow."""
    state: dict = {"entities": {}}
    _frei(state, UPLOAD, _ORDNER)
    [alt] = themenbaum.speicher.v.values()
    alt.akte["teile"]["ablage"] = {"typ": "wlo.ablage@1", "version": 1, "zusammenfassung": "1",
                                   "wert": {"format": "wlo.ablage@1", "inhalte": []}}
    _starte(state, "themenbaum")
    assert len(themenbaum.speicher.v) == 2
    neu = themenbaum.speicher.v["v-2"]
    assert themenbaum.speicher.v[alt.id].status == "fertig"
    assert "structure" in neu.akte["teile"] and "ablage" not in neu.akte["teile"]


def test_minor12_ein_unlesbares_dokument_wird_nicht_angeboten(themenbaum, monkeypatch):
    """Das Dokument einer anderen Sitzung (oder abgelaufen) ist nicht lesbar — der gewöhnliche
    Einstieg, im echten Zug (nicht in der Simulation, die jedes Dokument für lesbar hält)."""
    async def keins(*_a):
        return None

    async def keine(*_a):
        return []

    monkeypatch.setattr(arbeitsstand, "lesbares_dokument", keins)
    monkeypatch.setattr(arbeitsstand, "lesbare_dokument_ids", keine)
    state: dict = {"entities": {}}
    _frei(state, UPLOAD, _ORDNER | {"struktur": {"name": "", "dateien": 1, "alle_dateien": 1,
                                                  "kinder": []}})
    [v] = themenbaum.speicher.v.values()
    v.akte["teile"]["document"] = {"typ": "wlo.dokument-verweis@1", "version": 1,
                                   "zusammenfassung": "Alt.pdf",
                                   "wert": {"ref": "dokument:11111111-1111-4111-8111-111111111111",
                                            "name": "Alt.pdf"}}
    assert _wahlen(_starte(state, "themenbaum")) == {"neu", "ohne"}


# ── MINOR 12: die Verdrahtung im Muster-Weg (``respond``) ────────────────────────────────────────

def test_minor12_muster_weg_reicht_die_vorbelegung_und_raeumt_auf(monkeypatch):
    from boerdi.services import tool_loop_module
    from tests.test_respond_node import _ctx, _install, _Rec, _run, respond_mod

    ablauf = AblaufArea.model_validate({
        "id": "baum", "titel": {"de": "Baum"}, "aktiv": True, "schritte": [
            {"id": "umfang", "typ": "nachricht", "text": {"de": "Wie fein?"},
             "freitext": {"ziel": "k", "schreibt": "umfang"}},
            {"id": "k", "typ": "agent", "agent": {"werkzeuge": ["ui_strukturentwurf"],
                                                  "vorbelegen": True}},
            {"id": "e", "typ": "ende"}]})
    rec = _Rec()
    _install(monkeypatch, rec)
    ctx = _ctx()
    gesehen: dict = {}

    async def generate(session, **kw):
        gesehen["vorsatz"] = kw.get("vorsatz") or ""
        gesehen["merker"] = ctx.session_state.get(tool_loop_module.VORBELEGUNG_KEY)
        return ("ANTWORT", [], [], [])

    def lader(_session, _sid, _entities):
        async def teil(name):
            return {"umfang": "Kompakt (1 Ebene, etwa 6 Punkte)"}.get(name)
        return teil

    monkeypatch.setattr(respond_mod, "generate_response", generate)
    monkeypatch.setattr(respond_mod.ki_schritt, "fuer_zug",
                        lambda state, sid, safety: (ablauf, ablauf.schritte[1]))
    monkeypatch.setattr(respond_mod.arbeitsstand, "teil_lader", lader)
    monkeypatch.setattr(respond_mod.ki_schritt, "beantwortet", lambda state, sid: ["umfang"])
    _run(ctx)
    vorbelegung, werkzeuge_ = gesehen["merker"]
    assert vorbelegung == {"tiefe": 1, "anzahl_oben": 6}
    assert werkzeuge_ == frozenset({"ui_strukturentwurf"})
    assert "[VORBELEGT — " in gesehen["vorsatz"] and "tiefe=1" in gesehen["vorsatz"]
    # nur für diesen Zug: danach weg
    assert tool_loop_module.VORBELEGUNG_KEY not in ctx.session_state


def test_minor12_die_vorbelegung_erreicht_das_modul_im_muster_weg(monkeypatch):
    from boerdi.api.schemas_debug import ToolOutcome
    from boerdi.services import tool_loop_module
    from boerdi.ui_module.datenquelle import Ergebnis

    gesehen: dict = {}

    async def asynchron(name, args, modul_umgebung=None):
        gesehen["umgebung"] = modul_umgebung
        return Ergebnis(None, "t", ToolOutcome(tool=name, status="error", error="test"))

    monkeypatch.setattr(tool_loop_module, "asynchron", asynchron)
    state = {tool_loop_module.VORBELEGUNG_KEY: ({"tiefe": 3, "anzahl_oben": 12},
                                                frozenset({"ui_strukturentwurf"}))}
    asyncio.run(tool_loop_module._ergebnis(
        "ui_strukturentwurf", '{"thema": "Karate"}', ["ui_strukturentwurf"], state,
        tool_loop_module.Vorrunde(), [], [], 0, None))
    assert gesehen["umgebung"].vorbelegung == {"tiefe": 3, "anzahl_oben": 12}



# ── Befund 10: die Leiste aus den Halten des Laufs, im echten Zug ────────────────────────────────

def test_befund10_die_leiste_im_zug_zaehlt_die_halte(themenbaum):
    from boerdi.services.ablauf import fortschritt
    from tests.test_ablauf_zug import _wahl

    state: dict = {"entities": {}}
    antwort = _starte(state, "themenbaum")
    stand = fortschritt.stand(state["entities"], "person-a", "de")
    assert (stand["nr"], stand["status"]) == (1, "wartet_wahl")     # „bereit“ zählt nicht
    _wahl(antwort, state, "neu")
    stand = fortschritt.stand(state["entities"], "person-a", "de")
    assert stand["nr"] == 2 and stand["von"] >= 2
