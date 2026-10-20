"""Paket 17 (D5): die öffentliche OpenAPI-Spec — nur die Chat-API, mit Namen und Beschreibung.

Leitfaden „Übergabe an Team 6“: die Spec ist Voraussetzung für die Einbindung in die b-api;
Anzeigename und ein Beschreibungstext für Endnutzende stehen in ihr; Infrastruktur- und
Verwaltungs-Endpunkte erscheinen dort nicht. Die volle Spec (Studio, Eval, Konfiguration)
gibt es nur am internen Port. Der eingefrorene Gesamtvertrag (``openapi-v1.json``) bleibt.
"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from boerdi.api.intern import create_intern_app
from boerdi.api.openapi_public import OEFFENTLICH, oeffentliche_spec
from boerdi.main import create_app
from boerdi.settings import get_settings


def _operationen(spec: dict) -> set[tuple[str, str]]:
    return {(pfad, methode) for pfad, ops in spec["paths"].items() for methode in ops}


def test_die_oeffentliche_spec_traegt_nur_die_chat_api() -> None:
    spec = TestClient(create_app()).get("/openapi.json").json()
    assert _operationen(spec) == set(OEFFENTLICH)
    assert not any(p.startswith(("/api/config/data", "/api/eval", "/studio", "/api/health"))
                   for p in spec["paths"])


def test_name_beschreibung_und_version(monkeypatch) -> None:
    monkeypatch.setenv("BOERDI_VERSION", "0.6.0")
    get_settings.cache_clear()
    spec = oeffentliche_spec(create_app())
    get_settings.cache_clear()
    assert spec["info"]["title"].startswith("BOERDi")
    assert "WirLernenOnline" in spec["info"]["description"]
    assert spec["info"]["version"] == "0.6.0"


def test_nur_die_gebrauchten_schemas() -> None:
    spec = oeffentliche_spec(create_app())
    schemas = set(spec["components"]["schemas"])
    assert "ChatRequest" in schemas and "ChatResponse" in schemas
    assert "LoadTestProfile" not in schemas and "GoldenRunRequest" not in schemas
    # jede Referenz löst sich auf
    text = json.dumps(spec)
    for name in schemas:
        assert f"#/components/schemas/{name}" in text or name in ("HTTPValidationError",)
    for ref in {t.split('"')[0] for t in text.split("#/components/schemas/")[1:]}:
        assert ref in schemas, ref


def test_die_volle_spec_nur_am_internen_port() -> None:
    haupt = create_app()
    intern = TestClient(create_intern_app(haupt, beendet=lambda: False))
    voll = intern.get("/openapi-full.json").json()
    assert "/api/eval/runs" in voll["paths"]
    assert TestClient(haupt).get("/openapi-full.json").status_code == 404


def test_keine_offene_doku_oberflaeche() -> None:
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404


def test_export_kennt_beide_dateien() -> None:
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parents[1] / "scripts" / "export_openapi.py"
    modul_spec = importlib.util.spec_from_file_location("export_openapi", pfad)
    modul = importlib.util.module_from_spec(modul_spec)
    modul_spec.loader.exec_module(modul)
    assert modul.OUT_PUBLIC.name == "openapi-public.json"
    oeffentlich = json.loads(modul.render_public())
    assert _operationen(oeffentlich) == set(OEFFENTLICH)


def test_die_interne_app_ist_unabhaengig_von_einer_leeren_haupt_app() -> None:
    assert "paths" in TestClient(
        create_intern_app(FastAPI(), beendet=lambda: False)).get("/openapi-full.json").json()


def test_agent_nennt_die_persoenliche_anmeldung_vor_dem_admin_schluessel() -> None:
    """Review Phase D (C7): ausgewiesen war nur ``StudioKey`` — der Admin-Schlüssel. Wer danach
    eine Gastanwendung baut, bettete ihn ein; vorgesehen ist der Zugangsblock der Person
    (``api/turn_auth.require_agent_caller``)."""
    spec = oeffentliche_spec(create_app())
    for pfad in ("/api/agent", "/api/agent/stream"):
        sicherheit = spec["paths"][pfad]["post"]["security"]
        assert sicherheit[0] == {"WloAccessBlock": []}
        assert {"StudioKey": []} in sicherheit
    schema = spec["components"]["securitySchemes"]["WloAccessBlock"]
    assert schema == {"type": "apiKey", "in": "header", "name": "WLO-Access-Block",
                      "description": schema["description"]}
