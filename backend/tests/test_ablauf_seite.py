"""AS-7a (Plan 2026-11-09 §5m): Führungen — Schritt ``seite``, Bedingung ``wenn_seite``, Auslöser
``seite`` (Modell und Prüfung), Ankunft per Seiten-Ping.

F-1: ``seite`` zeigt einen Navigations-Chip; mit ``ankunft`` wartet der Lauf (``wartet_seite``),
bis die Person auf einer passenden Seite ist. F-3: Muster mit ``*``, ohne reguläre Ausdrücke.
F-6: ``wenn_seite`` prüft die Seite des Zuges.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.domain import seiten_muster
from boerdi.domain.config_models.ablauf import AblaufArea, AblaufTest
from boerdi.services.ablauf import simulation, treiber
from boerdi.services.ablauf.pruefung import nachfolger, pruefe

_HIN = {"id": "hin", "typ": "seite", "text": {"de": "Schau dir die Mitmach-Seite an."},
        "url": "/mitmachen/", "label": {"de": "Zur Mitmach-Seite", "en": "To the page"},
        "ankunft": ["/mitmachen*"]}
_ENDE = {"id": "ende", "typ": "ende", "text": {"de": "Angekommen."}}


def _ablauf(*schritte, **mehr) -> AblaufArea:
    return AblaufArea.model_validate({"id": "fuehrung", "titel": {"de": "Führung"},
                                      "aktiv": True, "schritte": list(schritte or [_HIN, _ENDE]),
                                      **mehr})


def _umgebung(seite: str = "/", teile=None) -> treiber.Umgebung:
    teile = dict(teile or {})

    async def lader(name):
        return teile.get(name)

    return treiber.Umgebung(teile=lader, seite=seite)


# ── Muster (F-3) ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("seite", "muster", "passt"), [
    ("/mitmachen/", ["/mitmachen*"], True),
    ("https://wirlernenonline.de/mitmachen/?x=1#a", ["/mitmachen*"], True),
    ("/MITMACHEN", ["/mitmachen"], True),
    ("/home/", ["/mitmachen*"], False),
    ("/fach/physik/optik/", ["/fach/*/optik"], True),
    ("/", ["/"], True),
    ("", ["/"], True),
])
def test_muster_mit_stern_auf_dem_normalisierten_pfad(seite, muster, passt):
    assert seiten_muster.passt(seite, muster) is passt


@pytest.mark.parametrize("muster", ["mitmachen", "/a[b]", "/" + "x" * 200, "/a?b", ""])
def test_ungueltige_muster(muster):
    assert seiten_muster.fehler(muster)


def test_gueltige_muster():
    assert not seiten_muster.fehler("/fach/*/optik*")


# ── Modell und Prüfung (F-1, F-2) ──────────────────────────────────────────────────────────────

def test_ein_seiten_schritt_ist_gueltig_und_hat_einen_nachfolger():
    assert pruefe(_ablauf()) == []
    assert nachfolger(_ablauf(), 0) == ["ende"]


@pytest.mark.parametrize(("aenderung", "erwartet"), [
    ({"url": None}, "url"),
    ({"url": "javascript:alert(1)"}, "url"),
    ({"url": "http://example.org/"}, "url"),
    ({"url": "https://nutzer@example.org/"}, "url"),
    ({"label": None}, "label"),
    ({"label": {"en": "only english"}}, "label"),
    ({"ankunft": ["kein-pfad"]}, "Muster"),
    ({"ankunft": [f"/s{i}" for i in range(11)]}, "höchstens 10"),
])
def test_befunde_am_seiten_schritt(aenderung, erwartet):
    befunde = pruefe(_ablauf({**_HIN, **aenderung}, _ENDE))
    assert any(erwartet in b for b in befunde), befunde


def test_eine_https_adresse_ist_erlaubt():
    assert pruefe(_ablauf({**_HIN, "url": "https://wirlernenonline.de/mitmachen/"}, _ENDE)) == []


def test_ohne_neue_felder_bleibt_die_fassung_gleich():
    """Neue Felder mit Vorgabe ``None`` — die Fassung eines Ablaufs ohne sie ändert sich nicht."""
    roh = {"id": "a", "titel": {"de": "A"}, "schritte": [
        {"id": "x", "typ": "nachricht", "text": {"de": "x"}}, {"id": "e", "typ": "ende"}]}
    ablauf = AblaufArea.model_validate(roh)
    dump = ablauf.schritte[0].model_dump(mode="json", exclude_none=True)
    assert not {"url", "label", "ankunft"} & dump.keys()


def test_der_ausloeser_seite_braucht_muster():
    befunde = pruefe(_ablauf(ausloeser=[{"art": "seite"}]))
    assert any("Muster" in b for b in befunde), befunde
    assert pruefe(_ablauf(ausloeser=[{"art": "seite", "muster": ["/mitmachen*"]}])) == []


# ── Treiber (F-1, F-4) ─────────────────────────────────────────────────────────────────────────

def test_mit_ankunft_wartet_der_lauf_und_bietet_den_weg_an():
    aus = asyncio.run(treiber.starten(_ablauf(), _umgebung()))
    assert aus.lauf["status"] == treiber.WARTET_SEITE and aus.lauf["schritt"] == "hin"
    assert aus.texte == ["Schau dir die Mitmach-Seite an."]
    assert aus.navigation == [{"url": "/mitmachen/", "label": "Zur Mitmach-Seite"}]


def test_steht_die_person_schon_dort_geht_es_gleich_weiter():
    aus = asyncio.run(treiber.starten(_ablauf(), _umgebung("/mitmachen/")))
    assert aus.lauf["status"] == "fertig"


def test_ohne_ankunft_zeigt_der_schritt_den_weg_und_geht_weiter():
    schritt = {k: v for k, v in _HIN.items() if k != "ankunft"}
    aus = asyncio.run(treiber.starten(_ablauf(schritt, _ENDE), _umgebung()))
    assert aus.lauf["status"] == "fertig"
    assert aus.navigation == [{"url": "/mitmachen/", "label": "Zur Mitmach-Seite"}]
    assert aus.texte == ["Schau dir die Mitmach-Seite an.", "Angekommen."]


def test_die_ankunft_setzt_fort_eine_andere_seite_nicht():
    ablauf = _ablauf()
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    assert asyncio.run(treiber.weiter_seite(ablauf, dict(lauf), _umgebung("/home/"))) is None
    aus = asyncio.run(treiber.weiter_seite(ablauf, dict(lauf), _umgebung("/mitmachen/x")))
    assert aus is not None and aus.lauf["status"] == "fertig" and aus.texte == ["Angekommen."]


def test_ankunft_nur_am_wartenden_seiten_schritt_und_in_derselben_fassung():
    ablauf = _ablauf()
    lauf = asyncio.run(treiber.starten(ablauf, _umgebung())).lauf
    anders = {**lauf, "status": treiber.WARTET_WAHL}
    assert asyncio.run(treiber.weiter_seite(ablauf, anders, _umgebung("/mitmachen/"))) is None
    alt = {**lauf, "fassung": "veraltet"}
    assert asyncio.run(treiber.weiter_seite(ablauf, alt, _umgebung("/mitmachen/"))) is None


def test_die_sprache_waehlt_das_label():
    aus = asyncio.run(treiber.starten(_ablauf(), treiber.Umgebung(
        teile=_umgebung().teile, sprache="en")))
    assert aus.navigation[0]["label"] == "To the page"


# ── wenn_seite (F-6) ───────────────────────────────────────────────────────────────────────────

_VERZWEIGUNG = {"id": "wo", "typ": "verzweigung", "weiter": [
    {"wenn_seite": ["/fach/*"], "dann": "fach"}, {"sonst": "sonst"}]}
_FACH = {"id": "fach", "typ": "ende", "text": {"de": "Fach."}}
_SONST = {"id": "sonst", "typ": "ende", "text": {"de": "Sonst."}}


@pytest.mark.parametrize(("seite", "ende"), [("/fach/physik/", "fach"), ("/home/", "sonst")])
def test_wenn_seite_verzweigt_nach_der_seite_des_zuges(seite, ende):
    aus = asyncio.run(treiber.starten(_ablauf(_VERZWEIGUNG, _FACH, _SONST), _umgebung(seite)))
    assert aus.lauf["schritt"] == ende


def test_wenn_seite_mit_ungueltigem_muster_ist_ein_befund():
    regel = {"id": "wo", "typ": "verzweigung", "weiter": [
        {"wenn_seite": ["fach"], "dann": "fach"}, {"sonst": "sonst"}]}
    befunde = pruefe(_ablauf(regel, _FACH, _SONST))
    assert any("Muster" in b for b in befunde), befunde


# ── Simulation ─────────────────────────────────────────────────────────────────────────────────

def test_die_simulation_kennt_die_seite_als_eingabe_und_startseite():
    test = AblaufTest.model_validate({"name": "führt", "eingaben": [
        {"bei": "hin", "seite": "/mitmachen/"}],
        "erwartet": {"weg": ["hin", "ende"], "status": "fertig"}})
    ergebnis = asyncio.run(simulation.testen(_ablauf(), test))
    assert ergebnis.ok, ergebnis.abweichungen
    wartet = AblaufTest.model_validate({"name": "wartet",
                                        "erwartet": {"status": "wartet_seite", "ende": "hin"}})
    assert asyncio.run(simulation.testen(_ablauf(), wartet)).ok
    start = AblaufTest.model_validate({"name": "schon da", "seite": "/fach/physik",
                                       "erwartet": {"weg": ["wo", "fach"]}})
    assert asyncio.run(simulation.testen(_ablauf(_VERZWEIGUNG, _FACH, _SONST), start)).ok


# ── Review AS-7a ───────────────────────────────────────────────────────────────────────────────

def test_review_1_kein_redos_der_vergleich_ist_linear():
    """Befund 1 (kritisch): ``.*`` im rückverfolgenden ``re`` brauchte für ``/*a*a*a*b`` gegen eine
    lange, fast passende Seite O(n^k) — die Seite schickt der Client."""
    import time

    seite = "/" + "a" * 50_000
    beginn = time.perf_counter()
    assert not seiten_muster.passt(seite, ["/*a*a*a*b", "/*a*a*a*a*a*b"])
    assert time.perf_counter() - beginn < 0.5


@pytest.mark.parametrize(("seite", "muster", "passt"), [
    ("/a/b/c", "/*/b/*", True),
    ("/a/b/c", "/*/c/*", False),
    ("/abc", "/a*c", True),
    ("/ac", "/a*c", True),
    ("/a", "/a*a", False),
    ("/aa", "/a*a", True),
    ("/fach/x/thema/y/start", "/fach/*/thema/*/start", True),
    ("/fach/x/thema/y/stop", "/fach/*/thema/*/start", False),
    ("/x", "*", False),            # ungültig (beginnt nicht mit /) — passt nie
    ("/x/y", "/*", True),
])
def test_review_1_der_lineare_vergleich_stimmt(seite, muster, passt):
    assert seiten_muster.passt(seite, [muster]) is passt


def test_review_1_eine_sehr_lange_seite_wird_gekappt():
    assert len(seiten_muster.normalisiert("/" + "x" * 10_000)) <= seiten_muster.MAX_SEITE


def test_review_2_der_wartende_status_steht_in_der_gemeinsamen_liste():
    assert treiber.WARTET_SEITE in treiber.WARTEND


def test_review_4_ein_kreis_ueber_einen_seiten_schritt_ist_ein_befund():
    """Befund 4: steht die Person schon dort, läuft der Schritt durch — kein Halt."""
    zurueck = {"id": "n", "typ": "nachricht", "text": {"de": "n"}, "weiter": "hin"}
    befunde = pruefe(_ablauf({**_HIN, "weiter": "n"}, zurueck, _ENDE))
    assert befunde, befunde


@pytest.mark.parametrize("url", ["//evil.example", r"/\evil.example", "/a b", "/a|b", "/a\tb",
                                 "/a\u0000b", "https://ex\ample.org/"])
def test_review_5_weitere_urls_werden_abgewiesen(url):
    befunde = pruefe(_ablauf({**_HIN, "url": url}, _ENDE))
    assert any("url" in b for b in befunde), (url, befunde)


def test_review_5_die_url_wird_getrimmt():
    ablauf = _ablauf({**_HIN, "url": "  /mitmachen/  "}, _ENDE)
    assert ablauf.schritte[0].url == "/mitmachen/" and pruefe(ablauf) == []


def test_review_6_ein_seiten_schritt_braucht_text():
    befunde = pruefe(_ablauf({k: v for k, v in _HIN.items() if k != "text"}, _ENDE))
    assert any("Text" in b for b in befunde), befunde


def test_review_7_eine_leere_musterliste_ist_keine_bedingung():
    regel = {"id": "wo", "typ": "verzweigung", "weiter": [
        {"wenn_seite": [], "dann": "fach"}, {"sonst": "sonst"}]}
    ablauf = _ablauf(regel, _FACH, _SONST)
    assert ablauf.schritte[0].weiter[0].wenn_seite is None
    assert pruefe(ablauf), "eine Regel ohne Bedingung ist ein Befund"


def test_review_9_zwei_seiten_schritte_in_einem_zug_zeigen_beide_wege():
    erster = {k: v for k, v in _HIN.items() if k != "ankunft"}
    zweiter = {**erster, "id": "hin2", "url": "/home/", "label": {"de": "Nach Hause"}}
    aus = asyncio.run(treiber.starten(_ablauf(erster, zweiter, _ENDE), _umgebung()))
    assert [n["url"] for n in aus.navigation] == ["/mitmachen/", "/home/"]


# ── Zweites Review AS-7a ───────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("seite", "muster", "passt"), [
    ("/mitmachen/", "/mitmachen/*", True),     # der Stamm selbst (Befund 1)
    ("/mitmachen", "/mitmachen/*", True),
    ("/mitmachen/a", "/mitmachen/*", True),
    ("/mitmachen-xyz", "/mitmachen/*", False),
    ("/fach/", "/fach/*", True),
    ("/", "/*", True),
])
def test_zweites_review_1_ein_muster_auf_slash_stern_passt_auch_auf_den_stamm(seite, muster, passt):
    assert seiten_muster.passt(seite, [muster]) is passt


def test_zweites_review_1_eine_url_die_ihre_ankunft_nie_erreicht_ist_ein_befund():
    befunde = pruefe(_ablauf({**_HIN, "ankunft": ["/anderswo*"]}, _ENDE))
    assert any("ankunft" in b.lower() for b in befunde), befunde
    assert pruefe(_ablauf({**_HIN, "ankunft": ["/mitmachen/*"]}, _ENDE)) == []
    https = {**_HIN, "url": "https://wirlernenonline.de/mitmachen/", "ankunft": ["/mitmachen/*"]}
    assert pruefe(_ablauf(https, _ENDE)) == []


# ── AS-7c: Beispiel-Ablauf „Führung“ (F-8) ─────────────────────────────────────────────────────

def test_as7c_das_beispiel_fuehrung_besteht_pruefung_und_eigene_tests():
    import pathlib

    import yaml

    roh = yaml.safe_load((pathlib.Path(__file__).parents[1] / "seeds" / "06-ablaeufe"
                          / "fuehrung.yaml").read_text(encoding="utf-8"))
    ablauf = AblaufArea.model_validate(roh)
    assert not ablauf.aktiv                      # aus, bis die Redaktion ihn einschaltet
    assert pruefe(ablauf) == []
    ergebnisse = asyncio.run(simulation.alle(ablauf))
    assert ergebnisse and all(e.ok for e in ergebnisse), [e.abweichungen for e in ergebnisse]


def test_review_as7b_1_ein_text_nur_aus_leerraum_zaehlt_nicht():
    """Review AS-7b, Befund 1: der Ping verlässt sich darauf, dass ein ``seite``-Schritt
    Inhalt hat."""
    befunde = pruefe(_ablauf({**_HIN, "text": {"de": "   "}}, _ENDE))
    assert any("Text" in b for b in befunde), befunde


# ── Querschnitts-Review AS-7 ───────────────────────────────────────────────────────────────────

def test_quer_6_gruende_ungueltiger_muster_auf_englisch():
    befunde = pruefe(_ablauf({**_HIN, "ankunft": ["kein-pfad"]}, _ENDE), lang="en")
    assert any("does not start with /" in b for b in befunde), befunde
    assert not any("beginnt" in b for b in befunde), befunde


def test_quer_9_ein_komma_ist_kein_zeichen_eines_musters():
    """Befund 9: der Regel-Editor trennt an Kommas — ein Muster mit Komma würde still geteilt."""
    assert seiten_muster.fehler("/a,b")
