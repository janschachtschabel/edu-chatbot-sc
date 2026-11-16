"""Plan 2026-11-15 (Webseitenführung als Ablauf), WF-2: Wahl wie in der eingebauten Führung.

- bis 12 Optionen (die Führung hat 11 Gruppen und „Bin mir nicht sicher“);
- ``synonyme`` an einer Option: getippter Text trifft per Teilwort (Beschriftung oder Synonym,
  ohne Groß/Klein, ab 3 Zeichen) — nur Optionen mit Synonymen, der genaue Treffer zuerst;
- ``kein_treffer`` an einem Wahl-Schritt ohne Freitext: ein getippter Text ohne Treffer bekommt
  einmal je Lauf und Schritt den Hinweis mit denselben Chips; danach geht er wie bisher an die KI.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models.ablauf import AblaufArea
from boerdi.services.ablauf import treiber, wahl_zug, zug
from boerdi.services.ablauf.pruefung import pruefe
from tests.test_ablauf_zug import (
    _S,
    _req,
    umgebung,  # noqa: F401 — Fixture
)


def _option(id_, label, **mehr):
    return {"id": id_, "label": {"de": label}, "ziel": "e", **mehr}


def _ablauf(optionen, **schritt):
    return AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "schritte": [{"id": "w", "typ": "nachricht", "text": {"de": "Wer bist du?"},
                      "optionen": optionen, "schreibt": "gruppe", **schritt},
                     {"id": "e", "typ": "ende", "text": {"de": "Danke."}}]})


_GRUPPEN = [
    _option("lehrkraft", "Lehrkraft", synonyme=["lehrer", "lehrerin", "ich unterrichte"]),
    _option("abnehmer", "Content-Abnehmer", synonyme=["schule", "lernplattform"]),
    _option("presse", "Presse"),
]


# ── bis 12 Optionen ──────────────────────────────────────────────────────────────────────────

def test_zwoelf_optionen_gehen_dreizehn_nicht():
    zwoelf = [_option(f"o{k}", f"Option {k}") for k in range(12)]
    assert pruefe(_ablauf(zwoelf)) == []
    assert any("12" in b for b in pruefe(_ablauf([*zwoelf, _option("o12", "Option 12")])))


# ── Synonyme ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("getippt", "erwartet"), [
    ("Lehrkraft", "lehrkraft"),                         # genau wie bisher
    ("Ich bin Lehrerin an einer Grundschule", "lehrkraft"),   # Synonym als Teilwort, vor „schule“
    ("wir betreiben eine LERNPLATTFORM", "abnehmer"),   # ohne Groß/Klein
    ("ich bin von der presse", None),                   # ohne Synonyme kein Teilwort-Treffer
    ("Presse", "presse"),
    ("hallo", None),
])
def test_synonyme_treffen_per_teilwort(getippt, erwartet):
    schritt = _ablauf(_GRUPPEN).schritte[0]
    assert treiber.wahl_aus_text(schritt, getippt) == erwartet


def test_der_genaue_treffer_geht_vor():
    schritt = _ablauf([_option("a", "Schule allgemein", synonyme=["schule"]),
                       _option("b", "Schule")]).schritte[0]
    assert treiber.wahl_aus_text(schritt, "Schule") == "b"


def test_synonyme_kuerzer_als_drei_zeichen_sind_ungueltig():
    with pytest.raises(ValidationError):
        _ablauf([_option("a", "A", synonyme=["ab"])])


# ── kein_treffer ─────────────────────────────────────────────────────────────────────────────

def test_kein_treffer_nur_an_einem_wahl_schritt_ohne_freitext():
    assert pruefe(_ablauf(_GRUPPEN, kein_treffer={"de": "Sag es mir grob."})) == []
    mit_freitext = _ablauf(_GRUPPEN, kein_treffer={"de": "x"},
                           freitext={"ziel": "e", "schreibt": "gruppe"})
    assert any("kein_treffer" in b for b in pruefe(mit_freitext))


def _katalog(umgebung, ablauf):  # noqa: F811
    umgebung.katalog["wert"] = {**umgebung.katalog["wert"],
                                "ablaeufe": [ablauf.model_dump(exclude_none=True)]}


def _start(state):
    return asyncio.run(zug.starten(_S(), _req(action=zug.AKTION, action_params={"ablauf": "probe"}),
                                   state))


def _getippt(state, text):
    return asyncio.run(wahl_zug.getippt(_S(), _req().model_copy(update={"message": text}), state))


def test_ein_fehlversuch_bekommt_einmal_den_hinweis_mit_den_chips(umgebung):  # noqa: F811
    _katalog(umgebung, _ablauf(_GRUPPEN, kein_treffer={"de": "Sag mir grob, was dich herführt."}))
    state: dict = {"entities": {}}
    _start(state)
    assert wahl_zug.nimmt_getippt("sitzung-0123456789", state, "keine Ahnung")
    antwort = _getippt(state, "keine Ahnung")
    assert antwort.content == "Sag mir grob, was dich herführt."
    assert len(antwort.quick_replies) == 3
    # ein zweiter Fehlversuch geht wie bisher an die KI — der Lauf wartet weiter
    assert not wahl_zug.nimmt_getippt("sitzung-0123456789", state, "weiß nicht")
    # ein Treffer setzt fort
    antwort = _getippt(state, "ich unterrichte Mathe")
    assert antwort.content.startswith("Danke.")


def test_ohne_kein_treffer_bleibt_es_beim_bisherigen_weg(umgebung):  # noqa: F811
    _katalog(umgebung, _ablauf(_GRUPPEN))
    state: dict = {"entities": {}}
    _start(state)
    assert not wahl_zug.nimmt_getippt("sitzung-0123456789", state, "keine Ahnung")


def test_review_nach_einem_rueckweg_kommt_der_hinweis_wieder(umgebung):  # noqa: F811
    """Review WF-2, Befund 1: die Marke galt je Vorgang und Schritt — nach „Nochmal wählen“ kam der
    Hinweis nie wieder. Jeder neu gerechnete Schritt ist ein neuer Besuch."""
    a = AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        "schritte": [
            {"id": "w", "typ": "nachricht", "text": {"de": "Wer?"}, "schreibt": "gruppe",
             "kein_treffer": {"de": "Sag es grob."},
             "optionen": [_option("lehrkraft", "Lehrkraft", synonyme=["lehrer"]) | {"ziel": "z"}]},
            {"id": "z", "typ": "nachricht", "text": {"de": "Sicher?"}, "optionen": [
                {"id": "nochmal", "label": {"de": "Nochmal"}, "ziel": "w"},
                {"id": "ok", "label": {"de": "Passt"}, "ziel": "e"}]},
            {"id": "e", "typ": "ende", "text": {"de": "Danke."}}]})
    _katalog(umgebung, a)
    state: dict = {"entities": {}}
    _start(state)
    assert _getippt(state, "keine Ahnung").content == "Sag es grob."
    assert wahl_zug.KEIN_TREFFER_KEY in state["entities"]          # gespeichert (update_session)
    _getippt(state, "Lehrer")                                       # → z
    _getippt(state, "Nochmal")                                      # → w, ein neuer Besuch
    assert _getippt(state, "immer noch keine Ahnung").content == "Sag es grob."


def test_review_englisch_mit_rueckfall_auf_deutsch(umgebung):  # noqa: F811
    from boerdi.api.schemas import Environment

    _katalog(umgebung, _ablauf(_GRUPPEN, kein_treffer={"de": "Sag es grob."}))
    state: dict = {"entities": {}}
    _start(state)
    env = Environment(locale="en")
    antwort = asyncio.run(wahl_zug.getippt(
        _S(), _req().model_copy(update={"message": "no idea", "environment": env}), state))
    assert antwort.content == "Sag es grob."                        # ohne Englisch: Deutsch


def test_review_ein_geleerter_hinweis_gilt_als_nicht_gesetzt():
    a = _ablauf(_GRUPPEN, kein_treffer={"de": "  ", "en": ""})
    assert a.schritte[0].kein_treffer is None and pruefe(a) == []


def test_review_kein_platzhalter_im_hinweis():
    a = _ablauf(_GRUPPEN, kein_treffer={"de": "Nicht {wahl.gruppe}?"})
    assert any("Platzhalter" in b for b in pruefe(a))


# ── Zweites Review, Befund M1: ``endet_bei_text`` wie die eingebaute Tour ───────────────────

def _weich(umgebung, **ablauf_mehr):  # noqa: F811
    a = AblaufArea.model_validate({
        "id": "probe", "titel": {"de": "Probe"}, "aktiv": True, "ausloeser": [{"art": "knopf"}],
        **ablauf_mehr,
        "schritte": [{"id": "w", "typ": "nachricht", "text": {"de": "Wer?"},
                      "schreibt": "gruppe", "optionen": _GRUPPEN},
                     {"id": "e", "typ": "ende", "text": {"de": "Danke."}}]})
    _katalog(umgebung, a)
    state: dict = {"entities": {}}
    _start(state)
    return state


def test_endet_bei_text_beendet_einen_wartenden_lauf_still(umgebung):  # noqa: F811
    from boerdi.services.ablauf import zug_basis

    state = _weich(umgebung, endet_bei_text=True)
    assert asyncio.run(wahl_zug.still_beenden(_S(), "sitzung-0123456789", state))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "abgebrochen"
    # die KI schlägt denselben Ablauf in den nächsten Zügen nicht gleich wieder vor
    assert (state["entities"].get(zug_basis.AUSSTIEG_KEY) or {}).get("ablauf") == "probe"


def test_ohne_endet_bei_text_wartet_der_lauf_weiter(umgebung):  # noqa: F811
    state = _weich(umgebung)
    assert not asyncio.run(wahl_zug.still_beenden(_S(), "sitzung-0123456789", state))
    [v] = umgebung.speicher.v.values()
    assert v.akte["lauf"]["status"] == "wartet_wahl"
