"""Paket U3-2a: Art eines hochgeladenen Strukturdokuments am Inhalt erkennen, nie an der Endung."""

from __future__ import annotations

import io
import zipfile

import pytest

from boerdi.domain.dokument_art import ENDUNG, erkenne, ist_bild


def _zip(*namen: str) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        for n in namen:
            z.writestr(n, "x")
    return puffer.getvalue()


def test_pdf_am_anfang():
    assert erkenne(b"%PDF-1.7\n...", "lehrplan.docx") == "pdf"   # die Endung täuscht nicht


def test_docx_braucht_content_types_und_word_dokument():
    assert erkenne(_zip("[Content_Types].xml", "word/document.xml"), "x.pdf") == "docx"
    assert erkenne(_zip("[Content_Types].xml", "ppt/presentation.xml"), "x.docx") is None
    assert erkenne(_zip("irgendwas.txt"), "x.docx") is None


_BILDER = [b"\x89PNG\r\n\x1a\n....", b"\xff\xd8\xff\xe0", b"GIF89a....",
           b"RIFF\x00\x00\x00\x00WEBP", b"<svg xmlns=", b"  <?xml version='1.0'?><svg"]


@pytest.mark.parametrize("kopf", _BILDER)
def test_bilder_sind_bilder_und_keine_dokumente(kopf):
    assert ist_bild(kopf) is True
    assert erkenne(kopf, "bild.pdf") is None


def test_text_und_markdown_nach_namen():
    assert erkenne("# Lehrplan\nÄpfel".encode(), "plan.md") == "md"
    assert erkenne(b"# Lehrplan", "plan.pdf") == "txt"
    assert erkenne("\ufeffMit BOM".encode(), "plan.MD") == "md"


@pytest.mark.parametrize("rumpf", [b"", b"abc\x00def", b"\xff\xfe\xfa kaputt"])
def test_leer_nul_oder_kein_utf8_ist_nichts(rumpf):
    assert erkenne(rumpf, "x.txt") is None


def test_endungen_aus_der_art():
    assert ENDUNG == {"pdf": ".pdf", "docx": ".docx", "txt": ".txt", "md": ".md"}
