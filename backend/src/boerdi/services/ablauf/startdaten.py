"""Startdaten eines Ablaufs prüfen (Paket AS-4a, Plan 2026-11-09 §5f, E2 A).

Die Gastseite gibt einem Ablauf mit dem Auslöser ``extern`` Daten mit (Widget-API
``startAblauf(id, daten)``, Attribut ``ablauf-start-daten``); das
Startschema (``AblaufArea.start``) sagt,
welche. Sie sind Eingaben einer fremden Seite und nie Rechte — geschrieben wird weiter nur unter
der Anmeldung der Person.

Geprüft wird je Feld der Typ (``text``: Steuer- und Formatzeichen fallen weg, Leerraum wird
zusammengezogen, zu lang wird abgewiesen; ``nodeid``: eine UUID, ganz; ``zahl``: endlich, kein
Wahrheitswert; ``ja_nein``: ``bool``), dazu Pflichtfelder und unbekannte Felder. Fehler kommen als
Codes ``<art>:<feld>`` — nie mit dem Wert. Rein, ohne I/O.
"""

from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea, StartFeld
from boerdi.ui_module.themenbaum import KNOTEN_UUID

#: Mehr Schlüssel nimmt die Prüfung gar nicht erst an (das Schema hat höchstens 10 Felder).
MAX_SCHLUESSEL: Final = 20
_UUID: Final = re.compile(KNOTEN_UUID)
_NAME: Final = re.compile(r"^[a-z][a-z0-9_]{1,29}\Z")


#: Fallen aus Text weg: Steuer-, Format-, Surrogat-, private und nicht vergebene Zeichen (ein
#: einzelnes Surrogat ließe sich nicht speichern, Review AS-4a, Befund 4).
_WEG: Final = frozenset({"Cc", "Cf", "Cs", "Co", "Cn"})
#: So groß darf eine Zahl höchstens sein (genau darstellbar; ``math.isfinite`` würfe bei mehr).
_ZAHL_MAX: Final = 2 ** 53


def text_bereinigt(wert: str) -> str:
    """Wie ein Text der Startdaten bereinigt wird — auch das Safety-Gate prüft diese Form."""
    return _text(wert)


def _text(wert: str) -> str:
    """Leerraum zuerst zusammenziehen — ein Zeilenumbruch trennt Wörter (Befund 3) —, dann die
    übrigen Zeichen der Kategorien in :data:`_WEG` entfernen."""
    zusammen = " ".join(wert.split())
    return "".join(z for z in zusammen if unicodedata.category(z) not in _WEG).strip()


def _wert(feld: StartFeld, roh: Any) -> tuple[Any, str | None]:
    """Der bereinigte Wert — oder ein Fehlercode."""
    if feld.typ == "text":
        if not isinstance(roh, str):
            return None, "typ"
        text = _text(roh)
        return (None, "zu_lang") if len(text) > feld.max_zeichen else (text, None)
    if feld.typ == "nodeid":
        return (roh, None) if isinstance(roh, str) and _UUID.fullmatch(roh) else (None, "typ")
    if feld.typ == "zahl":
        if isinstance(roh, bool) or not isinstance(roh, (int, float)):
            return None, "typ"
        gut = abs(roh) <= _ZAHL_MAX if isinstance(roh, int) else math.isfinite(roh)
        return (roh, None) if gut and abs(roh) <= _ZAHL_MAX else (None, "typ")
    return (roh, None) if isinstance(roh, bool) else (None, "typ")


def pruefen(ablauf: AblaufArea, roh: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """``(bereinigte Daten, [])`` oder ``(None, [Fehlercodes])``. ``roh`` ``None`` heißt „keine
    Daten“ — gut, solange kein Feld Pflicht ist. Ein leerer Text gilt als nicht angegeben."""
    if roh is None:
        roh = {}
    if not isinstance(roh, dict) or len(roh) > MAX_SCHLUESSEL:
        return None, ["form"]
    felder = {f.name: f for f in ablauf.start or []}
    fehler = [f"unbekannt:{k if isinstance(k, str) and _NAME.match(k) else '?'}"
              for k in roh if k not in felder]
    sauber: dict[str, Any] = {}
    for name, feld in felder.items():
        if roh.get(name) is None:
            if feld.pflicht:
                fehler.append(f"pflicht:{name}")
            continue
        wert, code = _wert(feld, roh[name])
        if code is not None:
            fehler.append(f"{code}:{name}")
        elif wert == "" and feld.pflicht:
            fehler.append(f"pflicht:{name}")
        elif wert != "":
            sauber[name] = wert
    return (None, fehler) if fehler else (sauber, [])


#: Woher die Startdaten eines Laufs kamen — nur von der Gastseite dürfen Kennungen an lesende
#: Werkzeuge (Entscheid zu AS-4a, Befund 10, Option 2).
QUELLE_GASTSEITE: Final = "gastseite"
#: AS-5a (A5-3): Daten, die die KI vorgeschlagen hat (Knopf eines Ablauf-Werkzeugs) — ohne Rechte.
QUELLE_KI: Final = "ki"

#: Feldtyp → JSON-Typ des Werkzeug-Parameters (AS-5a, A5-1).
_JSON_TYP: Final = {"text": "string", "nodeid": "string", "zahl": "number", "ja_nein": "boolean"}


def werkzeug_schema(ablauf: AblaufArea, lang: str) -> dict[str, Any]:
    """Das Startschema als Parameter-Schema eines Werkzeugs der KI. Die Prüfung der Argumente
    bleibt :func:`pruefen` — das Schema leitet nur das Modell (Muster, Länge, Pflicht)."""
    eigenschaften: dict[str, Any] = {}
    for feld in ablauf.start or []:
        e: dict[str, Any] = {"type": _JSON_TYP[feld.typ]}
        if feld.typ == "text":
            e["maxLength"] = feld.max_zeichen
        elif feld.typ == "nodeid":
            e["pattern"] = KNOTEN_UUID
        text = (feld.beschreibung.get(lang) or feld.beschreibung.get("de") or "").strip()
        if text:
            e["description"] = text
        eigenschaften[feld.name] = e
    schema: dict[str, Any] = {"type": "object", "properties": eigenschaften,
                              "additionalProperties": False}
    if pflicht := pflichtfelder(ablauf):
        schema["required"] = pflicht
    return schema


def kennungsfelder(ablauf: AblaufArea) -> frozenset[str]:
    """Die Felder vom Typ ``nodeid``."""
    return frozenset(f.name for f in ablauf.start or [] if f.typ == "nodeid")


def kennung_verweis(felder: frozenset[str], wert: Any) -> str | None:
    """Das Feld, wenn ``wert`` genau ``{"$teil": "start", "pfad": "<feld>"}`` mit einem Feld vom
    Typ ``nodeid`` ist — die einzige Form, in der ein lesendes WLO-Werkzeug einen Teil bekommt
    (als ganzes Argument; keine Auswahl, kein tieferer Pfad)."""
    from boerdi.services.teil_verweise import ist_auswahl, verweis

    v = verweis(wert)
    if v is None or ist_auswahl(wert) or v[0] != "start" or v[1] not in felder:
        return None
    return v[1]


def ist_kennung(wert: Any) -> bool:
    return isinstance(wert, str) and _UUID.fullmatch(wert) is not None


def pflichtfelder(ablauf: AblaufArea) -> list[str]:
    return [f.name for f in ablauf.start or [] if f.pflicht]
