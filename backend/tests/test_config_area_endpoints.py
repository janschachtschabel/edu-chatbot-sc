"""P2-5: typed config-area endpoints + generic file CRUD + element browser.

Ported behavior from ALT config_areas.py / config_files.py / config_elements.py:
same validation status codes (400 business rules, 422 pydantic/entry), same
re-read-after-write shape. Storage is jsonb (V2) instead of YAML files —
DATA + VALIDATION preserved, the YAML-dumper machinery is intentionally dropped.

Runs against a fresh Compose-PG test DB with a real (non-listening) ConfigStore
bound to the loader facade; each test seeds only the areas it needs.
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.config_store import ConfigStore
from boerdi.services.mcp import transport
from boerdi.settings import Settings, get_settings
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p2_endpoints_test"
_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture(scope="module")
def _module_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


@pytest.fixture()
def cfg(_module_db, monkeypatch):
    """(client, seed) with a real store bound; DB rows are per-test-fresh
    via a unique store cache — endpoints read only what the test seeded."""
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    # NullPool: the fixture mixes asyncio.run() seeding with the TestClient's
    # own loop; a pooled asyncpg connection would be reused across loops.
    engine = make_engine(
        Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
        poolclass=NullPool,
    )
    store = ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(_DB))  # no start(): no listener
    config_loader.bind_store(store)
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    client = TestClient(create_app())  # no context manager -> lifespan not run

    def seed(area: str, data: dict) -> None:
        asyncio.run(store.put(area, data, updated_by="seed"))

    yield client, seed
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())


# ── generic file CRUD ──────────────────────────────────────────────
def test_file_list_and_read(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config", {"welcome": {"greeting": "Hi", "quick_replies": ["a"]}})
    listing = client.get("/api/config/files", headers=_AUTH)
    assert listing.status_code == 200
    paths = {f["path"] for f in listing.json()}
    assert "01-base/welcome-config.yaml" in paths

    r = client.get("/api/config/file",
                   params={"path": "01-base/welcome-config.yaml"}, headers=_AUTH)
    assert r.status_code == 200
    assert "greeting: Hi" in r.json()["content"]


def test_file_read_missing_404_and_traversal_400(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/file", params={"path": "01-base/nope.yaml"},
                      headers=_AUTH).status_code == 404
    assert client.get("/api/config/file", params={"path": "../../../etc/passwd"},
                      headers=_AUTH).status_code == 400


def test_file_write_and_delete(cfg) -> None:
    client, _ = cfg
    body = {"path": "01-base/welcome-config.yaml",
            "content": "welcome:\n  greeting: Servus\n  quick_replies: [x]\n"}
    assert client.put("/api/config/file", json=body, headers=_AUTH).json()["status"] == "saved"
    # now readable
    assert "Servus" in client.get("/api/config/file",
                                  params={"path": body["path"]}, headers=_AUTH).json()["content"]
    d = client.request("DELETE", "/api/config/file",
                       params={"path": body["path"]}, headers=_AUTH)
    assert d.status_code == 200 and d.json()["status"] == "deleted"
    assert client.get("/api/config/file", params={"path": body["path"]},
                      headers=_AUTH).status_code == 404


def test_file_write_traversal_400(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/file",
                   json={"path": "../evil.yaml", "content": "x"}, headers=_AUTH)
    assert r.status_code == 400


# ── welcome ────────────────────────────────────────────────────────
def test_welcome_get_default_and_put_roundtrip(cfg) -> None:
    client, seed = cfg
    seed("01-base/welcome-config",
         {"welcome": {"greeting": "Moin", "quick_replies": ["a", "b"], "tour_reply": "a"}})
    g = client.get("/api/config/welcome", headers=_AUTH).json()
    assert g == {"greeting": "Moin", "quick_replies": ["a", "b"], "tour_reply": "a"}

    put = client.put("/api/config/welcome", headers=_AUTH, json={
        "greeting": "Servus", "quick_replies": ["x", "y"], "tour_reply": "y"})
    assert put.status_code == 200
    assert put.json()["greeting"] == "Servus"
    # persisted -> GET reflects
    assert client.get("/api/config/welcome", headers=_AUTH).json()["tour_reply"] == "y"


def test_welcome_put_rejects_empty_and_bad_tour_reply(cfg) -> None:
    client, _ = cfg
    assert client.put("/api/config/welcome", headers=_AUTH, json={
        "greeting": "  ", "quick_replies": ["a"]}).status_code == 400
    assert client.put("/api/config/welcome", headers=_AUTH, json={
        "greeting": "hi", "quick_replies": []}).status_code == 400
    assert client.put("/api/config/welcome", headers=_AUTH, json={
        "greeting": "hi", "quick_replies": ["a"], "tour_reply": "not-in-list"}).status_code == 400


# ── privacy (safety forced true) ───────────────────────────────────
def test_privacy_put_forces_safety_true(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/privacy", headers=_AUTH, json={
        "messages": False, "memory": False, "quality": False, "safety": False})
    assert r.status_code == 200
    assert r.json() == {"messages": False, "memory": False, "quality": False, "safety": True}


# ── context-actions ────────────────────────────────────────────────
def _valid_context_payload() -> dict:
    pills = {k: [{"label": "Los", "kind": "text"}] for k in ("collection", "content", "topic")}
    return {
        "enabled": True, "report_url": "https://x/report",
        "greetings": {"collection": "c", "content": "i", "topic": "t"},
        "pills": pills, "curate_prompt": "kuratiere",
    }


def test_context_actions_put_roundtrip(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/context-actions", headers=_AUTH, json=_valid_context_payload())
    assert r.status_code == 200
    assert r.json()["report_url"] == "https://x/report"
    assert r.json()["pills"]["collection"][0]["label"] == "Los"


def test_context_actions_put_validation(cfg) -> None:
    client, _ = cfg
    bad = _valid_context_payload()
    bad["report_url"] = "  "
    assert client.put("/api/config/context-actions", headers=_AUTH, json=bad).status_code == 400
    bad2 = _valid_context_payload()
    bad2["pills"]["content"] = [{"label": "X", "kind": "action"}]  # action pill without action
    assert client.put("/api/config/context-actions", headers=_AUTH, json=bad2).status_code == 400


# ── canvas material-types ──────────────────────────────────────────
def test_canvas_material_types_put(cfg) -> None:
    client, _ = cfg
    ok = {"material_types": [
        {"id": "ab", "label": "Arbeitsblatt", "category": "didaktisch"},
        {"id": "an", "label": "Analyse", "category": "analytisch"},
    ]}
    assert client.put("/api/config/canvas/material-types",
                      headers=_AUTH, json=ok).status_code == 200

    dup = {"material_types": [
        {"id": "x", "label": "A", "category": "didaktisch"},
        {"id": "x", "label": "B", "category": "didaktisch"},
    ]}
    assert client.put("/api/config/canvas/material-types",
                      headers=_AUTH, json=dup).status_code == 400
    badcat = {"material_types": [{"id": "y", "label": "Y", "category": "bogus"}]}
    assert client.put("/api/config/canvas/material-types",
                      headers=_AUTH, json=badcat).status_code == 400


# ── intents / states / entities (single-area list editors) ─────────
def test_intents_put_and_get_roundtrip(cfg) -> None:
    client, _ = cfg
    payload = {"intents": [
        {"id": "I01", "label": "Orientierung", "trigger_verbs": ["hilf"]},
        {"id": "I02", "label": "Suche"},
    ]}
    r = client.put("/api/config/intents", headers=_AUTH, json=payload)
    assert r.status_code == 200 and r.json()["count"] == 2
    got = client.get("/api/config/intents", headers=_AUTH).json()["intents"]
    assert [i["id"] for i in got] == ["I01", "I02"]


def test_intents_put_422_on_bad_entry_and_400_on_dup(cfg) -> None:
    client, _ = cfg
    assert client.put("/api/config/intents", headers=_AUTH,
                      json={"intents": [{"label": "no id"}]}).status_code == 422
    assert client.put("/api/config/intents", headers=_AUTH, json={"intents": [
        {"id": "I01", "label": "a"}, {"id": "I01", "label": "b"}]}).status_code == 400


def test_states_put_roundtrip(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/states", headers=_AUTH, json={"states": [
        {"id": "S1", "label": "Orientierung", "bot_directive": "line1\nline2"}]})
    assert r.status_code == 200
    got = client.get("/api/config/states", headers=_AUTH).json()["states"]
    assert got[0]["bot_directive"] == "line1\nline2"


def test_entities_put_preserves_accumulation_rules(cfg) -> None:
    client, seed = cfg
    seed("04-entities/entities", {
        "entities": [{"id": "old", "label": "Old"}],
        "accumulation_rules": {"initial": "replace"},
    })
    r = client.put("/api/config/entities", headers=_AUTH, json={
        "entities": [{"id": "fach", "label": "Fach"}]})
    assert r.status_code == 200
    got = client.get("/api/config/entities", headers=_AUTH).json()
    assert [e["id"] for e in got["entities"]] == ["fach"]
    assert got["accumulation_rules"] == {"initial": "replace"}  # untouched


# ── personas / patterns (per-area MD editors) ──────────────────────
def test_personas_put_writes_per_area(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/personas", headers=_AUTH, json={"personas": [
        {"id": "P-LEH", "label": "Lehrkraft", "tone": "sachlich",
         "goals": ["helfen"], "personality_text": "Ich bin sachlich."},
        {"id": "P-LER", "label": "Lernende", "positive_markers": ["ich lerne"]},
    ]})
    assert r.status_code == 200 and r.json()["count"] == 2
    got = client.get("/api/config/personas", headers=_AUTH).json()["personas"]
    by_id = {p["id"]: p for p in got}
    assert by_id["P-LEH"]["tone"] == "sachlich"
    assert by_id["P-LEH"]["goals"] == ["helfen"]
    assert by_id["P-LER"]["positive_markers"] == ["ich lerne"]


def test_patterns_put_validation_and_roundtrip(cfg) -> None:
    client, _ = cfg
    assert client.put("/api/config/patterns", headers=_AUTH, json={"patterns": [
        {"id": "M01", "label": "X", "quick_replies_mode": "bogus"}]}).status_code == 400
    assert client.put("/api/config/patterns", headers=_AUTH, json={"patterns": [
        {"id": "M01", "label": "A"}, {"id": "M01", "label": "B"}]}).status_code == 400
    r = client.put("/api/config/patterns", headers=_AUTH, json={"patterns": [
        {"id": "M05", "label": "Suche", "core_rule": "Immer suchen.",
         "trigger_phrases": ["such"], "body_md": "Details."}]})
    assert r.status_code == 200 and r.json()["count"] == 1
    got = client.get("/api/config/patterns", headers=_AUTH).json()["patterns"]
    m05 = next(p for p in got if p["id"] == "M05")
    assert m05["core_rule"] == "Immer suchen."
    assert "_source_file" not in m05


# ── tone-modifiers (persona frontmatter + default) ─────────────────
def test_tone_modifiers_get_and_put(cfg) -> None:
    client, seed = cfg
    seed("04-personas/leh", {"frontmatter": {"id": "P-LEH", "label": "Lehrkraft",
                                             "tone": "sachlich"}, "body": "x"})
    seed("01-base/tone-modifiers", {"default_modifier": {"tone": "locker"}})
    g = client.get("/api/config/tone-modifiers", headers=_AUTH).json()
    assert "P-LEH" in g["modifiers"]
    assert g["default_modifier"]["tone"] == "locker"

    put = client.put("/api/config/tone-modifiers", headers=_AUTH, json={
        "modifiers": {"P-LEH": {"tone": "warm", "formality": "siezen"}},
        "default_modifier": {"tone": "formell"},
    })
    assert put.status_code == 200
    assert put.json()["modifiers"]["P-LEH"]["tone"] == "warm"
    assert put.json()["default_modifier"]["tone"] == "formell"


# ── mcp-servers registry (GET here; the PUT + discover SSRF gates + the tool-
# description enrichment unit tests live in their own offline files) ──
def test_mcp_servers_get_returns_registry(cfg, monkeypatch) -> None:
    client, seed = cfg
    # GET enriches each enabled server that has a url + tools via an MCP handshake;
    # wlo-mcp qualifies (env-owned url), so spy the network boundary to keep this
    # DB test offline. The enrichment itself is unit-tested in test_mcp_tool_descriptions.
    async def _no_handshake(url):
        return []

    monkeypatch.setattr(transport, "discover_server_tools", _no_handshake)
    seed("05-knowledge/mcp-servers", {"servers": [
        {"id": "wlo-mcp", "name": "WLO", "enabled": True, "tools": ["search"]},
        {"id": "other", "name": "Other", "enabled": False, "url": "https://x/mcp"},
    ]})
    servers = client.get("/api/config/mcp-servers", headers=_AUTH).json()
    by_id = {s["id"]: s for s in servers}
    assert by_id["wlo-mcp"]["url_readonly"] is True  # primary URL is env-owned
    assert by_id["other"]["url"] == "https://x/mcp"


# ── element browser ────────────────────────────────────────────────
def test_elements_browser_groups(cfg) -> None:
    client, _ = cfg
    client.put("/api/config/intents", headers=_AUTH,
               json={"intents": [{"id": "I01", "label": "Orient"}]})
    client.put("/api/config/personas", headers=_AUTH,
               json={"personas": [{"id": "P-LEH", "label": "Lehrkraft"}]})
    els = client.get("/api/config/elements", headers=_AUTH).json()
    assert set(els) >= {"patterns", "personas", "intents", "states", "signals",
                        "entities", "device", "base_files"}
    assert any(i["id"] == "I01" for i in els["intents"])
    assert any(p["id"] == "P-LEH" for p in els["personas"])
    assert els["intents"][0]["file"] == "04-intents/intents.yaml"
    assert isinstance(els["base_files"], list) and els["base_files"]


# ── auth ───────────────────────────────────────────────────────────
def test_typed_endpoints_require_studio_key(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/welcome").status_code == 401
    assert client.put("/api/config/intents", json={"intents": []}).status_code == 401
    assert client.get("/api/config/elements").status_code == 401
