"""Paket U4 (Plan 2026-11-08, E-6): ein Strukturentwurf gegen eine WLO-Sammlung — rein, ohne I/O.

Jeder Punkt des Entwurfs (Ebene 1 und 2) bekommt eine Art:

- ``vorhanden`` — eine Sammlung mit demselben Titel (nach :func:`normalisiert`);
- ``aehnlich`` — eine Sammlung mit Token-Jaccard ≥ :data:`AEHNLICH_AB` (die beste zuerst);
- ``neu`` — nichts Passendes; ``ungewiss``, wenn der Baum dort gekürzt ist (der Server liefert bei
  Tiefe 2 nur einige Kinder je Sammlung, ``hasMoreChildren``) — dann heißt es „nicht gefunden“.

Jede WLO-Sammlung wird höchstens einem Punkt zugeordnet; was übrig bleibt, ist ``nur_in_wlo``.
Ebene 1 wird gegen Ebene 1 abgeglichen. Ebene 2 zuerst unter der zugeordneten Sammlung des
Elternpunkts, danach — für Punkte, deren Elternpunkt keine hat — gegen die übrigen Sammlungen der
Ebene 2 (Review U4, Befund 3: sonst schnappte ein ungebundener Punkt die Kinder weg). Die
Inhaltszahl (``fileCount``, sonst ``contentsCount``) zählt, was direkt in der Sammlung liegt.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterator
from typing import Any, Final

AEHNLICH_AB: Final = 0.5
#: So viele WLO-Sammlungen der Ebene 1 fragt der Dienst an (``maxResults``); Kinder gibt der Server
#: bei Tiefe 2 selbst gedeckelt (3–10 je Sammlung) — mehr als :data:`WLO_KINDER` nimmt der Abgleich
#: aus Vorsicht nicht.
WLO_OBEN: Final = 31
WLO_KINDER: Final = 100
#: So viele Punkte des Entwurfs zeigt der Abgleich höchstens (wie der Entwurf selbst).
HOECHSTENS_PUNKTE: Final = 250
_TITEL: Final = 120
#: Vor dem Zerlegen (Review U4, Befund 5): „Anfänger“ und „Anfaenger“ sind dasselbe Wort.
_FALTEN: Final = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "ø": "o", "æ": "ae",
                                "œ": "oe", "ł": "l", "đ": "d"})
_FUELLWOERTER: Final = frozenset({
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "eines", "und", "oder",
    "mit", "von", "vom", "zu", "zum", "zur", "im", "in", "am", "an", "auf", "fuer", "bei",
    "the", "of", "and", "a", "to", "for", "on", "with",
})
_NICHT_WORT: Final = re.compile(r"[^0-9a-z]+")


def normalisiert(titel: Any) -> tuple[str, ...]:
    """Die Wörter eines Titels: Umlaute gefaltet, ohne Akzente, klein, ohne Satzzeichen und
    Füllwörter."""
    if not isinstance(titel, str):
        return ()
    gefaltet = titel.casefold().translate(_FALTEN)
    zerlegt = unicodedata.normalize("NFKD", gefaltet)
    ohne = "".join(z for z in zerlegt if not unicodedata.combining(z))
    return tuple(w for w in _NICHT_WORT.split(ohne) if w and w not in _FUELLWOERTER)


def aehnlichkeit(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    """Token-Jaccard zweier normalisierter Titel (0 ohne Wörter)."""
    sa, sb = set(a), set(b)
    return len(sa & sb) / len(sa | sb) if sa and sb else 0.0


def _text(wert: Any) -> str:
    return " ".join(wert.split())[:_TITEL] if isinstance(wert, str) else ""


def _anzahl(k: dict[str, Any]) -> int | None:
    for feld in ("fileCount", "contentsCount"):
        if type(k.get(feld)) is int and k[feld] >= 0:
            return k[feld]
    return None


def _wlo_knoten(roh: Any, ebene: int, eltern: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(roh, dict) or not isinstance(roh.get("nodeId"), str) or \
            not 0 < len(roh["nodeId"]) <= 80:
        return None
    url = roh.get("url") if isinstance(roh.get("url"), str) else ""
    return {"nodeId": roh["nodeId"], "titel": _text(roh.get("title")), "ebene": ebene,
            "eltern": eltern["nodeId"] if eltern else None,
            "eltern_titel": eltern["titel"] if eltern else None,
            "anzahl": _anzahl(roh), "mehr": roh.get("hasMoreChildren") is True,
            **({"url": url} if url.startswith(("https://", "http://")) and len(url) <= 500
               else {})}


def wlo_aus(baum: Any) -> list[dict[str, Any]]:
    """Die Sammlungen der Ebenen 1 und 2 aus der Antwort von ``browse_collection_tree``
    (``{results: [{nodeId, title, fileCount?, contentsCount?, hasMoreChildren?, children}]}``)."""
    ergebnisse = baum.get("results") if isinstance(baum, dict) else None
    aus: list[dict[str, Any]] = []
    for roh in (ergebnisse if isinstance(ergebnisse, list) else [])[:WLO_OBEN]:
        if (oben := _wlo_knoten(roh, 1, None)) is None:
            continue
        aus.append(oben)
        kinder = roh.get("children") if isinstance(roh.get("children"), list) else []
        for kind in kinder[:WLO_KINDER]:
            if (k := _wlo_knoten(kind, 2, oben)) is not None:
                aus.append(k)
    return aus


def _zuordnen(paare: list[tuple[float, int, str]], frei_e: set[int], frei_w: set[str]
              ) -> dict[int, tuple[str, float]]:
    """Gierig, die beste Ähnlichkeit zuerst; bei Gleichstand die Lesereihenfolge."""
    zu: dict[int, tuple[str, float]] = {}
    for wert, e, w in sorted(paare, key=lambda p: (-p[0], p[1])):
        if wert >= AEHNLICH_AB and e in frei_e and w in frei_w:
            zu[e] = (w, wert)
            frei_e.discard(e)
            frei_w.discard(w)
    return zu


def _entwurf_knoten(knoten: Any, ebene: int = 1) -> Iterator[tuple[dict[str, Any], int]]:
    """Nur Objekte, nur Listen als ``kinder``, nur Ebene 1 und 2 — ein Teil kommt ungeprüft."""
    if ebene > 2 or not isinstance(knoten, list):
        return
    for k in knoten:
        if isinstance(k, dict):
            yield k, ebene
            yield from _entwurf_knoten(k.get("kinder"), ebene + 1)


def _wert(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    return 2.0 if a and a == b else aehnlichkeit(a, b)


def abgleichen(entwurf: Any, wlo: list[dict[str, Any]], *, gekuerzt: bool = False
               ) -> dict[str, Any]:
    """``{zeilen, nur_in_wlo, zahlen, gekuerzt}`` — Zeilen in der Reihenfolge des Entwurfs.
    ``gekuerzt``: der Server hat die erste Ebene gekürzt (``truncated``)."""
    knoten = entwurf.get("knoten") if isinstance(entwurf, dict) else None
    punkte: list[dict[str, Any]] = []
    eltern_von: dict[int, int | None] = {}
    letzter_oben: int | None = None
    zu_viele = False
    for k, ebene in _entwurf_knoten(knoten):
        if not _text(k.get("titel")):
            continue
        if len(punkte) >= HOECHSTENS_PUNKTE:
            zu_viele = True
            break
        if ebene == 1:
            letzter_oben = len(punkte)
        eltern_von[len(punkte)] = None if ebene == 1 else letzter_oben
        punkte.append({"id": str(k.get("id") or "")[:40], "titel": _text(k.get("titel")),
                       "ebene": ebene})
    nach_id = {w["nodeId"]: w for w in wlo}
    worte_e = [normalisiert(p["titel"]) for p in punkte]
    worte_w = {w["nodeId"]: normalisiert(w["titel"]) for w in wlo}
    frei_w = set(nach_id)
    oben = {i for i, p in enumerate(punkte) if p["ebene"] == 1}
    zuordnung = _zuordnen([(_wert(worte_e[i], worte_w[w["nodeId"]]), i, w["nodeId"])
                           for i in oben for w in wlo if w["ebene"] == 1], set(oben), frei_w)

    def ziel(i: int) -> str | None:
        eltern = eltern_von.get(i)
        return zuordnung[eltern][0] if eltern is not None and eltern in zuordnung else None

    unten = [i for i, p in enumerate(punkte) if p["ebene"] == 2]
    gebunden = {i for i in unten if ziel(i) is not None}
    zuordnung |= _zuordnen([(_wert(worte_e[i], worte_w[w["nodeId"]]), i, w["nodeId"])
                            for i in gebunden for w in wlo
                            if w["ebene"] == 2 and w["eltern"] == ziel(i)], set(gebunden), frei_w)
    frei = set(unten) - gebunden
    zuordnung |= _zuordnen([(_wert(worte_e[i], worte_w[w["nodeId"]]), i, w["nodeId"])
                            for i in frei for w in wlo if w["ebene"] == 2], frei, frei_w)
    irgendwo_mehr = gekuerzt or any(w["mehr"] for w in wlo if w["ebene"] == 1)
    zeilen: list[dict[str, Any]] = []
    for i, p in enumerate(punkte):
        if i in zuordnung:
            w = nach_id[zuordnung[i][0]]
            zeilen.append({**p, "art": "vorhanden" if zuordnung[i][1] >= 2.0 else "aehnlich",
                           "wlo": {k: v for k, v in w.items()
                                   if k in ("nodeId", "titel", "anzahl", "url")
                                   and v is not None}})
            continue
        if p["ebene"] == 1:
            ungewiss = gekuerzt
        elif (z := ziel(i)) is not None:
            ungewiss = bool(nach_id[z]["mehr"])
        else:
            ungewiss = irgendwo_mehr
        zeilen.append({**p, "art": "neu", **({"ungewiss": True} if ungewiss else {})})
    nur = [{k: v for k, v in w.items()
            if k in ("nodeId", "titel", "anzahl", "url", "ebene", "eltern_titel")
            and v is not None}
           for w in wlo if w["nodeId"] in frei_w]
    zahlen = {art: sum(1 for z in zeilen if z["art"] == art)
              for art in ("vorhanden", "aehnlich", "neu")} | {"nur_in_wlo": len(nur)}
    return {"zeilen": zeilen, "nur_in_wlo": nur, "zahlen": zahlen,
            "gekuerzt": gekuerzt or zu_viele or any(w["mehr"] for w in wlo)}
