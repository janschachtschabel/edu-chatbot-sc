"""Lizenzfilter ohne Nachschlagen (Paket 11 L, C-1).

Gemessen 2026-10-16 am WLO-Server (``search_wlo_content``, ``license``): Schlüssel (``CC_BY_NC``),
Bezeichnungen und Aliasse wirken gleich; „OER“ ist ein Sammelwert des Servers. Daneben:
„CC BY NC“ landete still bei „CC BY“, unbekannte Werte wurden still übergangen (ungefiltert).
Der Client gleicht deshalb gegen das Lizenz-Vokabular des Servers ab — nur exakt nach
Vereinheitlichung, nie über Teilwörter („CC BY“ steckt in „CC BY-NC“) und ohne LLM-Rückfall:
eine geratene Lizenz wäre schlimmer als keine.
"""

from __future__ import annotations

import asyncio

import pytest

from boerdi.services.mcp import arg_resolvers as ar
from boerdi.services.mcp.lizenz_abgleich import lizenz_schluessel

_LIZENZEN = {
    "cc by": "CC_BY", "cc by 4.0": "CC_BY",
    "cc by-nc": "CC_BY_NC", "cc by-nc 4.0": "CC_BY_NC",
    "cc by-sa": "CC_BY_SA", "cc by-nc-sa": "CC_BY_NC_SA", "cc by-nc-nd": "CC_BY_NC_ND",
    "cc 0": "CC_0", "cc0": "CC_0", "gemeinfrei": "PDM", "public domain mark": "PDM",
    "public domain dedication": "CC_0",
}


def test_schreibweisen_finden_den_schluessel():
    assert lizenz_schluessel(_LIZENZEN, "CC BY NC") == "CC_BY_NC"
    assert lizenz_schluessel(_LIZENZEN, "cc_by_nc") == "CC_BY_NC"
    assert lizenz_schluessel(_LIZENZEN, "CC BY-NC 3.0") == "CC_BY_NC"
    assert lizenz_schluessel(_LIZENZEN, "CC BY") == "CC_BY"
    assert lizenz_schluessel(_LIZENZEN, "Gemeinfrei") == "PDM"


def test_kein_teilwort_und_kein_sammelwert():
    assert lizenz_schluessel(_LIZENZEN, "OER") is None
    assert lizenz_schluessel(_LIZENZEN, "CC") is None
    assert lizenz_schluessel(_LIZENZEN, "Namensnennung") is None
    assert lizenz_schluessel(_LIZENZEN, "") is None


# Review 2026-10-16 (#2): was hier nicht aufging, ging roh an den Server, der über Teilwörter
# abgleicht („cc by“ steckt in jedem CC-Wert) — „CC BY-NC-SA 3.0 DE“ filterte still auf CC BY.
@pytest.mark.parametrize(("wert", "schluessel"), [
    ("CC BY-NC-SA 3.0 DE", "CC_BY_NC_SA"),
    ("CC BY-SA 2.0 DE", "CC_BY_SA"),
    ("cc by-nc-nd 4.0 international", "CC_BY_NC_ND"),
    ("CC BY 4", "CC_BY"),
    ("CC-BY-SA-Lizenz", "CC_BY_SA"),
    ("Creative Commons BY NC SA", "CC_BY_NC_SA"),
    ("CC 0 1.0", "CC_0"),
])
def test_cc_werte_mit_zusaetzen_finden_ihren_schluessel(wert, schluessel):
    assert lizenz_schluessel(_LIZENZEN, wert) == schluessel


def test_mehrdeutiges_findet_keinen_schluessel():
    assert lizenz_schluessel(_LIZENZEN, "Public Domain") is None  # PDM oder CC0?
    assert lizenz_schluessel(_LIZENZEN, "CC BY-SA-ND") is None    # SA und ND schließen sich aus


def test_sammelwerte_bleiben_auch_wenn_das_vokabular_sie_kennte():
    """Review #5: „OER“ hängt sonst nur daran, dass das Vokabular keinen Alias „oer“ führt."""
    from boerdi.services.mcp.lizenz_abgleich import lizenz_filter

    mit_oer = {**_LIZENZEN, "oer": "CC_BY"}
    for wert in ("OER", "freie Lizenzen", "offene Lizenz", "OER-Lizenz"):
        assert lizenz_filter(mit_oer, wert) == wert


def test_lizenz_filter_laesst_unbekanntes_weg():
    from boerdi.services.mcp.lizenz_abgleich import lizenz_filter

    assert lizenz_filter(_LIZENZEN, "CC BY NC") == "CC_BY_NC"
    assert lizenz_filter(_LIZENZEN, "frei nutzbar") is None
    assert lizenz_filter({}, "frei nutzbar") == "frei nutzbar"  # Vokabular fehlt: nicht raten


def _vokabular(monkeypatch, gefragt: list[str]):
    monkeypatch.setitem(ar._label_to_uri_cache, "license", dict(_LIZENZEN))

    async def fake_ensure(vocab):
        pass

    async def fake_llm(vocab, value):
        gefragt.append(f"{vocab}={value}")
        return None

    monkeypatch.setattr(ar, "_ensure_label_cache", fake_ensure)
    monkeypatch.setattr(ar, "_llm_vocab_match", fake_llm)


def test_suche_bekommt_den_lizenzschluessel(monkeypatch):
    gefragt: list[str] = []
    _vokabular(monkeypatch, gefragt)
    out = asyncio.run(ar._resolve_filter_uris({"query": "x", "license": "CC BY NC"}))
    assert out["license"] == "CC_BY_NC"


def test_oer_bleibt_unbekanntes_faellt_weg_und_kein_llm(monkeypatch):
    """Review #2: ein unbekannter Wert ging roh an den Server und filterte dort über Teilwörter
    falsch; weggelassen gilt, was die Werkzeugbeschreibung sagt: er filtert nicht."""
    gefragt: list[str] = []
    _vokabular(monkeypatch, gefragt)
    assert asyncio.run(ar._resolve_filter_uris({"license": "OER"}))["license"] == "OER"
    assert "license" not in asyncio.run(ar._resolve_filter_uris({"license": "frei", "q": 1}))
    assert gefragt == []


def test_suche_in_der_sammlung_wird_ebenfalls_abgeglichen():
    assert ar.TOOL_PREPROCESSORS["search_wlo_within_collection"] is ar._resolve_filter_uris


def test_lizenz_vokabular_wird_aus_der_server_antwort_gelesen(monkeypatch):
    """Live gefunden: der Parser nahm nur ``URI: http…`` — die Lizenz liefert Schlüssel."""
    roh = ("# Vokabular: Lizenzen (license)\n\n"
           "- **CC BY-NC** | Aliases: CC BY-NC 4.0, creative commons by-nc\n  URI: CC_BY_NC\n"
           "- **Public Domain Mark** | Aliases: gemeinfrei\n  URI: PDM\n")

    async def fake_call(tool, args):
        return roh

    monkeypatch.setattr(ar, "call_mcp_tool", fake_call)
    monkeypatch.setitem(ar._label_to_uri_cache, "license", {})
    monkeypatch.setitem(ar._label_cache_loaded, "license", False)
    asyncio.run(ar._ensure_label_cache("license"))
    assert ar._label_to_uri_cache["license"]["cc by-nc 4.0"] == "CC_BY_NC"
    assert ar._label_to_uri_cache["license"]["gemeinfrei"] == "PDM"
