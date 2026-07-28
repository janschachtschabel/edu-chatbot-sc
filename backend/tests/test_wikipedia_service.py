"""Coverage + Verhaltens-Pins für wikipedia_service (vorher 16 %).

Reine Relevanz-Logik (``_normalize`` / ``_word_match`` / ``_is_relevant``) +
async ``fetch_wikipedia_summary`` (2-Schritt: Suche → Summary) mit Fake-httpx-
Client — kein echter Netzcall.

Hinweis (Charakterisierung, NICHT gefixt): der Title-länger-Suffix-Zweig in
``_is_relevant`` (Zeilen ~138-143) ist praktisch unerreichbar, weil die
Containment-Prüfung ``t in nt`` Prefix-Beziehungen schon vorher abfängt. Wird
daher hier nicht getestet."""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services import wikipedia_service as ws


# ── _normalize ─────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,exp", [
    ("Bruchrechnung", "bruchrechnung"),
    ("Über", "uber"),                        # NFKD: ü → u (combining entfernt)
    ("Mathematik & Physik!", "mathematik physik"),
    ("  viel   raum  ", "viel raum"),
    ("", ""),
])
def test_normalize(raw, exp):
    assert ws._normalize(raw) == exp


# ── _word_match ────────────────────────────────────────────────────
def test_word_match():
    assert ws._word_match("berlin", "stadt berlin mitte") is True
    assert ws._word_match("berlin", "ueberlingen") is False   # Substring, kein Ganzwort
    assert ws._word_match("", "text") is False
    assert ws._word_match("x", "") is False


# ── _is_relevant ───────────────────────────────────────────────────
def test_is_relevant_direct_containment():
    assert ws._is_relevant("Bruchrechnung", "Bruchrechnung", "egal") is True   # t == nt
    assert ws._is_relevant("Bruch", "Bruch (Mathematik)", "egal") is True      # t ⊂ nt


def test_is_relevant_multiword_longest_wholeword():
    assert ws._is_relevant("Stadt Berlin", "Berlin Hauptstadt", "egal") is True
    assert ws._is_relevant("Stadt Berlin", "Stadtbergen", "irgendwas") is False  # 'berlin' kein Ganzwort


def test_is_relevant_singleword_match_in_extract():
    # Titel enthält Topic NICHT, Extract schon → Word-Match im Extract.
    assert ws._is_relevant("Osmose", "Diffusion", "Die Osmose ist ein Vorgang") is True


def test_is_relevant_topic_longer_compound():
    # 'bruchrechnung' startsWith Titel-Wort 'bruch' (multi-word Titel → keine
    # Containment) → Compound-Beziehung → relevant.
    assert ws._is_relevant("Bruchrechnung", "Bruch Grundlagen", "kein match text") is True


def test_is_relevant_singleword_no_match_anywhere():
    assert ws._is_relevant("Photosynthese", "Astronomie", "Sterne am Himmel") is False


def test_is_relevant_empty_topic():
    assert ws._is_relevant("", "Titel", "Extract") is False


def test_is_relevant_no_content_words():
    # Nur Stopwörter/kurze Tokens → keine Content-Words → False.
    assert ws._is_relevant("die der und", "xyz", "abc") is False


# ── fetch_wikipedia_summary (Fake-httpx) ───────────────────────────
class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._p = payload if payload is not None else {}

    def json(self):
        return self._p


class _Client:
    """Async-Context-Manager-Ersatz; ``handler(url) -> _Resp | Exception``."""

    def __init__(self, handler):
        self._handler = handler

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_a):
        return False

    async def get(self, url, params=None):
        r = self._handler(url)
        if isinstance(r, Exception):
            raise r
        return r


def _patch(monkeypatch, handler):
    monkeypatch.setattr(ws.httpx, "AsyncClient", lambda **_kw: _Client(handler))


def test_fetch_empty_topic_returns_none():
    assert asyncio.run(ws.fetch_wikipedia_summary("")) is None


def test_fetch_happy_path(monkeypatch):
    def handler(url):
        if "/search/title" in url:
            return _Resp(200, {"pages": [{"key": "Photosynthese", "title": "Photosynthese"}]})
        return _Resp(200, {
            "title": "Photosynthese", "description": "Biologischer Prozess",
            "extract": "Die Photosynthese ist ein Prozess der Pflanzen.",
            "content_urls": {"desktop": {"page": "https://de.wikipedia.org/wiki/Photosynthese"}},
        })

    _patch(monkeypatch, handler)
    out = asyncio.run(ws.fetch_wikipedia_summary("Photosynthese"))
    assert out["title"] == "Photosynthese"
    assert out["description"] == "Biologischer Prozess"
    assert out["extract"].startswith("Die Photosynthese")
    assert out["url"] == "https://de.wikipedia.org/wiki/Photosynthese"


def test_fetch_search_non_200_returns_none(monkeypatch):
    _patch(monkeypatch, lambda url: _Resp(503, {}))
    assert asyncio.run(ws.fetch_wikipedia_summary("x")) is None


def test_fetch_no_pages_returns_none(monkeypatch):
    _patch(monkeypatch, lambda url: _Resp(200, {"pages": []}))
    assert asyncio.run(ws.fetch_wikipedia_summary("x")) is None


def test_fetch_skips_disambiguation_and_irrelevant(monkeypatch):
    def handler(url):
        if "/search/title" in url:
            return _Resp(200, {"pages": [
                {"key": "Disambig", "title": "D"},
                {"key": "Astronomie", "title": "A"},
                {"key": "Photosynthese", "title": "Photosynthese"},
            ]})
        if url.endswith("/Disambig"):
            return _Resp(200, {"type": "disambiguation", "extract": "x", "title": "D"})
        if url.endswith("/Astronomie"):
            return _Resp(200, {"title": "Astronomie", "extract": "Sterne am Himmel", "content_urls": {}})
        return _Resp(200, {"title": "Photosynthese", "extract": "Die Photosynthese ist ein Prozess", "content_urls": {}})

    _patch(monkeypatch, handler)
    out = asyncio.run(ws.fetch_wikipedia_summary("Photosynthese"))
    assert out["title"] == "Photosynthese"   # Disambig + irrelevant übersprungen


def test_fetch_summary_http_error_skips_page(monkeypatch):
    def handler(url):
        if "/search/title" in url:
            return _Resp(200, {"pages": [{"key": "A", "title": "A"}, {"key": "Photosynthese", "title": "Photosynthese"}]})
        if url.endswith("/A"):
            raise ws.httpx.ReadTimeout("timeout")
        return _Resp(200, {"title": "Photosynthese", "extract": "Die Photosynthese ist", "content_urls": {}})

    _patch(monkeypatch, handler)
    out = asyncio.run(ws.fetch_wikipedia_summary("Photosynthese"))
    assert out["title"] == "Photosynthese"   # /A warf → innerer except → weiter


def test_fetch_outer_http_error_returns_none(monkeypatch):
    def handler(url):
        raise ws.httpx.ConnectError("boom")

    _patch(monkeypatch, handler)
    assert asyncio.run(ws.fetch_wikipedia_summary("x")) is None
