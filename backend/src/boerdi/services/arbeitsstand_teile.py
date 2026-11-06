"""Teile aus einer geprüften Modul-Antwort (aus ``arbeitsstand`` gelöst, Querschnitts-Review
2026-11-06, Q4): nur, was das Manifest dem Modul erlaubt (``vorgang.schreibt``), in der Normalform
des Moduls — rein, ohne I/O.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.ui_module import katalog
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from boerdi.ui_module.rahmen import zeile

_ANTWORT_MERKER: Final = ("uebernommen", "bearbeitet")

Teil = tuple[str, str, Any, str]   # (Name, Typ, Wert, Kurzbeschreibung)


def _punkte(knoten: Any) -> int:
    if not isinstance(knoten, list):
        return 0
    return sum(1 + _punkte(k.get("kinder")) for k in knoten if isinstance(k, dict))


def _schreibt(modul: Any) -> list[str]:
    """Die Teile, die das Manifest dem Modul erlaubt (``vorgang.schreibt``, Paket V2)."""
    manifest = katalog.katalog().get(modul) if isinstance(modul, str) else None
    namen = ((manifest or {}).get("vorgang") or {}).get("schreibt") or []
    return [n for n in namen if isinstance(n, str)]


def teile_aus_antwort(geprueft: dict[str, Any] | None) -> list[Teil]:
    """Was eine geprüfte Antwort als Teile hinterlässt — nur Teile, die das Manifest dem Modul
    erlaubt (``vorgang.schreibt``), in der Normalform des Moduls (ohne Dateinamen). simplify: heute
    ``ui_upload`` und ``ui_strukturentwurf``; ein weiteres Modul bekommt seine Normalform, wenn es
    ``schreibt`` braucht (Review V2, Befund 6: ein allgemeiner Teil ohne Labels nützte nichts)."""
    if not geprueft:
        return []
    erlaubt = _schreibt(geprueft.get("modul"))
    return [t for t in _teile(geprueft) if t[0] in erlaubt]


def _teile(geprueft: dict[str, Any]) -> list[Teil]:
    daten = geprueft.get("daten") or {}
    if geprueft.get("modul") == UPLOAD and isinstance(daten.get("struktur"), dict):
        z = daten.get("zahlen") or {}
        teile: list[Teil] = [(
            "structure", "wlo.ordnerbaum@1",
            {"struktur": daten["struktur"], "zahlen": z},
            f"{int(z.get('ordner') or 0)} Ordner, {int(z.get('inhalte') or 0)} Inhalte")]
        if daten.get("aktion") == "dokument" and isinstance(dok := daten.get("dokument"), dict):
            befund = dok.get("befund") or {}
            teile.append((
                "document", "wlo.dokument-verweis@1",
                {k: dok.get(k) for k in ("upload_id", "name", "format", "befund")},
                f"{zeile(dok.get('name'), 80)}, {int(befund.get('abschnitte') or 0)} Abschnitte"))
        return teile
    if geprueft.get("modul") == STRUKTURENTWURF and isinstance(daten.get("knoten"), list):
        wert = {k: v for k, v in daten.items() if k not in _ANTWORT_MERKER}
        return [("draft", "wlo.sammlungsstruktur@1", wert,
                 f"„{zeile(daten.get('titel'), 60)}“, {_punkte(daten['knoten'])} Punkte")]
    return []


def _titel(teile: list[Teil]) -> str:
    for name, _typ, wert, _z in teile:
        kandidat = {"structure": (wert.get("struktur") or {}).get("name"),
                    "document": wert.get("name"), "draft": wert.get("titel")}.get(name)
        if kandidat := zeile(kandidat, 120):
            return kandidat
    return "Vorgang"
