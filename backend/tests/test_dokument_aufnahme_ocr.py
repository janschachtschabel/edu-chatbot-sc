"""Plan 2026-11-19, Paket C (C2): ``aufbereiten`` liest gescannte PDF per Texterkennung.

Nur PDF, nur wenn ``gescannt`` und der Endpunkt eine Texterkennung mitgibt (``ocr_lesen``, sonst
wie bisher ``kein_text``). Danach der gewohnte Weg — Moderation, Gliederung, Befund mit Warnung
``ocr``. Die Texterkennung selbst ist hier eine Attrappe (``test_dokument_ocr``).
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.dokumente import aufnahme
from boerdi.services.dokumente.aufnahme import Abweisung, Aufbereitet
from boerdi.services.dokumente.ocr import OcrErgebnis
from boerdi.services.dokumente.umwandlung import Gewandelt

_OCR_MD = ("# Rahmenlehrplan Aufbereitungsmechaniker\n\n## Lernfeld 1\nGesteine erkunden und "
           "einordnen, Proben nehmen.\n\n## Lernfeld 2\nMaschinen warten und pflegen.\n")


@pytest.fixture
def scan(monkeypatch):
    async def fast_leer(*_a, **_k):
        return Gewandelt(markdown="12\n", seiten=2, gekuerzt=False)

    monkeypatch.setattr(aufnahme, "wandle", fast_leer)


def _lauf(rumpf: bytes, name: str, *, ocr_lesen, moderieren=None):
    gelesen: list[str] = []

    async def sauber(text):
        gelesen.append(text)
        return {"flagged": False}

    erg = asyncio.run(aufnahme.aufbereiten(rumpf, name, max_seiten=300, frist_s=5,
                                           moderieren=moderieren or sauber, ocr_lesen=ocr_lesen))
    return erg, gelesen


def _ocr(ergebnis: OcrErgebnis):
    aufrufe: list[bytes] = []

    async def lesen(rumpf: bytes) -> OcrErgebnis:
        aufrufe.append(rumpf)
        return ergebnis

    return lesen, aufrufe


def test_gescannte_pdf_wird_per_texterkennung_gelesen_und_moderiert(scan):
    lesen, aufrufe = _ocr(OcrErgebnis(markdown=_OCR_MD, seiten=2, gelesen=2, gekuerzt=False))
    erg, moderiert = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=lesen)
    assert isinstance(erg, Aufbereitet)
    assert aufrufe == [b"%PDF-1.4 scan"]
    assert erg.markdown.startswith("# Rahmenlehrplan") and "Lernfeld 2" in erg.markdown
    assert "ocr" in erg.befund["warnungen"] and erg.befund["seiten"] == 2
    assert erg.vorschau[:2] == ["Rahmenlehrplan Aufbereitungsmechaniker", "Lernfeld 1"]
    assert "Lernfeld 1" in moderiert[0]                       # moderiert wird der gelesene Text


def test_ohne_texterkennung_bleibt_es_kein_text(scan):
    erg, _ = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=None)
    assert erg == Abweisung(400, "kein_text")


def test_nur_pdf_geht_an_die_texterkennung():
    lesen, aufrufe = _ocr(OcrErgebnis(markdown=_OCR_MD, seiten=1, gelesen=1, gekuerzt=False))
    erg, _ = _lauf(b"   \n\n  ", "leer.txt", ocr_lesen=lesen)
    assert erg == Abweisung(400, "kein_text") and aufrufe == []


def test_pdf_mit_text_braucht_keine_texterkennung(monkeypatch):
    async def mit_text(*_a, **_k):
        return Gewandelt(markdown=_OCR_MD * 5, seiten=1, gekuerzt=False)

    monkeypatch.setattr(aufnahme, "wandle", mit_text)
    lesen, aufrufe = _ocr(OcrErgebnis(markdown="x", seiten=1, gelesen=1, gekuerzt=False))
    erg, _ = _lauf(b"%PDF-1.4 text", "text.pdf", ocr_lesen=lesen)
    assert isinstance(erg, Aufbereitet) and aufrufe == []
    assert "ocr" not in erg.befund["warnungen"]


def test_auch_die_texterkennung_findet_kaum_text(scan):
    lesen, _ = _ocr(OcrErgebnis(markdown="- 1 -", seiten=2, gelesen=2, gekuerzt=False))
    erg, _ = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=lesen)
    assert erg == Abweisung(400, "kein_text")


def test_keine_seite_gelesen_weil_der_anbieter_fehlte_ist_ausgelastet(scan):
    """Frist oder Anbieterfehler bei jeder Seite: ein neuer Versuch kann helfen — nicht
    „kein lesbarer Text“."""
    lesen, _ = _ocr(OcrErgebnis(markdown="", seiten=2, gelesen=0, gekuerzt=True, fehlend=2))
    erg, _ = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=lesen)
    assert erg == Abweisung(503, "ausgelastet")


def test_gekuerzte_texterkennung_steht_im_befund(scan):
    lesen, _ = _ocr(OcrErgebnis(markdown=_OCR_MD, seiten=30, gelesen=2, gekuerzt=True,
                                  versucht=20, fehlend=18))
    erg, _ = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=lesen)
    assert isinstance(erg, Aufbereitet)
    assert erg.befund["gekuerzt"] is True
    assert {"ocr", "gekuerzt"} <= set(erg.befund["warnungen"])


def test_moderation_weist_den_gelesenen_text_ab(scan):
    async def flagged(_text):
        return {"flagged": True}

    lesen, _ = _ocr(OcrErgebnis(markdown=_OCR_MD, seiten=2, gelesen=2, gekuerzt=False))
    erg, _ = _lauf(b"%PDF-1.4 scan", "scan.pdf", ocr_lesen=lesen, moderieren=flagged)
    assert erg == Abweisung(400, "abgewiesen")
