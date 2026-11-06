"""Gliederung eines umgewandelten Dokuments (Paket U3-2a, Plan 2026-11-04 §16.6) — rein, ohne I/O.

markitdown liefert für DOCX echte Überschriften (``#``), für PDF meist nur Fließtext (pdfminer). Die
Gliederung entsteht deshalb in drei Stufen:

1. **ATX-Überschriften** (``#`` … ``######``), ab drei Treffern;
2. sonst **nummerierte Zeilen** (``1``, ``2.1``, ``3.4.1`` + Titel, der nicht auf ``.,;:`` endet);
   Punktreihen und Seitenzahlen am Ende fallen weg, und kommt dieselbe Nummer mit demselben Titel
   mehrfach vor (Inhaltsverzeichnis, dann Text), zählt das **letzte** Vorkommen;
3. sonst **Teile** von etwa 3000 Zeichen aus ganzen Absätzen.

Höchstens :data:`MAX_ABSCHNITTE` Abschnitte (die tiefsten Ebenen fallen zuerst weg). Kennungen
``a1``, ``a2`` … der Reihe nach. Der Dienst des Entwurfs liest die Abschnitte per Kennung
serverseitig (:func:`abschnitt_text`); an die KI geht nur die gedeckelte :func:`uebersicht`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

MAX_ABSCHNITTE: Final = 400
TITEL_ZEICHEN: Final = 120
TEIL_ZEICHEN: Final = 3000
_MIN_TREFFER: Final = 3

GliederungArt = Literal["ueberschriften", "nummeriert", "teile"]

#: Linear (Review U3-2, Befund 1): ``(\S.*?)[ \t#]*$`` brauchte für eine lange Zeile aus
#: Leerzeichen quadratische Zeit — die Ereignisschleife stand. Schluss-``#`` schneidet ``_atx`` ab.
_ATX: Final = re.compile(r"^(#{1,6})[ \t]+(\S[^\n]*)$", re.M)
_NUMMER: Final = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?[ \t]+(\S.{2,160})$", re.M)
_SEITENZAHL: Final = re.compile(r"(?:[ \t]*\.{2,}[ \t.]*|[ \t]{2,})\d{1,4}[ \t]*$")
_STEUER: Final = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LEERZEILEN: Final = re.compile(r"\n{3,}")
_GEKUERZT: Final = "…(gekürzt)"


@dataclass(frozen=True)
class Abschnitt:
    id: str
    ebene: int
    titel: str
    start: int
    ende: int


_BILD_ALT: Final = 500


def _ohne_data_bilder(md: str) -> tuple[str, int]:
    """``![alt](data:…)`` heraus — in einem Durchgang ohne Regex (Review U3-2, Befund 1: die Regex
    brauchte für viele offene ``![a](data:`` quadratische Zeit). Ohne schließende Klammer bleibt
    der Rest stehen."""
    teile: list[str] = []
    i = bilder = 0
    while (k := md.find("](data:", i)) != -1:
        a = md.rfind("![", max(i, k - _BILD_ALT), k)
        if a == -1 or "\n" in md[a:k]:
            teile.append(md[i:k + 7])
            i = k + 7
            continue
        e = md.find(")", k)
        if e == -1:
            break
        teile.append(md[i:a])
        i = e + 1
        bilder += 1
    teile.append(md[i:])
    return "".join(teile), bilder


def bereinigen(md: str) -> tuple[str, int]:
    """Eingebettete Bilder (Base64), Steuerzeichen und Leerzeilen-Stapel heraus; Zahl der Bilder."""
    md, bilder = _ohne_data_bilder(md)
    md = _LEERZEILEN.sub("\n\n", _STEUER.sub("", md.replace("\r\n", "\n").replace("\r", "\n")))
    return md.strip("\n"), bilder


def _eine_zeile(titel: str) -> str:
    return " ".join(titel.split())[:TITEL_ZEICHEN]


def _atx(md: str) -> list[tuple[int, int, str]]:
    treffer = ((m.start(), len(m.group(1)), _eine_zeile(m.group(2).rstrip(" \t#")))
               for m in _ATX.finditer(md))
    return [t for t in treffer if t[2]]


def _nummeriert(md: str) -> list[tuple[int, int, str]]:
    letzte: dict[tuple[str, str], tuple[int, int, str]] = {}
    for m in _NUMMER.finditer(md):
        titel = _eine_zeile(_SEITENZAHL.sub("", m.group(2)))
        if not titel or titel[-1] in ".,;:" or len(titel) < 3:
            continue
        nummer = m.group(1)
        letzte[(nummer, titel.lower())] = (m.start(), nummer.count(".") + 1, titel)
    return sorted(letzte.values())


def _teile(md: str) -> list[tuple[int, int, str]]:
    treffer: list[tuple[int, int, str]] = []
    start, laenge = 0, 0
    for absatz in re.finditer(r"[^\n]+(?:\n(?!\n)[^\n]*)*", md):
        if laenge == 0:
            start = absatz.start()
        laenge += len(absatz.group(0))
        if laenge >= TEIL_ZEICHEN:
            treffer.append((start, 1, ""))
            laenge = 0
    if laenge:
        treffer.append((start, 1, ""))
    return [(s, e, _eine_zeile(f"Teil {i}: {md[s:s + 60]}"))
            for i, (s, e, _) in enumerate(treffer, 1)]


def _gedeckelt(treffer: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    while len(treffer) > MAX_ABSCHNITTE and max(e for _, e, _ in treffer) > 1:
        tiefste = max(e for _, e, _ in treffer)
        treffer = [t for t in treffer if t[1] != tiefste]
    return treffer[:MAX_ABSCHNITTE]


def gliederung(md: str) -> tuple[list[Abschnitt], GliederungArt]:
    art: GliederungArt
    if len(treffer := _atx(md)) >= _MIN_TREFFER:
        art = "ueberschriften"
    elif len(treffer := _nummeriert(md)) >= _MIN_TREFFER:
        art = "nummeriert"
    else:
        treffer, art = _teile(md), "teile"
    treffer = _gedeckelt(treffer)
    abschnitte = [Abschnitt(id=f"a{i}", ebene=e, titel=t, start=s,
                            ende=treffer[i][0] if i < len(treffer) else len(md))
                  for i, (s, e, t) in enumerate(treffer, 1)]
    return abschnitte, art


def uebersicht(abschnitte: list[Abschnitt], max_zeichen: int) -> tuple[str, bool]:
    """Eingerückte Liste der Titel bis Ebene 3; abgeschnitten mit Marke, wenn sie zu lang wird —
    die Marke zählt mit, das Ergebnis bleibt ≤ ``max_zeichen``."""
    zeilen: list[str] = []
    laenge = 0
    for a in abschnitte:
        if a.ebene > 3:
            continue
        zeile = f"{'  ' * (a.ebene - 1)}- {a.titel} [{a.id}]"
        if laenge + len(zeile) + 1 + len(_GEKUERZT) > max_zeichen:
            zeilen.append(_GEKUERZT)
            return "\n".join(zeilen), True
        zeilen.append(zeile)
        laenge += len(zeile) + 1
    return "\n".join(zeilen), False


def mit_unterabschnitten(abschnitte: list[Abschnitt], ids: list[str]) -> list[str]:
    """Die genannten Abschnitte samt ihren Unterabschnitten (alles bis zum nächsten Abschnitt
    gleicher oder höherer Ebene), in Dokumentreihenfolge; unbekannte Kennungen fallen weg."""
    gesucht, ergebnis, ebene = set(ids), [], None
    for a in abschnitte:
        if ebene is not None and a.ebene <= ebene:
            ebene = None
        if ebene is None and a.id in gesucht:
            ebene = a.ebene
        if ebene is not None:
            ergebnis.append(a.id)
    return ergebnis


def abschnitt_text(md: str, abschnitte: list[Abschnitt], ids: list[str], max_zeichen: int) -> str:
    """Der Text der gewählten Abschnitte in Dokumentreihenfolge, je Abschnitt anteilig gekürzt."""
    gewaehlt = [a for a in abschnitte if a.id in set(ids)]
    if not gewaehlt:
        return ""
    je = max(1, (max_zeichen - len(gewaehlt)) // len(gewaehlt))
    return "\n".join(md[a.start:a.ende].strip()[:je] for a in gewaehlt)[:max_zeichen]
