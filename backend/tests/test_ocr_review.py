"""Review Paket C (2026-11-19): Befunde zur Texterkennung — Pixelbombe und Kindprozess (1),
gemeinsamer Deckel (2), Grenze und Zwischenspeicher je Sitzung (3), Frist je Rolle (4),
nicht renderbare Seiten (5), Tabellenkopf (6), Nenner nach der Texterkennung (7), Bildgröße (8),
Buchung im ``finally`` (14), abgeschnittene Antwort (15)."""

from __future__ import annotations

import asyncio
import io
import time
import zlib
from types import SimpleNamespace

import pypdfium2 as pdfium
import pytest

from boerdi.services.dokumente import aufnahme, ocr, ocr_rendern, ocr_sitzung
from boerdi.services.dokumente.aufnahme import Abweisung, Aufbereitet
from boerdi.services.dokumente.ocr import OcrErgebnis
from boerdi.services.dokumente.umwandlung import Gewandelt
from tests import pg_utils


def _pdf(seiten: int = 1, breite: float = 595, hoehe: float = 842) -> bytes:
    dok = pdfium.PdfDocument.new()
    for _ in range(seiten):
        dok.new_page(breite, hoehe)
    puffer = io.BytesIO()
    dok.save(puffer)
    return puffer.getvalue()


def _bildbombe(kante: int) -> bytes:
    """Eine kleine PDF mit einem riesigen, stark gepackten Graustufenbild (wie im Review)."""
    packer = zlib.compressobj(9)
    zeile = b"\x80" * kante
    daten = b"".join(packer.compress(zeile) for _ in range(kante)) + packer.flush()
    objekte = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /XObject << /Im0 4 0 R"
        b" >> >> /Contents 5 0 R >>",
        b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceGray "
        b"/BitsPerComponent 8 /Filter /FlateDecode /Length %d >>\nstream\n"
        % (kante, kante, len(daten))
        + daten + b"\nendstream",
    ]
    inhalt = b"q 595 0 0 842 0 0 cm /Im0 Do Q"
    objekte.append(b"<< /Length %d >>\nstream\n" % len(inhalt) + inhalt + b"\nendstream")
    pdf, stellen = b"%PDF-1.4\n", []
    for i, o in enumerate(objekte):
        stellen.append(len(pdf))
        pdf += b"%d 0 obj\n" % (i + 1) + o + b"\nendobj\n"
    xref = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % s for s in stellen)
    pdf += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objekte) + 1, xref))
    return pdf


def _lauf(rumpf: bytes, lesen, *, seiten_max: int = 20, frist_s: float = 60.0):
    return asyncio.run(ocr.seiten_lesen(rumpf, seiten_max=seiten_max,
                                        frist_ende=time.monotonic() + frist_s,
                                        usage_acc=None, lesen=lesen))


async def _null() -> int:
    return 0


async def _buchen(_acc) -> None:
    return None


async def _nie(jpeg, usage_acc, frist_s):
    raise AssertionError("eine Seite ohne Bild darf nicht ans Modell")


# ── 1 + 8: Rendern im Kindprozess, Pixelbudget, Bildgröße ─────────────────

def test_1_bildbombe_wird_nicht_dekodiert_und_der_elternprozess_bleibt_schlank():
    import psutil

    prozess = psutil.Process()
    vorher = prozess.memory_info().rss
    erg = _lauf(_bildbombe(9000), _nie)            # 81 MP > Budget je Seite
    assert (erg.seiten, erg.gelesen, erg.unrenderbar, erg.fehlend) == (1, 0, 1, 0)
    assert prozess.memory_info().rss - vorher < 100 * 1024 * 1024


def test_1_das_rendern_laeuft_im_kindprozess(monkeypatch):
    aufrufe = []
    echt = ocr.im_kind_mit_datei

    async def spion(funktion, *args, **kw):
        aufrufe.append(funktion)
        return await echt(funktion, *args, **kw)

    monkeypatch.setattr(ocr, "im_kind_mit_datei", spion)

    async def lesen(jpeg, usage_acc, frist_s):
        return "Text"

    assert _lauf(_pdf(2), lesen).gelesen == 2
    assert aufrufe == [ocr_rendern.seiten_rendern]


def test_1_ein_ausgelasteter_kindprozess_ist_voruebergehend(monkeypatch):
    from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler

    async def voll(*_a, **_k):
        return Umwandlungsfehler("Fehler: Umwandlung ausgelastet", art="ausgelastet")

    monkeypatch.setattr(ocr, "im_kind_mit_datei", voll)
    erg = _lauf(_pdf(1), _nie)
    assert erg.gelesen == 0 and erg.fehlend == 1 and erg.unrenderbar == 0


def test_8_eine_riesige_seite_wird_hoechstens_max_pixel_gross():
    from PIL import Image

    seiten, bilder = ocr_rendern.bilder(_pdf(1, 14400, 14400), 5)
    assert seiten == 1 and len(bilder) == 1
    assert max(Image.open(io.BytesIO(bilder[0])).size) <= ocr_rendern.MAX_PIXEL


def test_8_das_pixelbudget_prueft_eingebettete_bilder_ohne_sie_zu_dekodieren():
    seiten, bilder = ocr_rendern.bilder(_bildbombe(9000), 5)
    assert (seiten, bilder) == (1, [b""])


# ── 2: ein Deckel für alle Texterkennungen zusammen ───────────────────────

def test_2_zwei_gleichzeitige_scans_teilen_sich_den_deckel(monkeypatch):
    monkeypatch.setattr(ocr, "anbieter_deckel", lambda: 4)       # parallel() == 2
    laufend = hoechstens = 0

    async def lesen(jpeg, usage_acc, frist_s):
        nonlocal laufend, hoechstens
        laufend += 1
        hoechstens = max(hoechstens, laufend)
        await asyncio.sleep(0.05)
        laufend -= 1
        return "Text"

    async def beide():
        rumpf = _pdf(3)
        ende = time.monotonic() + 60
        return await asyncio.gather(
            *(ocr.seiten_lesen(rumpf, seiten_max=3, frist_ende=ende, usage_acc=None,
                               lesen=lesen) for _ in range(2)))

    a, b = asyncio.run(beide())
    assert a.gelesen == b.gelesen == 3
    assert hoechstens == 2


# ── 3: Grenze und Zwischenspeicher je Sitzung ─────────────────────────────

def test_3_dieselbe_datei_in_derselben_sitzung_wird_nur_einmal_gelesen(monkeypatch):
    ocr_sitzung.leeren()
    aufrufe = []

    async def seiten_lesen(rumpf, **kw):
        aufrufe.append(kw["seiten_max"])
        return OcrErgebnis(markdown="# Text", seiten=2, gelesen=2, gekuerzt=False, versucht=2)

    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)

    def leser(sitzung: str, rest: int):
        return ocr_sitzung.leser(session_id=sitzung, budget=rest, seiten_max=20, gebucht=_null,
                                 buchen=_buchen, frist_ende=time.monotonic() + 30)

    asyncio.run(leser("bb-1", 50)(b"%PDF scan"))
    asyncio.run(leser("bb-1", 50)(b"%PDF scan"))
    asyncio.run(leser("bb-2", 50)(b"%PDF scan"))              # andere Sitzung: neu
    assert aufrufe == [20, 20]
    # die Grenze der Sitzung deckelt die Seiten
    asyncio.run(leser("bb-3", 7)(b"%PDF anderer scan"))
    assert aufrufe[-1] == 7


def test_3_ohne_seitenbudget_weist_die_aufnahme_mit_grenze_ocr_ab(monkeypatch):
    ocr_sitzung.leeren()

    async def fast_leer(*_a, **_k):
        return Gewandelt(markdown="", seiten=2, gekuerzt=False)

    async def sauber(_t):
        return {"flagged": False}

    monkeypatch.setattr(aufnahme, "wandle", fast_leer)
    lesen = ocr_sitzung.leser(session_id="bb-1", budget=0, seiten_max=20, gebucht=_null,
                              buchen=_buchen, frist_ende=time.monotonic() + 30)
    erg = asyncio.run(aufnahme.aufbereiten(b"%PDF-1.4 scan", "scan.pdf", max_seiten=300,
                                           frist_s=5, moderieren=sauber, ocr_lesen=lesen))
    assert erg == Abweisung(429, "grenze_ocr")


def test_3_unvollstaendige_ergebnisse_werden_nicht_zwischengespeichert(monkeypatch):
    ocr_sitzung.leeren()
    aufrufe = []

    async def seiten_lesen(rumpf, **kw):
        aufrufe.append(1)
        return OcrErgebnis(markdown="# T", seiten=2, gelesen=1, gekuerzt=True, fehlend=1,
                           versucht=2)

    monkeypatch.setattr(ocr, "seiten_lesen", seiten_lesen)
    for _ in range(2):
        asyncio.run(ocr_sitzung.leser(session_id="bb-1", budget=50, seiten_max=20, gebucht=_null,
                                      buchen=_buchen, frist_ende=time.monotonic() + 30)(b"x"))
    assert len(aufrufe) == 2


@pytest.mark.pg
@pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON)
def test_3_gebuchte_seiten_zaehlen_nur_die_texterkennung_der_sitzung():
    from boerdi.db.models import ChatSession, UsageEvent
    from boerdi.db.session import make_engine, make_session_factory
    from boerdi.settings import Settings

    db = "boerdi_ocr_budget_test"
    pg_utils.create_migrated_db(db)

    async def szenario() -> tuple[int, int]:
        engine = make_engine(Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(db)))
        try:
            async with make_session_factory(engine)() as s:
                s.add_all([ChatSession(session_id="bb-ocr-1"), ChatSession(session_id="bb-ocr-2")])
                await s.flush()
                s.add_all([
                    UsageEvent(session_id="bb-ocr-1", model="m", calls=18, quelle=ocr.PHASE),
                    UsageEvent(session_id="bb-ocr-1", model="m", calls=3, quelle=ocr.PHASE),
                    UsageEvent(session_id="bb-ocr-1", model="m", calls=40),          # Chat
                    UsageEvent(session_id="bb-ocr-2", model="m", calls=5, quelle=ocr.PHASE),
                ])
                await s.commit()
                return (await ocr_sitzung.seiten_gebucht(s, "bb-ocr-1"),
                        await ocr_sitzung.seiten_gebucht(s, "bb-ocr-neu"))
        finally:
            await engine.dispose()

    try:
        assert asyncio.run(szenario()) == (21, 0)
    finally:
        pg_utils.drop_db(db)


# ── 5 + 7: Ergebnis der Texterkennung in der Aufnahme ─────────────────────

def _aufnahme(monkeypatch, gewandelt_seiten: int, ergebnis: OcrErgebnis):
    async def fast_leer(*_a, **_k):
        return Gewandelt(markdown="", seiten=gewandelt_seiten, gekuerzt=False)

    async def sauber(_t):
        return {"flagged": False}

    async def lesen(_r):
        return ergebnis

    monkeypatch.setattr(aufnahme, "wandle", fast_leer)
    return asyncio.run(aufnahme.aufbereiten(b"%PDF-1.4 scan", "scan.pdf", max_seiten=300,
                                            frist_s=5, moderieren=sauber, ocr_lesen=lesen))


def test_5_nichts_renderbar_ist_unlesbar_nicht_ausgelastet(monkeypatch):
    erg = _aufnahme(monkeypatch, 2, OcrErgebnis(markdown="", seiten=2, gelesen=0, gekuerzt=True,
                                                versucht=2, unrenderbar=2))
    assert erg == Abweisung(400, "unlesbar")


def test_7_der_nenner_sind_die_gelesenen_seiten(monkeypatch):
    text = ("Lernfeld eins beschreibt Gesteine und ihre Aufbereitung im Betrieb. " * 6).strip()
    erg = _aufnahme(monkeypatch, 30, OcrErgebnis(markdown=f"{text}\n\n{text}", seiten=30,
                                                 gelesen=2, gekuerzt=True, versucht=20))
    assert isinstance(erg, Aufbereitet)
    assert "wenig_text" not in erg.befund["warnungen"]
    assert erg.befund["seiten"] == 30


# ── 6: Tabellenkopf bleibt ────────────────────────────────────────────────

def test_6_ein_tabellenkopf_auf_jeder_seite_ist_kein_seitenkopf():
    seiten = iter(["| Lernziele | Lerninhalte |\n|---|---|\n| A | B |",
                   "| Lernziele | Lerninhalte |\n|---|---|\n| C | D |",
                   "| Lernziele | Lerninhalte |\n|---|---|\n| E | F |"])

    async def lesen(jpeg, usage_acc, frist_s):
        return next(seiten)

    md = _lauf(_pdf(3), lesen).markdown
    assert md.count("| Lernziele | Lerninhalte |") == 3


# ── 15: abgeschnittene Antwort ───────────────────────────────────────────

def test_15_eine_abgeschnittene_antwort_macht_das_ergebnis_gekuerzt(monkeypatch):
    from boerdi.services import llm

    async def chat_completion(**_kw):
        return SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="length", message=SimpleNamespace(content="# Halb"))])

    monkeypatch.setattr(llm, "chat_completion", chat_completion)
    erg = _lauf(_pdf(1), None)
    assert (erg.gelesen, erg.abgeschnitten, erg.gekuerzt, erg.markdown) == (1, 1, True, "# Halb")
