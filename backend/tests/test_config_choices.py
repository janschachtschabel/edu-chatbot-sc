"""S1: GET /api/config/choices — die Kataloge, aus denen ein Formularfeld
seine Vorschläge zieht.

Warum ein eigener Endpunkt und nicht `/config/elements`: der Element-Browser
liefert ganze Persona- und Muster-Dokumente (Frontmatter + Fließtext). Ein
Auswahlfeld braucht davon `value` und `label` — und `area`, damit aus dem
Verweis ein Sprung ins Bereichs-Formular werden kann.
"""

from __future__ import annotations

import asyncio

import pytest
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

_DB = "boerdi_choices_test"
_AUTH = {"X-Studio-Key": "k"}


@pytest.fixture(scope="module")
def _module_db():
    pg_utils.create_migrated_db(_DB)
    yield
    pg_utils.drop_db(_DB)


@pytest.fixture()
def cfg(_module_db, monkeypatch):
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


def test_requires_studio_key(cfg) -> None:
    client, _ = cfg
    assert client.get("/api/config/choices").status_code == 401


def test_leerer_bestand_liefert_alle_kataloge_leer(cfg) -> None:
    """Ein leerer Katalog ist eine Antwort, kein Fehler — das Formular soll
    dann ein normales Textfeld zeigen, nicht auf einen 404 laufen."""
    client, _ = cfg
    body = client.get("/api/config/choices", headers=_AUTH).json()
    for name in ("patterns", "personas", "intents", "states", "entities",
                 "rag_areas", "tools"):
        assert body[name] == [], name


def test_muster_tragen_beschriftung_und_sprungziel(cfg) -> None:
    client, seed = cfg
    seed("03-patterns/m06-material-suche",
         {"frontmatter": {"id": "M06", "label": "Material-Suche"}, "body": "# M06"})
    eintraege = client.get("/api/config/choices", headers=_AUTH).json()["patterns"]
    assert eintraege == [{"value": "M06", "label": "Material-Suche",
                          "area": "03-patterns/m06-material-suche"}]


def test_personas_intents_states_entities(cfg) -> None:
    client, seed = cfg
    # Schlüssel wie im echten Seed (`04-personas/leh.md`), nicht wie die ID
    # lautet — das Sprungziel kommt aus dem Speicherort, nicht aus der ID.
    seed("04-personas/leh",
         {"frontmatter": {"id": "P-LEH", "label": "Lehrkraft"}, "body": "# P-LEH"})
    seed("04-intents/intents", {"intents": [{"id": "I01", "label": "Suchen"}]})
    seed("04-states/states", {"states": [{"id": "S1", "label": "Offen"}]})
    seed("04-entities/entities", {"entities": [{"id": "thema", "label": "Thema"}]})
    body = client.get("/api/config/choices", headers=_AUTH).json()

    assert body["personas"] == [{"value": "P-LEH", "label": "Lehrkraft",
                                 "area": "04-personas/leh"}]
    assert body["intents"] == [{"value": "I01", "label": "Suchen",
                                "area": "04-intents/intents"}]
    assert body["states"] == [{"value": "S1", "label": "Offen",
                               "area": "04-states/states"}]
    assert body["entities"] == [{"value": "thema", "label": "Thema",
                                 "area": "04-entities/entities"}]


def test_rag_bereiche_kommen_aus_der_rag_config(cfg) -> None:
    """Der Fall aus der Nutzer-Meldung: die 8 Wissensbereiche existieren, sie
    wurden nur nie angeboten."""
    client, seed = cfg
    seed("05-knowledge/rag-config",
         {"FAQ": {"mode": "on-demand"}, "OER-Wissen": {"mode": "always"}})
    eintraege = client.get("/api/config/choices", headers=_AUTH).json()["rag_areas"]
    assert eintraege == [
        {"value": "FAQ", "label": "FAQ", "area": "05-knowledge/rag-config"},
        {"value": "OER-Wissen", "label": "OER-Wissen", "area": "05-knowledge/rag-config"},
    ]


def test_werkzeuge_vereinigen_die_eingeschalteten_server(cfg) -> None:
    """Ein abgeschalteter Server steuert nichts bei — was der Bot nicht rufen
    kann, soll ein Muster auch nicht vorschlagen bekommen. `area` bleibt leer:
    ein Werkzeug hat keine eigene Bereichsseite."""
    client, seed = cfg
    seed("05-knowledge/mcp-servers", {"servers": [
        {"id": "wlo", "enabled": True, "tools": ["search_wlo_all", "get_node_details"]},
        {"id": "zweit", "enabled": True, "tools": ["search_wlo_all", "get_url_text"]},
        {"id": "aus", "enabled": False, "tools": ["darf_nicht_erscheinen"]},
    ]})
    eintraege = client.get("/api/config/choices", headers=_AUTH).json()["tools"]
    assert [e["value"] for e in eintraege] == [
        "get_node_details", "get_url_text", "search_wlo_all"]
    assert all(e["area"] == "" for e in eintraege)


def test_eintrag_ohne_beschriftung_faellt_auf_die_id_zurueck(cfg) -> None:
    """Eine leere Beschriftung darf keine leere Zeile in der Auswahl werden."""
    client, seed = cfg
    seed("04-intents/intents", {"intents": [{"id": "I09"}]})
    assert client.get("/api/config/choices", headers=_AUTH).json()["intents"] == [
        {"value": "I09", "label": "I09", "area": "04-intents/intents"}]
