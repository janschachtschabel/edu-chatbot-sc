"""ST-5 — ``GET /api/config/effects``: die Wirkungs-Zuordnung für das Studio.

TestClient ohne ``with`` (kein Lifespan, keine Postgres), die Vorgabe-Maschine
je Test gesetzt. Die Zuordnung selbst hält ``test_area_effects.py`` fest; hier
zählt, was die Route ausliefert und wer sie lesen darf.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.config_effects as effects_api
from boerdi.domain.area_effects import AREA_EFFECTS
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    return TestClient(create_app())


def test_liefert_die_zuordnung_und_die_vorgabe_maschine(client, monkeypatch) -> None:
    monkeypatch.setattr(effects_api, "choose_engine", lambda header: "agent")
    r = client.get("/api/config/effects", headers=_AUTH)
    assert r.status_code == 200
    body = r.json()
    assert body["engine"] == "agent"
    assert body["areas"] == AREA_EFFECTS


def test_fragt_nach_der_vorgabe_nicht_nach_einer_kopfzeile(client, monkeypatch) -> None:
    # Die Studio-Anfrage trägt keine Maschinen-Kopfzeile; gefragt ist die
    # gepflegte Vorgabe, die für jede Einbettung ohne eigene Wahl gilt.
    gefragt: list[object] = []
    monkeypatch.setattr(effects_api, "choose_engine",
                        lambda header: gefragt.append(header) or "pattern")
    client.get("/api/config/effects", headers={**_AUTH, "X-Boerdi-Engine": "agent"})
    assert gefragt == [None]


def test_braucht_den_studio_schluessel(client) -> None:
    assert client.get("/api/config/effects").status_code == 401
