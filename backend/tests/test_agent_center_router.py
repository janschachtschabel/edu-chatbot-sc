"""ST-8: die Routen der Agent-Steuerzentrale im Studio.

Harness wie ``test_master_skill_router.py``: ``TestClient`` ohne Lifespan, die
Quellen hinter den Routen gefälscht. Geprüft wird hier nur, was der Router
selbst tut — Schlüssel, Parameter, Weitergabe. Was die Listen enthalten, prüfen
die Tests der Dienste.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.agent_center as api
from boerdi.i18n.messages import msg
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k-studio-testkey"}


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k-studio-testkey")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def test_werkzeuge_nur_mit_studio_schluessel(client, monkeypatch):
    monkeypatch.setattr(api, "werkzeugliste", lambda: {"tools": []})
    assert client.get("/api/agent-center/tools").status_code == 401
    r = client.get("/api/agent-center/tools", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"tools": []}


# ── Skill-Verzeichnis (ST-8c) ──────────────────────────────────────────


def test_verzeichnis_reicht_die_sammlung_durch(client, monkeypatch):
    gefragt: list[str] = []

    async def fake(sammlung):
        gefragt.append(sammlung)
        return {"collection_id": sammlung, "entries": []}

    monkeypatch.setattr(api, "skill_verzeichnis", fake)
    assert client.get("/api/agent-center/skills?collection=f35c17d1").status_code == 401
    r = client.get("/api/agent-center/skills?collection=f35c17d1", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"collection_id": "f35c17d1", "entries": []}
    assert gefragt == ["f35c17d1"]


@pytest.mark.parametrize("abfrage", ["", "?collection=", "?collection=a%20b",
                                     "?collection=" + "x" * 65, "?collection=../x"])
def test_verzeichnis_verlangt_eine_kennung(client, monkeypatch, abfrage):
    async def fake(_sammlung):  # pragma: no cover - darf nicht laufen
        raise AssertionError("ohne gültige Kennung kein MCP-Abruf")

    monkeypatch.setattr(api, "skill_verzeichnis", fake)
    assert client.get("/api/agent-center/skills" + abfrage, headers=_AUTH).status_code == 422


def test_ein_mcp_fehler_wird_502_mit_dem_grund(client, monkeypatch):
    async def fake(_sammlung):
        raise api.VerzeichnisFehler("mcp", "MCP error: timeout")

    monkeypatch.setattr(api, "skill_verzeichnis", fake)
    r = client.get("/api/agent-center/skills?collection=f35c17d1",
                   headers={**_AUTH, "Accept-Language": "de"})
    assert r.status_code == 502
    assert "timeout" in r.json()["detail"]
    assert r.json()["detail"].startswith("Das Repositorium")


def test_eine_unlesbare_antwort_wird_502_in_der_sprache_der_anfrage(client, monkeypatch):
    async def fake(_sammlung):
        raise api.VerzeichnisFehler("unlesbar")

    monkeypatch.setattr(api, "skill_verzeichnis", fake)
    url = "/api/agent-center/skills?collection=f35c17d1"
    deutsch = client.get(url, headers={**_AUTH, "Accept-Language": "de"})
    englisch = client.get(url, headers={**_AUTH, "Accept-Language": "en"})
    assert deutsch.status_code == englisch.status_code == 502
    assert deutsch.json()["detail"] == "Das Repositorium hat eine unlesbare Antwort geliefert."
    assert englisch.json()["detail"] == "The repository returned an unreadable answer."


# ── Skill-Suche per Suchbegriff (Paket F3) ──────────────────────────────


def test_suche_reicht_den_suchbegriff_bereinigt_durch(client, monkeypatch):
    gefragt: list[str] = []

    async def fake(begriff):
        gefragt.append(begriff)
        return {"query": begriff, "available": True, "entries": []}

    monkeypatch.setattr(api, "skill_suche", fake)
    assert client.get("/api/agent-center/skills/search?q=Optik").status_code == 401
    r = client.get("/api/agent-center/skills/search?q=%20Optik%20", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"query": "Optik", "available": True, "entries": []}
    assert gefragt == ["Optik"]


@pytest.mark.parametrize("abfrage", ["", "?q=", "?q=%20%20", "?q=" + "x" * 201])
def test_suche_verlangt_einen_suchbegriff(client, monkeypatch, abfrage):
    async def fake(_begriff):  # pragma: no cover - darf nicht laufen
        raise AssertionError("ohne Suchbegriff kein MCP-Abruf")

    monkeypatch.setattr(api, "skill_suche", fake)
    r = client.get("/api/agent-center/skills/search" + abfrage, headers=_AUTH)
    assert r.status_code == 422


def test_ein_fehler_der_suche_wird_502_in_der_sprache_der_anfrage(client, monkeypatch):
    async def fake(_begriff):
        raise api.VerzeichnisFehler("mcp", "MCP error: timeout")

    monkeypatch.setattr(api, "skill_suche", fake)
    url = "/api/agent-center/skills/search?q=Optik"
    deutsch = client.get(url, headers={**_AUTH, "Accept-Language": "de"})
    englisch = client.get(url, headers={**_AUTH, "Accept-Language": "en"})
    assert deutsch.status_code == englisch.status_code == 502
    assert deutsch.json()["detail"] == (
        "Das Repositorium hat die Skill-Suche nicht beantwortet (MCP error: timeout).")
    assert englisch.json()["detail"] == (
        "The repository did not answer the skill search (MCP error: timeout).")


# ── Der MCP-Fehlertext im Studio (Review 2026-09-29) ────────────────────
#
# Bis hierher ging er ungekürzt in die Antwort, bei einem Transportfehler samt
# interner MCP-Adresse; das Protokoll kürzt auf 200 Zeichen.

_ROUTEN = [
    ("skill_verzeichnis", "/api/agent-center/skills?collection=f35c17d1",
     "agentCenter.registryFailed"),
    ("skill_suche", "/api/agent-center/skills/search?q=Optik", "agentCenter.searchFailed"),
]


@pytest.mark.parametrize(("quelle", "url", "_code"), _ROUTEN)
def test_die_mcp_adresse_geht_nicht_ins_studio(client, monkeypatch, quelle, url, _code):
    # So kommt ein HTTP-Fehler des MCP-Servers (oder eines Proxys davor) an:
    # httpx nennt die angefragte URL.
    async def fake(_wert):
        raise api.VerzeichnisFehler("mcp", (
            "MCP error: Client error '401 Unauthorized' for url "
            "'http://wlo-mcp.intern:3000/mcp'\nFor more information check: "
            "https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/401"))

    monkeypatch.setattr(api, quelle, fake)
    r = client.get(url, headers=_AUTH)
    assert r.status_code == 502
    assert "wlo-mcp.intern" not in r.json()["detail"]
    assert "://" not in r.json()["detail"]
    assert "401 Unauthorized" in r.json()["detail"], "Der Grund bleibt lesbar"


@pytest.mark.parametrize(("quelle", "url", "code"), _ROUTEN)
def test_ein_langer_mcp_fehler_wird_gekuerzt(client, monkeypatch, quelle, url, code):
    async def fake(_wert):
        raise api.VerzeichnisFehler("mcp", "MCP error: " + "Invalid input " * 60)

    monkeypatch.setattr(api, quelle, fake)
    detail = client.get(url, headers={**_AUTH, "Accept-Language": "de"}).json()["detail"]
    assert len(detail) <= len(msg("de", code, error="")) + 200
    assert "…" in detail


# ── Prompt-Vorschau (ST-8d) ────────────────────────────────────────────


def test_vorschau_in_der_sprache_des_widgets(client, monkeypatch):
    gefragt: list[str] = []

    async def fake(sprache):
        gefragt.append(sprache)
        return {"locale": sprache, "chain": []}

    monkeypatch.setattr(api, "prompt_vorschau", fake)
    assert client.get("/api/agent-center/prompt").status_code == 401
    assert client.get("/api/agent-center/prompt", headers=_AUTH).json()["locale"] == "de"
    assert client.get("/api/agent-center/prompt?locale=en", headers=_AUTH).json()["locale"] == "en"
    assert client.get("/api/agent-center/prompt?locale=fr", headers=_AUTH).status_code == 422
    assert gefragt == ["de", "en"]
