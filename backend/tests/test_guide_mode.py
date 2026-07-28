"""Port der ALT-Tests für ``guide_mode_service`` → NEU ``domain/guide_mode.py``.

Card-URL-Filter + Allow-List. Rein bis auf ``_cfg()`` (guide-mode-Config) — das
wird via monkeypatch auf eine feste Allow-Liste gesetzt, damit die Tests
unabhängig von der Repo-Config sind.
"""

from __future__ import annotations

import pytest

from boerdi.domain import guide_mode as gms

_CFG = {
    "allowed_hosts": ["wirlernenonline.de", "wp-test.wirlernenonline.de", "*.openeduhub.net"],
    "url_fields_priority": ["topic_page_url", "wlo_url", "url", "content_url", "preview_url"],
    "max_guide_targets_per_turn": 5,
}

_RENDER = ("https://redaktion.openeduhub.net/edu-sharing/components/render/"
           "12345678-1234-1234-1234-123456789abc")


@pytest.fixture
def cfg(monkeypatch):
    monkeypatch.setattr(gms, "_cfg", lambda: _CFG)


# ── reine Helfer ───────────────────────────────────────────────────
@pytest.mark.parametrize("raw,exp", [
    ("Example.COM", "example.com"),
    ("host:8080", "host"),
    ("www.wirlernenonline.de", "wirlernenonline.de"),
    ("www.a.de:443", "a.de"),
    ("", ""),
    (None, ""),
])
def test_normalize_host(raw, exp):
    assert gms._normalize_host(raw) == exp


@pytest.mark.parametrize("host,pat,exp", [
    ("wirlernenonline.de", "wirlernenonline.de", True),
    ("foo.openeduhub.net", "*.openeduhub.net", True),
    ("a.b.openeduhub.net", "*.openeduhub.net", True),
    ("openeduhub.net", "*.openeduhub.net", False),   # Bare nicht durch Wildcard
    ("other.de", "wirlernenonline.de", False),
    ("", "x", False),
    ("x", "", False),
])
def test_host_matches_pattern(host, pat, exp):
    assert gms.host_matches_pattern(host, pat) is exp


def test_is_collection_card():
    assert gms._is_collection_card({"node_type": "collection"}) is True
    assert gms._is_collection_card({"node_type": "material"}) is False
    assert gms._is_collection_card({}) is False


def test_rewrite_render_to_browse():
    out = gms._rewrite_collection_render_to_browse(_RENDER)
    assert out == ("https://redaktion.openeduhub.net/edu-sharing/components/"
                   "collections?id=12345678-1234-1234-1234-123456789abc")


def test_rewrite_non_render_passthrough():
    assert gms._rewrite_collection_render_to_browse("https://x.de/other") == "https://x.de/other"


def test_rewrite_non_str():
    assert gms._rewrite_collection_render_to_browse(None) is None


# ── config-abhängig (cfg-Fixture) ──────────────────────────────────
def test_host_is_allowed(cfg):
    assert gms.host_is_allowed("wirlernenonline.de") is True
    assert gms.host_is_allowed("www.wirlernenonline.de") is True   # www gestrippt
    assert gms.host_is_allowed("foo.openeduhub.net") is True       # Wildcard
    assert gms.host_is_allowed("evil.com") is False
    assert gms.host_is_allowed(None) is False
    assert gms.host_is_allowed("") is False


def test_is_guide_eligible_url(cfg):
    assert gms.is_guide_eligible_url("https://wirlernenonline.de/oer") is True
    assert gms.is_guide_eligible_url("ftp://wirlernenonline.de") is False   # Schema
    assert gms.is_guide_eligible_url("https://evil.com") is False
    assert gms.is_guide_eligible_url("") is False
    assert gms.is_guide_eligible_url(None) is False
    assert gms.is_guide_eligible_url(123) is False


def test_pick_guide_url_priority_topic_first(cfg):
    card = {"topic_page_url": "https://wirlernenonline.de/themenseite/klima",
            "wlo_url": "https://wirlernenonline.de/render/x"}
    assert gms.pick_guide_url(card) == "https://wirlernenonline.de/themenseite/klima"


def test_pick_guide_url_skips_disallowed(cfg):
    card = {"topic_page_url": "https://evil.com/x", "url": "https://wirlernenonline.de/oer"}
    assert gms.pick_guide_url(card) == "https://wirlernenonline.de/oer"


def test_pick_guide_url_topic_pages_variants(cfg):
    card = {"topic_pages": [{"url": "https://evil.com/x"}, {"url": "https://wirlernenonline.de/tp"}]}
    assert gms.pick_guide_url(card) == "https://wirlernenonline.de/tp"


def test_pick_guide_url_none_when_no_allowed(cfg):
    assert gms.pick_guide_url({"url": "https://evil.com"}) is None
    assert gms.pick_guide_url(None) is None
    assert gms.pick_guide_url({}) is None


def test_pick_guide_url_rewrites_collection_render(cfg):
    card = {"node_type": "collection", "wlo_url": _RENDER}
    out = gms.pick_guide_url(card)
    assert "collections?id=12345678-1234-1234-1234-123456789abc" in out


# ── annotate_cards_with_guide_url ──────────────────────────────────
def test_annotate_noop_when_disabled_or_bad_host(cfg):
    cards = [{"url": "https://wirlernenonline.de/oer"}]
    assert gms.annotate_cards_with_guide_url(cards, enabled=False, host="wirlernenonline.de") == 0
    assert gms.annotate_cards_with_guide_url(cards, enabled=True, host="evil.com") == 0
    assert "guide_url" not in cards[0]


def test_annotate_sets_only_eligible(cfg):
    cards = [{"url": "https://wirlernenonline.de/oer"}, {"url": "https://evil.com"}]
    n = gms.annotate_cards_with_guide_url(cards, enabled=True, host="wirlernenonline.de")
    assert n == 1
    assert cards[0]["guide_url"] == "https://wirlernenonline.de/oer"
    assert "guide_url" not in cards[1]


def test_annotate_respects_explicit_max_targets(cfg):
    cards = [{"url": f"https://wirlernenonline.de/{i}"} for i in range(5)]
    n = gms.annotate_cards_with_guide_url(
        cards, enabled=True, host="wirlernenonline.de", max_targets=2,
    )
    assert n == 2
    assert "guide_url" in cards[1]
    assert "guide_url" not in cards[2]


def test_annotate_max_targets_from_config(monkeypatch):
    monkeypatch.setattr(gms, "_cfg", lambda: {**_CFG, "max_guide_targets_per_turn": 1})
    cards = [{"url": f"https://wirlernenonline.de/{i}"} for i in range(3)]
    assert gms.annotate_cards_with_guide_url(cards, enabled=True, host="wirlernenonline.de") == 1


def test_annotate_zero_targets_means_unlimited(monkeypatch):
    # Regressionsschutz: "0 = unlimited" darf NICHT auf 5 gecoerct werden.
    monkeypatch.setattr(gms, "_cfg", lambda: {**_CFG, "max_guide_targets_per_turn": 0})
    cards = [{"url": f"https://wirlernenonline.de/{i}"} for i in range(3)]
    assert gms.annotate_cards_with_guide_url(cards, enabled=True, host="wirlernenonline.de") == 3


# ── Pydantic-Card-Pfad (Produktion übergibt Card-Modelle, keine Dicts) ──
class _FakeCard:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self):
        return dict(self.__dict__)


def test_pick_guide_url_accepts_model_like(cfg):
    card = _FakeCard(url="https://wirlernenonline.de/oer")
    assert gms.pick_guide_url(card) == "https://wirlernenonline.de/oer"


def test_annotate_sets_attr_on_object(cfg):
    card = _FakeCard(url="https://wirlernenonline.de/oer")
    n = gms.annotate_cards_with_guide_url([card], enabled=True, host="wirlernenonline.de")
    assert n == 1
    assert card.guide_url == "https://wirlernenonline.de/oer"
