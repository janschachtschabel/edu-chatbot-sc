"""Die Umwandlung im eigenen Prozess — Frist, Vorprüfung, einer zugleich (Paket 9).

Review Paket 7 (MAJOR 6, V4): markitdown lief im Chat-Prozess ohne Zeit-, Speicher-
oder Seitengrenze, beliebig viele zugleich, und entpackte eine ``.zip`` samt allen
Einträgen. Die Kindprozess-Tests starten echte Prozesse (``spawn``, je etwa zwei
Sekunden).
"""

from __future__ import annotations

import asyncio
import io
import logging
import time
import zipfile

import pytest

from boerdi.services.rag import umwandeln_kind as kind
from boerdi.services.rag.umwandeln import Umwandlungsfehler, convert_to_markdown
from boerdi.settings import get_settings
from tests import helfer_umwandeln as helfer


def _zip(**eintraege: bytes) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in eintraege.items():
            z.writestr(name, inhalt)
    return puffer.getvalue()


class TestVorpruefung:
    def test_ein_zip_container_wird_nach_entpackter_groesse_geprueft(self, monkeypatch):
        """Ein DOCX ist ein ZIP: drei Megabyte Nullen packen sich auf wenige Kilobyte."""
        bombe = _zip(**{"word/document.xml": b"\0" * (3 * 1024 * 1024)})
        assert len(bombe) < 50_000
        monkeypatch.setattr(kind, "MAX_ENTPACKT_MB", 2)
        fehler = kind.vorpruefung(bombe)
        assert isinstance(fehler, Umwandlungsfehler) and fehler.art == "entpackt_zu_gross"
        monkeypatch.setattr(kind, "MAX_ENTPACKT_MB", 5)
        assert kind.vorpruefung(bombe) is None

    def test_zu_viele_eintraege(self, monkeypatch):
        monkeypatch.setattr(kind, "MAX_EINTRAEGE", 20)
        fehler = kind.vorpruefung(_zip(**{f"x{i}.txt": b"a" for i in range(30)}))
        assert fehler is not None and fehler.art == "entpackt_zu_gross"

    def test_ein_pdf_wird_nach_seitenzahl_geprueft(self, monkeypatch, tmp_path):
        pdf = tmp_path / "drei.pdf"
        pdf.write_bytes(helfer.pdf_mit_seiten(3))
        monkeypatch.setattr(kind, "MAX_PDF_SEITEN", 2)
        fehler = kind.vorpruefung(str(pdf))
        assert fehler is not None and fehler.art == "zu_viele_seiten" and fehler.wert == 2
        monkeypatch.setattr(kind, "MAX_PDF_SEITEN", 3)
        assert kind.vorpruefung(str(pdf)) is None

    def test_anderes_und_kaputtes_geht_durch(self, tmp_path):
        # Kein Urteil ohne Befund — die Umwandlung meldet selbst, was sie nicht liest.
        assert kind.vorpruefung(b"Hallo, Welt") is None
        assert kind.vorpruefung(b"%PDF-1.4 kaputt") is None
        assert kind.vorpruefung(b"PK\x03\x04 kaputt") is None


class TestUmbenannteVariablen:
    """2026-10-28: alle Variablennamen englisch. Die alten deutschen Namen wirken
    übergangsweise weiter — eine bestehende Anlage darf ihren Wert nicht still verlieren."""

    def test_der_alte_name_wirkt_weiter_der_neue_gewinnt(self, monkeypatch):
        from boerdi.settings import Settings

        monkeypatch.setenv("RAG_UMWANDLUNG_FRIST_S", "7")
        assert Settings().rag_conversion_timeout_s == 7.0
        monkeypatch.setenv("RAG_CONVERSION_TIMEOUT_S", "3")
        assert Settings().rag_conversion_timeout_s == 3.0

    def test_der_alte_name_wird_beim_start_gemeldet(self, monkeypatch, caplog):
        from boerdi.main import _warn_insecure_config
        from boerdi.settings import Settings

        monkeypatch.setenv("RAG_UMWANDLUNG_MAX_MB", "512")
        with caplog.at_level(logging.WARNING, logger="boerdi.main"):
            _warn_insecure_config(Settings())
        assert "RAG_UMWANDLUNG_MAX_MB" in caplog.text
        assert "RAG_CONVERSION_MAX_MB" in caplog.text


class TestKindprozess:
    def test_die_frist_beendet_den_kindprozess(self, monkeypatch):
        monkeypatch.setenv("RAG_CONVERSION_TIMEOUT_S", "4")
        get_settings.cache_clear()
        t0 = time.perf_counter()
        aus = asyncio.run(kind.im_kindprozess(helfer.schlafe, 60))
        assert isinstance(aus, Umwandlungsfehler) and aus.art == "umwandlung_zu_langsam"
        assert aus.wert == 4
        assert time.perf_counter() - t0 < 20

    def test_ein_fehler_im_kind_kommt_als_umwandlungsfehler(self):
        aus = asyncio.run(kind.im_kindprozess(helfer.wirft, None))
        assert isinstance(aus, Umwandlungsfehler) and aus.art == "datei"
        assert "kaputt im Kind" in aus.detail

    def test_zu_viel_text_bleibt_im_kind(self):
        """Review Paket 9 (MINOR 14): der ganze Text reiste per ``pickle`` in den
        Chat-Prozess, und der Import nahm ihn ungedeckelt — ein XLSX unter dem
        Upload-Deckel ergibt leicht Hunderte MB Markdown. Ab ``recv()`` galt die
        Speichergrenze des Kindes nicht mehr."""
        aus = asyncio.run(kind.im_kindprozess(helfer.langer_text, kind.MAX_TEXT_ZEICHEN + 1))
        assert isinstance(aus, Umwandlungsfehler) and aus.art == "text_zu_lang"
        assert aus.wert == kind.MAX_TEXT_ZEICHEN / 1_000_000

    def test_eine_echte_umwandlung_laeuft_im_kind(self, tmp_path):
        csv = tmp_path / "tabelle.csv"
        csv.write_text("Fach,Stufe\nPhysik,Sek I\n", encoding="utf-8")
        aus = asyncio.run(convert_to_markdown(str(csv)))
        assert not isinstance(aus, Umwandlungsfehler), aus
        assert "Physik" in aus and "|" in aus

    def test_immer_nur_eine_umwandlung_zugleich(self, monkeypatch):
        laufend = [0, 0]

        def _ausfuehren(funktion, args, frist_s, max_mb):
            laufend[0] += 1
            laufend[1] = max(laufend)
            time.sleep(0.05)
            laufend[0] -= 1
            return "ok"

        monkeypatch.setattr(kind, "_ausfuehren", _ausfuehren)

        async def _drei():
            return await asyncio.gather(*(kind.im_kindprozess(helfer.schlafe, 0)
                                          for _ in range(3)))

        assert asyncio.run(_drei()) == ["ok", "ok", "ok"]
        assert laufend[1] == 1


@pytest.fixture(autouse=True)
def _frische_einstellungen():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
