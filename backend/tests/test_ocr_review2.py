"""Zweites Review Paket C (2026-11-19): Speichergrenze und Anmerkungen beim Rendern (1), Sperre und
„läuft schon“ je Sitzung, abgebrochene Seiten gebucht (2), Restfrist vor dem Rendern (3),
Zwischenspeicher nach Größe (5), Codes des Kindprozesses (7), ``OcrGrenze`` ohne DB-Import (8),
JPEG-Größe (10)."""

from __future__ import annotations

import asyncio
import io
import os
import time
import zlib

import pypdfium2 as pdfium
import pytest

from boerdi.services.dokumente import aufnahme, ocr, ocr_rendern, ocr_sitzung, umwandlung
from boerdi.services.dokumente.aufnahme import Abweisung
from boerdi.services.dokumente.ocr import OcrErgebnis
from boerdi.services.dokumente.umwandlung import Gewandelt
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler


def _pdf_aus(objekte: list[bytes]) -> bytes:
    pdf, stellen = b"%PDF-1.7\n", []
    for i, o in enumerate(objekte):
        stellen.append(len(pdf))
        pdf += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % s for s in stellen)
    pdf += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objekte) + 1, xref))
    return pdf


def _strom(kopf: bytes, rumpf: bytes) -> bytes:
    return kopf + b" /Length %d >>\nstream\n" % len(rumpf) + rumpf + b"\nendstream"


def _bild(breite: int, hoehe: int, daten: bytes) -> bytes:
    return _strom(b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
                  b"/BitsPerComponent 8 /Filter /FlateDecode" % (breite, hoehe), daten)


_KOPF = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"]
_ZEICHNEN = b"q 595 0 0 842 0 0 cm /Im0 Do Q"


def _kachelmuster(kante: int) -> bytes:
    """Wie im Review (``r2_pattern.pdf``): das große Bild steckt in einem Kachelmuster."""
    packer = zlib.compressobj(9)
    daten = b"".join(packer.compress(b"\x80" * kante) for _ in range(kante)) + packer.flush()
    muster = _strom(b"<< /Type /Pattern /PatternType 1 /PaintType 1 /TilingType 1 "
                    b"/BBox [0 0 595 842] /XStep 595 /YStep 842 "
                    b"/Resources << /XObject << /Im0 6 0 R >> >>", _ZEICHNEN)
    return _pdf_aus([*_KOPF,
                     b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Pattern "
                     b"<< /P0 5 0 R >> >> /Contents 4 0 R >>",
                     _strom(b"<<", b"/Pattern cs /P0 scn 0 0 595 842 re f"), muster,
                     _bild(kante, kante, daten)])


def _rauschen(kante: int = 2400, punkte: int = 1152) -> bytes:
    """Eine Seite voller Rauschen (``r2_noise20.pdf``): als JPEG mehrere MB."""
    daten = zlib.compress(os.urandom(kante * kante), 1)
    return _pdf_aus([*_KOPF,
                     b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /XObject "
                     b"<< /Im0 5 0 R >> >> /Contents 4 0 R >>" % (punkte, punkte),
                     _strom(b"<<", b"q %d 0 0 %d 0 0 cm /Im0 Do Q" % (punkte, punkte)),
                     _bild(kante, kante, daten)])


def _leer(seiten: int = 1) -> bytes:
    dok = pdfium.PdfDocument.new()
    for _ in range(seiten):
        dok.new_page(595, 842)
    puffer = io.BytesIO()
    dok.save(puffer)
    return puffer.getvalue()


# ── 1: Speichergrenze des Kindes, keine Anmerkungen, Umgehung des Budgets ──

def test_1_das_rendern_hat_eine_eigene_kleinere_speichergrenze(monkeypatch):
    gesehen = {}

    async def spion(funktion, *args, **kw):
        gesehen.update(kw)
        return "1" + ocr_rendern.TRENNER

    monkeypatch.setattr(ocr, "im_kind_mit_datei", spion)
    asyncio.run(ocr.seiten_lesen(_leer(), seiten_max=1, frist_ende=time.monotonic() + 60,
                                 usage_acc=None))
    assert gesehen["max_mb"] == ocr.RENDER_MAX_MB == 512


def test_1_die_speichergrenze_reicht_bis_in_den_kindprozess(monkeypatch):
    from boerdi.services.rag import umwandeln_kind

    gesehen = []

    def ausfuehren(funktion, args, frist_s, max_mb):
        gesehen.append(max_mb)
        return "ok"

    monkeypatch.setattr(umwandeln_kind, "_ausfuehren", ausfuehren)
    assert asyncio.run(umwandeln_kind.im_kindprozess(len, "x", frist_s=5, max_mb=512)) == "ok"
    assert gesehen == [512]


def test_1_anmerkungen_werden_nicht_gezeichnet(monkeypatch):
    gesehen = []
    echt = pdfium.PdfPage.render

    def render(self, *a, **kw):
        gesehen.append(kw.get("draw_annots"))
        return echt(self, *a, **kw)

    monkeypatch.setattr(pdfium.PdfPage, "render", render)
    ocr_rendern.bilder(_leer(), 1)
    assert gesehen == [False]


def test_1_kachelmuster_umgeht_das_budget_aber_nie_den_elternprozess():
    import psutil

    prozess = psutil.Process()
    vorher = prozess.memory_info().rss

    async def lesen(jpeg, usage_acc, frist_s):
        return "Text"

    erg = asyncio.run(ocr.seiten_lesen(_kachelmuster(9000), seiten_max=1,
                                       frist_ende=time.monotonic() + 60, usage_acc=None,
                                       lesen=lesen))
    # gerendert (das Budget sieht das Muster nicht) oder nicht renderbar — nie ein Absturz
    assert erg.seiten == 1 and erg.gelesen + erg.unrenderbar == 1
    assert prozess.memory_info().rss - vorher < 100 * 1024 * 1024


# ── 2: Sperre je Sitzung, „läuft schon“, abgebrochene Seiten ─────────────

def test_2_parallele_uploads_derselben_sitzung_lesen_nacheinander_mit_frischem_rest(monkeypatch):
    ocr_sitzung.leeren()
    gebucht = {"n": 0}
    laufend = hoechstens = 0
    seiten_max: list[int] = []

    async def seiten_lesen(rumpf, **kw):
        nonlocal laufend, hoechstens
        laufend += 1
        hoechstens = max(hoechstens, laufend)
        seiten_max.append(kw["seiten_max"])
        await asyncio.sleep(0.05)
        kw["usage_acc"]["models"]["m"] = {"calls": kw["seiten_max"]}
        laufend -= 1
        return OcrErgebnis(markdown="# T", seiten=8, gelesen=8, gekuerzt=False, versucht=8)

    async def zaehlen():
        return gebucht["n"]

    async def buchen(acc):
        gebucht["n"] += acc["models"]["m"]["calls"]

    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)

    def leser():
        return ocr_sitzung.leser(session_id="bb-1", budget=12, seiten_max=8, gebucht=zaehlen,
                                 buchen=buchen, frist_ende=time.monotonic() + 30)

    async def beide():
        return await asyncio.gather(leser()(b"%PDF a"), leser()(b"%PDF b"),
                                    return_exceptions=True)

    asyncio.run(beide())
    assert hoechstens == 1                     # nacheinander
    assert seiten_max == [8, 4]                # der Zweite sieht den gebuchten Rest
    assert gebucht["n"] == 12


def test_2_dieselbe_datei_zugleich_wird_einmal_gelesen(monkeypatch):
    ocr_sitzung.leeren()
    aufrufe = []

    async def seiten_lesen(rumpf, **kw):
        aufrufe.append(1)
        await asyncio.sleep(0.05)
        return OcrErgebnis(markdown="# T", seiten=2, gelesen=2, gekuerzt=False, versucht=2)

    async def null():
        return 0

    async def buchen(acc):
        return None

    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)

    def leser():
        return ocr_sitzung.leser(session_id="bb-1", budget=50, seiten_max=20, gebucht=null,
                                 buchen=buchen, frist_ende=time.monotonic() + 30)

    async def beide():
        return await asyncio.gather(leser()(b"%PDF gleich"), leser()(b"%PDF gleich"))

    a, b = asyncio.run(beide())
    assert len(aufrufe) == 1 and a == b


def test_2_eine_mitten_im_aufruf_abgebrochene_seite_wird_als_aufruf_gebucht(monkeypatch):
    from boerdi.obs.usage import new_accumulator

    async def gerendert(rumpf, seiten_max, rest_s):
        return 1, [b"\xff\xd8a"]

    async def haengt(jpeg, usage_acc, frist_s):
        await asyncio.sleep(30)

    monkeypatch.setattr(ocr, "_bilder", gerendert)
    monkeypatch.setattr(ocr, "MINDEST_REST_S", 0.1)
    zaehler = new_accumulator()
    erg = asyncio.run(ocr.seiten_lesen(b"%PDF", seiten_max=1, frist_ende=time.monotonic() + 0.4,
                                       usage_acc=zaehler, lesen=haengt))
    assert erg.fehlend == 1
    [(modell, werte)] = zaehler["models"].items()
    assert werte["calls"] == 1 and werte["prompt"] == 0 and werte["completion"] == 0


# ── 3: Restfrist vor dem Rendern, Platz an die Frist gebunden ─────────────

def test_3_ohne_restfrist_wird_nicht_gerendert(monkeypatch):
    async def nie(*_a, **_k):
        raise AssertionError("ohne Restfrist kein Kindprozess")

    monkeypatch.setattr(ocr, "im_kind_mit_datei", nie)
    erg = asyncio.run(ocr.seiten_lesen(_leer(), seiten_max=1,
                                       frist_ende=time.monotonic() + ocr.MINDEST_REST_S - 1,
                                       usage_acc=None))
    assert erg.gelesen == 0 and erg.fehlend == 1


def test_3_platz_und_renderfrist_haengen_an_der_restfrist(monkeypatch):
    gesehen = {}

    async def spion(funktion, *args, **kw):
        gesehen.update(kw)
        return "1" + ocr_rendern.TRENNER

    monkeypatch.setattr(ocr, "im_kind_mit_datei", spion)
    rest = ocr.MINDEST_REST_S + 10
    asyncio.run(ocr.seiten_lesen(_leer(), seiten_max=1, frist_ende=time.monotonic() + rest,
                                 usage_acc=None))
    assert 0 < gesehen["platz_frist_s"] <= 10
    assert 0 < gesehen["frist_s"] <= 10


def test_3_im_kind_mit_datei_reicht_die_platzfrist_durch(monkeypatch):
    gesehen = {}

    async def ausfuehren(funktion, *args, **kw):
        gesehen.update(kw)
        return "x"

    monkeypatch.setattr(umwandlung, "im_kindprozess", ausfuehren)
    asyncio.run(umwandlung.im_kind_mit_datei(len, b"x", ".pdf", frist_s=5, platz_frist_s=3,
                                             max_mb=512))
    assert gesehen["platz_frist_s"] == 3 and gesehen["max_mb"] == 512


# ── 5: Zwischenspeicher nach Größe, nur vollständige Ergebnisse ───────────

def test_5_der_zwischenspeicher_verdraengt_nach_zeichen(monkeypatch):
    ocr_sitzung.leeren()
    monkeypatch.setattr(ocr_sitzung, "MAX_ZEICHEN", 10)
    erg = OcrErgebnis(markdown="x" * 6, seiten=1, gelesen=1, gekuerzt=False, versucht=1)
    ocr_sitzung._merken(("bb", "a"), erg)
    ocr_sitzung._merken(("bb", "b"), erg)            # zusammen 12 > 10 → „a“ geht
    assert ocr_sitzung._gemerkt(("bb", "a")) is None
    assert ocr_sitzung._gemerkt(("bb", "b")) is erg


def test_5_ein_gekuerztes_ergebnis_wird_nicht_gemerkt(monkeypatch):
    ocr_sitzung.leeren()
    aufrufe = []

    async def seiten_lesen(rumpf, **kw):
        aufrufe.append(1)
        return OcrErgebnis(markdown="# T", seiten=30, gelesen=20, gekuerzt=True, versucht=20)

    async def null():
        return 0

    async def buchen(acc):
        return None

    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)
    for _ in range(2):
        asyncio.run(ocr_sitzung.leser(session_id="bb-1", budget=50, seiten_max=20, gebucht=null,
                                      buchen=buchen, frist_ende=time.monotonic() + 30)(b"x"))
    assert len(aufrufe) == 2


# ── 7: Codes des Kindprozesses ───────────────────────────────────────────

@pytest.mark.parametrize(("art", "abweisung"), [
    ("ausgelastet", Abweisung(503, "ausgelastet")),
    ("umwandlung_zu_langsam", Abweisung(400, "unlesbar")),
    ("umwandlung_zu_gross", Abweisung(413, "zu_gross")),
    ("text_zu_lang", Abweisung(413, "zu_gross")),
    ("datei", Abweisung(400, "unlesbar")),
])
def test_7_fehler_beim_rendern_werden_zu_codes(monkeypatch, art, abweisung):
    async def scheitert(*_a, **_k):
        return Umwandlungsfehler("Fehler", art=art)

    async def fast_leer(*_a, **_k):
        return Gewandelt(markdown="", seiten=1, gekuerzt=False)

    async def sauber(_t):
        return {"flagged": False}

    async def lesen(rumpf):
        return await ocr.seiten_lesen(rumpf, seiten_max=1, frist_ende=time.monotonic() + 60,
                                      usage_acc=None)

    monkeypatch.setattr(ocr, "im_kind_mit_datei", scheitert)
    monkeypatch.setattr(aufnahme, "wandle", fast_leer)
    erg = asyncio.run(aufnahme.aufbereiten(b"%PDF-1.4", "scan.pdf", max_seiten=10, frist_s=5,
                                           moderieren=sauber, ocr_lesen=lesen))
    assert erg == abweisung


# ── 8: OcrGrenze ohne DB-Import ──────────────────────────────────────────

def test_8_die_aufnahme_kennt_die_grenze_aus_ocr_ohne_die_datenbank():
    import ast
    import inspect

    assert ocr_sitzung.OcrGrenze is ocr.OcrGrenze
    baum = ast.parse(inspect.getsource(aufnahme))
    importe = {n.module for n in ast.walk(baum) if isinstance(n, ast.ImportFrom)}
    assert "boerdi.services.dokumente.ocr_sitzung" not in importe


# ── 10: JPEG-Größe ───────────────────────────────────────────────────────

def test_10_eine_verrauschte_seite_wird_kleiner_kodiert():
    _seiten, [jpeg] = ocr_rendern.bilder(_rauschen(), 1)
    assert 0 < len(jpeg) <= ocr_rendern.MAX_JPEG_BYTES
