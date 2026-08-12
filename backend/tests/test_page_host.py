"""Behavior pins for domain/page_host.classify_page_host (Seitenkontext-Erweiterung,
Aufgabe 3). Pure, offline, deterministic — the own-host list is a parameter, so no
config is read here.

Two properties carry the weight and both are regressions waiting to happen:

* A host on the own list NEVER overrules a page kind the widget already detected.
  The real staging URL of the collection "Geometrische Optik" lives on
  ``repository.staging.openeduhub.net`` AND carries ``page_kind='collection'`` —
  classifying it as ``home`` would silently destroy the collection detection.
* A host that is NOT on the list becomes ``external``, which is what later turns
  into the "add this page to WLO" offer. A repository page falling through to
  ``external`` would make the bot offer to add WLO to WLO.
"""

from __future__ import annotations

from boerdi.domain.page_host import classify_page_host

OWN = (
    "wirlernenonline.de",
    "wissenlebt.online",
    "repository.staging.openeduhub.net",
    "redaktion.openeduhub.net",
)


# ── own hosts → home ────────────────────────────────────────────────
def test_eigener_host_wird_home():
    assert classify_page_host("wirlernenonline.de", OWN) == "home"


def test_www_praefix_zaehlt_als_derselbe_host():
    assert classify_page_host("www.wirlernenonline.de", OWN) == "home"


def test_grossschreibung_und_port_stoeren_nicht():
    assert classify_page_host("WirLernenOnline.DE:8443", OWN) == "home"


def test_repository_host_ist_eigen_nicht_fremd():
    # Aus dem Nutzer-Beispiel 2026-08-11: ohne diesen Eintrag böte der Bot an,
    # eine WLO-eigene Seite "in WLO aufzunehmen".
    assert classify_page_host("repository.staging.openeduhub.net", OWN) == "home"


def test_wildcard_deckt_unterdomaenen():
    assert classify_page_host("beta.wirlernenonline.de", ("*.wirlernenonline.de",)) == "home"


def test_wildcard_deckt_die_nackte_domaene_nicht():
    # Verhalten von host_matches_pattern (guide_mode) — hier nur festgehalten,
    # damit die Seed-Liste beide Formen führt, wenn sie beide meint.
    assert classify_page_host("wirlernenonline.de", ("*.wirlernenonline.de",)) == "external"


# ── foreign hosts → external ────────────────────────────────────────
def test_fremder_host_wird_external():
    assert classify_page_host("example.org", OWN) == "external"


def test_aehnlicher_aber_fremder_host_wird_external():
    # Kein Suffix-Vergleich: ein Angreifer-Host darf sich nicht als eigen ausgeben.
    assert classify_page_host("boese-wirlernenonline.de", OWN) == "external"
    assert classify_page_host("wirlernenonline.de.example.org", OWN) == "external"


# ── nothing to decide → "" (caller keeps what it had) ───────────────
def test_leerer_host_entscheidet_nichts():
    assert classify_page_host("", OWN) == ""
    assert classify_page_host(None, OWN) == ""


def test_ohne_gepflegte_liste_ist_nichts_eigen_aber_alles_fremd():
    # Leere Liste heisst "nicht gepflegt": eine Aussage "eigen" wäre geraten,
    # "fremd" ist die sichere Seite — der Dublettencheck läuft ohnehin davor.
    assert classify_page_host("wirlernenonline.de", ()) == "external"


def test_leere_und_kaputte_eintraege_werden_uebersprungen():
    assert classify_page_host("wirlernenonline.de", ("", "   ", "wirlernenonline.de")) == "home"
