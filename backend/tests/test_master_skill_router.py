"""AG-2: der Master-Skill im Studio — anzeigen und neu laden, nicht bearbeiten.

Der Master-Skill bleibt im Repositorium (Nutzer 2026-09-26: „das ist so
gewollt"). Das Studio zeigt Zustand und Wortlaut und verweist zum Bearbeiten
auf den Knoten. Harness wie ``test_safety_router.py``: ``TestClient`` ohne
Lifespan, der MCP-Abruf gefälscht.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.master_skill as api
from boerdi.main import create_app
from boerdi.services import master_skill
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k-studio-testkey"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    monkeypatch.setenv("MASTER_SKILL_ENABLED", "true")
    monkeypatch.setenv("MASTER_SKILL_NODE_ID", "knoten-1")
    get_settings.cache_clear()
    master_skill.leere_den_zwischenspeicher()
    monkeypatch.setattr(api, "get_repo_base_url", lambda: "https://repo.example")
    yield TestClient(create_app())
    master_skill.leere_den_zwischenspeicher()


def _fake_mcp(monkeypatch, *texte: str) -> list:
    aufrufe: list = []
    antworten = iter(texte)

    async def fake(name, args, **_kw):
        aufrufe.append((name, args))
        return next(antworten)

    monkeypatch.setattr(master_skill, "call_mcp_tool", fake)
    return aufrufe


def test_anzeige_liefert_zustand_wortlaut_und_bearbeiten_link(client, monkeypatch):
    text = "# Vorgehen\n\nSuche breit."
    _fake_mcp(monkeypatch, text)

    r = client.get("/api/master-skill", headers=_AUTH)

    assert r.status_code == 200
    d = r.json()
    assert (d["enabled"], d["node_id"], d["text"]) == (True, "knoten-1", text)
    # Paket F (Nutzer 2026-09-29): Bearbeiten öffnet den md-editor, die
    # Render-Seite bleibt zum Ansehen.
    assert d["edit_url"] == (
        "https://repo.example/edu-sharing/services/md-editor/?nodeId=knoten-1&field=file")
    assert d["view_url"] == "https://repo.example/edu-sharing/components/render/knoten-1"
    assert d["length"] == len(text) and len(d["sha256"]) == 64
    assert d["ttl_seconds"] == 300 and d["last_error"] is None


def test_neu_laden_holt_erneut(client, monkeypatch):
    aufrufe = _fake_mcp(monkeypatch, "# v1\n\nalt", "# v2\n\nneu")
    client.get("/api/master-skill", headers=_AUTH)

    r = client.post("/api/master-skill/reload", headers=_AUTH)

    assert r.status_code == 200 and r.json()["text"] == "# v2\n\nneu"
    assert len(aufrufe) == 2


def test_ohne_kennung_weder_text_noch_link(client, monkeypatch):
    monkeypatch.setenv("MASTER_SKILL_NODE_ID", "   ")
    get_settings.cache_clear()

    d = client.get("/api/master-skill", headers=_AUTH).json()

    assert (d["node_id"], d["text"], d["edit_url"], d["view_url"]) == ("", None, None, None)


def test_ohne_studio_schluessel_gesperrt(client):
    assert client.get("/api/master-skill").status_code == 401
    assert client.post("/api/master-skill/reload").status_code == 401
