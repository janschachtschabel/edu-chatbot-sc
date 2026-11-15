"""Paket U4 (Plan 2026-11-08, E-6): ein Strukturentwurf gegen eine WLO-Sammlung — rein, ohne I/O.

SW-4 (Plan 2026-11-14): bis vier Ebenen, wenn der Bestand als flache Liste vorliegt
(``list_collection_tree``, :func:`wlo_aus_liste`); aus ``browse_collection_tree`` weiter zwei
(:func:`wlo_aus`). Die Regeln unten gelten je Ebene: erst unter der zugeordneten Sammlung des
Elternpunkts, dann — für Punkte ohne solche — gegen die übrigen Sammlungen derselben Ebene.

Jeder Punkt des Entwurfs (bis zur gelesenen Tiefe) bekommt eine Art:

- ``vorhanden`` — eine Sammlung mit demselben Titel (nach :func:`normalisiert`);
- ``aehnlich`` — eine Sammlung mit Token-Jaccard ≥ :data:`AEHNLICH_AB` (die beste zuerst);
- ``neu`` — nichts Passendes; ``ungewiss``, wenn der Baum dort gekürzt ist (der Server liefert bei
  Tiefe 2 nur einige Kinder je Sammlung, ``hasMoreChildren``) oder die Liste dort nicht
  vollständig gelesen wurde — dann heißt es „nicht gefunden“.

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
#: So tief reicht der Abgleich je Quelle: ``browse_collection_tree`` liefert hier zwei Ebenen,
#: ``list_collection_tree`` bis vier (so tief legt ``wlo_create_collection_tree`` an).
TIEFE_BAUM: Final = 2
TIEFE_LISTE: Final = 4
#: So viele WLO-Sammlungen der Ebene 1 fragt der Dienst an (``maxResults``); Kinder gibt der Server
#: bei Tiefe 2 selbst gedeckelt (3–10 je Sammlung) — mehr als :data:`WLO_KINDER` nimmt der Abgleich
#: aus Vorsicht nicht.
WLO_OBEN: Final = 31
WLO_KINDER: Final = 100
#: So viele Einträge einer Seite von ``list_collection_tree`` nimmt der Abgleich (der Server
#: liefert höchstens so viele; einer, der sich nicht daran hält, bremst sonst die Schleife).
LISTE_SEITE: Final = 250
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
    for feld in ("fileCount", "contentsCount", "contentCount"):
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


def wlo_aus_liste(liste: Any) -> list[dict[str, Any]]:
    """Die Sammlungen aller Ebenen aus der Antwort von ``list_collection_tree``
    (``{root, items: [{nodeId, title, path, depth, parentId, contentCount?}]}``). Die Liste ist
    je Elternknoten ungekürzt — ``mehr`` ist deshalb überall falsch. Ab welcher Ebene sie nicht
    sicher vollständig ist, sagt der Aufrufer (:func:`abgleichen`, ``unvollstaendig_ab``).

    Die Marken ``childrenUnread``/``childrenRefused`` je Sammlung zählen hier bewusst nicht
    (zweites Review SW-4): Sie stehen nur an Einträgen der gelieferten Seite, und für einen
    Ausfall an der gelesenen Sammlung selbst gibt es keine — „nur dort ungewiss“ ließe einen
    zweiten Ausfall als nicht geschehen gelten. Wo nicht gelesen wurde, sagt der Kopf der
    Antwort für den ganzen Lauf (``unreadParents``/``refusedParents``, MCP-Stand 15.11.2026);
    der Dienst setzt danach ``mehr`` (``dienst_strukturabgleich._ganzer_baum``)."""
    items = liste.get("items") if isinstance(liste, dict) else None
    aus: list[dict[str, Any]] = []
    for roh in (items if isinstance(items, list) else [])[:LISTE_SEITE]:
        if not isinstance(roh, dict):
            continue
        ebene = roh.get("depth")
        if type(ebene) is not int or not 1 <= ebene <= TIEFE_LISTE:
            continue
        eltern = None
        if ebene > 1:
            if not isinstance(roh.get("parentId"), str) or not roh["parentId"]:
                continue
            pfad = roh.get("path") if isinstance(roh.get("path"), list) else []
            eltern = {"nodeId": roh["parentId"],
                      "titel": _text(pfad[-2]) if len(pfad) >= 2 else ""}
        if (k := _wlo_knoten(roh, ebene, eltern)) is not None:
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


def _entwurf_knoten(knoten: Any, tiefe: int, ebene: int = 1
                    ) -> Iterator[tuple[dict[str, Any], int]]:
    """Nur Objekte mit Titel, nur Listen als ``kinder``, nur bis ``tiefe`` — ein Teil kommt
    ungeprüft. Ein Punkt ohne Titel fällt mit allem darunter weg: Er lässt sich nicht anlegen,
    und seine Kinder hingen sonst in Abgleich und Anzeige am Geschwister davor."""
    if ebene > tiefe or not isinstance(knoten, list):
        return
    for k in knoten:
        if isinstance(k, dict) and _text(k.get("titel")):
            yield k, ebene
            yield from _entwurf_knoten(k.get("kinder"), tiefe, ebene + 1)


def tiefe_von(entwurf: Any) -> int:
    """So viele Ebenen hat der Entwurf (0 ohne Punkte, höchstens :data:`TIEFE_LISTE`)."""
    knoten = entwurf.get("knoten") if isinstance(entwurf, dict) else None
    return max((ebene for _, ebene in _entwurf_knoten(knoten, TIEFE_LISTE)), default=0)


def _wert(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    return 2.0 if a and a == b else aehnlichkeit(a, b)


def abgleichen(entwurf: Any, wlo: list[dict[str, Any]], *, gekuerzt: bool = False,
               tiefe: int = TIEFE_BAUM, unvollstaendig_ab: int | None = None
               ) -> dict[str, Any]:
    """``{zeilen, nur_in_wlo, zahlen, gekuerzt}`` — Zeilen in der Reihenfolge des Entwurfs.

    - ``gekuerzt``: der Server hat die erste Ebene gekürzt (``truncated``).
    - ``tiefe``: so viele Ebenen des Entwurfs werden abgeglichen — so tief, wie ``wlo`` reicht.
    - ``unvollstaendig_ab``: ab dieser Ebene ist der Bestand nicht sicher vollständig (die Liste
      liest Ebene für Ebene und brach dort ab) — dort ist „neu“ nur „nicht gefunden“. Darüber
      bleibt „neu“ verbindlich."""
    knoten = entwurf.get("knoten") if isinstance(entwurf, dict) else None
    punkte: list[dict[str, Any]] = []
    eltern_von: dict[int, int | None] = {}
    letzter: dict[int, int] = {}                 # Ebene → der letzte Punkt dieser Ebene
    zu_viele = False
    for k, ebene in _entwurf_knoten(knoten, tiefe):
        if len(punkte) >= HOECHSTENS_PUNKTE:
            zu_viele = True
            break
        eltern_von[len(punkte)] = letzter.get(ebene - 1) if ebene > 1 else None
        letzter[ebene] = len(punkte)
        for tiefer in [e for e in letzter if e > ebene]:
            del letzter[tiefer]          # ein neuer Punkt schließt die Zweige unter seiner Ebene
        punkte.append({"id": str(k.get("id") or "")[:40], "titel": _text(k.get("titel")),
                       "ebene": ebene})
    nach_id = {w["nodeId"]: w for w in wlo}
    worte_e = [normalisiert(p["titel"]) for p in punkte]
    worte_w = {w["nodeId"]: normalisiert(w["titel"]) for w in wlo}
    frei_w = set(nach_id)
    zuordnung: dict[int, tuple[str, float]] = {}
    fremd: set[int] = set()        # ab Ebene 2 ohne zugeordneten Elternpunkt gefunden

    def ziel(i: int) -> str | None:
        eltern = eltern_von.get(i)
        return zuordnung[eltern][0] if eltern is not None and eltern in zuordnung else None

    def paare(wer: set[int], ebene: int, *, unter_eltern: bool) -> list[tuple[float, int, str]]:
        return [(_wert(worte_e[i], worte_w[w["nodeId"]]), i, w["nodeId"])
                for i in wer for w in wlo
                if w["ebene"] == ebene and (not unter_eltern or w["eltern"] == ziel(i))]

    # Je Ebene: erst unter der zugeordneten Sammlung des Elternpunkts, dann — für Punkte, deren
    # Elternpunkt keine hat — gegen die übrigen Sammlungen der Ebene (Review U4, Befund 3: sonst
    # schnappte ein ungebundener Punkt die Kinder weg). Auf Ebene 1 gibt es nur die zweite Runde.
    for ebene in range(1, tiefe + 1):
        stufe = {i for i, p in enumerate(punkte) if p["ebene"] == ebene}
        gebunden = {i for i in stufe if ziel(i) is not None}
        zuordnung |= _zuordnen(paare(gebunden, ebene, unter_eltern=True), set(gebunden), frei_w)
        frei = stufe - gebunden
        ohne_eltern = _zuordnen(paare(frei, ebene, unter_eltern=False), frei, frei_w)
        zuordnung |= ohne_eltern
        if ebene > 1:
            fremd |= set(ohne_eltern)
    zeilen: list[dict[str, Any]] = []
    for i, p in enumerate(punkte):
        if i in zuordnung:
            w = nach_id[zuordnung[i][0]]
            # Ohne Elternpunkt gefunden heißt: irgendwo auf dieser Ebene. Dann steht dabei, unter
            # welcher Sammlung — „Grundlagen“ gibt es in vielen Zweigen.
            unter = ({"eltern_titel": w["eltern_titel"]}
                     if i in fremd and w.get("eltern_titel") else {})
            zeilen.append({**p, "art": "vorhanden" if zuordnung[i][1] >= 2.0 else "aehnlich",
                           "wlo": {k: v for k, v in w.items()
                                   if k in ("nodeId", "titel", "anzahl", "url")
                                   and v is not None} | unter})
            continue
        if unvollstaendig_ab is not None and p["ebene"] >= unvollstaendig_ab:
            ungewiss = True
        elif p["ebene"] == 1:
            ungewiss = gekuerzt
        elif (z := ziel(i)) is not None:
            ungewiss = bool(nach_id[z]["mehr"])
        else:
            # ohne zugeordneten Elternpunkt: gekürzt ist, sobald irgendwo darüber etwas fehlt
            ungewiss = gekuerzt or any(w["mehr"] for w in wlo if w["ebene"] < p["ebene"])
        zeilen.append({**p, "art": "neu", **({"ungewiss": True} if ungewiss else {})})
    nur = [{k: v for k, v in w.items()
            if k in ("nodeId", "titel", "anzahl", "url", "ebene", "eltern_titel")
            and v is not None}
           for w in wlo if w["nodeId"] in frei_w]
    zahlen = {art: sum(1 for z in zeilen if z["art"] == art)
              for art in ("vorhanden", "aehnlich", "neu")} | {"nur_in_wlo": len(nur)}
    return {"zeilen": zeilen, "nur_in_wlo": nur, "zahlen": zahlen,
            "gekuerzt": gekuerzt or zu_viele or unvollstaendig_ab is not None
            or any(w["mehr"] for w in wlo)}
