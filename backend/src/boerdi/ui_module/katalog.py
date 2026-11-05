"""Katalog der UI-Module: Manifeste laden und prüfen (Paket U1-a).

Die Manifeste entstehen im Frontend, je Modul-Ordner eine ``manifest.json``; ``npm run
module:register`` legt sie gesammelt als ``manifeste.json`` neben dieses Modul und kopiert das
Vertrags-Schema ``manifest.schema.json`` mit. Beides ist erzeugt — von Hand geändert wäre es eine
zweite Wahrheit (Drift-Wächter in ``tests/test_ui_modul_katalog.py``).

Geprüft wird beim Laden: jedes Manifest gegen das Schema, ``eingabe``/``antwort`` als gültiges
JSON Schema, ``textfassung.feld`` als Feld der Eingabe, jedes Beispiel gegen ``eingabe`` und, wo
vorhanden, ``antwort`` des Moduls, Namen eindeutig. Ein Modul, dessen eigene Beispiele nicht
zu seiner Beschreibung passen, brächte der KI eine falsche Struktur bei.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path
from typing import Any, Final

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

_HIER: Final = Path(__file__).resolve().parent
STANDARD_PFAD: Final = _HIER / "manifeste.json"
SCHEMA_PFAD: Final = _HIER / "manifest.schema.json"

Manifest = dict[str, Any]


class KatalogFehler(ValueError):
    """Ein Manifest passt nicht zum Vertrag; die Meldung nennt Modul und Pfad."""


@functools.cache
def vertrags_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PFAD.read_text(encoding="utf-8"))


def _fehlerliste(validator: Draft202012Validator, wert: Any) -> list[str]:
    return [f"{'/'.join(str(t) for t in f.absolute_path) or '(Wurzel)'}: {f.message}"
            for f in sorted(validator.iter_errors(wert), key=lambda f: list(f.absolute_path))]


def daten_fehler(manifest: Manifest, daten: Any) -> list[str]:
    """Abweichungen der Daten eines Blocks von der Eingabe des Moduls (leer = passt)."""
    return _fehlerliste(Draft202012Validator(manifest["eingabe"]), daten)


def antwort_fehler(manifest: Manifest, antwort: Any) -> list[str]:
    """Abweichungen einer Antwort vom Antwort-Schema eines abfragenden Moduls."""
    return _fehlerliste(Draft202012Validator(manifest.get("antwort") or {"type": "object"}),
                        antwort)


def _pruefe(manifest: Any, schema_pruefer: Draft202012Validator) -> Manifest:
    name = manifest.get("name", "?") if isinstance(manifest, dict) else "?"
    fehler = _fehlerliste(schema_pruefer, manifest)
    if fehler:
        raise KatalogFehler(f"Manifest {name}: " + "; ".join(fehler))
    dienst = manifest.get("dienst")
    schemas = {feld: manifest[feld] for feld in ("eingabe", "antwort") if feld in manifest}
    if isinstance(dienst, dict):
        # Paket U2 (T-4): der Auftrag ist die Werkzeugbeschreibung — Datenquelle und Dienst sind
        # zwei Wege zu denselben Block-Daten, nie beide.
        if manifest.get("datenquelle"):
            raise KatalogFehler(f"Manifest {name}: Datenquelle und Dienst schließen sich aus")
        schemas["dienst.parameter"] = dienst["parameter"]
    for feld, schema in schemas.items():
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError as e:
            raise KatalogFehler(f"Manifest {name}, {feld}: kein gültiges JSON Schema "
                                f"({e.message})") from e
    feld = manifest["textfassung"].get("feld")
    if feld is not None and feld not in manifest["eingabe"].get("properties", {}):
        raise KatalogFehler(f"Manifest {name}: textfassung.feld „{feld}“ steht nicht in eingabe")
    for beispiel in manifest["beispiele"]:
        titel = beispiel["titel"]
        if fehler := daten_fehler(manifest, beispiel["daten"]):
            raise KatalogFehler(f"Manifest {name}, Beispiel „{titel}“: " + "; ".join(fehler))
        if "antwort" in beispiel and (fehler := antwort_fehler(manifest, beispiel["antwort"])):
            raise KatalogFehler(f"Manifest {name}, Beispiel „{titel}“, Antwort: "
                                + "; ".join(fehler))
    return manifest


def lade(pfad: Path | None = None) -> dict[str, Manifest]:
    """Alle Manifeste nach Name; ohne Datei leer. Wirft ``KatalogFehler`` bei Verstößen."""
    datei = pfad or STANDARD_PFAD
    if not datei.exists():
        return {}
    roh = json.loads(datei.read_text(encoding="utf-8"))
    if not isinstance(roh, list):
        raise KatalogFehler(f"{datei.name}: erwartet eine Liste von Manifesten")
    schema_pruefer = Draft202012Validator(vertrags_schema())
    katalog: dict[str, Manifest] = {}
    for eintrag in roh:
        manifest = _pruefe(eintrag, schema_pruefer)
        if manifest["name"] in katalog:
            raise KatalogFehler(f"Manifest {manifest['name']}: Name doppelt")
        katalog[manifest["name"]] = manifest
    return katalog


@functools.cache
def katalog() -> dict[str, Manifest]:
    """Der ausgelieferte Katalog, einmal je Prozess geladen."""
    return lade()


def widget_module() -> list[str]:
    """Was das heutige Widget als ``environment.ui_module`` meldet: alle Katalog-Module, sortiert
    (die Schlüssel seines Registers, ``ui/src/shell/chat-shell.component.ts``). Die Evaluation
    meldet dieselbe Liste (Paket U1-g, G-1)."""
    return sorted(katalog())
