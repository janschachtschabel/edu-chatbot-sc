"""Plan 2026-11-19, A3 (E5, Befund S2c): Scan-Prüfung im WLO-Weg.

Ein Volltext aus WLO, der nach ``bereinigen`` weniger als ``KAUM_TEXT_WOERTER`` Wörter hat
(Seitenzahlen, OCR-Reste eines Scans), gilt als „kein lesbarer Text“ — Grund ``not_extracted`` wie
ein leerer, mit denselben Texten an die KI. Seitenzahlen kennt der WLO-Weg nicht, deshalb Wörter.
"""

from __future__ import annotations

import asyncio

from boerdi.services.dokumente import strukturdokument as leser
from tests.test_dokument_stand import _mcp


def _antwort(text: str) -> dict:
    return {"nodeId": "n-1", "title": "T", "text": text, "source": "repository",
            "charCount": len(text), "truncated": False}


def test_nur_seitenzahlen_sind_kein_lesbarer_text(monkeypatch):
    _mcp(monkeypatch, _antwort("- 1 -\n- 2 -"))
    assert asyncio.run(leser.volltext("n-1")) == (None, leser.NICHT_EXTRAHIERT)


def test_knapp_unter_der_grenze_kein_text_an_der_grenze_der_text(monkeypatch):
    wenig = "\n".join(f"Seite {n}" for n in range(leser.KAUM_TEXT_WOERTER - 1))
    _mcp(monkeypatch, _antwort(wenig))
    assert asyncio.run(leser.volltext("n-1")) == (None, leser.NICHT_EXTRAHIERT)
    genug = " ".join(["Lernfeld"] * leser.KAUM_TEXT_WOERTER)
    _mcp(monkeypatch, _antwort(genug))
    assert asyncio.run(leser.volltext("n-1")) == (genug, "")


def test_zahlen_und_zeichen_zaehlen_nicht_als_woerter():
    assert leser.woerter("- 12 - 3.4 § 5 a b") == 0
    assert leser.woerter("Lernfeld 3: Kunden beraten") == 3


def test_eine_echte_kurze_systematik_gilt():
    """Review A, MINOR 7: eine knappe Gliederung mit 40 Wörtern ist ein Dokument — 100 Wörter
    verwarfen echte kurze Systematiken."""
    text = ("# Physik Klasse 7\n## 1 Mechanik\n- Kraft und Bewegung\n- Masse und Gewicht\n"
            "- Reibung im Alltag\n## 2 Optik\n- Licht und Schatten\n- Spiegel und Reflexion\n"
            "- Linsen und Brechung\n## 3 Akustik\n- Schall und Ton\n- Lautstärke messen\n"
            "## 4 Wärme\n- Temperatur und Thermometer\n- Ausdehnung von Körpern\n"
            "- Wärmeleitung und Isolation\n## 5 Elektrizität\n- Stromkreis bauen\n")
    assert 30 <= leser.woerter(text) <= 45
    assert leser.lesbar(text)


def test_ocr_reste_mit_wenig_buchstaben_gelten_nicht():
    reste = " ".join(f"{n:06d} ab" for n in range(60))         # 60 „Wörter“, 25 % Buchstaben
    assert leser.woerter(reste) >= leser.KAUM_TEXT_WOERTER
    assert not leser.lesbar(reste)
    assert not leser.lesbar("- 1 -\n- 2 -")
