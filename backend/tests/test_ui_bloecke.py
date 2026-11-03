"""Paket U1-a: UI-Blöcke — Modell, Regeln je Antwort, Speichern und Wiederherstellen.

Ein UI-Block ist ein Aufruf eines UI-Moduls in einer Bot-Antwort (Plan
``docs/plans/2026-11-02-paket-u1-ui-module.md``). Er reist öffentlich an ``ui`` — live und im
Verlauf —, gespeichert im Debug-Block der Nachricht wie die Dokument-Boxen.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.api import publikum
from boerdi.api.schemas import ChatResponse, DebugInfo
from boerdi.api.schemas_ui import UiBlock, UiInfo
from boerdi.domain import ui_bloecke


def _block(modul="ui_test", art="anzeigen", **mehr) -> UiBlock:
    return ui_bloecke.neuer_block(modul, 1, art, {"x": 1}, "Text", **mehr)


# ── a1: Modell ────────────────────────────────────────────────────────────
def test_ein_block_traegt_kennung_modul_version_art_daten_text():
    b = _block()
    assert b.modul == "ui_test" and b.version == 1 and b.art == "anzeigen"
    assert b.daten == {"x": 1} and b.text == "Text"
    assert len(b.block_id) == 16 and b.block_id.isalnum()


def test_anzeigende_bloecke_sind_nur_anzeige_abfragende_offen():
    assert _block().status == "nur_anzeige"
    assert _block(art="abfragen").status == "offen"


@pytest.mark.parametrize("feld,wert", [
    ("modul", "Ui_Gross"), ("modul", "zeige_dokument"), ("modul", "ui_"),
    ("art", "fragen"), ("status", "fertig"), ("version", 0), ("block_id", "x"),
])
def test_das_modell_weist_falsche_werte_ab(feld, wert):
    roh = _block().model_dump() | {feld: wert}
    with pytest.raises(ValidationError):
        UiBlock.model_validate(roh)


# ── a2: Regeln je Antwort ─────────────────────────────────────────────────
def test_hoechstens_fuenf_bloecke_je_antwort(caplog):
    bloecke = [_block(modul=f"ui_m{i}") for i in range(7)]
    behalten = ui_bloecke.regeln_anwenden(bloecke)
    assert [b.modul for b in behalten] == [f"ui_m{i}" for i in range(5)]
    assert "verworfen" in caplog.text


def test_hoechstens_ein_offener_abfragender_block():
    bloecke = [_block(modul="ui_aa"), _block(modul="ui_f1", art="abfragen"),
               _block(modul="ui_bb"), _block(modul="ui_f2", art="abfragen")]
    assert [b.modul for b in ui_bloecke.regeln_anwenden(bloecke)] == ["ui_aa", "ui_f1", "ui_bb"]


def test_zu_grosse_daten_fallen_weg():
    gross = ui_bloecke.neuer_block("ui_gross", 1, "anzeigen", {"t": "x" * 300_000}, "kurz")
    assert [b.modul for b in ui_bloecke.regeln_anwenden([gross, _block()])] == ["ui_test"]


# ── a3: speichern, live, Verlauf ──────────────────────────────────────────
def test_live_traegt_die_antwort_ihre_bloecke():
    b = _block()
    resp = ChatResponse(session_id="bb-12345678-1234", content="x", debug=DebugInfo())
    resp.ui = UiInfo(ui_bloecke=[b])
    aus = publikum.antwort_fuer(resp, intern=False)
    assert [x.block_id for x in aus.ui.ui_bloecke] == [b.block_id]


def test_der_verlauf_stellt_die_bloecke_aus_dem_debug_block_her():
    b = _block(art="abfragen")
    ui = publikum.ui_aus_gespeichert({ui_bloecke.DEBUG_KEY: [b.model_dump()]})
    assert ui.ui_bloecke[0].block_id == b.block_id and ui.ui_bloecke[0].status == "offen"


def test_kaputte_gespeicherte_bloecke_fallen_weg_der_verlauf_laedt():
    gut = _block().model_dump()
    ui = publikum.ui_aus_gespeichert({ui_bloecke.DEBUG_KEY: [gut, {"modul": "Kaputt"}, "text", 3]})
    assert [b.block_id for b in ui.ui_bloecke] == [gut["block_id"]]
    assert publikum.ui_aus_gespeichert({ui_bloecke.DEBUG_KEY: "kein Liste"}).ui_bloecke == []


def test_fuer_den_debug_block_werden_die_bloecke_als_json_abgelegt():
    b = _block()
    assert ui_bloecke.fuer_den_debug_block([b]) == [b.model_dump(mode="json")]


# ── Review U1-a ───────────────────────────────────────────────────────────
def test_nicht_speicherbare_daten_fallen_weg_statt_den_zug_zu_brechen(caplog):
    kaputt = ui_bloecke.neuer_block("ui_kaputt", 1, "anzeigen", {"x": object()}, "kurz")
    assert [b.modul for b in ui_bloecke.regeln_anwenden([kaputt, _block()])] == ["ui_test"]
    assert "ui_kaputt verworfen" in caplog.text


def test_der_verlauf_behaelt_leere_daten_und_text_der_bloecke():
    leer = ui_bloecke.neuer_block("ui_leer", 1, "anzeigen", {}, "")
    verlauf = publikum.verlauf_fuer(
        [{"role": "assistant", "content": "x",
          "debug": {ui_bloecke.DEBUG_KEY: ui_bloecke.fuer_den_debug_block([leer])}}],
        intern=False)
    block = verlauf[0]["ui"]["ui_bloecke"][0]
    assert block["daten"] == {} and block["text"] == "" and block["status"] == "nur_anzeige"
    assert "type_focus" not in verlauf[0]["ui"]          # übrige ui-Felder weiter nur gesetzt
