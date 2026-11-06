"""Ordner → Entwurf (Paket U3-1b, Plan 2026-11-04 §16.5): die Ordnerstruktur aus ``ui_upload`` als
Strukturentwurf, ohne LLM.

Gegenstück zu ``strukturentwurf_bestand`` (WLO-Sammlung → Entwurf). Ordner werden Punkte, Dateien
nicht (sie sind Inhalte, keine Gliederung). Namen werden bereinigt: führende Nummern (``01_``,
``1.2 ``) und Unterstriche fallen weg — bleibt davon nichts übrig, bleibt der Name. Höchstens drei
Ebenen und die Deckel jedes Entwurfs (``ui_module/strukturentwurf``); was wegfällt, meldet
``gekuerzt``. Die Kennungen entstehen der Reihe nach (``k1``, ``k1-1`` …), derselbe Baum ergibt
dieselben Kennungen — die spätere Zuordnung von Inhalten zu Punkten baut darauf auf.
"""

from __future__ import annotations

import re
from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se

#: Ebenen des Entwurfs aus Ordnern (Wurzel nicht mitgezählt); tiefere Ordner fallen weg.
TIEFE: Final = 3
_NUMMER: Final = re.compile(r"^\d+(?:[._-]\d+)*[\s._-]+")


def sauberer_name(roh: str) -> str:
    """``01_Mechanik`` → ``Mechanik``, ``1.2 Kräfte_und_Bewegung`` → ``Kräfte und Bewegung``."""
    eine_zeile = " ".join(str(roh).split())
    ohne = " ".join(_NUMMER.sub("", eine_zeile).replace("_", " ").split())
    return (ohne or eine_zeile)[:se.TITEL_ZEICHEN]


class _Zaehler:
    def __init__(self) -> None:
        self.knoten = 0
        self.gekuerzt = False
        self.vergeben: set[str] = set()


def _punkte(kinder: Any, eltern: str | None, ebene: int, z: _Zaehler) -> list[dict[str, Any]]:
    if not isinstance(kinder, list):
        return []
    deckel = se.HOECHSTENS_OBEN if eltern is None else se.HOECHSTENS_KINDER
    if len(kinder) > deckel:
        z.gekuerzt = True
    punkte: list[dict[str, Any]] = []
    for roh in kinder[:deckel]:
        if z.knoten >= se.HOECHSTENS_KNOTEN:
            z.gekuerzt = True
            break
        if not isinstance(roh, dict) or not (titel := sauberer_name(roh.get("name") or "")):
            continue
        k: dict[str, Any] = {"id": se.neue_kennung(eltern, z.vergeben), "titel": titel}
        z.knoten += 1
        unter = roh.get("kinder")
        if isinstance(unter, list) and unter:
            if ebene >= TIEFE:
                z.gekuerzt = True
            elif kinder_k := _punkte(unter, k["id"], ebene + 1, z):
                k["kinder"] = kinder_k
        punkte.append(k)
    return punkte


def aus_ordnern(struktur: Any, *, ersatz_titel: str = "Gliederung aus Ordnern"
                ) -> dict[str, Any] | None:
    """Block-Daten von ``ui_strukturentwurf`` (``quelle: ordner``) — ``None`` ohne Unterordner.
    ``ersatz_titel`` für die künstliche Wurzel (mehrere Ordner gewählt), in der Sprache der
    Person."""
    if not isinstance(struktur, dict):
        return None
    z = _Zaehler()
    knoten = _punkte(struktur.get("kinder"), None, 1, z)
    if not knoten:
        return None
    titel = sauberer_name(struktur.get("name") or "") or ersatz_titel
    daten: dict[str, Any] = {"titel": titel, "quelle": "ordner"}
    if z.gekuerzt:
        daten["gekuerzt"] = True
    daten["knoten"] = knoten
    return daten
