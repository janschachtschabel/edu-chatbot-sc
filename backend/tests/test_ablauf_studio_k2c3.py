"""Paket K2c-3 (Plan 2026-11-08): ``argumente`` und ``daten`` als Tabelle im Studio — was das
Backend dafür liefert.

- ``x-widget: teil-werte`` an ``Schritt.argumente`` und ``Schritt.daten`` (am Objekt, innen in
  ``… | None``): das Studio zeigt statt rohem JSON eine Tabelle Name → fester Text, Teil oder JSON.
- Katalog ``vorgang_teile``: die Teile, die Module in den Vorgang schreiben (``vorgang.schreibt`` im
  Manifest), dazu ``ablage`` (Übertragung in WLO). Die Teile aus ``schreibt`` und ``agent.ausgabe``
  der vorigen Schritte kennt nur das Formular selbst.
- Nur Schema: Daten und Fassung bleiben (die Goldfassung steht in ``test_ablauf_studio_k2c1``).
"""

from __future__ import annotations

from boerdi.domain.config_models.ablauf import Schritt


def _props() -> dict:
    return Schritt.model_json_schema()["properties"]


def test_argumente_und_daten_sind_teil_werte():
    for feld in ("argumente", "daten"):
        prop = _props()[feld]
        objekt = next(o for o in prop["anyOf"] if o.get("type") == "object")
        assert objekt.get("x-widget") == "teil-werte", feld
        assert "x-nur-bei" in prop, feld          # K2c-1 bleibt


def test_der_katalog_nennt_die_teile_der_module():
    from boerdi.api import config_choices

    eintraege = config_choices._SOURCES["vorgang_teile"]()
    werte = [e["value"] for e in eintraege]
    # Mindestens diese (ein neues Manifest darf Teile hinzufügen), sortiert und je einmal.
    assert {"ablage", "document", "draft", "structure"} <= set(werte)
    assert werte == sorted(set(werte))
    beschriftung = {e["value"]: e["label"] for e in eintraege}
    assert "ui_upload" in beschriftung["document"] and "ui_strukturentwurf" in beschriftung["draft"]
    assert all(e["area"] == "" for e in eintraege)
