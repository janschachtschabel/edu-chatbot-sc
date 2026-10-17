"""Ziele für den Kindprozess der Umwandlung (``services/rag/umwandeln_kind``).

Eigenes Modul, weil der Kindprozess (``spawn``) sein Ziel über den Modulnamen
importiert — eine Funktion im Testmodul selbst zöge dessen Fixtures mit.
"""

from __future__ import annotations

import time


def schlafe(sekunden: float) -> str:
    time.sleep(sekunden)
    return "zu spät"


def wirft(_egal: object) -> str:
    raise RuntimeError("kaputt im Kind")


def pdf_mit_seiten(anzahl: int) -> bytes:
    """Ein kleinstes gültiges PDF mit ``anzahl`` leeren Seiten (samt Querverweisen)."""
    objekte = ["<< /Type /Catalog /Pages 2 0 R >>",
               "<< /Type /Pages /Kids [{}] /Count {} >>".format(
                   " ".join(f"{3 + i} 0 R" for i in range(anzahl)), anzahl)]
    objekte += ["<< /Type /Page /Parent 2 0 R /MediaBox [0 0 10 10] >>"] * anzahl
    daten = b"%PDF-1.4\n"
    lagen = []
    for nummer, inhalt in enumerate(objekte, start=1):
        lagen.append(len(daten))
        daten += f"{nummer} 0 obj {inhalt} endobj\n".encode()
    verweis = len(daten)
    daten += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode()
    daten += "".join(f"{lage:010d} 00000 n \n" for lage in lagen).encode()
    daten += (f"trailer << /Size {len(objekte) + 1} /Root 1 0 R >>\n"
              f"startxref\n{verweis}\n%%EOF\n").encode()
    return daten


def langer_text(zeichen: int) -> str:
    return "x" * zeichen
