"""Ergebnis-Schema eines Gastgebers prüfen (Paket 4, A3; externes Audit F11).

Das Schema reist wörtlich in die Parameter von ``submit_result`` bzw.
``liefere_ergebnis``. Der Anbieter erzwingt es nicht: Das täte er nur mit
``strict``, und das verlangte ``additionalProperties: false`` und alle Felder
als Pflicht — freie Gastgeber-Schemata brächen daran. Geprüft wird deshalb hier,
nach dem Modellaufruf.

Das Schema kommt aus der Anfrage, also von außen (Prüfer 2026-10-04):

- **Nie nachladen.** ``jsonschema`` holt ohne eigene Registry jede unbekannte
  Adresse per ``urlopen`` — ``$id`` unterhalb der Wurzel reichte dafür (SSRF).
  Geprüft wird deshalb mit einer leeren Registry; der Eingang weist ``$id`` und
  ``$schema`` unterhalb der Wurzel, Anker und dynamische Verweise ab, und jedes
  ``$ref`` muss als JSON-Pointer im Schema selbst landen.
- **Muster wertet der Server nicht aus.** Ein Regex des Gastgebers gegen die
  Ausgabe des Modells kann den Server blockieren (ReDoS). ``pattern`` und
  ``patternProperties`` bleiben ein Hinweis an das Modell.
- **Das Gastgeber-Schema ist seine eigene Wurzel** — sonst zeigten
  ``#/$defs/…`` und ``#`` auf die Werkzeug-Hülle.
- **Der Dialekt folgt ``$schema``** (Vorgabe 2020-12); draft-07 galt sonst als
  kaputt.

Rein (CLAUDE.md, Regel 4): ohne I/O.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import unquote

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from referencing import Registry
from referencing.exceptions import Unresolvable

#: So viele Abweichungen gehen höchstens an das Modell zurück.
MAX_MELDUNGEN = 5

#: Tiefer verschachtelt nimmt der Eingang nichts an; die Prüfung läuft rekursiv.
MAX_TIEFE = 32

# Wo Teilschemata stehen: als Wert, als Liste, als Karte Name → Teilschema.
# Alles andere (``enum``, ``const``, ``default`` …) sind Daten, keine Schemata.
_EIN_SCHEMA = ("additionalProperties", "unevaluatedProperties", "items", "additionalItems",
               "unevaluatedItems", "contains", "propertyNames", "not", "if", "then", "else",
               "contentSchema")
_SCHEMA_LISTE = ("allOf", "anyOf", "oneOf", "prefixItems", "items")
_SCHEMA_KARTE = ("properties", "patternProperties", "$defs", "definitions",
                 "dependentSchemas", "dependencies")

_NUR_AN_DER_WURZEL = ("$id", "$schema")
_NICHT_UNTERSTUETZT = ("$anchor", "$dynamicAnchor", "$dynamicRef",
                       "$recursiveRef", "$recursiveAnchor")
_MUSTER = ("pattern", "patternProperties")


def _teilschemata(wurzel: Any) -> Iterator[tuple[dict[str, Any], int]]:
    """Jedes Teilschema mit seiner Tiefe (0 = Wurzel), ohne Rekursion."""
    offen = [(wurzel, 0)]
    while offen:
        schema, tiefe = offen.pop()
        if not isinstance(schema, dict):
            continue  # true/false sind Schemata ohne Inhalt
        yield schema, tiefe
        for schluessel, wert in schema.items():
            if schluessel in _EIN_SCHEMA and isinstance(wert, dict):
                offen.append((wert, tiefe + 1))
            elif schluessel in _SCHEMA_LISTE and isinstance(wert, list):
                offen.extend((teil, tiefe + 1) for teil in wert)
            elif schluessel in _SCHEMA_KARTE and isinstance(wert, dict):
                offen.extend((teil, tiefe + 1) for teil in wert.values())


def _ziel(wurzel: dict[str, Any], verweis: str) -> Any:
    """Worauf ``#`` bzw. ``#/…`` im Schema zeigt — ``None``, wenn auf nichts."""
    if verweis == "#":
        return wurzel
    ziel: Any = wurzel
    for teil in verweis[2:].split("/"):
        teil = unquote(teil).replace("~1", "/").replace("~0", "~")
        if isinstance(ziel, dict) and teil in ziel:
            ziel = ziel[teil]
        elif isinstance(ziel, list) and teil.isdigit() and int(teil) < len(ziel):
            ziel = ziel[int(teil)]
        else:
            return None
    return ziel


def schema_fehler(schema: dict[str, Any]) -> str | None:
    """Warum ``schema`` als Ergebnis-Schema nicht taugt — oder ``None``."""
    for teil, tiefe in _teilschemata(schema):
        if tiefe > MAX_TIEFE:
            return f"Das Schema ist zu tief verschachtelt (höchstens {MAX_TIEFE} Ebenen)."
        if tiefe and any(schluessel in teil for schluessel in _NUR_AN_DER_WURZEL):
            return "$id und $schema sind nur am obersten Element erlaubt."
        if any(schluessel in teil for schluessel in _NICHT_UNTERSTUETZT):
            return "Anker und dynamische Verweise ($anchor, $dynamicRef …) gehen nicht."
        verweis = teil.get("$ref")
        if verweis is None:
            continue
        if not isinstance(verweis, str) or not (verweis == "#" or verweis.startswith("#/")):
            return "Verweise ($ref) dürfen nur innerhalb des Schemas zeigen (#/…)."
        if not isinstance(_ziel(schema, verweis), (dict, bool)):
            return f"Der Verweis {verweis} zeigt auf nichts im Schema."
    try:
        validator_for(schema, default=Draft202012Validator).check_schema(schema)
    except SchemaError as err:
        return err.message
    return None


def _ohne_muster(schema: Any) -> Any:
    """Kopie ohne ``pattern``/``patternProperties``, nur zum Prüfen.

    Fällt ``patternProperties`` weg, fällt ``additionalProperties`` desselben
    Objekts mit — sonst zählten die Schlüssel, die das Muster zugelassen hätte,
    als zusätzliche. Gab es irgendwo ``patternProperties``, fällt jedes
    ``unevaluatedProperties``: es sieht über ``allOf`` & Co. auch Muster anderer
    Teilschemata. Die Kopie ist damit nie strenger als das Original.
    """
    lockern = any("patternProperties" in teil for teil, _ in _teilschemata(schema))

    def kopie(teil: Any) -> Any:
        if not isinstance(teil, dict):
            return teil
        neu: dict[str, Any] = {}
        for schluessel, wert in teil.items():
            if schluessel in _MUSTER:
                continue
            if schluessel == "additionalProperties" and "patternProperties" in teil:
                continue
            if schluessel == "unevaluatedProperties" and lockern:
                continue
            if schluessel in _EIN_SCHEMA and isinstance(wert, dict):
                neu[schluessel] = kopie(wert)
            elif schluessel in _SCHEMA_LISTE and isinstance(wert, list):
                neu[schluessel] = [kopie(s) for s in wert]
            elif schluessel in _SCHEMA_KARTE and isinstance(wert, dict):
                neu[schluessel] = {name: kopie(s) for name, s in wert.items()}
            else:
                neu[schluessel] = wert
        return neu

    return kopie(schema)


def _abweichungen(schema: Any, wert: Any, vorne: tuple[str, ...]) -> list[tuple[str, str]]:
    """``(pfad, meldung)`` je Abweichung — geprüft ohne Nachladen und ohne Muster."""
    klasse = validator_for(schema, default=Draft202012Validator)
    pruefer = klasse(_ohne_muster(schema), registry=Registry())
    try:
        return [(".".join((*vorne, *(str(t) for t in f.absolute_path))) or "(oben)", f.message)
                for f in pruefer.iter_errors(wert)]
    except Unresolvable:
        # Am Eingang ausgeschlossen; nicht prüfbar heißt nicht angenommen.
        return [(".".join(vorne) or "(oben)",
                 "Das Schema verweist auf etwas, das es nicht enthält.")]


def argument_fehler(parameter: dict[str, Any] | None, args: dict[str, Any]) -> list[str]:
    """Abweichungen der Argumente von den angebotenen Parametern.

    Jede als ``pfad: meldung``, höchstens :data:`MAX_MELDUNGEN`; leer heißt:
    passt. Ohne ``parameter`` (eine Definition ohne Schema) gibt es nichts zu
    prüfen. Die Hülle (``text``, Pflichtfelder) und ``result`` werden getrennt
    geprüft: das Gastgeber-Schema ist dabei seine eigene Wurzel.
    """
    if not parameter:
        return []
    eigenschaften = parameter.get("properties")
    ergebnis = eigenschaften.get("result") if isinstance(eigenschaften, dict) else None
    if ergebnis is None:
        fehler = _abweichungen(parameter, args, ())
    else:
        huelle = {**parameter, "properties": {**eigenschaften, "result": True}}
        fehler = _abweichungen(huelle, args, ())
        if isinstance(args, dict) and "result" in args:
            fehler += _abweichungen(ergebnis, args["result"], ("result",))
    fehler.sort(key=lambda f: f[0])
    return [f"{pfad}: {meldung}" for pfad, meldung in fehler[:MAX_MELDUNGEN]]


def ergebnis_ungueltig(fehler: list[str]) -> str:
    """Die Werkzeug-Antwort an das Modell, wenn das Ergebnis nicht passt."""
    zeilen = "\n".join(f"- {f}" for f in fehler)
    return (
        "Fehler: Das Ergebnis passt nicht zum verlangten Schema. Abweichungen:\n"
        f"{zeilen}\n"
        "Korrigiere es und rufe das Werkzeug noch einmal auf."
    )
