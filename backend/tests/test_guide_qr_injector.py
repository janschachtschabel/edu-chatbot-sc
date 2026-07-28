"""Coverage + Verhaltens-Pins für guide_qr_injector (Port des ALT-Tests).

Der Injektor ist fast rein; die einzige externe Grenze ist ``host_is_allowed``
(Allow-Liste) — das wird via autouse-Fixture deterministisch gemockt. Die
kompilierten Regeln (``_COMPILED``) werden pro Test kontrolliert gesetzt, damit
die Tests unabhängig von der guide-rules-YAML sind. ``find_rag_area_match`` nutzt
die echten (hardcodierten) ``_RAG_AREA_URLS`` — rein und deterministisch.

Deviation vom ALT-Test: Import-Roots (``boerdi.services`` / ``boerdi.domain``) und
``host_is_allowed`` liegt in NEU in ``boerdi.domain.guide_mode``. ALTs
``test_inject_rag_chunk_source`` ist hier NICHT enthalten — es braucht das
``rag_url_index``-Modul (P6-RAG, noch unportiert); Stage 3b degradiert ohne es
graceful (try/except). Der Test kommt mit dem ``rag_url_index``-Port zurück.
"""

from __future__ import annotations

import re

import pytest

from boerdi.services import guide_qr_injector as gqi

_ALLOWED = (
    "wirlernenonline.de", "wissenlebtonline.de", "edu-sharing.com",
    "edu-sharing.net", "edu-sharing-network.org", "its.jointly.info", "metaventis.com",
)


def _allowed_host(host):
    return bool(host) and any(host == h or host.endswith("." + h) for h in _ALLOWED)


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    from boerdi.domain import guide_mode
    monkeypatch.setattr(guide_mode, "host_is_allowed", _allowed_host)
    gqi.reset_compiled_cache()
    yield
    gqi.reset_compiled_cache()


# ── Reine Helfer ───────────────────────────────────────────────────
def test_has_guide_qr():
    assert gqi._has_guide_qr(["x", gqi.GUIDE_QR_PREFIX + "Hin|https://a"]) is True
    assert gqi._has_guide_qr(["a", "b"]) is False
    assert gqi._has_guide_qr([1, None, "c"]) is False


@pytest.mark.parametrize("raw,exp", [
    ("http://x.de/", "https://x.de/"),
    ("https://x.de/", "https://x.de/"),
    ("  http://x.de ", "https://x.de"),
    ("", ""),
])
def test_normalize_to_https(raw, exp):
    assert gqi._normalize_to_https(raw) == exp


def test_normalize_to_https_non_str():
    assert gqi._normalize_to_https(None) == ""


def test_format_qr_upgrades_http():
    assert gqi._format_qr("Label", "http://x.de/") == "__guide__|Label|https://x.de/"


@pytest.mark.parametrize("qr,exp", [
    ("__guide__|Label|https://x.de/", ("Label", "https://x.de/")),
    ("kein prefix", None),
    ("__guide__|nurlabel", None),      # kein zweiter |
    ("__guide__|Label|", None),        # leere URL
])
def test_parse_existing_guide(qr, exp):
    assert gqi._parse_existing_guide(qr) == exp


def test_parse_existing_guide_non_str():
    assert gqi._parse_existing_guide(123) is None


@pytest.mark.parametrize("url,exp", [
    ("https://wirlernenonline.de", True),
    ("https://wirlernenonline.de/", True),
    ("https://wirlernenonline.de/oer/", False),
    ("https://wirlernenonline.de/?q=x", False),
    ("https://wirlernenonline.de/#frag", False),
])
def test_is_domain_root(url, exp):
    assert gqi._is_domain_root(url) is exp


def test_allow_listed_host():
    assert gqi._allow_listed_host("https://wirlernenonline.de/oer") is True
    assert gqi._allow_listed_host("ftp://wirlernenonline.de") is False   # Schema
    assert gqi._allow_listed_host("https://evil.com/") is False


# ── find_guide_match (kontrolliertes _COMPILED) ────────────────────
def test_find_guide_match_highest_priority(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [
        (re.compile("klima", re.I), "Klima", "https://wirlernenonline.de/klima", 50),
        (re.compile("klimawandel", re.I), "KW", "https://wirlernenonline.de/kw", 90),
    ])
    assert gqi.find_guide_match("erzähl über klimawandel") == ("KW", "https://wirlernenonline.de/kw")


def test_find_guide_match_none(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [])
    assert gqi.find_guide_match("nichts passt hier") is None
    assert gqi.find_guide_match("") is None
    assert gqi.find_guide_match(None) is None


# ── find_rag_area_match (echte _RAG_AREA_URLS) ─────────────────────
def test_find_rag_area_match_requires_brand_in_text():
    r = gqi.find_rag_area_match(
        ["WissenLebtOnline"], response_text="Schau bei WissenLebtOnline vorbei"
    )
    assert r == ("WissenLebtOnline-Webseite", "https://wissenlebtonline.de/")


def test_find_rag_area_match_brand_absent_returns_none():
    assert gqi.find_rag_area_match(
        ["WissenLebtOnline"], response_text="völlig anderes thema"
    ) is None


def test_find_rag_area_match_no_text_skips_brand_check():
    r = gqi.find_rag_area_match(["OER-Wissen"], response_text=None)
    assert r == ("OER-Erklärung", "https://wirlernenonline.de/oer")


def test_find_rag_area_match_unmapped_and_empty():
    assert gqi.find_rag_area_match(["Nonexistent"], "text") is None
    assert gqi.find_rag_area_match([], "text") is None
    assert gqi.find_rag_area_match(None) is None


# ── find_response_urls / find_response_url ─────────────────────────
def test_find_response_urls_specific_before_root():
    text = "Siehe [WLO](https://wirlernenonline.de/) und [Angebote](https://wirlernenonline.de/angebote/)."
    urls = gqi.find_response_urls(text)
    assert urls[0] == ("Angebote", "https://wirlernenonline.de/angebote/")   # spezifisch zuerst
    assert ("WLO", "https://wirlernenonline.de/") in urls


def test_find_response_urls_filters_disallowed_host():
    assert gqi.find_response_urls("[X](https://evil.com/page)") == []


def test_find_response_urls_dedupes():
    text = "[A](https://wirlernenonline.de/oer) [B](https://wirlernenonline.de/oer)"
    assert len(gqi.find_response_urls(text)) == 1


def test_find_response_urls_anglebracket_label_from_path():
    urls = gqi.find_response_urls("<https://wirlernenonline.de/mein-thema>")
    assert urls == [("Mein Thema", "https://wirlernenonline.de/mein-thema")]


def test_find_response_urls_empty():
    assert gqi.find_response_urls("") == []
    assert gqi.find_response_urls(None) == []


def test_find_response_url_single():
    assert gqi.find_response_url("[A](https://wirlernenonline.de/oer)") == ("A", "https://wirlernenonline.de/oer")
    assert gqi.find_response_url("kein link hier") is None


# ── _compiled / reset_compiled_cache ───────────────────────────────
def test_reset_compiled_cache():
    gqi._COMPILED = [("dummy",)]
    gqi.reset_compiled_cache()
    assert gqi._COMPILED is None


def test_compiled_falls_back_to_hardcoded(monkeypatch):
    from boerdi.services import config_loader
    monkeypatch.setattr(config_loader, "load_guide_rules_config", lambda: {})
    gqi.reset_compiled_cache()
    compiled = gqi._compiled()
    assert len(compiled) == len(gqi._RULES)
    assert gqi._COMPILED_SOURCE == "hardcoded"


# ── inject_guide_qr (Orchestrator) ─────────────────────────────────
def test_inject_disabled_is_identity():
    assert gqi.inject_guide_qr("klimawandel themenseite", ["a", "b"], enabled=False) == ["a", "b"]


def test_inject_message_regex_specific(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [
        (re.compile("themenseite.*klimawandel", re.I), "Klima",
         "https://wirlernenonline.de/themenseite/klimawandel", 90),
    ])
    out = gqi.inject_guide_qr("zeig die themenseite zu klimawandel", ["Andere Frage"])
    assert out[0] == "__guide__|Klima|https://wirlernenonline.de/themenseite/klimawandel"
    assert "Andere Frage" in out


def test_inject_no_match_unchanged(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [])
    assert gqi.inject_guide_qr("smalltalk ohne treffer", ["a", "b"]) == ["a", "b"]


def test_inject_response_url(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [])
    out = gqi.inject_guide_qr("frage", ["a"], response_text="Siehe [OER](https://wirlernenonline.de/oer)")
    assert out[0] == "__guide__|OER|https://wirlernenonline.de/oer"


def test_inject_existing_llm_guide_specific_kept(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [])
    out = gqi.inject_guide_qr("frage", ["__guide__|LLM|https://wirlernenonline.de/oer", "normal"])
    assert out[0] == "__guide__|LLM|https://wirlernenonline.de/oer"
    assert "normal" in out


def test_inject_weak_domain_root_message_match(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [
        (re.compile("wlo allgemein", re.I), "WLO", "https://wirlernenonline.de/", 50),
    ])
    out = gqi.inject_guide_qr("erzähl mir wlo allgemein", ["a"])
    assert out[0] == "__guide__|WLO|https://wirlernenonline.de/"


def test_inject_respects_max_qrs(monkeypatch):
    monkeypatch.setattr(gqi, "_COMPILED", [
        (re.compile("klima", re.I), "Klima", "https://wirlernenonline.de/themenseite/klima", 90),
    ])
    out = gqi.inject_guide_qr("klima", ["a", "b", "c", "d"], max_qrs=4)
    assert len(out) == 4
    assert out[0].startswith("__guide__|")
