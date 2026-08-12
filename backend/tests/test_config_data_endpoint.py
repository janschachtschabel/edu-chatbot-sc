"""9-3a: GET/PUT /api/config/data/{area} — the JSON counterpart to
GET /api/config/schema/{area}.

Why this exists: ``/api/config/file`` returns YAML *text*, which no form can
bind to, and the typed endpoints (``/config/welcome`` …) cover only 8 of the
35 areas. Without this pair the exported schema has nothing to render against
— that is the V3 gap ("every area editable, no forgotten ones").

The load-bearing contract is that PUT **replaces** and ``data`` is the WHOLE
document. Measured against the ALT config, 357 data paths are not pinned by
their area model (``01-base/policy`` -> ``rules[*].effect.disclaimer``,
``01-base/classify-overrides`` -> ``pattern_disambiguators_legacy[*]``), and
they sit *nested*, not at the top level. So a schema form must edit a copy of
the whole document and send it back whole — a server-side merge could not have
saved it (shallow protects the wrong level; deep cannot express deletion).
"""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from boerdi.main import create_app
from boerdi.services import config_loader
from boerdi.services.config_store import ConfigStore
from boerdi.settings import Settings, get_settings
from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_p9_data_test"
_AUTH = {"X-Studio-Key": "k"}
_WELCOME = "01-base/welcome-config"


@pytest.fixture(scope="module")
def _module_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


@pytest.fixture()
def cfg(_module_db, monkeypatch):
    """(client, seed) with a real store bound — mirrors test_config_area_endpoints."""
    from sqlalchemy.pool import NullPool

    from boerdi.db.session import make_engine

    engine = make_engine(
        Settings(_env_file=None, database_url=pg_utils.sqlalchemy_url(_DB)),
        poolclass=NullPool,
    )
    store = ConfigStore(engine, listen_dsn=pg_utils.asyncpg_dsn(_DB))
    config_loader.bind_store(store)
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    client = TestClient(create_app())

    def seed(area: str, data: dict) -> None:
        asyncio.run(store.put(area, data, updated_by="seed"))

    yield client, seed
    config_loader.bind_store(None)
    asyncio.run(engine.dispose())


# ── GET ────────────────────────────────────────────────────────────
def test_get_returns_the_stored_area_as_json(cfg) -> None:
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin", "quick_replies": ["a"]}})
    r = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "area": _WELCOME,
        "data": {"welcome": {"greeting": "Moin", "quick_replies": ["a"]}},
        "type": "yaml",
    }


def test_get_an_area_that_has_a_model_but_no_row_yields_empty_data(cfg) -> None:
    """Not a 404: the schema exists, so the form can render defaults and the
    first save creates the area."""
    client, _ = cfg
    r = client.get("/api/config/data/05-canvas/type-aliases", headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["data"] == {}


def test_get_unknown_area_404(cfg) -> None:
    client, _ = cfg
    r = client.get("/api/config/data/does/not-exist", headers=_AUTH)
    assert r.status_code == 404
    # asserting the detail keeps this honest: a missing ROUTE would 404 too
    assert r.json()["detail"] == "unknown config area: does/not-exist"


def test_grouped_file_key_returns_that_file_not_the_group(cfg) -> None:
    client, seed = cfg
    seed("03-patterns/m01-krisen", {"frontmatter": {"id": "m01"}, "body": "x"})
    r = client.get("/api/config/data/03-patterns/m01-krisen", headers=_AUTH)
    assert r.status_code == 200
    assert r.json()["data"]["frontmatter"]["id"] == "m01"


def test_get_reports_which_file_the_raw_editor_must_ask_for(cfg) -> None:
    """The studio must not derive md-vs-yaml from the document shape: the store
    decides it with an EXACT `{frontmatter, body}` match, and a superset test on
    the other side would send a `.md` save into a YAML document (destroying it,
    because `write_config_file` then splits frontmatter off raw YAML text)."""
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin"}})
    seed("03-patterns/m01-krisen", {"frontmatter": {"id": "m01"}, "body": "x"})
    assert client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()["type"] == "yaml"
    assert client.get("/api/config/data/03-patterns/m01-krisen",
                      headers=_AUTH).json()["type"] == "md"


def test_a_frontmatter_body_document_with_an_extra_key_is_not_markdown(cfg) -> None:
    """The exact-match rule, at the boundary that a superset test gets wrong."""
    client, seed = cfg
    seed(_WELCOME, {"frontmatter": {}, "body": "x", "notiz": "dritter Schlüssel"})
    assert client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()["type"] == "yaml"


def test_get_requires_studio_key(cfg) -> None:
    client, _ = cfg
    assert client.get(f"/api/config/data/{_WELCOME}").status_code == 401


# ── keys that address no single document ───────────────────────────
@pytest.mark.parametrize("bad", ["03-patterns", "03-patterns/", "03-patterns/a/b", "04-personas"])
def test_a_key_that_addresses_no_single_document_is_404(cfg, bad: str) -> None:
    """`model_for` answers for the bare group key and for anything under the
    prefix, so without a second check these would create permanent junk rows —
    visible in the area list, and a `03-patterns/`-shaped one is picked up by
    pattern classification as a real conversation pattern."""
    client, _ = cfg
    assert client.get(f"/api/config/data/{bad}", headers=_AUTH).status_code == 404
    assert client.put(f"/api/config/data/{bad}", headers=_AUTH,
                      json={"data": {"frontmatter": {"id": "x"}, "body": ""}}).status_code == 404
    assert not any(f["path"].startswith(f"{bad}.")
                   for f in client.get("/api/config/files", headers=_AUTH).json())


def test_the_group_key_still_serves_a_schema(cfg) -> None:
    """The stricter rule applies to documents, not to schemas: one model
    describes every file in the group, and 9-3's form needs to fetch it."""
    client, _ = cfg
    assert client.get("/api/config/schema/03-patterns", headers=_AUTH).status_code == 200


# ── PUT ────────────────────────────────────────────────────────────
def test_put_replaces_the_document_so_removals_stick(cfg) -> None:
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin", "quick_replies": ["a", "b"]}})
    r = client.put(
        f"/api/config/data/{_WELCOME}",
        headers=_AUTH,
        json={"data": {"welcome": {"greeting": "Servus", "quick_replies": ["x"]}}},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "saved"
    reread = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()
    assert reread["data"] == {"welcome": {"greeting": "Servus", "quick_replies": ["x"]}}


def test_put_carries_unpinned_keys_the_caller_sends_back(cfg) -> None:
    """Replace semantics put preservation in the caller's hands — and this
    proves the endpoint does not strip what the model does not pin. Both keys
    below are real shapes: a nested unpinned key and an unpinned sibling."""
    client, seed = cfg
    doc = {
        "welcome": {"greeting": "Moin", "haus_intern": "nicht im Modell"},
        "notiz": "auch nicht im Modell",
    }
    seed(_WELCOME, doc)
    edited = {**doc, "welcome": {**doc["welcome"], "greeting": "Servus"}}
    assert client.put(f"/api/config/data/{_WELCOME}", headers=_AUTH,
                      json={"data": edited}).status_code == 200
    saved = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()["data"]
    assert saved == {
        "welcome": {"greeting": "Servus", "haus_intern": "nicht im Modell"},
        "notiz": "auch nicht im Modell",
    }


def test_put_does_not_inject_model_defaults_into_the_document(cfg) -> None:
    """Validation is a gate, not a transform: `WelcomeBlock` defaults
    `quick_replies`/`tour_reply`, and a `model_dump()`-based write would add
    them to a document that never had them."""
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin"}})
    client.put(f"/api/config/data/{_WELCOME}", headers=_AUTH,
               json={"data": {"welcome": {"greeting": "Tach"}}})
    saved = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()["data"]
    assert saved == {"welcome": {"greeting": "Tach"}}


def test_put_creates_an_area_that_had_no_row(cfg) -> None:
    client, _ = cfg
    r = client.put(
        "/api/config/data/05-canvas/persona-priorities",
        headers=_AUTH,
        json={"data": {"persona_priorities": {"lehrkraft": 5}}},
    )
    assert r.status_code == 200
    got = client.get("/api/config/data/05-canvas/persona-priorities", headers=_AUTH)
    assert got.json()["data"] == {"persona_priorities": {"lehrkraft": 5}}


def test_put_is_visible_through_the_yaml_text_endpoint(cfg) -> None:
    """Proves the write lands in the same store the rest of the app reads."""
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin"}})
    client.put(f"/api/config/data/{_WELCOME}", headers=_AUTH,
               json={"data": {"welcome": {"greeting": "Tach"}}})
    text = client.get("/api/config/file", params={"path": f"{_WELCOME}.yaml"},
                      headers=_AUTH).json()["content"]
    assert "greeting: Tach" in text


def test_put_rejects_a_value_the_area_model_forbids(cfg) -> None:
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin"}})
    r = client.put(f"/api/config/data/{_WELCOME}", headers=_AUTH,
                   json={"data": {"welcome": {"quick_replies": "not-a-list"}}})
    assert r.status_code == 422
    # rejected means NOT persisted
    reread = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()
    assert reread["data"]["welcome"] == {"greeting": "Moin"}


# ── K3: der Preis ist über das Studio einstellbar ──────────────────────────
def test_gepflegter_preis_aendert_den_betrag(cfg) -> None:
    """Abnahmekriterium §7 des Kostenplans: „Preis einstellbar".

    Geprüft wird die ganze Kette statt nur des Schreibvorgangs: ungepflegt
    heißt kein Betrag, und nach dem Speichern rechnet dieselbe Zeile eine Zahl.
    Ohne das letzte Stück bliebe offen, ob der Editor auf etwas schreibt, das
    die Rechnung überhaupt liest.
    """
    from decimal import Decimal

    from boerdi.domain.config_models.pricing import PricingArea
    from boerdi.domain.pricing import TokenCounts, cost_for

    client, seed = cfg
    area = "01-base/pricing"
    zeile = TokenCounts("gpt-5.4-mini", prompt=1_000_000, cached=0, completion=0)
    seed(area, {"currency": "EUR", "models": {
        "gpt-5.4-mini": {"input": 0.0, "cached_input": 0.0, "output": 0.0}}})

    def tafel() -> PricingArea:
        antwort = client.get(f"/api/config/data/{area}", headers=_AUTH)
        assert antwort.status_code == 200
        return PricingArea.model_validate(antwort.json()["data"])

    assert cost_for(zeile, tafel()) is None, "ungepflegt muss betraglos bleiben"

    r = client.put(f"/api/config/data/{area}", headers=_AUTH, json={"data": {
        "currency": "EUR",
        "models": {"gpt-5.4-mini": {"input": 3.0, "cached_input": 0.3,
                                    "output": 15.0}}}})
    assert r.status_code == 200

    assert cost_for(zeile, tafel()) == Decimal("3")


def test_put_unknown_area_404(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/data/does/not-exist", headers=_AUTH, json={"data": {}})
    assert r.status_code == 404
    assert r.json()["detail"] == "unknown config area: does/not-exist"


def test_a_traversal_key_under_a_grouped_prefix_is_rejected(cfg) -> None:
    """`model_for` matches any `03-patterns/*` prefix, so the allow-list alone
    would accept `03-patterns/../../evil` and write a junk row.

    Percent-encoded on purpose: httpx collapses a literal `..` in the client,
    so the plain form never reaches the server and would test nothing. The
    encoded form is also the one that survives a normalizing reverse proxy.
    """
    client, _ = cfg
    evil = "03-patterns/%2e%2e/%2e%2e/evil"
    assert client.get(f"/api/config/data/{evil}", headers=_AUTH).status_code == 400
    assert client.put(f"/api/config/data/{evil}",
                      headers=_AUTH, json={"data": {}}).status_code == 400
    # ...and the guard itself, independent of any client's URL handling
    from boerdi.api.config import _resolve_area

    with pytest.raises(HTTPException) as err:
        _resolve_area("03-patterns/../../evil")
    assert err.value.status_code == 400


def test_put_requires_studio_key(cfg) -> None:
    client, _ = cfg
    assert client.put(f"/api/config/data/{_WELCOME}", json={"data": {}}).status_code == 401


# ── the raw text endpoint the editor's second tab writes to ────────
def test_malformed_yaml_is_a_400_with_the_parser_message_not_a_500(cfg) -> None:
    """`yaml.safe_load` raises `YAMLError`, which is not a `ValueError`, so the
    route let it escape as a 500. The studio's raw tab is the first UI that
    lets an editor submit arbitrary YAML, which is how this surfaced."""
    client, _ = cfg
    r = client.put("/api/config/file", headers=_AUTH,
                   json={"path": f"{_WELCOME}.yaml", "content": "welcome: [unclosed"})
    assert r.status_code == 400
    assert "nicht lesbar" in r.json()["detail"]


def test_yaml_whose_root_is_not_a_mapping_is_also_a_400(cfg) -> None:
    client, _ = cfg
    r = client.put("/api/config/file", headers=_AUTH,
                   json={"path": f"{_WELCOME}.yaml", "content": "- eine Liste\n- keine Abbildung"})
    assert r.status_code == 400


# ── C1-g2: die zweite Sprache übersteht den Editor-Weg ──────────────────────
# Das Studio speichert Bereiche über GENAU diese Route, nicht über die
# handgeschriebenen typisierten Endpunkte (`/config/welcome`,
# `/config/context-actions`) — die haben keinen Studio-Aufrufer. Weil hier das
# ganze Dokument ersetzt wird, hängt alles daran, dass das Bereichsmodell die
# `*_en`-Felder kennt: was es nicht kennt, lehnt die Validierung ab.

def test_put_traegt_die_englische_fassung_der_begruessung(cfg) -> None:
    client, seed = cfg
    seed(_WELCOME, {"welcome": {"greeting": "Moin"}})
    doc = {"welcome": {
        "greeting": "Moin", "greeting_en": "Hello",
        "quick_replies": ["Tour"], "quick_replies_en": ["Tour EN"],
        "tour_reply": "Tour", "tour_reply_en": "Tour EN",
    }}
    assert client.put(f"/api/config/data/{_WELCOME}", headers=_AUTH,
                      json={"data": doc}).status_code == 200
    saved = client.get(f"/api/config/data/{_WELCOME}", headers=_AUTH).json()["data"]
    assert saved == doc


def test_put_traegt_die_englische_fassung_der_kontext_aktionen(cfg) -> None:
    area = "01-base/context-actions"
    client, seed = cfg
    seed(area, {"context_actions": {"enabled": True}})
    doc = {"context_actions": {
        "enabled": True,
        "greetings": {"collection": "Du bist in „{title}“."},
        "greetings_en": {"collection": "You are in “{title}”."},
        "pills": {"collection": [
            {"label": "Sammlung erkunden", "label_en": "Explore collection",
             "kind": "action", "action": "browse_collection"},
        ]},
    }}
    assert client.put(f"/api/config/data/{area}", headers=_AUTH,
                      json={"data": doc}).status_code == 200
    saved = client.get(f"/api/config/data/{area}", headers=_AUTH).json()["data"]
    assert saved == doc
