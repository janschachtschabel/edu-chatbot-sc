"""Rückmeldung 16.11.: Die Führung als Ablauf hat dieselben Texte und Verzweigungen wie die
eingebaute Web-Tour (``seeds/01-base/website-tour.yaml``, ``domain/tour``).

Die Führung wird von ``scripts/fuehrung_aus_tour.py`` erzeugt; die Texte kommen aus
``domain/tour.render``. Diese Tests halten Seed und Tour gleich und prüfen die Verzweigungen gegen
die Tour selbst (``detect_entry``, ``expected``, ``match_group``).
"""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib

import pytest
import yaml

from boerdi.domain import seiten_muster, tour
from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.domain.tour_i18n import localize

_BACKEND = pathlib.Path(__file__).parents[1]
_spec = importlib.util.spec_from_file_location(
    "fuehrung_aus_tour", _BACKEND / "scripts" / "fuehrung_aus_tour.py")
erzeuger = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(erzeuger)

CFG = erzeuger.tour_config()
ROH = yaml.safe_load((_BACKEND / "seeds" / "06-ablaeufe" / "fuehrung.yaml")
                     .read_text(encoding="utf-8"))
ABLAUF = AblaufArea.model_validate(ROH)
SCHRITT = {s.id: s for s in ABLAUF.schritte}
GRUPPEN = [g["id"] for g in CFG["groups"]]


def test_der_seed_ist_der_frisch_erzeugte_stand():
    """Wer die Tour oder den Erzeuger ändert, muss das Skript laufen lassen."""
    assert ROH == erzeuger.erzeugen(CFG)


@pytest.mark.parametrize("seite", [
    *sorted(erzeuger.einstiege(CFG)), "/", "/impressum/", "/mitmachen", "/mitmachen/kontakt/",
    "/home/oer-community/?x=1", "/angebote/unbekannt/"])
def test_der_einstieg_folgt_detect_entry(seite):
    schritt, gruppe = tour.detect_entry(seite, CFG)
    erwartet = {"group": "gruppe", "contact": "kontakt", "intro": "intro"}.get(
        schritt, f"einstieg_{erzeuger.sid(gruppe)}")
    ziel = next(r.dann or r.sonst for r in SCHRITT["wo"].weiter
                if r.sonst or seiten_muster.passt(seite, r.wenn_seite or []))
    assert ziel == erwartet


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_gruppenwahl_mit_denselben_chips_und_hilfetexten(sprache):
    gruppe = tour.render("group", localize(CFG, sprache))
    unsicher = tour.render("group", localize(CFG, sprache), kind="unsure")
    s = SCHRITT["gruppe"]
    chips = [o.label[sprache] for o in s.optionen] + [t.label[sprache] for t in s.text_antworten]
    assert chips == gruppe["quick_replies"]
    assert s.text[sprache] == gruppe["text"]
    assert s.kein_treffer[sprache] == unsicher["text"]
    # Plan 2026-11-20, G2a: „Bin mir nicht sicher“ ist in der Tour ein Fehlversuch, keine Wahl —
    # ein Chip, der wie getippt zählt; einen eigenen Schritt dafür gibt es nicht mehr
    assert "unsicher" not in SCHRITT


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_ein_chip_trifft_in_der_tour_seine_eigene_gruppe(sprache):
    """Der Ablauf nimmt zuerst die genau getroffene Beschriftung, die Tour die erste Gruppe mit
    einem Treffer — gleich, solange keine Beschriftung ein Synonym einer früheren Gruppe enthält."""
    cfg = localize(CFG, sprache)
    for g in cfg["groups"]:
        assert tour.match_group(g["label"], cfg)["id"] == g["id"]


def test_review_g2_7_der_tour_chip_der_begruessung_startet_die_fuehrung():
    assert ABLAUF.tour_chip is True


def test_synonyme_wie_in_der_tour():
    for g in CFG["groups"]:
        option = next(o for o in SCHRITT["gruppe"].optionen if o.id == erzeuger.sid(g["id"]))
        assert option.synonyme == list(dict.fromkeys(g["synonyms"]))


@pytest.mark.parametrize("gruppe", GRUPPEN)
def test_ankunft_und_umschau_wie_in_der_tour(gruppe):
    sid = erzeuger.sid(gruppe)
    adv, _, _ = tour.expected("group_page", gruppe, CFG)
    assert SCHRITT[f"seite_{sid}"].ankunft == [adv]
    adv, umschau, _ = tour.expected("solutions", gruppe, CFG)
    for halt in (f"loesungen_{sid}", f"einstieg_{sid}"):
        if halt in SCHRITT:
            assert SCHRITT[halt].ankunft == [adv]
            assert set(SCHRITT[halt].umsehen.muster) == set(umschau)


@pytest.mark.parametrize("gruppe", GRUPPEN)
@pytest.mark.parametrize("sprache", ["de", "en"])
def test_texte_wie_in_der_tour(gruppe, sprache):
    cfg = localize(CFG, sprache)
    sid = erzeuger.sid(gruppe)
    for halt, schritt, art in ((f"seite_{sid}", "group_page", "normal"),
                               (f"loesungen_{sid}", "solutions", "normal"),
                               (f"einstieg_{sid}", "solutions", "entry")):
        if halt not in SCHRITT:
            continue
        r = tour.render(schritt, cfg, gruppe, kind=art)
        _, label, url = r["quick_replies"][0].split("|")
        s = SCHRITT[halt]
        assert (s.text[sprache], s.label[sprache], s.url) == (r["text"], label, url)
        assert s.abweichung[sprache] == tour.render(schritt, cfg, gruppe, kind="nudge")["text"]
        if s.umsehen:
            assert s.umsehen.text[sprache] == tour.render(schritt, cfg, gruppe,
                                                          kind="explore")["text"]
        # Review G2 (MINOR 3): auf eine Wendung hin rendert die Tour den Schritt neu (``normal``)
        erneut = (s.text_erneut or s.text)[sprache]
        assert erneut == tour.render(schritt, cfg, gruppe)["text"]
    label = next(o.label[sprache] for o in SCHRITT["gruppe"].optionen if o.id == sid)
    inhalte = SCHRITT["inhalte"].text[sprache].replace("{wahl.gruppe}", label)
    assert inhalte == tour.render("content", cfg, gruppe)["text"]


@pytest.mark.parametrize("sprache", ["de", "en"])
def test_intro_und_kontakt_wie_in_der_tour(sprache):
    cfg = localize(CFG, sprache)
    assert SCHRITT["intro"].text[sprache] == tour.render("intro", cfg)["text"]
    assert SCHRITT["kontakt"].text[sprache] == tour.render("contact", cfg)["text"]


def test_jede_gruppe_kommt_wie_in_der_tour_zu_ihrer_seite_und_ihren_loesungen():
    for regel, ziel in (("zur_gruppenseite", "seite_"), ("zu_loesungen", "loesungen_")):
        wege = {r.wenn_gewaehlt: r.dann for r in SCHRITT[regel].weiter if r.wenn_gewaehlt}
        assert wege == {erzeuger.sid(g): ziel + erzeuger.sid(g) for g in GRUPPEN}


# ── Review 16.11.: über die echte Engine ───────────────────────────────────────────────────────

_SAETZE = ["Lehrkraft", "Ich bin Lehrer", "Lehrerin an einer Grundschule", "hallo boerdi",
           "Impressum", "Espresso bitte", "Teachers", "Parents", "Developers and teachers",
           "ich entwickle software", "Wir sind ein Verlag", "für mein Kind", "Ministerium",
           "keine Ahnung", "Press", "I'm a journalist", "OER community", "Policy makers"]


@pytest.mark.parametrize("sprache", ["de", "en"])
@pytest.mark.parametrize("satz", _SAETZE)
def test_getippte_gruppe_trifft_wie_in_der_tour(sprache, satz):
    """m1: der Teilwort-Treffer sieht nur die Beschriftung der Zugsprache — wie die Tour."""
    from boerdi.services.ablauf import treiber

    tour_gruppe = tour.match_group(satz, localize(CFG, sprache))
    erwartet = erzeuger.sid(tour_gruppe["id"]) if tour_gruppe else None
    assert treiber.wahl_aus_text(SCHRITT["gruppe"], satz, sprache) == erwartet


@pytest.fixture
def fuehrung(umgebung):  # noqa: F811 — Fixture aus test_ablauf_zug
    from tests import test_ablauf_seite_zug as seite_test

    roh = {**ABLAUF.model_dump(exclude_none=True), "aktiv": True}
    return lambda seite="/": seite_test._starten(umgebung, roh, seite)


from tests.test_ablauf_zug import umgebung  # noqa: E402, F401 — Fixture


def _req(**mehr):
    from tests import test_ablauf_seite_zug as seite_test

    return seite_test._req(**mehr)


@pytest.mark.parametrize("seite", ["/impressum/", "/home/", "/home/redaktionen/",
                                   "/angebote/bildungs-api/", "/mitmachen/"])
def test_die_erste_nachricht_ist_die_der_tour(fuehrung, seite):
    schritt, gruppe = tour.detect_entry(seite, CFG)
    _zustand, antwort = fuehrung(seite)
    erwartet = tour.render(schritt, CFG, gruppe, kind="entry" if schritt == "solutions"
                           else "normal")
    assert antwort.content.strip() == erwartet["text"]


def test_ein_ausloeser_satz_zeigt_den_wartenden_schritt_erneut(fuehrung):
    """M1: wie die Tour (``wiederholen``) — vorher beendete ``endet_bei_text`` die Führung."""
    from boerdi.services.ablauf import seite_zug, treiber
    from tests.test_ablauf_seite_zug import _SID

    zustand, _ = fuehrung("/impressum/")
    assert seite_zug.wiederholt(_SID, zustand, "Kannst du die Tour starten? starte die tour")
    assert not seite_zug.wiederholt(_SID, zustand, "Was ist OER?")
    antwort = asyncio.run(seite_zug.wiederholen(_S(), _req(message="starte die tour"), zustand))
    intro = tour.render("intro", CFG)
    assert antwort.content == intro["text"]
    assert antwort.quick_replies == ["__fuehrung__|" + intro["quick_replies"][0].split("|", 1)[1]]
    stand = seite_zug.wartend(_SID, zustand)
    assert stand is not None and stand[0]["status"] == treiber.WARTET_SEITE


def test_der_erste_fehlversuch_zeigt_den_hilfetext_der_tour(fuehrung):
    from boerdi.services.ablauf import wahl_zug

    zustand, _ = fuehrung("/home/")
    antwort = asyncio.run(wahl_zug.getippt(_S(), _req(message="Impressum"), zustand))
    assert antwort.content == tour.render("group", CFG, kind="unsure")["text"]


@pytest.mark.parametrize(("seite", "art"), [("/impressum/", "nudge"),
                                            ("/fachportale/", "explore")])
def test_hinweis_und_umschau_wie_in_der_tour(fuehrung, seite, art):
    from tests.test_ablauf_seite_zug import _ping

    zustand, _ = fuehrung("/home/redaktionen/")       # Einstieg: wartet auf /mitmachen
    antwort = _ping(zustand, seite)
    assert antwort.content == tour.render("solutions", CFG, "redaktionen", kind=art)["text"]


def _S():
    from tests.test_ablauf_zug import _S as sitzung

    return sitzung()


def test_die_leiste_springt_nach_der_gruppenwahl_nicht():
    """m5: auf „Schritt n“ der Gruppenwahl folgt „Schritt n+1“ (der Hilfetext steht seit G2a am
    Schritt selbst, ``kein_treffer``)."""
    from boerdi.services.ablauf import fortschritt

    n, m = fortschritt.position(ABLAUF, "gruppe")
    assert fortschritt.position(ABLAUF, "seite_lehrkraft") == (n + 1, m)
