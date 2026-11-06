"""Paket U3-2a: ein hochgeladenes Dokument umwandeln — Grenzen, Frist, Temp-Datei, Wartedeckel.

Seit dem Review U3-2 (Befund 2) prüft und parst nur der Kindprozess (:func:`pruefe_und_wandle`);
die Attrappe ``_Kind`` führt ihn im eigenen Prozess aus, ``wandle_datei`` ist ersetzt.
"""

from __future__ import annotations

import asyncio
import io
import os
import zipfile

import pytest

from boerdi.services.dokumente import umwandlung
from boerdi.services.rag import umwandeln_kind
from boerdi.services.rag.umwandeln_fehler import Umwandlungsfehler


def _pdf(seiten: int) -> bytes:
    """Ein minimales PDF mit ``/Count`` — mehr liest die Seitenprüfung nicht."""
    koerper = (b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
               b"2 0 obj << /Type /Pages /Kids [] /Count " + str(seiten).encode() + b" >> endobj\n")
    xref = len(koerper)
    return (koerper + b"xref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n"
            b"0000000058 00000 n \ntrailer << /Size 3 /Root 1 0 R >>\nstartxref\n"
            + str(xref).encode() + b"\n%%EOF\n")


@pytest.fixture
def gewandelt(monkeypatch):
    """``wandle_datei`` ersetzt: merkt sich die Aufrufe, liefert einen Text (oder einen Fehler)."""
    aufrufe: list[tuple[str, bool]] = []
    antwort = {"text": "# Lehrplan\nInhalt"}

    def wandle_datei(pfad, vorgeprueft=False):
        aufrufe.append((pfad, vorgeprueft))
        assert os.path.exists(pfad)
        return antwort["text"]

    monkeypatch.setattr(umwandlung, "wandle_datei", wandle_datei)
    return aufrufe, antwort


class _Kind:
    """Attrappe des Kindprozesses: führt die Funktion im eigenen Prozess aus (oder schläft)."""

    def __init__(self, schlafen: float = 0.0) -> None:
        self.schlafen, self.pfade = schlafen, []

    async def __call__(self, funktion, *args):  # noqa: ANN001 — Signatur von im_kindprozess
        self.pfade.append(args[0])
        if self.schlafen:
            await asyncio.sleep(self.schlafen)
        return funktion(*args)


def _wandle(rumpf, art, kind, **mehr):
    return asyncio.run(umwandlung.wandle(rumpf, art, max_seiten=mehr.pop("max_seiten", 300),
                                         frist_s=mehr.pop("frist_s", 5), ausfuehren=kind, **mehr))


def test_pdf_geht_durch_den_kindprozess_und_die_temp_datei_ist_danach_weg(gewandelt):
    kind = _Kind()
    erg = _wandle(_pdf(3), "pdf", kind)
    assert not isinstance(erg, Umwandlungsfehler)
    assert erg.markdown.startswith("# Lehrplan") and erg.seiten == 3 and erg.gekuerzt is False
    assert kind.pfade[0].endswith(".pdf")                # Endung aus der Art, nie aus dem Namen
    assert not os.path.exists(os.path.dirname(kind.pfade[0]))
    assert gewandelt[0] == [(kind.pfade[0], True)]        # kein zweites Parsen in wandle_datei


def test_zu_viele_seiten_ohne_umwandlung(gewandelt):
    erg = _wandle(_pdf(301), "pdf", _Kind())
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "zu_viele_seiten" and erg.wert == 300
    assert gewandelt[0] == []


def test_zip_bombe_im_kind_ohne_umwandlung(gewandelt, monkeypatch):
    monkeypatch.setattr(umwandeln_kind, "MAX_EINTRAEGE", 3)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for i in range(5):
            z.writestr(f"word/x{i}.xml", "x")
    erg = _wandle(puffer.getvalue(), "docx", _Kind())
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "entpackt_zu_gross"
    assert gewandelt[0] == []


def test_text_und_markdown_ohne_kindprozess():
    kind = _Kind()
    erg = _wandle("﻿# Titel\nÄpfel".encode(), "md", kind)
    assert erg.markdown == "# Titel\nÄpfel" and erg.seiten is None
    assert kind.pfade == []


def test_zu_langer_text_wird_gekuerzt(gewandelt):
    gewandelt[1]["text"] = "x" * (umwandlung.MAX_ZEICHEN + 10)
    erg = _wandle(_pdf(1), "pdf", _Kind())
    assert len(erg.markdown) == umwandlung.MAX_ZEICHEN and erg.gekuerzt is True


def test_ein_trenner_im_text_bleibt_text(gewandelt):
    gewandelt[1]["text"] = "a\x1eb"
    assert _wandle(_pdf(2), "pdf", _Kind()).markdown == "a\x1eb"


def test_die_letzte_wache_ergibt_zu_langsam_und_raeumt_auf(gewandelt, monkeypatch):
    monkeypatch.setattr(umwandlung, "PLATZ_FRIST_S", 0.0)
    monkeypatch.setattr(umwandlung, "_PUFFER_S", 0.0)
    kind = _Kind(schlafen=2.0)
    erg = _wandle(_pdf(1), "pdf", kind, frist_s=0.05)
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "umwandlung_zu_langsam"
    assert not os.path.exists(os.path.dirname(kind.pfade[0]))
    assert umwandlung._wartende == 0


def test_ein_fehler_der_umwandlung_kommt_durch_und_raeumt_auf(gewandelt):
    gewandelt[1]["text"] = Umwandlungsfehler("kaputt", art="datei")
    kind = _Kind()
    erg = _wandle(_pdf(1), "pdf", kind)
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "datei"
    assert not os.path.exists(os.path.dirname(kind.pfade[0]))


def test_mehr_als_drei_wartende_sind_ausgelastet(gewandelt):
    async def ablauf():
        kind = _Kind(schlafen=0.3)
        laeufe = [umwandlung.wandle(_pdf(1), "pdf", max_seiten=300, frist_s=5, ausfuehren=kind)
                  for _ in range(5)]
        return await asyncio.gather(*laeufe)

    ergebnisse = asyncio.run(ablauf())
    ausgelastet = [e for e in ergebnisse
                   if isinstance(e, Umwandlungsfehler) and e.art == "ausgelastet"]
    assert len(ausgelastet) >= 1
    assert len([e for e in ergebnisse if not isinstance(e, Umwandlungsfehler)]) >= 3
    assert umwandlung._wartende == 0


def test_kein_temp_verzeichnis_haelt_den_zaehler_nicht_fest(monkeypatch):
    """Review Befund 5: ein voller Datenträger darf den Wartedeckel nicht dauerhaft belegen."""
    def voll(**_k):
        raise OSError("kein Platz")

    monkeypatch.setattr(umwandlung.tempfile, "mkdtemp", voll)
    erg = _wandle(_pdf(1), "pdf", _Kind())
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "server"
    assert umwandlung._wartende == 0


def test_temp_verzeichnis_ist_nur_fuer_den_prozess_lesbar(gewandelt):
    if os.name == "nt":
        pytest.skip("Rechte 0700 prüft nur ein POSIX-System")

    async def gucken(funktion, pfad, max_seiten):  # noqa: ANN001
        assert oct(os.stat(os.path.dirname(pfad)).st_mode & 0o777) == "0o700"
        return "\x1eok"

    assert _wandle(_pdf(1), "pdf", gucken).markdown == "ok"


def test_text_ohne_utf8_und_mit_nul_wird_lesbar():
    erg = _wandle("Grüße\x00!".encode("cp1252"), "txt", _Kind())
    assert erg.markdown == "Grüße!"


def test_der_platz_hat_eine_eigene_wartegrenze():
    """Review Befund 4: wer den Platz nicht bekommt, wartet nicht die Frist der Umwandlung ab."""
    async def ablauf():
        platz = umwandeln_kind._einer()
        await platz.acquire()
        try:
            return await umwandeln_kind.im_kindprozess(len, "x", frist_s=5, platz_frist_s=0.05)
        finally:
            platz.release()

    erg = asyncio.run(ablauf())
    assert isinstance(erg, Umwandlungsfehler) and erg.art == "ausgelastet"
