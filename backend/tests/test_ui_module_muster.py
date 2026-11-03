"""Paket U1-c1: der Muster-Schlüssel ``ui_module`` — welche abgeleiteten Module ein Muster zeigt.

Wie bei ``rag_areas``: fehlt der Schlüssel, gelten alle (heutiges Verhalten), ``[]`` heißt
keine. Nur Namen abgeleiteter Module sind erlaubt; das Studio verliert den Schlüssel beim
Speichern nicht.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.api import publikum
from boerdi.api.config_element_models import PatternEntry
from boerdi.api.config_elements import _pattern_frontmatter
from boerdi.api.schemas import ChatResponse, DebugInfo, WebLink
from boerdi.domain.config_models.patterns import PatternFrontmatter
from boerdi.ui_module import abgeleitet


@pytest.mark.parametrize("wert", [None, [], ["ui_linkbox"]])
def test_das_frontmatter_nimmt_abgeleitete_module(wert):
    assert PatternFrontmatter(id="M05", ui_module=wert).ui_module == wert


def test_ein_unbekannter_modulname_wird_abgewiesen():
    with pytest.raises(ValidationError, match="ui_quatsch"):
        PatternFrontmatter(id="M05", ui_module=["ui_quatsch"])


def test_ein_geliefertes_modul_ist_kein_abgeleitetes():
    """Der Inhaltsrahmen entsteht aus einem Werkzeugaufruf, nicht aus der Antwort."""
    with pytest.raises(ValidationError, match="ui_inhaltsrahmen"):
        PatternFrontmatter(id="M05", ui_module=["ui_inhaltsrahmen"])


@pytest.fixture
def muster(monkeypatch):
    def setze(*defs):
        monkeypatch.setattr("boerdi.services.config_loader.load_pattern_definitions",
                            lambda: list(defs))
    return setze


def test_erlaubte_module_je_muster(muster):
    muster({"id": "M05", "ui_module": []}, {"id": "M06", "ui_module": ["ui_linkbox"]},
           {"id": "M07"})
    assert abgeleitet.erlaubte_module("M05") == frozenset()
    assert abgeleitet.erlaubte_module("M06") == frozenset({"ui_linkbox"})
    assert abgeleitet.erlaubte_module("M07") is None          # ohne Schlüssel: alle
    assert abgeleitet.erlaubte_module("AGENT") is None        # kein Muster: alle
    assert abgeleitet.erlaubte_module("") is None


def test_ein_muster_mit_leerer_liste_zeigt_keine_linkbox(muster):
    muster({"id": "M05", "ui_module": []})
    resp = ChatResponse(session_id="bb-12345678-1234", content="x", debug=DebugInfo(pattern="M05"),
                        web_links=[WebLink(title="WLO", url="https://wirlernenonline.de/")])
    assert publikum.antwort_fuer(resp, intern=False).ui.ui_bloecke == []
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "M05", "_web_links": [{"title": "WLO", "url": "https://wirlernenonline.de/"}]})
    assert verlauf.ui_bloecke == []


@pytest.mark.parametrize("wert,erwartet",
                         [(None, None), ([], []), (["ui_linkbox"], ["ui_linkbox"])])
def test_das_studio_schreibt_den_schluessel_wie_er_ist(wert, erwartet):
    """``[]`` und „fehlt“ sind verschieden — ein GET→PUT darf das eine nicht ins andere kippen."""
    fm = _pattern_frontmatter(PatternEntry(id="M05", label="Suche", ui_module=wert))
    assert fm.get("ui_module", None) == erwartet


def test_der_katalog_bietet_die_abgeleiteten_module_an():
    from boerdi.api.config_choices import _SOURCES

    werte = [c["value"] for c in _SOURCES["ui_module"]()]
    assert werte == list(abgeleitet.ABGELEITETE)


# ── Review U1-c1 ──────────────────────────────────────────────────────────
def test_das_muster_kommt_im_betrieb_mit_bezeichnung(muster):
    """Der Debug-Block trägt ``"M05 (Suche)"`` (``turn_persist``) — gemeint ist ``M05``."""
    muster({"id": "M05", "ui_module": []})
    assert abgeleitet.erlaubte_module("M05 (Suche)") == frozenset()
    resp = ChatResponse(session_id="bb-12345678-1234", content="x",
                        debug=DebugInfo(pattern="M05 (Suche)"),
                        web_links=[WebLink(title="WLO", url="https://wirlernenonline.de/")])
    assert publikum.antwort_fuer(resp, intern=False).ui.ui_bloecke == []
    verlauf = publikum.ui_aus_gespeichert(
        {"pattern": "M05 (Suche)",
         "_web_links": [{"title": "WLO", "url": "https://wirlernenonline.de/"}]})
    assert verlauf.ui_bloecke == []


@pytest.mark.parametrize("wert", [5, "ui_linkbox", {"a": 1}])
def test_kaputter_bestand_bricht_keine_antwort(muster, wert):
    """Alte Sicherungen laufen am Validator vorbei — dann gilt die Vorgabe (alle)."""
    muster({"id": "M05", "ui_module": wert})
    assert abgeleitet.erlaubte_module("M05") is None


def test_der_typisierte_studio_eintrag_weist_unbekannte_namen_ab():
    with pytest.raises(ValidationError, match="ui_quatsch"):
        PatternEntry(id="M05", label="Suche", ui_module=["ui_quatsch"])
