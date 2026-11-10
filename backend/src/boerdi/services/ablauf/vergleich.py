"""Die Bedingung ``wenn_wert`` einer Verzweigung (Paket AS-3c, Plan 2026-11-09 §5d, D4).

Eine Regel vergleicht eine Stelle eines Teils (``quelle``: ``teil.<name>[.<pfad>]``) mit einem Wert:

- ``vorhanden`` / ``leer``: gibt es dort etwas (nicht ``None``, kein leerer Text, keine leere Liste
  oder Objekt)?
- ``gleich``: als Zahl, wenn die Stelle eine Zahl ist (JSON-Zahl) und der Wert eine; sonst als Text
  (ohne Rücksicht auf Groß- und Kleinschreibung, Leerraum am Rand und Unicode-Form) — zwei Texte wie
  ``"01067"`` und ``"1067"`` bleiben verschieden (Review AS-3c, Befund 2); ja/nein bzw. true/false
  für Wahrheitswerte;
- ``enthaelt``: Teil eines Texts, ein Element einer Liste (verglichen wie ``gleich``), ein Schlüssel
  eines Objekts;
- ``groesser`` / ``kleiner``: nur, wenn beide Seiten Zahlen sind — sonst greift die Regel nicht.

Zahlen sind exakt (``Decimal``): Text nur in der Form ``-12``, ``1,5`` oder ``1.5`` — kein ``nan``,
``inf``, ``1e3`` oder ``1_000`` (Befund 1); sehr große Zahlen laufen nicht über.

Ein lesendes WLO-Werkzeug liefert Text: ein Pfad in sein Ergebnis findet nichts, ``enthaelt`` auf
den ganzen Teil schon. Rein, ohne I/O außer dem Lader der Teile.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Awaitable, Callable
from decimal import Decimal, InvalidOperation
from typing import Any, Final

from boerdi.services.teil_verweise import NAME, PFAD, stelle

VERGLEICHE: Final = ("gleich", "enthaelt", "vorhanden", "leer", "groesser", "kleiner")
#: Diese Vergleiche brauchen einen Wert, ``vorhanden`` und ``leer`` keinen.
MIT_WERT: Final = frozenset({"gleich", "enthaelt", "groesser", "kleiner"})
ZAHL_NOETIG: Final = frozenset({"groesser", "kleiner"})
_QUELLE: Final = re.compile(r"^teil\.([^.]+)(?:\.(.+))?\Z")
#: Eine Zahl als Text: Vorzeichen, Ziffern, ein Dezimalkomma oder -punkt (Befund 1).
_ZAHL: Final = re.compile(r"^[+-]?\d{1,40}(?:[.,]\d{1,40})?\Z")
_WAHR: Final = frozenset({"ja", "true", "wahr", "1"})
_FALSCH: Final = frozenset({"nein", "false", "falsch", "0"})


def quelle(text: str | None) -> tuple[str, str | None] | None:
    """Name und Pfad einer Quelle ``teil.<name>[.<pfad>]`` — ``None``, wenn die Form nicht gilt."""
    treffer = _QUELLE.match(text or "")
    if treffer is None or not NAME.match(treffer.group(1)):
        return None
    pfad = treffer.group(2)
    if pfad is not None and not PFAD.match(pfad):
        return None
    return treffer.group(1), pfad


def zahl(wert: Any) -> Decimal | None:
    """Eine Zahl, exakt — auch als Text mit Komma oder Punkt; Wahrheitswerte, ``nan``, ``inf`` und
    andere Schreibweisen zählen nicht."""
    if isinstance(wert, bool):
        return None
    if isinstance(wert, int):
        return Decimal(wert)
    if isinstance(wert, float):
        return Decimal(repr(wert)) if wert == wert and abs(wert) != float("inf") else None
    if isinstance(wert, str) and _ZAHL.match(roh := wert.strip()):
        try:
            return Decimal(roh.replace(",", "."))
        except InvalidOperation:
            return None
    return None


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text.strip()).casefold()


def _text(wert: Any) -> str:
    if isinstance(wert, bool):
        return "ja" if wert else "nein"
    if isinstance(wert, str):
        return wert.strip()
    if isinstance(wert, int | float):
        return str(wert)
    return json.dumps(wert, ensure_ascii=False, default=str)


def _vorhanden(wert: Any) -> bool:
    if wert is None:
        return False
    if isinstance(wert, str):
        return bool(wert.strip())
    if isinstance(wert, list | dict):
        return bool(wert)
    return True


def vergleiche(wert: Any, vergleich: str, soll: str | None) -> bool:
    """Greift ``vergleich`` für ``wert`` (die Stelle im Teil) und ``soll`` (den Wert der Regel)?"""
    if vergleich == "vorhanden":
        return _vorhanden(wert)
    if vergleich == "leer":
        return not _vorhanden(wert)
    if soll is None or wert is None:
        return False
    if vergleich in ZAHL_NOETIG:
        a, b = zahl(wert), zahl(soll)
        if a is None or b is None:
            return False
        return a > b if vergleich == "groesser" else a < b
    s = _norm(soll)
    if vergleich == "gleich":
        return _gleich(wert, soll)
    if vergleich == "enthaelt":
        if isinstance(wert, list):
            return any(_gleich(x, soll) for x in wert)
        if isinstance(wert, dict):
            return any(_norm(str(k)) == s for k in wert)
        return s in _norm(_text(wert))
    return False


def _gleich(wert: Any, soll: str) -> bool:
    if isinstance(wert, bool):
        s = _norm(soll)
        return s in (_WAHR if wert else _FALSCH)
    if isinstance(wert, int | float):
        a, b = zahl(wert), zahl(soll)
        if a is not None and b is not None:
            return a == b
    return _norm(_text(wert)) == _norm(soll)


async def greift(quelle_text: str, vergleich: str, soll: str | None,
                 teile: Callable[[str], Awaitable[Any]]) -> bool:
    """Die Regel gegen die Teile des Laufs — eine ungültige Quelle greift nie."""
    q = quelle(quelle_text)
    if q is None:
        return False
    name, pfad = q
    return vergleiche(stelle(await teile(name), pfad), vergleich, soll)
