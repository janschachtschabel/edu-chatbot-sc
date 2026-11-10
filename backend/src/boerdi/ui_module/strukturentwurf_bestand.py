"""Bestand → Entwurf (Paket U2, Plan 2026-11-04 T-13): eine WLO-Sammlung als Strukturentwurf.

Aus dem Ergebnis von ``browse_collection_tree`` (zwei Ebenen, Vorgaben des Themenbaums) wird ein
bearbeitbarer Entwurf — ohne LLM. Anders als der Themenbaum (``ui_module/themenbaum``, nur fünf
Felder) übernimmt er Beschreibung und Schlagworte und merkt sich je Punkt die Kennung der
WLO-Sammlung (``wlo_id``), damit eine spätere Übergabe weiß, was es schon gibt.

Gedeckelt wie jeder Entwurf (``ui_module/strukturentwurf``); wo der Bestand mehr hat, steht
``gekuerzt``.

Dazu (Paket AS-Dd) die Brücke zum Anlegen: :func:`baum_aus_entwurf` macht aus dem Entwurf den Baum
für ``wlo_create_collection_tree``, :func:`mit_kennungen` trägt danach je Punkt die Kennung seiner
Sammlung ein — dasselbe Feld ``wlo_id``.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.themenbaum import KNOTEN_UUID

_UUID: Final = re.compile(KNOTEN_UUID)


def _wlo_id(wert: Any) -> str | None:
    # ganz, nicht nur am Anfang: ``$`` ließe ein Zeilenende durch (Review AS-Dd)
    return wert if isinstance(wert, str) and _UUID.fullmatch(wert) else None


def _punkt(roh: Any, eltern: str | None, vergeben: set[str]) -> dict[str, Any] | None:
    if not isinstance(roh, dict):
        return None
    k = se.knoten_aus({"titel": roh.get("title"), "beschreibung": roh.get("description"),
                       "keywords": roh.get("keywords")}, "", wurzel={})
    if k is None:
        return None
    k["id"] = se.neue_kennung(eltern, vergeben)
    if wlo := _wlo_id(roh.get("nodeId")):
        k["wlo_id"] = wlo
    return k


def aus_bestand(payload: Any, titel: str, *, ersatz_titel: str = "Gliederung aus WLO"
                ) -> dict[str, Any] | None:
    """Block-Daten von ``ui_strukturentwurf`` (``quelle: wlo``) — oder ``None`` ohne Punkte.
    ``ersatz_titel`` ohne Titel, in der Sprache der Person (``action.draft.ohneTitel``)."""
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        return None
    vergeben: set[str] = set()
    zahl = 0
    gekuerzt = payload.get("truncated") is True or len(payload["results"]) > se.HOECHSTENS_OBEN
    knoten: list[dict[str, Any]] = []
    for roh in payload["results"][:se.HOECHSTENS_OBEN]:
        if zahl >= se.HOECHSTENS_KNOTEN:
            gekuerzt = True
            break
        if (k := _punkt(roh, None, vergeben)) is None:
            continue
        zahl += 1
        kinder_roh = roh.get("children") if isinstance(roh.get("children"), list) else []
        gekuerzt = gekuerzt or roh.get("hasMoreChildren") is True
        gekuerzt = gekuerzt or len(kinder_roh) > se.HOECHSTENS_KINDER
        kinder = []
        for kind_roh in kinder_roh[:se.HOECHSTENS_KINDER]:
            if zahl >= se.HOECHSTENS_KNOTEN:
                gekuerzt = True
                break
            if kind := _punkt(kind_roh, k["id"], vergeben):
                kinder.append(kind)
                zahl += 1
        if kinder:
            k["kinder"] = kinder
        knoten.append(k)
    if not knoten:
        return None
    ueberschrift = " ".join(titel.split())[:se.TITEL_ZEICHEN] if isinstance(titel, str) else ""
    daten: dict[str, Any] = {"titel": ueberschrift or ersatz_titel, "quelle": "wlo"}
    if wurzel := _wlo_id(payload.get("parent")):
        daten["wurzel_wlo_id"] = wurzel
    if gekuerzt:
        daten["gekuerzt"] = True
    daten["knoten"] = knoten
    return daten


#: So viele Einträge des Anlage-Ergebnisses werden gelesen (der Server legt höchstens 250 an).
_HOECHSTENS_ANGELEGT: Final = 500


def _schluessel(pfad: str) -> str:
    """Der Pfad, wie der Server Titel vergleicht (``normTitle``: Rand, Leerraum, Groß/Klein) — je
    Glied. Ein Titel mit „/“ zerfällt auf beiden Seiten gleich."""
    return "/".join(" ".join(t.split()).lower() for t in pfad.split("/"))


def _kennungen(nodes: list[Any]) -> dict[str, str | None]:
    """Pfadschlüssel → Kennung aus dem Anlage-Ergebnis; ``None``: mehrdeutig (Review AS-Dd,
    Befund 4 — der Server hält „a/B“ und „A“→„B“ getrennt, der Schlüssel nicht). Eine Kennung gilt
    unabhängig vom Status (``failed`` mit ``code: exists`` trägt die vorhandene Sammlung)."""
    kennungen: dict[str, str | None] = {}
    for n in nodes[:_HOECHSTENS_ANGELEGT]:
        if isinstance(n, dict) and isinstance(n.get("path"), str) and (
                wlo := _wlo_id(n.get("nodeId"))):
            schluessel = _schluessel(n["path"])
            kennungen[schluessel] = wlo if kennungen.get(schluessel, wlo) == wlo else None
    return kennungen


def _punkte(knoten: list[Any]) -> list[tuple[dict[str, Any], str]]:
    """Jeder Punkt mit seinem Pfadschlüssel, in Baumreihenfolge."""
    aus: list[tuple[dict[str, Any], str]] = []
    stapel: list[tuple[Any, str]] = [(k, "") for k in reversed(knoten)]
    while stapel:
        k, eltern = stapel.pop()
        if not isinstance(k, dict) or not isinstance(k.get("titel"), str):
            continue
        pfad = f"{eltern}/{_schluessel(k['titel'])}" if eltern else _schluessel(k["titel"])
        aus.append((k, pfad))
        if isinstance(k.get("kinder"), list):
            stapel.extend((c, pfad) for c in reversed(k["kinder"]))
    return aus


def mit_kennungen(entwurf: Any, angelegt: Any) -> dict[str, Any] | None:
    """Eine Kopie von ``entwurf`` (``wlo.sammlungsstruktur@1``), deren Punkte die Kennung ihrer
    angelegten Sammlung in ``wlo_id`` tragen — oder ``None``, wenn Entwurf oder Ergebnis fehlen
    oder kein Punkt eine Kennung bekam (dann gilt ``bei_fehler``; Review AS-Dd, Befund 3).

    ``angelegt`` ist das Ergebnis von ``wlo_create_collection_tree`` (``{nodes: [{path, nodeId?,
    status}]}``) oder dessen Liste ``nodes``. Zugeordnet wird über den Titelpfad (Titel mit „/“
    verbunden, unter der Elternsammlung, ``collection-tree.ts``). Nur Kennungen in UUID-Form;
    mehrdeutige Pfade bekommen keine. Alte Kennungen (``wlo_id``, ``wurzel_wlo_id``, etwa aus
    einem Entwurf aus dem Bestand) fallen weg — sie zeigten auf die Quellsammlung (Befund 2)."""
    nodes = angelegt.get("nodes") if isinstance(angelegt, dict) else angelegt
    if not (isinstance(entwurf, dict) and isinstance(entwurf.get("knoten"), list)
            and isinstance(nodes, list)):
        return None
    kennungen = _kennungen(nodes)
    neu = copy.deepcopy(entwurf)
    neu.pop("wurzel_wlo_id", None)
    punkte = _punkte(neu["knoten"])
    je_pfad: dict[str, int] = {}
    for _k, pfad in punkte:
        je_pfad[pfad] = je_pfad.get(pfad, 0) + 1
    verbunden = False
    for k, pfad in punkte:
        k.pop("wlo_id", None)
        if je_pfad[pfad] == 1 and (wlo := kennungen.get(pfad)):
            k["wlo_id"] = wlo
            verbunden = True
    return neu if verbunden else None


def baum_aus_entwurf(entwurf: Any) -> list[dict[str, Any]] | None:
    """Der Baum für ``wlo_create_collection_tree`` (``[{title, description?, children?}]``) aus
    einem Entwurf — mit genau dessen Titeln, damit :func:`mit_kennungen` danach jeden Punkt
    findet (Review AS-Dd, Befund 5: eine Auswahl kann ``titel`` nicht in ``title`` umbenennen).
    ``None`` ohne Punkte."""

    def baum(knoten: Any, ebene: int) -> list[dict[str, Any]]:
        aus: list[dict[str, Any]] = []
        for k in knoten if isinstance(knoten, list) else []:
            if not isinstance(k, dict) or not isinstance(k.get("titel"), str) or not (
                    titel := k["titel"].strip()):
                continue
            punkt: dict[str, Any] = {"title": titel}
            if isinstance(k.get("beschreibung"), str) and k["beschreibung"].strip():
                punkt["description"] = k["beschreibung"].strip()
            # tiefer als ein Entwurf sein darf, geht nichts (der Server prüft seine Grenzen selbst)
            if ebene < se.HOECHSTE_TIEFE and (kinder := baum(k.get("kinder"), ebene + 1)):
                punkt["children"] = kinder
            aus.append(punkt)
        return aus

    if not isinstance(entwurf, dict):
        return None
    return baum(entwurf.get("knoten"), 1) or None
