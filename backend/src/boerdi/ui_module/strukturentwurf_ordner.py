"""Ordner → Entwurf (Paket U3-1b, Plan 2026-11-04 §16.5): die Ordnerstruktur aus ``ui_upload`` als
Strukturentwurf, ohne LLM.

Gegenstück zu ``strukturentwurf_bestand`` (WLO-Sammlung → Entwurf). Ordner werden Punkte, Dateien
nicht (sie sind Inhalte, keine Gliederung). Namen werden bereinigt: führende Nummern (``01_``,
``1.2 ``) und Unterstriche fallen weg — bleibt davon nichts übrig, bleibt der Name. Höchstens drei
Ebenen und die Deckel jedes Entwurfs (``ui_module/strukturentwurf``); was wegfällt, meldet
``gekuerzt``. Die Kennungen entstehen der Reihe nach (``k1``, ``k1-1`` …), derselbe Baum ergibt
dieselben Kennungen — die spätere Zuordnung von Inhalten zu Punkten baut darauf auf.

Plan 2026-11-16, TG-3f (Nutzer: „enthaltene Inhalte werden erschlossen oder/und gemerkt“): Trägt
der Baum die Dateien je Ordner (``dateiliste``, Teil ``struktur``), bekommt jeder Punkt die Inhalte
seines Ordners als Verweise — ``inhalte: [{i, name, node_id?}]``:

- **gemerkt** — ``i`` (die feste Nummer der Auswahl) und der Dateiname, auch anonym;
- **erschlossen** — dazu ``node_id``, sobald die Datei nach WLO übertragen ist (Teil ``ablage``,
  verknüpft über ``i``, TG-3b); Metadaten liegen im Teil ``metadaten`` unter derselben ``i``.

Nur Dateien mit der Rolle ``inhalt`` (oder ``beides``, P1): reine Strukturdokumente sind keine
Inhalte, ignorierte gehen nicht mit. Die Dateien eines Ordners unter der dritten Ebene gehören
zum tiefsten Punkt darüber (der Ordner fällt weg, die Inhalte nicht). Dateien direkt in der Wurzel
haben keinen Punkt. Das spätere Befüllen („Sammlungen 1:1“) liest diese Verweise.
"""

from __future__ import annotations

import re
from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.rollen import ist_material

#: Ebenen des Entwurfs aus Ordnern (Wurzel nicht mitgezählt); tiefere Ordner fallen weg.
TIEFE: Final = 3
_NUMMER: Final = re.compile(r"^\d+(?:[._-]\d+)*[\s._-]+")
_NODE: Final = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}$")


def sauberer_name(roh: str) -> str:
    """``01_Mechanik`` → ``Mechanik``, ``1.2 Kräfte_und_Bewegung`` → ``Kräfte und Bewegung``."""
    eine_zeile = " ".join(str(roh).split())
    ohne = " ".join(_NUMMER.sub("", eine_zeile).replace("_", " ").split())
    return (ohne or eine_zeile)[:se.TITEL_ZEICHEN]


def knoten_ids(ablage: Any) -> dict[int, str]:
    """TG-3f: ``i`` → node_id der abgelegten Dateien (Teil ``ablage``; auch aus einem ersetzten
    Stapel nicht — dort fehlt ``i``, TG-3b)."""
    if not isinstance(ablage, dict):
        return {}
    return {e["i"]: e["node_id"] for e in ablage.get("inhalte") or []
            if isinstance(e, dict) and e.get("stand") == "stored"
            and isinstance(e.get("i"), int) and not isinstance(e.get("i"), bool)
            and isinstance(e.get("node_id"), str) and _NODE.match(e["node_id"])}


class _Zaehler:
    def __init__(self, knoten: dict[int, str]) -> None:
        self.knoten = 0
        self.gekuerzt = False
        self.vergeben: set[str] = set()
        self.ids = knoten
        self.inhalte = 0


def _inhalte(ordner: dict[str, Any], z: _Zaehler) -> list[dict[str, Any]]:
    """Die Inhaltsdateien dieses Ordners (P1: auch ``beides``) als Verweise (bis zur Grenze des
    Entwurfs)."""
    aus: list[dict[str, Any]] = []
    for d in ordner.get("dateiliste") or []:
        if not isinstance(d, dict) or not ist_material(d.get("rolle")):
            continue
        i, name = d.get("i"), " ".join(str(d.get("name") or "").split())[:se.TITEL_ZEICHEN]
        if not isinstance(i, int) or isinstance(i, bool) or not name:
            continue
        if z.inhalte >= se.HOECHSTENS_INHALTE:
            z.gekuerzt = True
            break
        eintrag: dict[str, Any] = {"i": i, "name": name}
        if (node_id := z.ids.get(i)) is not None:
            eintrag["node_id"] = node_id
        aus.append(eintrag)
        z.inhalte += 1
    return aus


def _darunter(ordner: Any, z: _Zaehler) -> list[dict[str, Any]]:
    """TG-3f: die Inhalte aller Ordner unter einem Punkt der letzten Ebene."""
    aus: list[dict[str, Any]] = []
    for k in ordner if isinstance(ordner, list) else []:
        if isinstance(k, dict):
            aus += _inhalte(k, z) + _darunter(k.get("kinder"), z)
    return aus


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
        inhalte = _inhalte(roh, z)
        unter = roh.get("kinder")
        if isinstance(unter, list) and unter:
            if ebene >= TIEFE:
                z.gekuerzt = True
                inhalte += _darunter(unter, z)      # die Ordner fallen weg, ihre Inhalte nicht
            elif kinder_k := _punkte(unter, k["id"], ebene + 1, z):
                k["kinder"] = kinder_k
        if inhalte:
            k["inhalte"] = inhalte
        punkte.append(k)
    return punkte


def aus_ordnern(struktur: Any, *, ersatz_titel: str = "Gliederung aus Ordnern",
                ablage: Any = None, quelle_block: str | None = None) -> dict[str, Any] | None:
    """Block-Daten von ``ui_strukturentwurf`` (``quelle: ordner``) — ``None`` ohne Unterordner.
    ``ersatz_titel`` für die künstliche Wurzel (mehrere Ordner gewählt), in der Sprache der
    Person. TG-3f: ``ablage`` (der Teil) ergänzt die node_ids der übertragenen Dateien.
    Nachprüfung TG-3d–f, MINOR 2: ``quelle_block`` (die block_id der Auswahl) steht im Entwurf —
    beim Speichern verknüpft der Server Inhalte und Ablage nur bei derselben Auswahl."""
    if not isinstance(struktur, dict):
        return None
    z = _Zaehler(knoten_ids(ablage))
    knoten = _punkte(struktur.get("kinder"), None, 1, z)
    if not knoten:
        return None
    titel = sauberer_name(struktur.get("name") or "") or ersatz_titel
    daten: dict[str, Any] = {"titel": titel, "quelle": "ordner"}
    if z.gekuerzt:
        daten["gekuerzt"] = True
    if quelle_block:
        daten["quelle_block"] = quelle_block
    daten["knoten"] = knoten
    return daten
