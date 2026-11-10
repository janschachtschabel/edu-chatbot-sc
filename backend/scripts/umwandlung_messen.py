"""P1 (Plan 2026-11-09 D9): der Chatbot-Weg der Umwandlung — Formate, Qualität, Dauer, Menge.

Erzeugt eigene Testdokumente (kein Download, keine fremden Dateien): PDF mit Textschicht, PDF nur
aus Bildern (Scan), DOCX, PPTX. Wandelt sie wie ein Upload um (``dokumente.umwandlung.wandle``,
Kindprozess) — ohne die übrige Aufbereitung (Bereinigung, Gliederung, Moderation). Jede Zeile trägt
eine Marke (``Z<seite>x<zeile>``); die Güte zählt gefundene Marken und ihre Reihenfolge. Ergebnis
und Deutung: ``docs/plans/2026-11-09-p1-chatbot-umwandlung.md``.

Aufruf aus ``backend/``: ``uv run python scripts/umwandlung_messen.py`` (rund 8 Minuten). Das
Skript hat einen eigenen Prozess und damit einen eigenen Umwandlungsplatz; es konkurriert aber um
CPU und Speicher. Auf dem vServer deshalb außerhalb der Betriebszeit und in einem eigenen Container
aus demselben Image mit eingebundenem Skript (das Image enthält ``scripts/`` nicht) — nicht im
laufenden Backend-Container.
"""
# ruff: noqa: E501 — die OOXML-Namensräume sind lange Literale
from __future__ import annotations

import asyncio
import io
import json
import statistics
import sys
import time
import zipfile

from boerdi.domain.dokument_art import erkenne
from boerdi.services.dokumente import umwandlung
from boerdi.services.rag.umwandeln import wandle_datei

WOERTER = ("Kompetenz Unterricht Lernende Fachbegriff Experiment Hypothese Beobachtung Auswertung "
           "Mechanik Optik Energie Bewegung Kraft Welle Brechung Linse Spiegel Messung Modell "
           "Thermodynamik Elektrizität Magnetfeld Spannung Stromstärke Widerstand").split()


def marke(start: int, i: int) -> str:
    return f"Z{start:03}x{i:03}"


def zeilen(n: int, start: int = 0) -> list[str]:
    return [marke(start, i) + " " + " ".join(WOERTER[(start + i * 7 + k) % len(WOERTER)]
                                              for k in range(10))
            for i in range(n)]


def marken(seiten: int, je_seite: int) -> list[str]:
    return [marke(s, i) for s in range(seiten) for i in range(je_seite)]


# ── PDF mit Textschicht (von Hand, Helvetica, WinAnsi) ──
def pdf(seiten: int, zeilen_je_seite: int = 45) -> bytes:
    objekte: list[bytes] = []

    def obj(inhalt: bytes) -> int:
        objekte.append(inhalt)
        return len(objekte)

    font = obj(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    seiten_platz = len(objekte) + 1 + seiten * 2   # Platzhalter für /Pages
    for s in range(seiten):
        text = [f"BT /F1 14 Tf 50 800 Td (Kapitel {s + 1}: Optik und Mechanik) Tj ET".encode()]
        y = 770
        for z in zeilen(zeilen_je_seite, s):
            text.append(f"BT /F1 10 Tf 50 {y} Td ({z}) Tj ET".encode("cp1252"))
            y -= 16
        strom = b"\n".join(text)
        inhalt = obj(b"<< /Length %d >>\nstream\n" % len(strom) + strom + b"\nendstream")
        kids.append(obj(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Contents %d 0 R "
                        b"/Resources << /Font << /F1 %d 0 R >> >> >>" % (seiten_platz, inhalt, font)))
    pages = obj(b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % k for k in kids)
                + b"] /Count %d >>" % seiten)
    assert pages == seiten_platz
    katalog = obj(b"<< /Type /Catalog /Pages %d 0 R >>" % pages)
    aus = io.BytesIO()
    aus.write(b"%PDF-1.4\n")
    stellen = []
    for i, o in enumerate(objekte, 1):
        stellen.append(aus.tell())
        aus.write(b"%d 0 obj\n" % i + o + b"\nendobj\n")
    xref = aus.tell()
    aus.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1))
    for st in stellen:
        aus.write(b"%010d 00000 n \n" % st)
    aus.write(b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
              % (len(objekte) + 1, katalog, xref))
    return aus.getvalue()


# ── PDF nur aus Bildern (Scan) ──
def scan_pdf(seiten: int) -> bytes:
    from PIL import Image, ImageDraw
    bilder = []
    for s in range(seiten):
        bild = Image.new("L", (1240, 1754), 255)
        zeichnen = ImageDraw.Draw(bild)
        for i, z in enumerate(zeilen(40, s)):
            zeichnen.text((80, 80 + i * 40), z, fill=0)
        bilder.append(bild)
    aus = io.BytesIO()
    bilder[0].save(aus, "PDF", save_all=True, append_images=bilder[1:], resolution=150)
    return aus.getvalue()


# ── DOCX (minimal, von Hand) ──
def docx(absaetze: int) -> bytes:
    def p(text: str, stil: str | None = None) -> str:
        pr = f'<w:pPr><w:pStyle w:val="{stil}"/></w:pPr>' if stil else ""
        return f"<w:p>{pr}<w:r><w:t>{text}</w:t></w:r></w:p>"

    rumpf = []
    for i, z in enumerate(zeilen(absaetze)):
        if i % 10 == 0:
            rumpf.append(p(f"Kapitel {i // 10 + 1}", "Heading1"))
        rumpf.append(p(z))
    tabelle = ("<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc><w:p><w:r><w:t>{WOERTER[(r + c) % len(WOERTER)]}</w:t></w:r></w:p></w:tc>"
                           for c in range(3)) + "</w:tr>" for r in range(4)) + "</w:tbl>")
    dokument = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body>{''.join(rumpf)}{tabelle}</w:body></w:document>")
    stile = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
             '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/></w:style>'
             "</w:styles>")
    typen = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
             "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>")
    doc_rels = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                "</Relationships>")
    aus = io.BytesIO()
    with zipfile.ZipFile(aus, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", typen)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", dokument)
        z.writestr("word/styles.xml", stile)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
    return aus.getvalue()


# ── PPTX ──
def pptx(folien: int) -> bytes:
    from pptx import Presentation
    praes = Presentation()
    for i in range(folien):
        folie = praes.slides.add_slide(praes.slide_layouts[1])
        folie.shapes.title.text = f"Folie {i + 1}: Optik"
        folie.placeholders[1].text = "\n".join(zeilen(6, i))
    aus = io.BytesIO()
    praes.save(aus)
    return aus.getvalue()


def guete(text: str, erwartet: list[str]) -> dict:
    """Anteil der gefundenen Marken und ob die gefundenen in ihrer Reihenfolge stehen."""
    if not erwartet:
        return {}
    stellen = [text.find(m) for m in erwartet]
    gefunden = [st for st in stellen if st >= 0]
    return {"guete": round(len(gefunden) / len(erwartet), 3),
            "reihenfolge": gefunden == sorted(gefunden)}


async def messen(name: str, rumpf: bytes, erwartet: list[str], frist_s: float = 60.0) -> dict:
    art = erkenne(rumpf, name)
    eintrag = {"datei": name, "kb": round(len(rumpf) / 1024), "art": getattr(art, "art", art)}
    art_name = art if isinstance(art, str) else getattr(art, "art", None)
    if art_name not in umwandlung.ENDUNG:
        eintrag["ergebnis"] = f"nicht zugelassen im Chat ({art_name})"
        return eintrag
    t = time.perf_counter()
    erg = await umwandlung.wandle(rumpf, art_name, max_seiten=300, frist_s=frist_s)
    eintrag["s"] = round(time.perf_counter() - t, 2)
    if isinstance(erg, umwandlung.Umwandlungsfehler):
        eintrag["ergebnis"] = f"Fehler {erg.art}"
        return eintrag
    eintrag.update(zeichen=len(erg.markdown), seiten=erg.seiten, gekuerzt=erg.gekuerzt,
                   ueberschriften=_ueberschriften(erg.markdown), tabellenzeilen=erg.markdown.count("\n|"),
                   **guete(erg.markdown, erwartet))
    return eintrag


def _ueberschriften(text: str) -> int:
    """Zeilen, die mit ``#`` beginnen — auch die erste (Review 2 zu P1, Befund 8)."""
    return sum(1 for z in text.splitlines() if z.lstrip().startswith("#"))


def direkt(name: str, rumpf: bytes, endung: str, erwartet: list[str]) -> dict:
    """Der RAG-Weg (``wandle_datei``) für Formate, die der Chat nicht zulässt."""
    import os
    import tempfile
    verzeichnis = tempfile.mkdtemp()
    pfad = os.path.join(verzeichnis, "d" + endung)
    try:
        with open(pfad, "wb") as f:
            f.write(rumpf)
        # ohne Kindprozess (~0,6 s), aber mit dem Laden von markitdown
        t = time.perf_counter()
        text = wandle_datei(pfad)
        dauer = round(time.perf_counter() - t, 2)
    finally:
        if os.path.exists(pfad):
            os.remove(pfad)
        os.rmdir(verzeichnis)
    if not isinstance(text, str) or text.startswith("Fehler"):
        return {"datei": name + " (RAG-Weg)", "s": dauer, "ergebnis": str(text)[:80]}
    return {"datei": name + " (RAG-Weg, ohne Kindprozess)", "s": dauer, "zeichen": len(text),
            "ueberschriften": _ueberschriften(text), **guete(text, erwartet)}


async def main() -> None:
    ergebnisse = []
    # P1-a Formate und Qualität
    for seiten in (10, 40, 120, 300):
        ergebnisse.append(await messen(f"lehrplan-{seiten}s.pdf", pdf(seiten), marken(seiten, 45)))
    ergebnisse.append(await messen("lehrplan-301s.pdf", pdf(301), []))
    ergebnisse.append(await messen("scan-5s.pdf", scan_pdf(5), marken(5, 40)))
    ergebnisse.append(await messen("material.docx", docx(400), marken(1, 400)))
    folien = pptx(30)
    ergebnisse.append(await messen("folien.pptx", folien, marken(30, 6)))
    ergebnisse.append(direkt("folien.pptx", folien, ".pptx", marken(30, 6)))
    for e in ergebnisse:
        print(json.dumps(e, ensure_ascii=False))
    # P1-b Menge: nacheinander durch den einen Platz
    for seiten, anzahl in ((40, 10), (120, 5)):
        rumpf = pdf(seiten)
        dauern = []
        fehler: dict[str, int] = {}
        t0 = time.perf_counter()
        for _ in range(anzahl):
            t = time.perf_counter()
            erg = await umwandlung.wandle(rumpf, "pdf", max_seiten=300, frist_s=60)
            # kein Abbruch: auf dem vServer reißt ein großes PDF die Frist — zählen, weitermessen
            # (Review 2 zu P1, Befund 10)
            if isinstance(erg, umwandlung.Umwandlungsfehler):
                fehler[erg.art] = fehler.get(erg.art, 0) + 1
            else:
                dauern.append(time.perf_counter() - t)
        gesamt = time.perf_counter() - t0
        print(json.dumps({"menge": f"{anzahl} x {seiten} Seiten nacheinander",
                          "gesamt_s": round(gesamt, 1),
                          "median_s": round(statistics.median(dauern), 2) if dauern else None,
                          "je_minute": round(len(dauern) / gesamt * 60, 1), "fehler": fehler},
                         ensure_ascii=False))
    # P1-b Menge: zugleich (zeigt den einen Platz und MAX_WARTENDE)
    rumpf = pdf(40)
    t0 = time.perf_counter()

    async def eine() -> tuple[object, float]:
        erg = await umwandlung.wandle(rumpf, "pdf", max_seiten=300, frist_s=60)
        return erg, time.perf_counter() - t0

    alle = await asyncio.gather(*(eine() for _ in range(6)))
    abgewiesen = [s for e, s in alle if isinstance(e, umwandlung.Umwandlungsfehler)
                  and e.art == "ausgelastet"]
    # sofort: ``MAX_WARTENDE``; nach etwa ``PLATZ_FRIST_S``: der Platz wurde nicht frei
    print(json.dumps({"menge": "6 x 40 Seiten zugleich", "gesamt_s": round(time.perf_counter() - t0, 1),
                      "ausgelastet_sofort": sum(1 for s in abgewiesen if s < 1.0),
                      "ausgelastet_nach_warten": sum(1 for s in abgewiesen if s >= 1.0),
                      "fertig": sum(1 for e, _s in alle if not isinstance(e, umwandlung.Umwandlungsfehler))},
                     ensure_ascii=False))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
