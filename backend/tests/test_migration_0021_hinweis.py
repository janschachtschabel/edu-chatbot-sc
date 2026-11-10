"""Review PR #51 (Konfiguration, C2): Migration 0021 lässt Einträge des Katalogs fallen, die kein
Dokument werden können (Kennung ``katalog``, ungültig, doppelt, kein Objekt) — nicht still: die
Migration nennt sie, damit der Betrieb sie in ``config_history`` des Katalogs findet. Ohne Postgres
prüfbar, weil die Auswahl eine reine Funktion ist."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_PFAD = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0021_ablauf_dokumente.py"


def _migration():
    spec = importlib.util.spec_from_file_location("migration_0021", _PFAD)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    return modul


def test_uebersprungene_eintraege_werden_genannt():
    m = _migration()
    katalog = {"ablaeufe": [
        {"id": "lesen"}, {"id": "katalog"}, {"id": "../boese"}, {"id": "lesen"}, "kein objekt",
        {"titel": "ohne Kennung"}]}
    assert set(m._ablaeufe(katalog)) == {"lesen"}
    assert m._uebersprungen(katalog) == ["katalog", "../boese", "lesen (doppelt)", "(ohne Kennung)",
                                         "(ohne Kennung)"]


def test_ohne_ueberspringen_nichts_zu_nennen():
    m = _migration()
    assert m._uebersprungen({"ablaeufe": [{"id": "lesen"}, {"id": "schreiben"}]}) == []
    assert m._uebersprungen({"ablaeufe": "kaputt"}) == []
    assert m._uebersprungen(None) == []


def test_lange_kennungen_werden_gekuerzt():
    m = _migration()
    assert m._uebersprungen({"ablaeufe": [{"id": "x" * 200}]}) == ["x" * 40 + "…"]
