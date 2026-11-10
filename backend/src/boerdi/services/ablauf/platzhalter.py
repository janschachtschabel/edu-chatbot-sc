"""Platzhalter in den Texten eines Ablaufs (Paket AS-3b, Plan 2026-11-09 §5d, D3).

``{teil.<name>}`` und ``{teil.<name>.<pfad>}`` in ``text`` und ``freigabe`` setzt der Treiber beim
Ausgeben aus den Teilen des Laufs ein (:func:`einsetzen`) — auch aus Teilen, die im selben Zug
entstanden sind. Der Wert wird Text:

- ein Objekt mit ``titel`` zeigt den Titel, sonst steht es (wie eine Liste) als kompaktes JSON da;
- höchstens :data:`MAX_ZEICHEN` Zeichen, Zeilenumbrüche werden Leerzeichen;
- ohne Markdown-Wirkung: ein Teil kann von der Person stammen (Freitext) und baute sonst Links
  oder Überschriften in die Antwort. Jedes ASCII-Satzzeichen wird escapt (CommonMark erlaubt das
  vor jedem, die Anzeige bleibt gleich) — auch ``:``, ``.`` und ``@``, sonst machte GFM aus einer
  nackten Adresse einen Link (Review AS-3b, Befund 1); ``$`` nicht, das zerlegte ``stripLatex``.
  Steuer- und Formatzeichen (Bidi, Nullbreite) fallen weg;
- ein fehlender Wert (Teil oder Stelle) wird „—“.

``{start.<feld>}`` (AS-4a) liest die Startdaten: dasselbe wie ``{teil.start.<feld>}``. Was nicht
wie ein Platzhalter aussieht (``{nicht}``), bleibt, wie es ist.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
from typing import Any, Final

from boerdi.services.teil_verweise import NAME, PFAD, stelle

MAX_ZEICHEN: Final = 200
FEHLT: Final = "—"
#: Was der Treiber einsetzt (gültig oder nicht — ungültige bleiben stehen).
_KANDIDAT: Final = re.compile(r"\{(teil|start)\.([^{}\s]*)\}")
#: Was die Prüfung als Platzhalter-Versuch ansieht — auch ``{Teil.x}`` oder ``{teil.a b}``
#: (Review AS-3b, Befund 8).
_VERSUCH: Final = re.compile(r"(?i)\{\s*(teil|start)\b[^{}]{0,80}\}")
#: Jedes ASCII-Satzzeichen (Befund 1).
_MARKDOWN: Final = re.compile(r"([!-/:-@\[-`{-~])")
#: Querschnitts-Review Gruppe E: diese als Entität, nicht mit Rückstrich — ``\(`` und ``\[`` hielte
#: das Widget seit TB-E4 für eine Formel, ``$`` für ihren Anfang.
_ENTITAETEN: Final = {"(": "&#40;", ")": "&#41;", "[": "&#91;", "]": "&#93;", "$": "&#36;"}


def _form(rest: str) -> tuple[str, str | None, bool]:
    """Name, Pfad und ob die Form gültig ist — ``{teil.x.}`` (Punkt ohne Pfad) ist es nicht
    (Befund 7)."""
    name, punkt, pfad = rest.partition(".")
    gueltig = bool(NAME.match(name)) and (not punkt or bool(PFAD.match(pfad)))
    return name, pfad or None, gueltig


def finden(text: str) -> list[tuple[str, str, str | None, bool]]:
    """Je Platzhalter-Versuch Art (``teil``/``start``), Name, Pfad und ob die Form gültig ist."""
    funde: list[tuple[str, str, str | None, bool]] = []
    for treffer in _VERSUCH.finditer(text or ""):
        genau = _KANDIDAT.fullmatch(treffer.group(0))
        if genau is None:
            funde.append((treffer.group(1).lower(), treffer.group(0)[1:-1].strip(), None, False))
            continue
        funde.append((genau.group(1), *_form(genau.group(2))))
    return funde


def _als_text(wert: Any) -> str:
    if wert is None:
        return FEHLT
    if isinstance(wert, str):
        return wert
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    if isinstance(wert, int | float):
        return str(wert)
    if isinstance(wert, dict) and isinstance(wert.get("titel"), str):
        return wert["titel"]
    return json.dumps(wert, ensure_ascii=False, separators=(",", ":"), default=str)


def entschaerft(wert: Any) -> str:
    """Ein Wert als einzeiliger Text ohne Markdown-Wirkung, gekürzt auf :data:`MAX_ZEICHEN`
    sichtbare Zeichen (die Escapes kommen danach dazu)."""
    roh = "".join(z for z in _als_text(wert)
                  if unicodedata.category(z) not in ("Cc", "Cf") or z in "\n\t")
    text = " ".join(roh.split())
    if len(text) > MAX_ZEICHEN:
        text = text[:MAX_ZEICHEN - 1] + "…"
    return _MARKDOWN.sub(lambda m: _ENTITAETEN.get(m.group(1), "\\" + m.group(1)),
                         text) if text else FEHLT


def herkuenfte(text: str) -> frozenset[str]:
    """Welche Arten von Platzhaltern ``text`` einsetzt (``teil``, ``start``) — Paket AS-Ua
    (Review, Befund 2): ein Teil kann KI-Ausgabe sein, dann ist der Text nicht mehr fest."""
    return frozenset(m.group(1) for m in _KANDIDAT.finditer(text or ""))


async def einsetzen(text: str, teile: Callable[[str], Awaitable[Any]]) -> str:
    """``text`` mit den Werten der gültigen ``{teil.…}``- und ``{start.…}``-Platzhalter."""
    if "{teil." not in (text or "") and "{start." not in (text or ""):
        return text
    teile_cache: dict[str, Any] = {}

    async def wert(treffer: re.Match[str]) -> str:
        art, rest = treffer.group(1), treffer.group(2)
        name, pfad, gueltig = _form(rest)
        if not gueltig:
            return treffer.group(0)
        if art == "start":
            # ``{start.feld.pfad}`` = ``{teil.start.feld.pfad}`` (AS-4a)
            name, pfad = "start", name + (f".{pfad}" if pfad else "")
        if name not in teile_cache:
            teile_cache[name] = await teile(name)
        return entschaerft(stelle(teile_cache[name], pfad))

    stuecke: list[str] = []
    ende = 0
    for treffer in _KANDIDAT.finditer(text):
        stuecke += [text[ende:treffer.start()], await wert(treffer)]
        ende = treffer.end()
    return "".join(stuecke) + text[ende:]
