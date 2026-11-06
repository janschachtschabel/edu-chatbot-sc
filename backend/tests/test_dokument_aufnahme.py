"""Paket U3-2a: ein hochgeladenes Dokument aufbereiten — Art, Umwandlung, Gliederung, Moderation.

Der Dienst kennt kein HTTP; er gibt entweder das Aufbereitete oder eine Abweisung mit Status und
Code zurück, die der Endpunkt unverändert ausliefert (``detail`` ohne Servertext).
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.dokumente import aufnahme
from boerdi.services.dokumente.aufnahme import Abweisung, Aufbereitet
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler

_MD = "# Lehrplan Physik\n\n## Mechanik\nKräfte und Bewegung.\n\n## Optik\nLicht und Linsen.\n" \
      "\n## Akustik\nSchall.\n"


async def _sauber(_text):
    return {"flagged": False}


def _lauf(rumpf: bytes, name: str = "Lehrplan.md", *, moderieren=_sauber, ausfuehren=None,
          max_seiten: int = 300):
    return asyncio.run(aufnahme.aufbereiten(rumpf, name, max_seiten=max_seiten, frist_s=5,
                                            moderieren=moderieren, ausfuehren=ausfuehren))


def test_markdown_wird_gegliedert_und_befundet():
    erg = _lauf(_MD.encode())
    assert isinstance(erg, Aufbereitet)
    assert erg.format == "md" and erg.markdown.startswith("# Lehrplan Physik")
    assert erg.befund["gliederung_art"] == "ueberschriften" and erg.befund["abschnitte"] == 4
    assert [a["titel"] for a in erg.gliederung][:2] == ["Lehrplan Physik", "Mechanik"]
    assert erg.vorschau[:2] == ["Lehrplan Physik", "Mechanik"]


@pytest.mark.parametrize(("rumpf", "name", "status", "code"), [
    (b"\x89PNG\r\n\x1a\n" + b"0" * 20, "foto.png", 415, "bild"),
    (b"\x00\x01\x02binaer", "x.bin", 400, "art_unbekannt"),
    (b"   \n\n  ", "leer.txt", 400, "kein_text"),
])
def test_abweisungen_vor_und_nach_der_umwandlung(rumpf, name, status, code):
    erg = _lauf(rumpf, name)
    assert erg == Abweisung(status, code)


@pytest.mark.parametrize(("art", "status", "code"), [
    ("zu_viele_seiten", 400, "zu_viele_seiten"),
    ("entpackt_zu_gross", 400, "entpackt_zu_gross"),
    ("umwandlung_zu_gross", 413, "zu_gross"),
    ("text_zu_lang", 413, "zu_gross"),
    ("umwandlung_zu_langsam", 504, "zu_langsam"),
    ("ausgelastet", 503, "ausgelastet"),
    ("format", 400, "art_unbekannt"),
    ("datei", 400, "unlesbar"),
    ("server", 500, "fehler"),
])
def test_umwandlungsfehler_werden_zu_codes(monkeypatch, art, status, code):
    async def scheitert(*_a, **_k):
        return Umwandlungsfehler("Fehler: geheimer Servertext", art=art)

    monkeypatch.setattr(aufnahme, "wandle", scheitert)
    assert _lauf(b"%PDF-1.4 x", "a.pdf") == Abweisung(status, code)


def test_gescanntes_pdf_ist_kein_text(monkeypatch):
    from boerdi.services.dokumente.umwandlung import Gewandelt

    async def fast_leer(*_a, **_k):
        return Gewandelt(markdown="12\n", seiten=40, gekuerzt=False)

    monkeypatch.setattr(aufnahme, "wandle", fast_leer)
    assert _lauf(b"%PDF-1.4 x", "scan.pdf") == Abweisung(400, "kein_text")


def test_moderation_liest_uebersicht_und_anfang_und_weist_ab():
    gelesen: list[str] = []

    async def markiert(text):
        gelesen.append(text)
        return {"flagged": True}

    assert _lauf(_MD.encode(), moderieren=markiert) == Abweisung(400, "abgewiesen")
    assert "Mechanik" in gelesen[0] and "Kräfte und Bewegung" in gelesen[0]


def test_ungepruefte_moderation_laesst_durch():
    async def ohne_zugang(_text):
        return {}

    assert isinstance(_lauf(_MD.encode(), moderieren=ohne_zugang), Aufbereitet)


def test_der_name_wird_eine_zeile_ohne_pfad():
    assert aufnahme.sauberer_name("C:\\fake\\..\\Lehr\nplan\x07.md") == "Lehr plan.md"
    assert aufnahme.sauberer_name("") == "Dokument"
    assert len(aufnahme.sauberer_name("x" * 500)) == aufnahme.MAX_NAME


def test_die_moderation_sieht_mindestens_was_der_entwurf_sieht():
    from boerdi.services import strukturentwurf_dienst

    assert aufnahme.MODERATION_UEBERSICHT >= strukturentwurf_dienst.DOKUMENT_GLIEDERUNG
    assert aufnahme.MODERATION_ANFANG >= strukturentwurf_dienst.DOKUMENT_ANFANG


@pytest.mark.parametrize(("modus", "erwartet"), [("open", Aufbereitet), ("closed", Abweisung)])
def test_ungepruefte_moderation_folgt_dem_failure_mode(monkeypatch, modus, erwartet):
    from boerdi.settings import get_settings

    async def ohne_zugang(_text):
        return {}

    monkeypatch.setenv("MODERATION_FAILURE_MODE", modus)
    get_settings.cache_clear()
    try:
        erg = _lauf(_MD.encode(), moderieren=ohne_zugang)
    finally:
        get_settings.cache_clear()
    assert isinstance(erg, erwartet)
    if modus == "closed":
        assert erg == Abweisung(503, "pruefung_fehlt")
