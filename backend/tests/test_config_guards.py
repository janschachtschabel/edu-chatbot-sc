"""Schlüssel- und Modellprüfung der generischen Schreibwege (Paket 4, D3).

Externes Audit F07: Das Wiederherstellen schrieb Bereiche ohne Modellprüfung,
und ``.``-Segmente sowie verschachtelte Muster- und Personen-Schlüssel kamen
durch. Ohne Datenbank — die Endpunkt-Tests stehen in
``test_snapshots_endpoints.py`` und ``test_config_data_endpoint.py``.
"""

from __future__ import annotations

import pytest

from boerdi.api.config_guards import is_restorable_area_key, modell_fehler


@pytest.mark.parametrize("key", [
    "01-base/welcome-config",
    "01-base/rag-retrieval",          # ohne Modell — kommt trotzdem zurück
    "03-patterns/m01-krisen-empathie",
    "04-personas/p-lk",
])
def test_gueltige_schluessel_kommen_durch(key):
    assert is_restorable_area_key(key)


@pytest.mark.parametrize("key", [
    "01-base/./welcome-config",       # dieselbe Datei unter zweitem Namen
    "./01-base/welcome-config",
    "03-patterns/a/b",                 # je Muster genau ein Blatt
    "04-personas/x/y",
    "03-patterns",                     # die Gruppe selbst ist kein Dokument
    "04-personas",
    "../boese",
    "01-base//x",
    "/01-base/x",
])
def test_ungueltige_schluessel_werden_abgewiesen(key):
    assert not is_restorable_area_key(key)


def test_ein_wert_gegen_das_modell_wird_mit_ort_gemeldet():
    fehler = modell_fehler("01-base/welcome-config",
                           {"welcome": {"quick_replies": "not-a-list"}})
    assert fehler
    assert fehler[0]["loc"] == ["welcome", "quick_replies"]
    assert "input" not in fehler[0]  # der eingereichte Inhalt geht nicht zurück


def test_ein_gueltiger_bereich_hat_keine_fehler():
    assert modell_fehler("01-base/welcome-config",
                         {"welcome": {"quick_replies": ["a"]}}) == []


def test_ein_bereich_ohne_modell_passiert():
    assert modell_fehler("01-base/rag-retrieval", {"top_k": "sieben"}) == []


# ── Paket 4, D6: Lotsen-Regeln mit ungültigem Muster ──────────────────────────

def test_ein_ungueltiges_lotsen_muster_wird_beim_speichern_abgewiesen():
    from fastapi import HTTPException

    from boerdi.api.config_guards import _assert_area_document_safe

    doc = {"message_rules": [
        {"pattern": "oer", "label": "OER", "url": "https://wirlernenonline.de/oer"},
        {"pattern": "(", "label": "Kaputt", "url": "https://wirlernenonline.de/x"},
    ]}
    with pytest.raises(HTTPException) as err:
        _assert_area_document_safe("02-domain/guide-rules", doc, "de")
    assert err.value.status_code == 400
    assert "2" in err.value.detail and "Kaputt" in err.value.detail


def test_gueltige_lotsen_muster_passieren():
    from boerdi.api.config_guards import _assert_area_document_safe

    doc = {"message_rules": [{"pattern": "klima(wandel)?", "label": "K", "url": "https://x"}]}
    _assert_area_document_safe("02-domain/guide-rules", doc, "de")


@pytest.mark.parametrize("key", ["03-patterns/.", "04-personas/.", "03-patterns/.."])
def test_der_formular_weg_weist_punkt_blaetter_ab(key):
    # Prüfer 2026-10-04: `PUT /api/config/data/03-patterns/%2E` legte einen
    # Bereich `03-patterns/.` an. Das Wiederherstellen weist denselben Schlüssel
    # ab — aus einer Sicherung kam er also nie zurück, nur mit einer Warnung.
    from fastapi import HTTPException

    from boerdi.api.config_guards import _resolve_area

    with pytest.raises(HTTPException) as err:
        _resolve_area(key, file_key=True)
    assert err.value.status_code in (400, 404)
