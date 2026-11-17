"""Teile aus einer geprüften Modul-Antwort (aus ``arbeitsstand`` gelöst, Querschnitts-Review
2026-11-06, Q4): nur, was das Manifest dem Modul erlaubt (``vorgang.schreibt``), in der Normalform
des Moduls — rein, ohne I/O.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.services.dokumente import strukturdokument_teil as sd
from boerdi.ui_module import katalog
from boerdi.ui_module import upload_antwort as upload
from boerdi.ui_module.namen import STRUKTURENTWURF, UPLOAD
from boerdi.ui_module.rahmen import zeile

_ANTWORT_MERKER: Final = ("uebernommen", "bearbeitet")
#: Plan 2026-11-16, Nachprüfung TG-2: die Teile, die ein Modul BEREITSTELLT (Daten der Person, kein
#: Ergebnis eines Laufs). Schließt ein Start einen Vorgang (``zug._ziel_vorbereiten``: Lauf beendet
#: oder fremd), nimmt der neue sie mit — die Person lädt nicht erneut hoch. TG-3a: ``struktur``
#: (die Auswahl mit Dateien); TG-3d: ``strukturdokument`` (die Verweise auf alle gelesenen bzw.
#: abgelegten Strukturdokumente); ``ablage`` (Knoten im Repositorium) nicht, mit Blick auf N14 (ein
#: schreibender Ablauf beginnt frisch, ``frisch``) — die Verweise auf die Strukturdokumente in WLO
#: gehen über ``strukturdokument`` mit.
BEREITSTELLUNG: Final[tuple[str, ...]] = ("structure", "struktur", "document", sd.TEIL)
#: Plan 2026-11-16, TG-3a: der Teil mit dem vollen Ordnerbaum samt Dateien je Ordner.
AUSWAHL: Final = "wlo.auswahl@1"

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
    erlaubt (``vorgang.schreibt``), in der Normalform des Moduls. simplify: heute
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
        # Plan 2026-11-16, TG-3a: ``structure`` bleibt die Sicht nur mit Ordnern (wie vor TG-3a) —
        # laufende Abläufe und ``strukturentwurf_aus_ordnern`` lesen sie weiter
        teile: list[Teil] = [(
            "structure", "wlo.ordnerbaum@1",
            {"struktur": upload.ohne_dateien(daten["struktur"]), "zahlen": z},
            f"{int(z.get('ordner') or 0)} Ordner, {int(z.get('inhalte') or 0)} Inhalte")]
        if satz := upload.dateien_satz(daten):
            # TG-3a: der volle Baum mit den Dateien je Ordner (feste Nummer ``i``), nur wenn das
            # Widget sie schickt — eine Antwort von vorher ergäbe sonst eine leere Auswahl
            # Review TG-3a–c, R3-2: die block_id der Auswahl — ``ablage`` trägt die des Felds,
            # das die Dateien übertragen hat; verknüpft wird nur bei gleicher (``auswahl_bindung``)
            wert = {"struktur": daten["struktur"], "zahlen": z,
                    "warnungen": list(daten.get("warnungen") or [])}
            if isinstance(geprueft.get("block_id"), str):
                wert["block_id"] = geprueft["block_id"]
            teile.append(("struktur", AUSWAHL, wert, satz))
        if daten.get("aktion") == "dokument" and (gelesen := upload.gelesene(daten)):
            # ``document`` bleibt der Rückwärts-Teil mit dem ersten Dokument (Abläufe und Seeds vor
            # TG-3d lesen ihn); TG-3d: ``strukturdokument`` verweist auf alle gelesenen
            dok = gelesen[0]
            befund = dok.get("befund") or {}
            teile.append((
                "document", "wlo.dokument-verweis@1",
                {k: dok.get(k) for k in ("upload_id", "name", "format", "befund")},
                f"{zeile(dok.get('name'), 80)}, {int(befund.get('abschnitte') or 0)} Abschnitte"))
            liste = [sd.chatbot(str(d.get("upload_id")), d.get("name")) for d in gelesen
                     if isinstance(d.get("upload_id"), str)]
            if liste := sd.eintraege(sd.wert(liste)):
                teile.append((sd.TEIL, sd.TYP, sd.wert(liste), sd.zusammenfassung(liste)))
        return teile
    if geprueft.get("modul") == STRUKTURENTWURF and isinstance(daten.get("knoten"), list):
        wert = {k: v for k, v in daten.items() if k not in _ANTWORT_MERKER}
        return [("draft", "wlo.sammlungsstruktur@1", wert,
                 f"„{zeile(daten.get('titel'), 60)}“, {_punkte(daten['knoten'])} Punkte")]
    return []


def gebunden(struktur: Any, ablage: Any) -> bool:
    """Review TG-3a–c, R3-2: gehören die Auswahl (Teil ``struktur``) und die Ablage (Teil
    ``ablage``) zusammen — dasselbe Upload-Feld (``block_id``)? Nur dann verknüpft ``i`` eine Datei
    der Auswahl mit einem Knoten; eine neue Auswahl oder eine Ablage aus einem anderen Feld vergibt
    die Nummern anders. Ohne ``block_id`` an einem der beiden (Stand vor R3-2): nicht verknüpft."""
    if not isinstance(struktur, dict) or not isinstance(ablage, dict):
        return False
    kennung = struktur.get("block_id")
    return isinstance(kennung, str) and bool(kennung) and kennung == ablage.get("block_id")


def _titel(teile: list[Teil]) -> str:
    for name, _typ, wert, _z in teile:
        kandidat = {"structure": (wert.get("struktur") or {}).get("name"),
                    "struktur": (wert.get("struktur") or {}).get("name"),
                    "document": wert.get("name"), "draft": wert.get("titel"),
                    sd.TEIL: next(iter(sd.eintraege(wert)), {}).get("name")}.get(name)
        if kandidat := zeile(kandidat, 120):
            return kandidat
    return "Vorgang"
