"""Endmarken der Rahmen im Fremdtext entschärfen (Audit 2026-09-29, B-M4).

Aus ``domain/untrusted_text`` gelöst (Paket 10, Dateigrößen): dort stehen die
Rahmen, hier die Frage, was das Modell im Fremdtext als ihre Endmarke liest — und
wie die Fundstelle so umgeschrieben wird, dass sie keine mehr ist.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_right
from itertools import accumulate

#: Audit 2026-09-29 B-M4: eine Endmarke IM Fremdtext schloss den Rahmen
#: vorzeitig — alles danach stand scheinbar ausserhalb, auf Anweisungsebene.
#: Review Paket 7, B-2: gesucht wird, was das Modell als Marke LIEST — die
#: Buchstaben, gleich mit welchen Trennern (Unterstrich, Bindestrich, keiner),
#: unsichtbaren Zeichen, Vollbreite oder kyrillischen Doppelgaengern. Je Name:
#: die Buchstaben ohne Trenner → die Schreibweise in der entschaerften Marke.
_MARKEN = {"FREMDINHALT": "FREMDINHALT", "ZULETZTGEZEIGT": "ZULETZT GEZEIGT",
           "SEITENKONTEXT": "SEITENKONTEXT"}

#: Kyrillische und griechische Doppelgaenger der Buchstaben in diesen Marken —
#: keine allgemeine Verwechslungstabelle, nur was eine Marke nachbilden kann.
_DOPPELGAENGER = str.maketrans({
    "\u0410": "A", "\u0430": "a", "\u0415": "E", "\u0435": "e", "\u041d": "H", "\u0406": "I",
    "\u0456": "i", "\u04c0": "I", "\u041a": "K", "\u041c": "M", "\u041e": "O", "\u043e": "o",
    "\u0422": "T", "\u0425": "X", "\u0445": "x", "\u0405": "S", "\u0455": "s", "\u0501": "d",
    "\u0391": "A", "\u0395": "E", "\u0397": "H", "\u0399": "I", "\u039a": "K", "\u039c": "M",
    "\u039d": "N", "\u039f": "O", "\u03bf": "o", "\u03a4": "T", "\u03a7": "X", "\u0396": "Z",
    # Review Paket 9: kleine kyrillische Buchstaben und Kapitälchen.
    "\u0442": "t", "\u043d": "h", "\u043a": "k", "\u043c": "m",
    "\u1d00": "A", "\u1d05": "D", "\u1d07": "E", "\u1d0b": "K", "\u1d0d": "M", "\u1d0f": "O",
    "\u1d1b": "T", "\u1d1c": "U", "\u1d22": "Z", "\u0262": "G", "\u026a": "I", "\u0274": "N",
    "\u0280": "R", "\u029c": "H", "\u029f": "L", "\ua730": "F", "\ua731": "S",
})


#: Trenner zwischen den Buchstaben einer Marke: alles außer Wortzeichen und
#: eckigen Klammern, beliebig viele. Gedeckelte Trenner (3 im Wort, 10 dazwischen)
#: ließen gepolsterte Marken durch, etwa „[ENDE“ + elf Leerzeichen +
#: „SEITENKONTEXT]“ (Review Paket 7). Ohne Klammern im Trenner bleibt der Abgleich
#: linear: jede Klammer prüft nur bis zur nächsten. Possessiv, weil ein Trenner
#: den folgenden Buchstaben nie schluckt — Zurückgehen brächte nichts.
_TRENNER = r"(?:[^\w\[\]]|_)*+"


def _buchstaben(wort: str) -> str:
    return _TRENNER.join(re.escape(b) for b in wort)


#: Je Name eine benannte Gruppe: welche Marke getroffen ist, sagt der Treffer,
#: nicht sein Text. Aus dem Text gelesen warf das türkische „I“ mit Punkt
#: (U+0130, passt ohne Groß-/Kleinschreibung auf „I“) einen ``KeyError``, und der
#: Zug brach ab (Review Paket 7).
_ENDMARKE = re.compile(
    r"\[" + _TRENNER + _buchstaben("ENDE") + _TRENNER
    + "(?:" + "|".join(f"(?P<{name}>{_buchstaben(name)})" for name in _MARKEN) + ")"
    + _TRENNER + r"\]",
    re.IGNORECASE)


#: Hangul-Füllzeichen: unsichtbar, aber Buchstaben — also kein Trenner, und die
#: Marke dahinter galt als zerteilt (Review Paket 9).
_FUELLER = frozenset("\u115f\u1160\u3164\uffa0")


def _ohne_akzente(c: str) -> str:
    """NFKD ohne Kombinationszeichen: aus „É“ wird „E“ — NFKC ließ es stehen
    (Review Paket 9)."""
    return "".join(z for z in unicodedata.normalize("NFKD", c)
                   if unicodedata.category(z) != "Mn")


def _lesarten(text: str) -> dict[str, str]:
    """Je Zeichen des Texts, das das Modell anders liest, seine Lesart — NFKD ohne
    Akzente, Doppelgänger lateinisch, Format-Zeichen (Kategorie Cf) und
    Hangul-Füllzeichen gestrichen.

    Gerechnet je VERSCHIEDENEM Zeichen. Bis Paket 9 lief eine Python-Schleife
    über jedes Zeichen des Texts: 300 000 × U+FDFA brauchten 1,9 s und hielten
    die Ereignisschleife für alle an (Review Paket 7)."""
    tabelle: dict[str, str] = {}
    for c in set(text):
        if unicodedata.category(c) == "Cf" or c in _FUELLER:
            tabelle[c] = ""
        elif (lesart := _ohne_akzente(c).translate(_DOPPELGAENGER)) != c:
            tabelle[c] = lesart
    return tabelle


#: Höchstens so viele Durchgänge (Review Paket 9, MAJOR 6). Aus „[[ENDE FREMDINHALT]]“
#: wurde „[(ENDE FREMDINHALT)]“ — runde Klammern sind Trenner, die Regel las darin
#: wieder eine Marke. Jeder Durchgang schält eine Schicht; unbegrenzt wäre das bei
#: tiefer Verschachtelung quadratisch.
_DURCHGAENGE = 3


def entschaerfe_endmarken(text: str) -> str:
    """Endmarken der Rahmen im Text unwirksam machen, bevor er gerahmt wird.

    Aus den eckigen werden runde Klammern: der Inhalt bleibt lesbar, aber er
    gleicht der echten Marke am Rahmenende nicht mehr. Ersetzt wird nur die
    Fundstelle; der uebrige Text bleibt Zeichen fuer Zeichen, wie er war — ausser
    bei Marken in mehr als drei Schichten eckiger Klammern: dann wird jede eckige
    Klammer rund.
    """
    for _ in range(_DURCHGAENGE):
        text, weiter = _ein_durchgang(text)
        if not weiter:
            return text
    return _eckige_klammern_rund(text)


def _eckige_klammern_rund(text: str) -> str:
    """Jede eckige Klammer rund, auch jede, die das Modell als eine liest — in einem
    Durchgang, gleich wie tief verschachtelt."""
    tabelle = _lesarten(text)
    rund: dict[int, str] = {}
    for c in set(text):
        lesart = tabelle.get(c, c)
        if "[" in lesart or "]" in lesart:
            rund[ord(c)] = lesart.replace("[", "(").replace("]", ")")
    return text.translate(rund)


def _ein_durchgang(text: str) -> tuple[str, bool]:
    """Jede gefundene Marke rund geklammert — und ob ein weiterer Durchgang noch eine
    finden könnte."""
    tabelle = _lesarten(text)
    # ``map(dict.get, …)`` statt ``str.translate``: das ist bei mehrzeichigen
    # Lesarten selbst langsam (300 000 × U+FDFA: 2,9 s gegen 0,05 s, gemessen).
    schatten = "".join(map(tabelle.get, text, text)) if tabelle else text
    # Je Zeichen des Originals: wo seine Lesart in der Schattenfassung endet —
    # nur nötig, wenn eine Lesart länger oder kürzer ist als ihr Zeichen.
    enden: list[int] | None = None
    gleich_lang = all(len(lesart) == 1 for lesart in tabelle.values())
    teile: list[str] = []
    pos = 0
    treffer = 0
    for m in _ENDMARKE.finditer(schatten):
        treffer += 1
        anfang, ende = m.start(), m.end()
        if not gleich_lang:
            if enden is None:
                enden = list(accumulate(map(len, map(tabelle.get, text, text))))
            anfang = bisect_right(enden, anfang)
            ende = bisect_right(enden, ende - 1) + 1
        teile += [text[pos:anfang], f"(ENDE {_MARKEN[m.lastgroup or '']})"]
        pos = max(pos, ende)
    if not treffer:
        return text, False
    # Jede Marke verbraucht genau eine eckige Klammer je Seite (Trenner schließen
    # Klammern aus). Bleibt auf einer Seite keine übrig, findet der nächste nichts.
    weiter = schatten.count("[") > treffer and schatten.count("]") > treffer
    return "".join(teile) + text[pos:], weiter
