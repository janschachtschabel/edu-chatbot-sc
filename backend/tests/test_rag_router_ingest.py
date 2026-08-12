"""P6-2b: RAG ingest endpoints (file/url/text).

Offline strategy as in test_rag_router.py: ``TestClient`` WITHOUT ``with`` (no
lifespan → no Postgres), ``get_session`` overridden with a sentinel, and the
service layer faked — its DB semantics are pinned in test_rag_ingest.py.
markitdown is never invoked: ``convert_to_markdown`` / ``convert_url_to_markdown``
are the boundary and are faked here.

The temp-file handling is deliberately NOT faked. ``tempfile.tempdir`` is
redirected into a pytest ``tmp_path``, so the real file is really written, really
handed to the converter, and really unlinked — that is what the assertions read.
Mocking ``tempfile`` would have tested the mock instead of the ``finally``.

Both 413 paths are driven by calling the endpoint directly with a real
``UploadFile``: the on-disk recheck is unreachable over HTTP (starlette's
multipart parser always sets ``size``), and the header path can then pin the
exact byte boundary without pushing megabytes through the client.
"""

from __future__ import annotations

import io
import os
import tempfile

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient

import boerdi.api.rag as rag_api
from boerdi.api.deps import get_session
from boerdi.main import create_app
from boerdi.settings import get_settings

_AUTH = {"X-Studio-Key": "k"}
_SESSION = object()  # sentinel: whatever get_session yields must reach the service
_MB = 1024 * 1024


@pytest.fixture()
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("STUDIO_API_KEY", "k")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # real files, isolated
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_session] = lambda: _SESSION
    return TestClient(app)


def _set_cap(monkeypatch, mb: str) -> None:
    """BOERDI_MAX_INGEST_MB for the next get_settings() read (cached per test)."""
    monkeypatch.setenv("BOERDI_MAX_INGEST_MB", mb)
    get_settings.cache_clear()


def _fake_convert(monkeypatch, text="# Doc", seen=None, name="convert_to_markdown"):
    async def fake(arg):
        if seen is not None:
            # Read the file back through the path the endpoint handed us — this
            # is what proves suffix/content/liveness at call time.
            seen.append((arg, os.path.exists(arg) and open(arg, "rb").read()))
        return text

    monkeypatch.setattr(rag_api, name, fake)


def _fake_ingest(monkeypatch, chunks=3):
    calls: list[tuple] = []

    async def fake(session, area, title, source, markdown):
        calls.append((session, area, title, source, markdown))
        return chunks

    monkeypatch.setattr(rag_api, "ingest_document", fake)
    return calls


def _upload(content=b"data", filename="report.pdf", size=None) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename, size=size)


# ── POST /api/rag/ingest/file ────────────────────────────────────────────
def test_ingest_file_converts_stores_and_returns_ok_with_preview(client, monkeypatch):
    _fake_convert(monkeypatch, text="# Klima" + "x" * 600)
    calls = _fake_ingest(monkeypatch, chunks=7)
    r = client.post(
        "/api/rag/ingest/file",
        files={"file": ("klima.pdf", b"%PDF-1.4 fake", "application/pdf")},
        data={"area": "erdkunde", "title": "Klimawandel"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["title"] == "Klimawandel"
    assert body["area"] == "erdkunde"
    assert body["chunks"] == 7
    assert body["preview"] == ("# Klima" + "x" * 600)[:500]  # ALT truncates at 500
    # source is the ORIGINAL filename, not the temp path
    assert calls == [(_SESSION, "erdkunde", "Klimawandel", "klima.pdf", "# Klima" + "x" * 600)]


def test_ingest_file_writes_real_temp_file_with_suffix_then_unlinks_it(
    client, monkeypatch, tmp_path
):
    seen: list[tuple] = []
    _fake_convert(monkeypatch, seen=seen)
    _fake_ingest(monkeypatch)
    r = client.post(
        "/api/rag/ingest/file",
        files={"file": ("folien.pptx", b"PK\x03\x04 body", "application/octet-stream")},
        headers=_AUTH,
    )
    assert r.status_code == 200
    (path, content), = seen
    # markitdown picks its parser by extension — the suffix must survive.
    assert path.endswith(".pptx")
    assert content == b"PK\x03\x04 body"  # fully flushed before conversion
    assert list(tmp_path.iterdir()) == []  # finally: unlinked


def test_ingest_file_title_defaults_to_filename(client, monkeypatch):
    _fake_convert(monkeypatch)
    calls = _fake_ingest(monkeypatch)
    r = client.post(
        "/api/rag/ingest/file",
        files={"file": ("skript.docx", b"x")},
        headers=_AUTH,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "skript.docx"
    assert calls[0][2] == "skript.docx"
    assert r.json()["area"] == "general"  # Form default


async def test_ingest_file_title_falls_back_to_unbenannt_without_filename(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    _fake_convert(monkeypatch)
    calls = _fake_ingest(monkeypatch)
    out = await rag_api.ingest_file(
        file=_upload(filename=None), session=_SESSION, lang="de", area="general", title=""
    )
    assert out["title"] == "Unbenannt"
    assert calls[0][3] == ""  # source: `file.filename or ""`


async def test_ingest_file_rejects_oversized_via_size_header_before_reading(
    monkeypatch, tmp_path
):
    _set_cap(monkeypatch, "1")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    _fake_convert(monkeypatch)
    calls = _fake_ingest(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        await rag_api.ingest_file(
            file=_upload(size=_MB + 1), session=_SESSION, lang="de", area="general", title=""
        )
    assert ei.value.status_code == 413
    assert "1 MB Limit" in ei.value.detail
    assert "BOERDI_MAX_INGEST_MB" in ei.value.detail  # tells the operator the knob
    assert calls == []
    assert list(tmp_path.iterdir()) == []  # rejected before any temp file exists


async def test_ingest_file_rejects_oversized_on_disk_when_size_unset(
    monkeypatch, tmp_path
):
    # starlette normally sets `size`; this pins ALT's defensive recheck.
    _set_cap(monkeypatch, "1")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    _fake_convert(monkeypatch)
    calls = _fake_ingest(monkeypatch)
    with pytest.raises(HTTPException) as ei:
        await rag_api.ingest_file(
            file=_upload(content=b"x" * (_MB + 1), size=None),
            session=_SESSION, lang="de", area="general", title="",
        )
    assert ei.value.status_code == 413
    assert calls == []
    assert list(tmp_path.iterdir()) == []  # temp file cleaned up on the 413 path


async def test_ingest_file_accepts_size_exactly_at_the_cap(monkeypatch, tmp_path):
    _set_cap(monkeypatch, "1")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    _fake_convert(monkeypatch)
    _fake_ingest(monkeypatch)
    out = await rag_api.ingest_file(  # `>` not `>=`: exactly at the limit passes
        file=_upload(content=b"x" * _MB, size=_MB),
        session=_SESSION, lang="de", area="general", title="",
    )
    assert out["status"] == "ok"


async def test_ingest_file_cap_zero_means_unlimited(monkeypatch, tmp_path):
    _set_cap(monkeypatch, "0")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    _fake_convert(monkeypatch)
    _fake_ingest(monkeypatch)
    out = await rag_api.ingest_file(
        file=_upload(size=99 * _MB), session=_SESSION, lang="de", area="general", title=""
    )
    assert out["status"] == "ok"  # no 413 despite a huge declared size


def test_ingest_file_converter_error_becomes_400_and_still_unlinks(
    client, monkeypatch, tmp_path
):
    _fake_convert(monkeypatch, text="Fehler beim Konvertieren: boom")
    calls = _fake_ingest(monkeypatch)
    r = client.post(
        "/api/rag/ingest/file", files={"file": ("a.pdf", b"x")}, headers=_AUTH
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Fehler beim Konvertieren: boom"
    assert calls == []  # never stored
    assert list(tmp_path.iterdir()) == []  # finally runs on the error path too


# ── POST /api/rag/ingest/url ─────────────────────────────────────────────
def test_ingest_url_converts_stores_and_returns_ok(client, monkeypatch):
    _fake_convert(monkeypatch, text="# Seite", name="convert_url_to_markdown")
    calls = _fake_ingest(monkeypatch, chunks=2)
    r = client.post(
        "/api/rag/ingest/url",
        data={"url": "https://example.org/a", "area": "bio", "title": "Zelle"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "title": "Zelle", "area": "bio",
                        "chunks": 2, "preview": "# Seite"}
    assert calls == [(_SESSION, "bio", "Zelle", "https://example.org/a", "# Seite")]


def test_ingest_url_title_defaults_to_the_url(client, monkeypatch):
    _fake_convert(monkeypatch, name="convert_url_to_markdown")
    calls = _fake_ingest(monkeypatch)
    r = client.post(
        "/api/rag/ingest/url", data={"url": "https://example.org/a"}, headers=_AUTH
    )
    assert r.status_code == 200
    assert r.json()["title"] == "https://example.org/a"
    assert calls[0][2] == "https://example.org/a"


def test_ingest_url_guard_error_becomes_400(client, monkeypatch):
    # url_safety rejects internal targets by returning a "Fehler:" string
    # (never raising) — the router is what turns it into a 400.
    _fake_convert(
        monkeypatch,
        text="Fehler: Internal network URLs not allowed",
        name="convert_url_to_markdown",
    )
    calls = _fake_ingest(monkeypatch)
    r = client.post(
        "/api/rag/ingest/url", data={"url": "http://169.254.169.254/"}, headers=_AUTH
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Fehler: Internal network URLs not allowed"
    assert calls == []


# ── POST /api/rag/ingest/text ────────────────────────────────────────────
def test_ingest_text_stores_raw_markdown_without_conversion(client, monkeypatch):
    calls = _fake_ingest(monkeypatch, chunks=1)
    r = client.post(
        "/api/rag/ingest/text",
        data={"content": "# Notiz", "area": "bio", "title": "T", "source": "wiki"},
        headers=_AUTH,
    )
    assert r.status_code == 200
    # no `preview` key here — ALT's text response is the short one
    assert r.json() == {"status": "ok", "title": "T", "area": "bio", "chunks": 1}
    assert calls == [(_SESSION, "bio", "T", "wiki", "# Notiz")]


def test_ingest_text_defaults_source_manual_and_title_fallback(client, monkeypatch):
    calls = _fake_ingest(monkeypatch)
    r = client.post("/api/rag/ingest/text", data={"content": "x"}, headers=_AUTH)
    assert r.status_code == 200
    assert calls == [(_SESSION, "general", "Manueller Eintrag", "manual", "x")]
    # ALT quirk, kept verbatim: the fallback title is what gets STORED, but the
    # response echoes the raw (empty) form value.
    assert r.json()["title"] == ""


# ── auth + validation ────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/api/rag/ingest/url", {"url": "https://example.org"}),
        ("/api/rag/ingest/text", {"content": "x"}),
    ],
)
def test_ingest_requires_studio_key(client, monkeypatch, path, data):
    calls = _fake_ingest(monkeypatch)
    assert client.post(path, data=data).status_code == 401
    assert calls == []


def test_ingest_file_requires_studio_key(client, monkeypatch):
    calls = _fake_ingest(monkeypatch)
    r = client.post("/api/rag/ingest/file", files={"file": ("a.pdf", b"x")})
    assert r.status_code == 401
    assert calls == []


@pytest.mark.parametrize(
    ("path", "data"),
    [
        ("/api/rag/ingest/url", {"area": "bio"}),  # url missing
        ("/api/rag/ingest/text", {"area": "bio"}),  # content missing
    ],
)
def test_ingest_rejects_missing_required_form_field(client, monkeypatch, path, data):
    calls = _fake_ingest(monkeypatch)
    r = client.post(path, data=data, headers=_AUTH)
    assert r.status_code == 422
    assert calls == []


# ── POST /api/rag/embed (6-2d) ───────────────────────────────────────────
# The backfill loop's DB/LLM semantics are pinned in test_rag_ingest.py; what
# matters here is the two ALT response shapes and the session hand-off.
def _fake_embed(monkeypatch, result):
    calls: list[tuple] = []

    async def fake(*args):
        calls.append(args)
        return result

    monkeypatch.setattr(rag_api, "embed_missing_chunks", fake)
    return calls


def test_embed_reports_alt_message_when_every_chunk_has_an_embedding(client, monkeypatch):
    calls = _fake_embed(monkeypatch, (0, 0))
    r = client.post("/api/rag/embed", headers=_AUTH)
    assert r.status_code == 200
    # ALT's early-return shape: carries a message and NO total key.
    assert r.json() == {"status": "ok", "embedded": 0,
                        "message": "All chunks already have embeddings"}
    assert calls == [(_SESSION,)]


def test_embed_reports_embedded_and_total(client, monkeypatch):
    _fake_embed(monkeypatch, (2, 3))
    r = client.post("/api/rag/embed", headers=_AUTH)
    assert r.status_code == 200
    # ALT's success shape: carries a total and NO message key.
    assert r.json() == {"status": "ok", "embedded": 2, "total": 3}


def test_embed_reports_the_total_even_when_every_chunk_failed(client, monkeypatch):
    _fake_embed(monkeypatch, (0, 4))
    # embedded=0 with rows present is NOT the "already embedded" case — ALT
    # tells them apart by whether anything was found, not by the count.
    assert client.post("/api/rag/embed", headers=_AUTH).json() == {
        "status": "ok", "embedded": 0, "total": 4,
    }


def test_embed_requires_studio_key(client):
    assert client.post("/api/rag/embed").status_code == 401
