"""Paket R1 (Plan 2026-11-12, R-E13/R-E14): ein Auftrag in Teilen und die Sprache der Person.

- ``aufteilen: {argument, hoechstens}`` am Schritt ``auftrag``: eine längere Liste geht in
  Teilaufträgen an die B-API, **nacheinander** (je „Stand prüfen“ der nächste) — höchstens
  :data:`auftrag_teile.MAX_TEILE` Teile, sonst werden die Teile größer (nichts fällt weg).
- Ein gescheiterter Teil hält die anderen nicht auf (Teilerfolg wie ``warnungen``); nur wenn alle
  scheitern, geht der Lauf zu ``bei_fehler``.
- ``{"$sprache": true}`` als Argument: die Sprache der Person (``de``/``en``).
"""

from __future__ import annotations

import asyncio
import copy

import pytest

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import auftrag_teile, treiber
from boerdi.services.ablauf.pruefung import pruefe
from boerdi.settings import get_settings

_ABLAGE = {"inhalte": [{"node_id": f"n{i}", "stand": "stored"} for i in range(5)]}
_SCHRITTE = [
    {"id": "meta", "typ": "auftrag", "flow": "wlo/meta", "schreibt": "lauf",
     "argumente": {"node_ids": {"$teil": "ablage", "liste": "inhalte", "feld": "node_id"},
                   "language": {"$sprache": True}},
     "aufteilen": {"argument": "node_ids", "hoechstens": 2},
     "bei_fehler": "schade", "text": {"de": "Ich lasse die Metadaten erzeugen."}},
    {"id": "fertig", "typ": "ende", "text": {"de": "Fertig."}},
    {"id": "schade", "typ": "ende", "text": {"de": "Nicht geklappt."}},
]


def _ablauf(**schritt):
    schritte = copy.deepcopy(_SCHRITTE)
    schritte[0].update(schritt)
    return AblaufArea.model_validate({
        "id": "meta", "titel": {"de": "Meta"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "voraussetzungen": ["anmeldung"], "schritte": schritte})


def _umgebung(sprache="de", jobs=None):
    gestartet: list = []
    jobs = list(jobs) if jobs is not None else None

    async def lader(name):
        return {"ablage": _ABLAGE}.get(name)

    async def starte(flow, args):
        gestartet.append(args)
        return jobs.pop(0) if jobs is not None else f"job-{len(gestartet)}"

    return treiber.Umgebung(teile=lader, auftrag_starten=starte, sprache=sprache), gestartet


@pytest.fixture
def freigeschaltet(monkeypatch):
    monkeypatch.setenv("B_API_JOBS_START_PATH", "/api/v1/jobs/flows/{flow}")
    monkeypatch.setenv("B_API_JOBS_FLOWS", "wlo/meta")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ── Teilen ──────────────────────────────────────────────────────────────────────────────────

def test_teilen_schneidet_die_liste_in_stuecke():
    args = {"node_ids": list("abcdefg"), "language": "de"}
    teile = auftrag_teile.teilen(args, "node_ids", 3)
    assert [t["node_ids"] for t in teile] == [list("abc"), list("def"), ["g"]]
    assert all(t["language"] == "de" for t in teile)


def test_eine_kurze_liste_bleibt_ein_auftrag():
    args = {"node_ids": ["a", "b"]}
    assert auftrag_teile.teilen(args, "node_ids", 2) == [args]
    assert auftrag_teile.teilen({"x": 1}, "node_ids", 2) == [{"x": 1}]


def test_hoechstens_max_teile_teilauftraege_nichts_faellt_weg():
    ids = [str(i) for i in range(200)]
    teile = auftrag_teile.teilen({"node_ids": ids}, "node_ids", 1)
    assert len(teile) == auftrag_teile.MAX_TEILE
    assert [x for t in teile for x in t["node_ids"]] == ids


# ── Prüfung ─────────────────────────────────────────────────────────────────────────────────

def test_ein_gueltiges_aufteilen(freigeschaltet):
    assert pruefe(_ablauf()) == []


@pytest.mark.parametrize(("aenderung", "erwartet"), [
    ({"aufteilen": {"argument": "fehlt", "hoechstens": 2}}, "aufteilen"),
    ({"dateien_holen": ["bericht"]}, "aufteilen"),
])
def test_befunde_am_aufteilen(freigeschaltet, aenderung, erwartet):
    befunde = pruefe(_ablauf(**aenderung))
    assert any(erwartet in b for b in befunde), befunde


def test_hoechstens_ist_begrenzt():
    with pytest.raises(ValueError):
        _ablauf(aufteilen={"argument": "node_ids", "hoechstens": 0})
    with pytest.raises(ValueError):
        _ablauf(aufteilen={"argument": "node_ids", "hoechstens": 201})


def test_aufteilen_aendert_die_fassung_eines_ablaufs_ohne_aufteilen_nicht():
    ohne = copy.deepcopy(_SCHRITTE)
    del ohne[0]["aufteilen"]
    roh = {"id": "m", "titel": {"de": "M"}, "ausloeser": [{"art": "knopf"}], "schritte": ohne}
    a = AblaufArea.model_validate(roh)
    assert "aufteilen" not in a.schritte[0].model_dump(mode="json", exclude_none=True)


# ── Treiber ─────────────────────────────────────────────────────────────────────────────────

def test_teilauftraege_laufen_nacheinander_und_werden_ein_teil():
    ablauf = _ablauf()
    umgebung, gestartet = _umgebung()
    aus = asyncio.run(treiber.starten(ablauf, umgebung))
    assert [a["node_ids"] for a in gestartet] == [["n0", "n1"]]
    assert aus.lauf["status"] == treiber.WARTET_AUFTRAG and aus.auftrag["job_id"] == "job-1"
    stapel = aus.lauf["auftrag_teile"]
    assert (stapel["n"], stapel["i"], stapel["ergebnisse"]) == (3, 0, [])
    assert stapel["args"]["node_ids"] == [f"n{i}" for i in range(5)]
    assert aus.texte == ["Ich lasse die Metadaten erzeugen.", "Das geht in 3 Teilen, einer nach "
                         "dem anderen."]

    lauf = aus.lauf
    zweiter = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, {"outputs": {"a": 1}}, umgebung))
    assert [a["node_ids"] for a in gestartet][1] == ["n2", "n3"]
    assert zweiter.lauf["status"] == treiber.WARTET_AUFTRAG
    assert zweiter.auftrag == {"flow": "wlo/meta", "job_id": "job-2", "schritt": "meta"}
    assert zweiter.lauf["auftrag_teile"]["i"] == 1 and zweiter.neue_teile == []
    assert zweiter.texte and "2" in zweiter.texte[0] and "3" in zweiter.texte[0]

    dritter = asyncio.run(treiber.weiter_auftrag(ablauf, zweiter.lauf, {"outputs": {"a": 2}},
                                                 umgebung))
    assert [a["node_ids"] for a in gestartet][2] == ["n4"]
    letzter = asyncio.run(treiber.weiter_auftrag(ablauf, dritter.lauf,
                                                 {"outputs": {"a": 3}, "warnungen": True},
                                                 umgebung))
    assert letzter.lauf["status"] == "fertig" and letzter.texte == ["Fertig."]
    assert "auftrag_teile" not in letzter.lauf
    [(name, _typ, wert, _z)] = letzter.neue_teile
    assert name == "lauf" and wert["teile"] == 3
    assert wert["outputs"] == {"a": 3} and wert["warnungen"] is True


def test_ein_gescheiterter_teil_haelt_die_anderen_nicht_auf():
    ablauf = _ablauf()
    umgebung, _ = _umgebung()
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    zwei = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, None, umgebung))
    assert zwei.lauf["status"] == treiber.WARTET_AUFTRAG
    assert "nicht geklappt" in zwei.texte[0]                         # Review R1, NIT 8
    drei = asyncio.run(treiber.weiter_auftrag(ablauf, zwei.lauf, {"outputs": {"a": 2}}, umgebung))
    ende = asyncio.run(treiber.weiter_auftrag(ablauf, drei.lauf, {"outputs": {"a": 3}}, umgebung))
    [(_n, _t, wert, _z)] = ende.neue_teile
    assert wert["gescheitert"] == 1 and wert["warnungen"] is True
    assert wert["outputs"] == {"a": 3}


def test_scheitern_alle_teile_geht_der_lauf_zu_bei_fehler():
    ablauf = _ablauf()
    umgebung, _ = _umgebung()
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    for _ in range(2):
        lauf = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, None, umgebung)).lauf
    ende = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, None, umgebung))
    assert ende.texte == ["Nicht geklappt."] and ende.neue_teile == []


def test_startet_der_naechste_teil_nicht_endet_der_auftrag_mit_dem_bisherigen():
    ablauf = _ablauf()
    umgebung, _ = _umgebung(jobs=["job-1", None])
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    aus = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, {"outputs": {"a": 1}}, umgebung))
    assert aus.lauf["status"] == "fertig" and aus.auftrag is None
    [(_n, _t, wert, _z)] = aus.neue_teile
    assert wert["outputs"] == {"a": 1} and wert["gescheitert"] == 2


def test_ohne_aufteilen_bleibt_das_ergebnis_wie_bisher():
    ablauf = _ablauf(aufteilen=None)
    umgebung, gestartet = _umgebung()
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    assert len(gestartet[0]["node_ids"]) == 5 and "auftrag_teile" not in lauf
    ergebnis = {"outputs": {"a": 1}, "dateien": []}
    aus = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, ergebnis, umgebung))
    assert aus.neue_teile[0][2] == ergebnis


# ── Sprache der Person ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("sprache", ["de", "en"])
def test_die_sprache_der_person_geht_an_den_flow(sprache):
    umgebung, gestartet = _umgebung(sprache=sprache)
    asyncio.run(treiber.starten(_ablauf(), umgebung))
    assert gestartet[0]["language"] == sprache


def test_der_seed_aus_inhalten_nutzt_die_sprache_und_teilt_auf():
    import pathlib

    import yaml

    pfad = (pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
            / "themenbaum_aus_inhalten.yaml")
    ablauf = AblaufArea.model_validate(yaml.safe_load(pfad.read_text(encoding="utf-8")))
    meta = next(s for s in ablauf.schritte if s.id == "metadaten")
    assert meta.argumente["language"] == {"$sprache": True}
    assert meta.aufteilen is not None and meta.aufteilen.argument == "node_ids"


# ── Review R1 ───────────────────────────────────────────────────────────────────────────────

def test_review_1_die_argumente_sind_eingefroren(monkeypatch):
    """Befund 1: ändert sich die Ablage während des Wartens, bleibt der Schnitt derselbe — kein
    ID fällt weg, keine geht doppelt an den (schreibenden) Flow."""
    ablauf = _ablauf()
    umgebung, gestartet = _umgebung()
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    _ABLAGE_NEU = {"inhalte": [{"node_id": "x"}, *_ABLAGE["inhalte"]]}

    async def anders(name):
        return {"ablage": _ABLAGE_NEU}.get(name)

    umgebung = treiber.Umgebung(teile=anders, auftrag_starten=umgebung.auftrag_starten,
                                sprache="en")
    for _ in range(2):
        lauf = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, {"outputs": {}}, umgebung)).lauf
    assert [a["node_ids"] for a in gestartet] == [["n0", "n1"], ["n2", "n3"], ["n4"]]
    assert {a["language"] for a in gestartet} == {"de"}


def test_review_3_der_stapel_im_lauf_ist_gedeckelt(monkeypatch):
    monkeypatch.setattr(auftrag_teile, "MAX_STAPEL_BYTES", 30)
    ablauf = _ablauf()
    umgebung, _ = _umgebung()
    lauf = asyncio.run(treiber.starten(ablauf, umgebung)).lauf
    gross = {"outputs": {"text": "x" * 100}}
    for erg in ({"outputs": {"a": [1]}}, gross):
        lauf = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, erg, umgebung)).lauf
    assert lauf["auftrag_teile"]["gekuerzt"] == 1 and len(lauf["auftrag_teile"]["ergebnisse"]) == 1
    ende = asyncio.run(treiber.weiter_auftrag(ablauf, lauf, {"outputs": {"a": [2]}}, umgebung))
    [(_n, _t, wert, _z)] = ende.neue_teile
    assert wert["gekuerzt"] == 1 and wert["warnungen"] is True


def test_review_3_zu_grosse_argumente_teilen_nicht(monkeypatch):
    monkeypatch.setattr(auftrag_teile, "MAX_ARGS_BYTES", 10)
    umgebung, gestartet = _umgebung()
    aus = asyncio.run(treiber.starten(_ablauf(), umgebung))
    assert gestartet == [] and aus.texte[-1] == "Nicht geklappt."


def test_review_4_listen_gleicher_schluessel_haengen_aneinander():
    stapel = auftrag_teile.neuer_stapel({"node_ids": ["a"]}, 2)
    for out in ({"report": [{"id": "a"}], "status": "ok"},
                {"report": [{"id": "b"}], "status": "teil"}):
        stapel = auftrag_teile.mit_ergebnis(stapel, {"outputs": out})
    gesamt = auftrag_teile.zusammenfuehren(stapel)
    assert gesamt["outputs"] == {"report": [{"id": "a"}, {"id": "b"}], "status": "teil"}


@pytest.mark.parametrize("argumente", [
    {"node_ids": {"$teil": "ablage"}, "tief": {"language": {"$sprache": True}}},
    {"node_ids": {"$teil": "ablage"}, "language": {"$sprache": False}},
])
def test_review_5_sprache_nur_oben_am_auftrag(freigeschaltet, argumente):
    befunde = pruefe(_ablauf(argumente=argumente))
    assert any("$sprache" in b for b in befunde), befunde


def test_review_5_sprache_nicht_am_werkzeug():
    ablauf = AblaufArea.model_validate({
        "id": "w", "titel": {"de": "W"}, "ausloeser": [{"art": "knopf"}],
        "schritte": [{"id": "w", "typ": "werkzeug", "werkzeug": "search_wlo_all",
                      "argumente": {"language": {"$sprache": True}}, "schreibt": "x"},
                     {"id": "e", "typ": "ende"}]})
    assert any("$sprache" in b for b in pruefe(ablauf))


def test_review_10_aufteilen_braucht_eine_liste(freigeschaltet):
    befunde = pruefe(_ablauf(argumente={"node_ids": "fest", "language": "de"}))
    assert any("Liste" in b for b in befunde), befunde
