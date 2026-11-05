"""Bestand → Entwurf (Paket U2, Plan 2026-11-04 T-13): eine WLO-Sammlung als Strukturentwurf.

Aus dem Ergebnis von ``browse_collection_tree`` (zwei Ebenen, Vorgaben des Themenbaums) wird ein
bearbeitbarer Entwurf — ohne LLM. Anders als der Themenbaum (``ui_module/themenbaum``, nur fünf
Felder) übernimmt er Beschreibung und Schlagworte und merkt sich je Punkt die Kennung der
WLO-Sammlung (``wlo_id``), damit eine spätere Übergabe weiß, was es schon gibt.

Gedeckelt wie jeder Entwurf (``ui_module/strukturentwurf``); wo der Bestand mehr hat, steht
``gekuerzt``.
"""

from __future__ import annotations

import re
from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.themenbaum import KNOTEN_UUID

_UUID: Final = re.compile(KNOTEN_UUID)


def _wlo_id(wert: Any) -> str | None:
    return wert if isinstance(wert, str) and _UUID.match(wert) else None


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
