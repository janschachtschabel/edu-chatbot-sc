"""Befundliste §2, ST-5 Befund 4: die Muster-Kennung ``AGENT`` ist reserviert.

``AGENT`` kennzeichnet die Züge der Agent-Schleife (``domain/agent_pattern``);
``services/turn_assembly`` und ``services/turn_links`` erkennen sie daran. Eine
Muster-Datei mit dieser Kennung schaltete in der Muster-Maschine den
Karten-Schutz ab.
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from boerdi.domain.agent_pattern import AGENT_PATTERN_ID
from boerdi.domain.config_models.patterns import (
    RESERVIERTE_KENNUNGEN,
    PatternArea,
    PatternFrontmatter,
)
from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.config_loader import classification
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    return TestClient(create_app())  # ohne Kontextmanager: keine Lebensdauer, keine DB


@pytest.fixture()
def geschrieben(monkeypatch) -> list[str]:
    """Die beiden Schreib-Grenzen; was hier ankommt, wäre gespeichert."""
    aufrufe: list[str] = []

    async def _area(key, data, updated_by="studio", **_bedingung):  # D5: Version/Anlegen
        aufrufe.append(key)
        return 1

    async def _datei(rel_path, content, **_bedingung):  # Paket 4 D5: Version/Anlegen
        aufrufe.append(rel_path)
        return 1

    monkeypatch.setattr(config_loader, "write_area", _area)
    monkeypatch.setattr(config_loader, "write_config_file", _datei)
    monkeypatch.setattr(config_loader, "load_pattern_definitions", lambda: [])
    return aufrufe


# Review 2026-10-03: Das Tor stand nur im Modell. Das rohe Datei-Schreiben und
# ``PUT /api/config/patterns`` meldeten „gespeichert“, und der Lader liess das
# Muster danach still fallen.


def test_rohes_datei_schreiben_weist_die_kennung_ab(client, geschrieben):
    r = client.put("/api/config/file", headers=_AUTH, json={
        "path": "03-patterns/boese.md",
        "content": "---\nid: AGENT\nlabel: Boese\n---\n# Boese\nText\n",
    })
    assert r.status_code == 400
    assert "AGENT" in r.json()["detail"]
    assert geschrieben == []


def test_getipptes_schreiben_weist_die_kennung_ab(client, geschrieben):
    r = client.put("/api/config/data/03-patterns/boese", headers=_AUTH, json={
        "data": {"frontmatter": {"id": "AGENT", "label": "Boese"}, "body": "Text"},
    })
    assert r.status_code == 400
    assert geschrieben == []


def test_muster_endpunkt_weist_die_kennung_ab(client, geschrieben):
    r = client.put("/api/config/patterns", headers=_AUTH, json={
        "patterns": [{"id": "agent", "label": "Boese"}],
    })
    assert r.status_code == 400
    assert geschrieben == []


def test_gewoehnliches_muster_wird_weiter_gespeichert(client, geschrieben):
    r = client.put("/api/config/file", headers=_AUTH, json={
        "path": "03-patterns/m99-neu.md",
        "content": "---\nid: M99\nlabel: Neu\n---\n# Neu\nText\n",
    })
    assert r.status_code == 200
    assert geschrieben == ["03-patterns/m99-neu.md"]


def test_die_kennung_der_agent_zuege_ist_reserviert():
    assert AGENT_PATTERN_ID in RESERVIERTE_KENNUNGEN


@pytest.mark.parametrize("kennung", ["AGENT", "agent", " Agent "])
def test_das_modell_weist_die_reservierte_kennung_ab(kennung):
    # Das Modell ist das Tor von ``PUT /api/config/data/03-patterns/…``.
    with pytest.raises(ValidationError):
        PatternFrontmatter(id=kennung)
    with pytest.raises(ValidationError):
        PatternArea.model_validate({"frontmatter": {"id": kennung}, "body": ""})


def test_gewoehnliche_kennungen_bleiben_gueltig():
    assert PatternFrontmatter(id="M01").id == "M01"
    assert PatternFrontmatter().id == ""


def test_der_lader_ueberspringt_die_reservierte_kennung(monkeypatch, caplog):
    # Der Lader liest die gespeicherten Daten roh, ohne das Modell: eine Datei
    # aus der Zeit vor dem Tor oder aus einem Import muss er selbst aussieben.
    daten = {
        "03-patterns/m01": {"frontmatter": {"id": "M01"}, "body": "# M01\nText"},
        "03-patterns/boese": {"frontmatter": {"id": "AGENT"}, "body": "# X\nText"},
    }
    monkeypatch.setattr(classification, "cached_keys", lambda _prefix: sorted(daten))
    monkeypatch.setattr(classification, "area", lambda key: daten[key])
    with caplog.at_level(logging.WARNING):
        kennungen = [m["id"] for m in classification.load_pattern_definitions()]
    assert kennungen == ["M01"]
    assert "AGENT" in caplog.text
