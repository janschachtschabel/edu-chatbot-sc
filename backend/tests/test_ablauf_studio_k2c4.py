"""Paket K2c-4 (Plan 2026-11-08): „Ablauf prüfen“ und die Schrittfolge im Studio — was das Backend
dafür liefert.

- ``x-widget: ablauf`` am Modell ``AblaufArea``: das Studio setzt unter jeden Ablauf den Knopf
  „Prüfen“ (``POST /api/config/ablauf-pruefen``, K2c-1) und die Schrittfolge.
- Nur Schema: Daten und Fassung bleiben (die Goldfassung steht in ``test_ablauf_studio_k2c1``).
"""

from __future__ import annotations

from boerdi.domain.config_models.ablauf import AblaufArea


def test_der_ablauf_traegt_die_auszeichnung():
    schema = AblaufArea.model_json_schema()
    assert schema.get("x-widget") == "ablauf"
    defs = schema["$defs"]
    # nur der Ablauf, nicht seine Teile
    assert "x-widget" not in defs["Schritt"]


def test_die_auszeichnung_aendert_keine_daten():
    roh = {"id": "a", "titel": {"de": "A"}, "schritte": [{"id": "e", "typ": "ende"}]}
    assert "x-widget" not in AblaufArea.model_validate(roh).model_dump(exclude_none=True)
