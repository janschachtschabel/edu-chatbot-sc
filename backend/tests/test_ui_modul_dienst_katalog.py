"""Paket U2-b (Plan 2026-11-04, T-4): das Manifest-Feld ``dienst``.

Ein Modul mit Dienst bekommt seine Daten vom Backend selbst erzeugt (nicht aus einem MCP-Werkzeug
wie die Datenquelle): Die KI sieht nur ``dienst.parameter`` — den Auftrag. Datenquelle und Dienst
schließen sich aus; ``parameter`` muss ein gültiges JSON Schema eines Objekts sein.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from boerdi.ui_module import katalog

_PARAMETER = {"type": "object", "required": ["thema"],
              "properties": {"thema": {"type": "string", "description": "Das Thema."}}}


def _manifest(**mehr) -> dict:
    m = {
        "name": "ui_probe", "version": 1, "art": "anzeigen",
        "titel": {"de": "Probe"}, "beschreibung": "Zeigt eine Probe für die Tests an.",
        "eingabe": {"type": "object", "required": ["text"],
                    "properties": {"text": {"type": "string", "description": "Der Text."}}},
        "textfassung": {"vorlage": "markdown", "feld": "text"},
        "beispiele": [{"titel": "Kurz", "daten": {"text": "Hallo"}}],
    }
    m.update(mehr)
    return m


def _lade(tmp_path: Path, manifest: dict) -> dict:
    p = tmp_path / "manifeste.json"
    p.write_text(json.dumps([manifest]), encoding="utf-8")
    return katalog.lade(p)


def test_ein_dienst_mit_parametern_ist_gueltig(tmp_path):
    kat = _lade(tmp_path, _manifest(dienst={"name": "probe", "parameter": _PARAMETER}))
    assert kat["ui_probe"]["dienst"]["name"] == "probe"


def test_ohne_dienst_null_ist_erlaubt(tmp_path):
    assert "ui_probe" in _lade(tmp_path, _manifest(dienst=None))


@pytest.mark.parametrize("dienst", [
    {"name": "probe"},                                            # ohne parameter
    {"name": "Probe!", "parameter": _PARAMETER},                  # Name in falscher Form
    {"name": "probe", "parameter": {"type": "array"}},            # kein Objekt-Schema
    {"name": "probe", "parameter": _PARAMETER, "mehr": 1},        # unbekanntes Feld
])
def test_ein_falscher_dienst_wird_abgewiesen(tmp_path, dienst):
    with pytest.raises(katalog.KatalogFehler, match="dienst"):
        _lade(tmp_path, _manifest(dienst=dienst))


def test_ungueltige_parameter_sind_kein_json_schema(tmp_path):
    kaputt = {"type": "object", "properties": {"thema": {"type": "zeichenkette"}}}
    with pytest.raises(katalog.KatalogFehler, match="dienst.parameter"):
        _lade(tmp_path, _manifest(dienst={"name": "probe", "parameter": kaputt}))


def test_datenquelle_und_dienst_schliessen_sich_aus(tmp_path):
    with pytest.raises(katalog.KatalogFehler, match="Datenquelle und Dienst"):
        _lade(tmp_path, _manifest(
            dienst={"name": "probe", "parameter": _PARAMETER},
            datenquelle={"werkzeug": "browse_collection_tree", "argumente": ["subject"]}))
