"""Paket U2-f (Plan 2026-11-04): der Gold-Zug „Entwurf übernehmen“.

``ui_antwort: {uebernehmen: true}`` antwortet auf den offenen ``ui_strukturentwurf``-Block des
vorigen Zugs wie der Knopf „Übernehmen“ im Widget: unverändert, ``uebernommen: true``,
``bearbeitet: false``, Nachricht „Entwurf „…“ übernommen (N Punkte).“. Ohne offenen Entwurf geht
die Nachricht getippt (wie bei der Auswahl, G-4).
"""

import asyncio

import pytest

from tests.test_golden_ui_module import _antwort, _block, _fake_post, rg

_ENTWURF = {"block_id": "efgh5678", "modul": "ui_strukturentwurf", "version": 1,
            "art": "abfragen", "status": "offen", "text": "",
            "daten": {"titel": "Optik", "quelle": "ki", "knoten": [
                {"id": "k1", "titel": "Licht", "kinder": [{"id": "k1-1", "titel": "Quellen"}]},
                {"id": "k2", "titel": "Farben"}]}}


def _flow() -> dict:
    return {"id": "GV-T", "erwartung": "Ein Entwurf, dann übernommen.", "turns": [
        {"message": "Entwirf eine Gliederung zur Optik", "anwendungsfall": "erzeugen",
         "expect": {"ui_any": ["ui_strukturentwurf"]}},
        {"message": "passt so", "anwendungsfall": "erzeugen", "ui_antwort": {"uebernehmen": True},
         "expect": {}},
    ]}


def test_die_form_uebernehmen_ist_gueltig_und_nur_mit_wahrheitswert():
    rg.validate_flows([_flow()])
    for falsch in ({"uebernehmen": False}, {"uebernehmen": "ja"},
                   {"uebernehmen": True, "waehle": ["x"]}):
        flow = _flow()
        flow["turns"][1]["ui_antwort"] = falsch
        with pytest.raises(ValueError, match="ui_antwort"):
            rg.validate_flows([flow])


def test_der_offene_entwurf_wird_wie_im_widget_uebernommen():
    antwort, text, beob = rg.baue_entwurf_antwort(rg.offener_entwurf(_antwort(_ENTWURF)), "x")
    assert antwort == {"block_id": "efgh5678", "daten": {
        **_ENTWURF["daten"], "uebernommen": True, "bearbeitet": False}}
    assert text == "Entwurf „Optik“ übernommen (3 Punkte)."
    assert beob == {"status": "gesendet", "uebernommen": True}


def test_ohne_offenen_entwurf_geht_die_nachricht_getippt():
    assert rg.offener_entwurf(_antwort(_block("ui_themenbaum"))) is None
    assert rg.offener_entwurf(_antwort({**_ENTWURF, "status": "veraltet"})) is None
    antwort, text, beob = rg.baue_entwurf_antwort(None, "passt so")
    assert antwort is None and text == "passt so" and beob == {"status": "kein_entwurf"}


def test_run_flows_uebernimmt_den_entwurf_des_vorigen_zugs(monkeypatch):
    gesehen: list[dict] = []
    monkeypatch.setattr(rg, "post_chat", _fake_post(gesehen, [_antwort(_ENTWURF), _antwort()]))
    convs = asyncio.run(rg.run_flows("http://x/api/chat", [_flow()]))
    assert gesehen[1]["ui_antwort"]["block_id"] == "efgh5678"
    assert gesehen[1]["message"] == "Entwurf „Optik“ übernommen (3 Punkte)."
    assert convs[0]["turns"][1]["golden"]["observed"]["ui_antwort"]["uebernommen"] is True
