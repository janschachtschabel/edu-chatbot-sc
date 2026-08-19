"""P6-2c: RAG admin endpoints (areas / area GET+DELETE / doc GET+DELETE).

Offline strategy as in the sibling router tests: TestClient WITHOUT `with` (no
lifespan → no Postgres), `get_session` overridden with a sentinel, service layer
faked. The DB semantics live in services/rag/admin.py and are pinned there
(test_rag_admin.py + pg-gated test_rag_admin_pg.py).

`get_area_documents` is the one endpoint with real logic of its own — ALT's
(title, source) grouping — so it is exercised through `get_rag_chunks` rather
than through a faked result.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import boerdi.api.rag as rag_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _fake(monkeypatch, name, result=None):
    calls: list[tuple] = []

    async def fake(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(rag_api, name, fake)
    return calls


def _chunk(title="Zelle", source="z.md", content="Inhalt", idx=0):
    return {"id": idx + 1, "area": "bio", "title": title, "source": source,
            "chunk_index": idx, "content": content}


# ── GET /api/rag/areas ───────────────────────────────────────────────────
def test_areas_passes_di_session_and_returns_the_service_list(client, monkeypatch):
    calls = _fake(monkeypatch, "list_areas", [{"area": "bio", "chunks": 4, "documents": 1}])
    monkeypatch.setattr(rag_api, "load_rag_config", lambda: {"bio": {"mode": "always"}})
    r = client.get("/api/rag/areas", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == [{"area": "bio", "chunks": 4, "documents": 1, "configured": True}]
    assert calls == [(_SESSION,)]


def test_areas_markiert_den_nur_eingelesenen_bereich(client, monkeypatch):
    """R: ein im Studio getippter Bereichsname landet nur in der Datenbank —
    der Chatbot durchsucht ihn nie. Die Liste sagt es jetzt."""
    _fake(monkeypatch, "list_areas", [{"area": "neu", "chunks": 3, "documents": 1}])
    monkeypatch.setattr(rag_api, "load_rag_config", lambda: {})
    r = client.get("/api/rag/areas", headers=_AUTH)
    assert r.json() == [{"area": "neu", "chunks": 3, "documents": 1, "configured": False}]


def test_areas_zeigt_auch_den_konfigurierten_ohne_dokumente(client, monkeypatch):
    """Der Gegenfall: steht in der Werkzeug-Beschreibung, ist aber immer leer."""
    _fake(monkeypatch, "list_areas", [])
    monkeypatch.setattr(rag_api, "load_rag_config", lambda: {"leer": {"mode": "always"}})
    r = client.get("/api/rag/areas", headers=_AUTH)
    assert r.json() == [{"area": "leer", "chunks": 0, "documents": 0, "configured": True}]


# ── GET /api/rag/area/{area} ─────────────────────────────────────────────
def test_area_groups_chunks_by_title_and_source(client, monkeypatch):
    # Same title from two sources must stay distinguishable (ALT's compound key).
    calls = _fake(monkeypatch, "get_rag_chunks", [
        _chunk(source="z.md", content="A" * 300, idx=0),
        _chunk(source="z.md", content="B", idx=1),
        _chunk(source="andere.md", content="C", idx=0),
    ])
    r = client.get("/api/rag/area/bio", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == [
        {"title": "Zelle", "source": "z.md", "chunks": 2, "preview": "A" * 200},
        {"title": "Zelle", "source": "andere.md", "chunks": 1, "preview": "C"},
    ]
    assert calls == [(_SESSION, "bio")]  # area is passed through


def test_area_preview_is_the_first_chunk_truncated_to_200(client, monkeypatch):
    _fake(monkeypatch, "get_rag_chunks", [
        _chunk(content="erster", idx=0), _chunk(content="zweiter", idx=1),
    ])
    doc = client.get("/api/rag/area/bio", headers=_AUTH).json()[0]
    assert doc["preview"] == "erster"  # later chunks never overwrite it


def test_area_maps_null_title_and_source_to_empty_strings(client, monkeypatch):
    # get_rag_chunks LEFT JOINs, so an orphan chunk yields None/None.
    _fake(monkeypatch, "get_rag_chunks", [_chunk(title=None, source=None, content="W")])
    assert client.get("/api/rag/area/bio", headers=_AUTH).json() == [
        {"title": "", "source": "", "chunks": 1, "preview": "W"},
    ]


def test_area_without_chunks_returns_empty_list(client, monkeypatch):
    _fake(monkeypatch, "get_rag_chunks", [])
    assert client.get("/api/rag/area/leer", headers=_AUTH).json() == []


# ── DELETE /api/rag/area/{area} ──────────────────────────────────────────
def test_delete_area_calls_service_and_echoes_alt_status(client, monkeypatch):
    calls = _fake(monkeypatch, "delete_area", None)
    r = client.delete("/api/rag/area/bio", headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "area": "bio"}  # ALT shape, no count
    assert calls == [(_SESSION, "bio")]


# ── GET /api/rag/area/{area}/doc ─────────────────────────────────────────
def test_doc_returns_chunks_with_counts_and_totals(client, monkeypatch):
    calls = _fake(monkeypatch, "get_document_chunks", [
        {"chunk_index": 0, "content": "abc", "created_at": "2026-07-17T12:00:00+00:00"},
        {"chunk_index": 1, "content": "de", "created_at": "2026-07-17T12:00:00+00:00"},
    ])
    r = client.get("/api/rag/area/bio/doc", params={"title": "Zelle", "source": "z.md"},
                   headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {
        "area": "bio", "title": "Zelle", "source": "z.md",
        "chunk_count": 2, "total_chars": 5,  # len("abc") + len("de")
        "chunks": [
            {"index": 0, "content": "abc", "created_at": "2026-07-17T12:00:00+00:00"},
            {"index": 1, "content": "de", "created_at": "2026-07-17T12:00:00+00:00"},
        ],
    }
    assert calls == [(_SESSION, "bio", "Zelle", "z.md")]


def test_doc_title_and_source_default_to_empty_strings(client, monkeypatch):
    calls = _fake(monkeypatch, "get_document_chunks", [])
    r = client.get("/api/rag/area/bio/doc", headers=_AUTH)
    assert r.status_code == 200
    assert calls == [(_SESSION, "bio", "", "")]  # ALT: exact match on empty, not a wildcard
    assert r.json()["chunk_count"] == 0 and r.json()["chunks"] == []


# ── DELETE /api/rag/area/{area}/doc ──────────────────────────────────────
def test_delete_doc_reports_deleted_with_the_chunk_count(client, monkeypatch):
    calls = _fake(monkeypatch, "delete_document", 3)
    r = client.request("DELETE", "/api/rag/area/bio/doc",
                       params={"title": "Zelle", "source": "z.md"}, headers=_AUTH)
    assert r.status_code == 200
    assert r.json() == {"status": "deleted", "area": "bio", "title": "Zelle",
                        "source": "z.md", "deleted": 3}
    assert calls == [(_SESSION, "bio", "Zelle", "z.md")]


def test_delete_doc_reports_noop_when_nothing_matched(client, monkeypatch):
    _fake(monkeypatch, "delete_document", 0)
    r = client.request("DELETE", "/api/rag/area/bio/doc",
                       params={"title": "weg", "source": "x"}, headers=_AUTH)
    assert r.status_code == 200
    # ALT distinguishes noop from deleted by the count — pinned verbatim.
    assert r.json() == {"status": "noop", "area": "bio", "title": "weg",
                        "source": "x", "deleted": 0}


# ── auth ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/rag/areas"),
        ("GET", "/api/rag/area/bio"),
        ("DELETE", "/api/rag/area/bio"),
        ("GET", "/api/rag/area/bio/doc"),
        ("DELETE", "/api/rag/area/bio/doc"),
    ],
)
def test_admin_endpoints_require_studio_key(client, method, path):
    assert client.request(method, path).status_code == 401
