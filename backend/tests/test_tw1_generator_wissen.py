"""Plan 2026-11-11, TW-1: Der Generator des Strukturentwurfs kennt die Regeln des Leitfadens.

Grundlage ist das Dokument „Themenbäume — Gestaltungsleitfaden“ (vom Nutzer am 11.11. eingefügt).
Es enthält:

- Form: flach und breit, 5–15 Punkte oben, Kinder 3–20 (Ziel 5–12), nie genau ein Unterpunkt;
- Benennung: 1–4 Wörter, Schlüsselwort zuerst, Geschwister in gleicher Form und Begriffsart;
- eine Ordnungslogik: Klassenstufen, Formate, Jahre, Kompetenzen, Methoden und Zielgruppen sind
  Facetten, keine Punkte;
- Dokumente (Lehrpläne): die inhaltlichen Ordnungselemente tragen die obere Ebene (Lernfelder,
  Themenfelder, Inhaltsbereiche). Vorwort, Kompetenzmodell, Basiskonzepte, Leistungsbewertung,
  Hinweise und Anhang tragen sie nicht.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import strukturentwurf_prompt as prompt


def _system(nachrichten) -> str:
    return next(n["content"] for n in nachrichten if n["role"] == "system")


def test_jede_aufforderung_traegt_die_formregeln():
    for nachrichten in (
        prompt.oben(thema="Optik", fach=None, bildungsstufe=None, anzahl_oben=8, hinweise=""),
        prompt.unterthemen(entwurf="Optik", thema="Optik", fach=None, bildungsstufe=None,
                           hinweise="", pfad=["Optik"], knoten={"titel": "Linsen"},
                           geschwister=[], anzahl=4, letzte_ebene=True)):
        text = _system(nachrichten)
        assert "1 bis 4 Wörter" in text
        assert "nie genau einen Unterpunkt" in text
        for facette in ("Klassenstufen", "Formate", "Jahreszahlen", "Kompetenzen"):
            assert facette in text, facette
        assert "Ordnungslogik" in text


def test_die_dokument_aufforderung_nimmt_die_strukturelemente():
    text = _system(prompt.oben_aus_dokument(
        thema="Lehrplan", fach=None, bildungsstufe=None, anzahl_oben=10, hinweise="",
        gliederung="- Vorwort [a1]", anfang=""))
    for element in ("Lernfelder", "Themenfelder", "Inhaltsbereiche"):
        assert element in text, element
    for weg in ("Kompetenzmodell", "Basiskonzepte", "Leistungsbewertung", "Stundentafel"):
        assert weg in text, weg


def test_ein_einzelner_unterpunkt_wird_keiner():
    """Leitfaden: nie genau ein Kind — ein Punkt mit einem Unterthema bleibt ein Blatt."""
    assert prompt.zahl_unterthemen({"unterthemen": 1}, 8) == 0
    assert prompt.zahl_unterthemen({"unterthemen": 2}, 8) == 2
    assert prompt.zahl_unterthemen({"unterthemen": 0}, 8) == 0


# ── Review TW-1 ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("wert", "erwartet"), [
    (True, 0), (-3, 0), ("4", 0), (1, 0), (2, 2), (5, 5), (99, prompt.UNTERTHEMEN_OBEN)])
def test_review_8_zahl_unterthemen(wert, erwartet):
    assert prompt.zahl_unterthemen({"unterthemen": wert}, prompt.UNTERTHEMEN_OBEN) == erwartet


def test_review_1_die_spanne_ist_ein_richtwert_und_das_dokument_gibt_die_zahl_vor():
    text = _system(prompt.oben_aus_dokument(
        thema="Lehrplan", fach=None, bildungsstufe=None, anzahl_oben=10, hinweise="",
        gliederung="- LF 1 [a1]", anfang=""))
    assert "Je Ordnungselement ein Punkt" in text and "Richtwert" in text
    for nachrichten in (
        prompt.oben(thema="Optik", fach=None, bildungsstufe=None, anzahl_oben=8, hinweise=""),
        prompt.oben_aus_inhalten(thema="L", fach=None, bildungsstufe=None, anzahl_oben=8,
                                 hinweise="", gliederung="- A [a1]", anfang="")):
        text = _system(nachrichten)
        assert "Richtwert" in text and "nie genau einen Unterpunkt" in text


def test_review_1_im_dokument_schneidet_der_dienst_nicht_bei_anzahl_oben():
    from boerdi.services import strukturentwurf_dienst as dienst
    from tests.test_strukturentwurf_dienst import Attrappe, _k
    from tests.test_strukturentwurf_dokument import _dokument

    llm = Attrappe([_k(f"Lernfeld {i}") for i in range(13)])

    async def los():
        ende = asyncio.get_running_loop().time() + 60
        return await dienst.erzeugen(dienst.Auftrag(thema="Rahmenlehrplan", anzahl_oben=10,
                                                    tiefe=1),
                                     llm=llm, frist_ende=ende, dokument=_dokument())

    erzeugt = asyncio.run(los())
    assert len(erzeugt.daten["knoten"]) == 13


def test_review_4_bis_6_ausnahmen_und_berufsbildung():
    text = _system(prompt.oben(thema="Medienkompetenz", fach=None, bildungsstufe=None,
                               anzahl_oben=8, hinweise=""))
    assert "sofern sie nicht selbst das Thema sind" in text
    assert "Planungsordnung" in text
    assert "Beruflichen Bildung" in text and "Lernfelder" in text
