"""Coverage + Verhaltens-Pins für wikipedia_service.

Reine Relevanz-Logik (``_normalize`` / ``_word_match`` / ``_is_relevant``) +
async ``fetch_wikipedia_summary``, das seit 2026-08-01 über das MCP-Werkzeug
``get_wikipedia_summary`` geht. Die MCP-Grenze wird auf DIESEM Modul gepatcht
(Bare-Name-Import, ALT-Konvention) — kein echter Netzcall.

Hinweis (Charakterisierung, NICHT gefixt): der Title-länger-Suffix-Zweig in
``_is_relevant`` (Zeilen ~138-143) ist praktisch unerreichbar, weil die
Containment-Prüfung ``t in nt`` Prefix-Beziehungen schon vorher abfängt. Wird
daher hier nicht getestet."""

from __future__ import annotations

import asyncio
import json

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


# ── fetch_wikipedia_summary (Fake-MCP) ─────────────────────────────
def _envelope(title: str, extract: str, url: str = "https://de.wikipedia.org/wiki/X") -> str:
    """Antwortform des Werkzeugs bei ``outputFormat="json"`` (live geprüft)."""
    return json.dumps({
        "query": title, "found": True,
        "summary": {"title": title, "extract": extract, "url": url, "lang": "de"},
    })


def _wire(monkeypatch, antwort):
    """Patcht die MCP-Grenze; ``antwort`` ist ein String oder eine Exception.

    Gibt die Aufruf-Liste zurück, damit Tests prüfen können, WAS gesendet wurde
    (bzw. dass gar nicht gesendet wurde).
    """
    aufrufe: list[tuple[str, dict]] = []

    async def fake(tool_name, arguments):
        aufrufe.append((tool_name, arguments))
        if isinstance(antwort, Exception):
            raise antwort
        return antwort

    monkeypatch.setattr(ws, "call_mcp_tool", fake)
    return aufrufe


def test_fetch_empty_topic_does_not_call_the_server(monkeypatch):
    aufrufe = _wire(monkeypatch, _envelope("X", "y"))
    assert asyncio.run(ws.fetch_wikipedia_summary("")) is None
    assert aufrufe == []


def test_fetch_happy_path(monkeypatch):
    aufrufe = _wire(monkeypatch, _envelope(
        "Photosynthese", "Die Photosynthese ist ein Prozess der Pflanzen.",
        "https://de.wikipedia.org/wiki/Photosynthese",
    ))
    out = asyncio.run(ws.fetch_wikipedia_summary("Photosynthese"))
    assert out["title"] == "Photosynthese"
    assert out["extract"].startswith("Die Photosynthese")
    assert out["url"] == "https://de.wikipedia.org/wiki/Photosynthese"
    assert aufrufe == [("get_wikipedia_summary", {"query": "Photosynthese"})]


def test_fetch_irrelevant_hit_is_rejected(monkeypatch):
    # Live gemessen 2026-08-01: das Werkzeug beantwortet „Stadt Berlin" mit dem
    # Artikel „Bern". Ohne den Relevanz-Filter landete die Schweizer
    # Bundesstadt samt CC-BY-SA-Quellenangabe in einem Material über Berlin.
    _wire(monkeypatch, _envelope("Bern", "Bern ist die Bundesstadt der Schweiz."))
    assert asyncio.run(ws.fetch_wikipedia_summary("Stadt Berlin")) is None


def test_fetch_not_found_returns_none(monkeypatch):
    _wire(monkeypatch, json.dumps({"query": "x", "found": False, "summary": None}))
    assert asyncio.run(ws.fetch_wikipedia_summary("x")) is None


def test_fetch_mcp_error_string_returns_none(monkeypatch):
    # ``call_mcp_tool`` wirft nicht, sondern liefert im Fehlerfall diesen Text.
    _wire(monkeypatch, "MCP error: tool not found")
    assert asyncio.run(ws.fetch_wikipedia_summary("Photosynthese")) is None


def test_fetch_transport_exception_returns_none(monkeypatch):
    _wire(monkeypatch, RuntimeError("boom"))
    assert asyncio.run(ws.fetch_wikipedia_summary("Photosynthese")) is None
