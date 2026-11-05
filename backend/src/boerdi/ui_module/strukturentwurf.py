"""Daten des Strukturentwurfs (Paket U2, Plan 2026-11-04 T-3/T-8) — ``wlo.sammlungsstruktur@1``.

Der Entwurf ist eine NEUE Gliederung (von der KI erzeugt oder aus einer WLO-Sammlung übernommen
und bearbeitbar), anders als der Themenbaum (``ui_module/themenbaum``), der nur Bestand zeigt.
Schema: ``frontend/projects/ui-module/src/ui-strukturentwurf/manifest.json`` (``eingabe``); die
Tiefe prüft schon das Schema (``ebene1`` … ``ebene4``). Was es nicht ausdrücken kann — Gesamtzahl,
eindeutige Kennungen — prüft :func:`fehler`.

Fach und Bildungsstufe sind Klartext-Labels (T-8): im Backend gibt es keine Abbildung auf die
URIs des WLO-Vokabulars (der MCP-Server löst Labels auf). Die Bildungsstufe nur aus der festen
Liste der WLO-Labels, sonst gar nicht — ein geratener Wert sähe aus wie ein erkannter.

Rein und ohne I/O.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final

HOECHSTENS_OBEN: Final = 30
HOECHSTENS_KINDER: Final = 15
HOECHSTE_TIEFE: Final = 4
HOECHSTENS_KNOTEN: Final = 250
TITEL_ZEICHEN: Final = 120
BESCHREIBUNG_ZEICHEN: Final = 300
KEYWORDS: Final = 8
KEYWORD_ZEICHEN: Final = 40
FACH_ZEICHEN: Final = 60
KENNUNG: Final = r"^[A-Za-z0-9_-]{1,40}$"

#: Die Bildungsstufen-Labels des WLO-Vokabulars (wie in den Werkzeugbeschreibungen,
#: ``services/mcp/tool_defs``) — und die Schreibweisen, die Modell und Person dafür nehmen.
BILDUNGSSTUFEN: Final = ("Elementarbereich", "Primarstufe", "Sekundarstufe I", "Sekundarstufe II",
                         "Berufliche Bildung", "Hochschule", "Erwachsenenbildung", "Fortbildung")
_SYNONYME: Final = {
    "grundschule": "Primarstufe", "kita": "Elementarbereich", "kindergarten": "Elementarbereich",
    "sekundarstufe 1": "Sekundarstufe I", "sek i": "Sekundarstufe I", "sek 1": "Sekundarstufe I",
    "sekundarstufe 2": "Sekundarstufe II", "sek ii": "Sekundarstufe II",
    "sek 2": "Sekundarstufe II", "oberstufe": "Sekundarstufe II",
    "berufsschule": "Berufliche Bildung", "universität": "Hochschule",
    "weiterbildung": "Fortbildung",
}
_STUFEN: Final = {s.lower(): s for s in BILDUNGSSTUFEN} | _SYNONYME


def _text(wert: Any, deckel: int) -> str:
    return " ".join(wert.split())[:deckel] if isinstance(wert, str) else ""


def bildungsstufe(wert: Any) -> str | None:
    """Das WLO-Label einer Bildungsstufe — oder ``None``, wenn es keines ist."""
    return _STUFEN.get(_text(wert, 80).lower()) or None


def fach(wert: Any) -> str | None:
    """Ein Fach als kurzes Label (≤ 60 Zeichen) — oder ``None``."""
    text = _text(wert, FACH_ZEICHEN + 1)
    return text if text and len(text) <= FACH_ZEICHEN else None


def _keywords(wert: Any) -> list[str]:
    if not isinstance(wert, list):
        return []
    aus: list[str] = []
    for w in wert:
        text = _text(w, KEYWORD_ZEICHEN)
        if text and text.lower() not in {a.lower() for a in aus}:
            aus.append(text)
    return aus[:KEYWORDS]


def knoten_aus(roh: Any, kennung: str, *, wurzel: dict[str, Any]) -> dict[str, Any] | None:
    """Ein bereinigter Knoten OHNE Kinder aus Modell- oder WLO-Daten; ``None`` ohne Titel.

    Fach und Bildungsstufe nur, wenn erkannt und anders als an der ``wurzel``."""
    if not isinstance(roh, dict) or not (titel := _text(roh.get("titel"), TITEL_ZEICHEN)):
        return None
    knoten: dict[str, Any] = {"id": kennung, "titel": titel}
    if beschreibung := _text(roh.get("beschreibung"), BESCHREIBUNG_ZEICHEN):
        knoten["beschreibung"] = beschreibung
    if keywords := _keywords(roh.get("keywords")):
        knoten["keywords"] = keywords
    for feld, form in (("fach", fach), ("bildungsstufe", bildungsstufe)):
        if (wert := form(roh.get(feld))) and wert != wurzel.get(feld):
            knoten[feld] = wert
    return knoten


def _eine_zeile(wert: Any) -> Any:
    return " ".join(wert.split()) if isinstance(wert, str) else wert


def normalisiert(daten: dict[str, Any]) -> dict[str, Any]:
    """Eine neue Kopie, in der jeder Text eine Zeile ist (Review U2, Befund 4): Titel,
    Beschreibungen, Schlagworte und Wurzel-Angaben der Person beginnen im Rahmen an die KI
    keine eigene Zeile — eine Rahmen-Startzeile ließe sich sonst nachbilden."""
    def knoten(k: dict[str, Any]) -> dict[str, Any]:
        neu = {f: _eine_zeile(w) for f, w in k.items() if f not in ("keywords", "kinder")}
        if isinstance(k.get("keywords"), list):
            neu["keywords"] = [_eine_zeile(w) for w in k["keywords"]]
        if isinstance(k.get("kinder"), list):
            neu["kinder"] = [knoten(c) if isinstance(c, dict) else c for c in k["kinder"]]
        return neu

    aus = {f: _eine_zeile(w) for f, w in daten.items() if f != "knoten"}
    if isinstance(daten.get("knoten"), list):
        aus["knoten"] = [knoten(k) if isinstance(k, dict) else k for k in daten["knoten"]]
    return aus


def alle(knoten: list[dict[str, Any]], ebene: int = 1) -> Iterator[tuple[dict[str, Any], int]]:
    """Jeder Knoten mit seiner Ebene, in Lesereihenfolge."""
    for k in knoten:
        yield k, ebene
        yield from alle(k.get("kinder") or [], ebene + 1)


def anzahl(knoten: list[dict[str, Any]]) -> int:
    return sum(1 for _ in alle(knoten))


def fehler(daten: dict[str, Any]) -> list[str]:
    """Was das Schema nicht prüft: Gesamtzahl, Tiefe (auch ohne Schema), eindeutige Kennungen."""
    aus: list[str] = []
    gesehen: set[str] = set()
    for k, ebene in alle(daten.get("knoten") or []):
        if ebene > HOECHSTE_TIEFE:
            aus.append(f"{k.get('id')}: zu tief (Ebene {ebene}, höchstens {HOECHSTE_TIEFE})")
        if (kennung := k.get("id")) in gesehen:
            aus.append(f"Kennung „{kennung}“ doppelt")
        gesehen.add(kennung)
    if (zahl := anzahl(daten.get("knoten") or [])) > HOECHSTENS_KNOTEN:
        aus.append(f"{zahl} Knoten, höchstens {HOECHSTENS_KNOTEN}")
    return aus


def neue_kennung(eltern: str | None, vergeben: set[str]) -> str:
    """Die nächste freie Kennung unter ``eltern`` (``k1`` → ``k1-1``, ``k1-2`` …; oben ``k1``,
    ``k2`` …) — und gleich vergeben."""
    praefix = f"{eltern}-" if eltern else "k"
    nummer = 1
    while f"{praefix}{nummer}" in vergeben:
        nummer += 1
    kennung = f"{praefix}{nummer}"
    if len(kennung) > 40:                 # tiefe Pfade aus langen WLO-Kennungen
        kennung = f"k{len(vergeben) + 1}"
        while kennung in vergeben:
            kennung += "x"
    vergeben.add(kennung)
    return kennung
