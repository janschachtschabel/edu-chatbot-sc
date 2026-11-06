"""Art eines hochgeladenen Dokuments (Paket U3-2a, Plan 2026-11-04 §16.6) — am Inhalt erkannt.

Nie an der Endung oder am ``Content-Type`` des Browsers: markitdown wählt seinen Wandler auch nach
der Endung, und eine umbenannte Datei soll nicht in einen anderen Wandler laufen. Die Endung
der temporären Datei kommt deshalb aus der erkannten Art (:data:`ENDUNG`). Zugelassen sind PDF,
DOCX (ZIP mit ``[Content_Types].xml`` und ``word/document.xml``) sowie UTF-8-Text (TXT; MD nur,
wenn der Name auf ``.md`` endet). Bilder werden eigens erkannt, damit die Person einen passenden
Satz bekommt.
Rein, ohne I/O.
"""

from __future__ import annotations

import io
import zipfile
from typing import Final, Literal

DokumentArt = Literal["pdf", "docx", "txt", "md"]

ENDUNG: Final[dict[str, str]] = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt", "md": ".md"}

_BILD_KOEPFE: Final = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"GIF87a", b"GIF89a")
#: So viel Text wird auf NUL-Bytes und gültiges UTF-8 geprüft.
_TEXT_PROBE: Final = 64 * 1024


def ist_bild(kopf: bytes) -> bool:
    if any(kopf.startswith(k) for k in _BILD_KOEPFE):
        return True
    if kopf[:4] == b"RIFF" and kopf[8:12] == b"WEBP":
        return True
    anfang = kopf[:256].lstrip().lower()
    return anfang.startswith(b"<svg") or (anfang.startswith(b"<?xml") and b"<svg" in anfang)


def _zip_namen(rumpf: bytes) -> set[str] | None:
    try:
        with zipfile.ZipFile(io.BytesIO(rumpf)) as z:
            return set(z.namelist())
    except (zipfile.BadZipFile, OSError, ValueError):
        return None


def _ist_text(rumpf: bytes) -> bool:
    probe = rumpf[:_TEXT_PROBE]
    if not probe or b"\x00" in probe:
        return False
    try:
        probe.decode("utf-8")
    except UnicodeDecodeError as fehler:
        # Abgeschnitten mitten in einem Zeichen ist kein Fehler des Textes.
        return fehler.start >= len(probe) - 3 and len(rumpf) > _TEXT_PROBE
    return True


def erkenne(rumpf: bytes, name: str) -> DokumentArt | None:
    """Die Art des Dokuments — ``None`` für alles, was kein zugelassenes Dokument ist."""
    if rumpf.startswith(b"%PDF-"):
        return "pdf"
    if rumpf.startswith(b"PK\x03\x04"):
        namen = _zip_namen(rumpf)
        return "docx" if namen and {"[Content_Types].xml", "word/document.xml"} <= namen else None
    if ist_bild(rumpf[:512]) or not _ist_text(rumpf):
        return None
    return "md" if name.lower().endswith(".md") else "txt"
