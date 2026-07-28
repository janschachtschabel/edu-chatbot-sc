"""Behaviour pins for the guide-marker *attach* half (``services/guide_markers``).

ALT ``chat_guide_markers.py`` split into a pure *strip* half (``domain/guide_markers``,
already ported + tested) and this *I/O attach* half. The attach functions carry NO
dedicated ALT unit test — they were integration-level glue in ALT — so these tests
pin the observable contract for the port:

* ``_attach_guide_qr`` — inserts a deterministic "bring-me-there" guide QR at the
  head of the quick-replies, gated by guide-mode + host allow-list; strips any
  ``__guide__|…`` entry when the gate is closed; swallows errors (QR = UX sugar).
* ``_attach_guide_urls`` — annotates ``card.guide_url`` on inline cards AND on a
  ``canvas_show_cards`` page-action payload; no-op when gated off; swallows errors.

Only the external boundaries are mocked (``host_is_allowed`` / ``inject_guide_qr`` /
``load_guide_mode_config`` / ``annotate_cards_with_guide_url``); the attach functions
import these function-locally, so patching the source module is picked up at call
time. One end-to-end test drives the *real* ``inject_guide_qr`` to prove the call
signature stays compatible across the two verbatim ports.
"""

from __future__ import annotations

import re

from boerdi.api.schemas import ChatRequest, Environment
from boerdi.services.guide_markers import _attach_guide_qr, _attach_guide_urls


def _req(message: str = "hallo", *, guide_mode: bool = True,
         host: str = "wirlernenonline.de") -> ChatRequest:
    return ChatRequest(
        session_id="s1",
        message=message,
        environment=Environment(guide_mode=guide_mode, host=host),
    )


# ══════════════════════════════════════════════════════════════════════════
# _attach_guide_qr — gate closed → strip
# ══════════════════════════════════════════════════════════════════════════
def test_attach_guide_qr_guide_off_strips_guide_entries():
    out = _attach_guide_qr(
        _req(guide_mode=False), ["Normal", "__guide__|X|https://a", "Andere"]
    )
    assert out == ["Normal", "Andere"]


def test_attach_guide_qr_empty_host_strips_guide_entries():
    out = _attach_guide_qr(_req(host=""), ["a", "__guide__|X|https://a"])
    assert out == ["a"]


def test_attach_guide_qr_host_not_allowed_strips(monkeypatch):
    from boerdi.domain import guide_mode
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: False)
    out = _attach_guide_qr(_req(host="evil.com"), ["a", "__guide__|X|https://a"])
    assert out == ["a"]


# ══════════════════════════════════════════════════════════════════════════
# _attach_guide_qr — gate open → inject_guide_qr wiring
# ══════════════════════════════════════════════════════════════════════════
def test_attach_guide_qr_passes_args_and_filters_session_state(monkeypatch):
    from boerdi.domain import guide_mode
    from boerdi.services import config_loader, guide_qr_injector
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(
        config_loader, "load_guide_mode_config",
        lambda: {"max_guide_quick_replies": 3},
    )
    captured = {}

    def fake_inject(message, quick_replies, *, rag_areas_used, response_text,
                    rag_top_sources, max_guide_qrs):
        captured.update(
            message=message, quick_replies=quick_replies,
            rag_areas_used=rag_areas_used, response_text=response_text,
            rag_top_sources=rag_top_sources, max_guide_qrs=max_guide_qrs,
        )
        return ["__guide__|Hin|https://x", *quick_replies]

    monkeypatch.setattr(guide_qr_injector, "inject_guide_qr", fake_inject)
    session_state = {
        "_rag_areas_used": ["WissenLebtOnline", 5, "OER"],   # non-str dropped
        "_rag_top_sources": ["src1", None, "src2"],          # None dropped
    }
    out = _attach_guide_qr(
        _req(message="mitmachen?"), ["Andere"],
        session_state=session_state, response_text="Antwort",
    )
    assert out[0] == "__guide__|Hin|https://x"
    assert "Andere" in out
    assert captured["message"] == "mitmachen?"
    assert captured["quick_replies"] == ["Andere"]
    assert captured["rag_areas_used"] == ["WissenLebtOnline", "OER"]
    assert captured["rag_top_sources"] == ["src1", "src2"]
    assert captured["response_text"] == "Antwort"
    assert captured["max_guide_qrs"] == 3


def test_attach_guide_qr_none_session_state_yields_empty_lists(monkeypatch):
    from boerdi.domain import guide_mode
    from boerdi.services import config_loader, guide_qr_injector
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(config_loader, "load_guide_mode_config", lambda: {})
    captured = {}

    def fake_inject(message, quick_replies, *, rag_areas_used, response_text,
                    rag_top_sources, max_guide_qrs):
        captured.update(rag_areas_used=rag_areas_used,
                        rag_top_sources=rag_top_sources, max_guide_qrs=max_guide_qrs)
        return quick_replies

    monkeypatch.setattr(guide_qr_injector, "inject_guide_qr", fake_inject)
    _attach_guide_qr(_req(), ["a"])
    assert captured["rag_areas_used"] == []
    assert captured["rag_top_sources"] == []
    # default when key missing: int({}.get("max_guide_quick_replies", 2)) == 2
    assert captured["max_guide_qrs"] == 2


def test_attach_guide_qr_end_to_end_real_injector(monkeypatch):
    """Full wiring through the REAL inject_guide_qr — proves the call signature
    stays compatible between the two verbatim ports."""
    from boerdi.domain import guide_mode
    from boerdi.services import config_loader, guide_qr_injector
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(config_loader, "load_guide_mode_config",
                        lambda: {"max_guide_quick_replies": 2})
    monkeypatch.setattr(guide_qr_injector, "_COMPILED", [
        (re.compile("themenseite.*klima", re.I), "Klima",
         "https://wirlernenonline.de/themenseite/klima", 90),
    ])
    out = _attach_guide_qr(_req(message="zeig die themenseite zu klima"), ["Andere Frage"])
    assert out[0] == "__guide__|Klima|https://wirlernenonline.de/themenseite/klima"
    assert "Andere Frage" in out


def test_attach_guide_qr_swallows_exception_returns_raw(monkeypatch):
    """On any injector error the raw quick-replies are returned unchanged
    (NOT stripped) — the except branch returns ``quick_replies`` verbatim."""
    from boerdi.domain import guide_mode
    from boerdi.services import config_loader, guide_qr_injector
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(config_loader, "load_guide_mode_config", lambda: {})

    def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(guide_qr_injector, "inject_guide_qr", boom)
    qrs = ["keep", "__guide__|X|https://a"]
    out = _attach_guide_qr(_req(), qrs)
    assert out == ["keep", "__guide__|X|https://a"]


# ══════════════════════════════════════════════════════════════════════════
# _attach_guide_urls — card guide_url annotation
# ══════════════════════════════════════════════════════════════════════════
def test_attach_guide_urls_guide_off_is_noop(monkeypatch):
    from boerdi.domain import guide_mode
    calls: list = []
    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url",
                        lambda *a, **k: calls.append((a, k)))
    _attach_guide_urls(_req(guide_mode=False), [{"title": "X"}], None)
    assert calls == []


def test_attach_guide_urls_empty_host_is_noop(monkeypatch):
    from boerdi.domain import guide_mode
    calls: list = []
    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url",
                        lambda *a, **k: calls.append((a, k)))
    _attach_guide_urls(_req(host=""), [{"title": "X"}], None)
    assert calls == []


def test_attach_guide_urls_host_not_allowed_is_noop(monkeypatch):
    from boerdi.domain import guide_mode
    calls: list = []
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: False)
    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url",
                        lambda *a, **k: calls.append((a, k)))
    _attach_guide_urls(_req(host="evil.com"), [{"title": "X"}], None)
    assert calls == []


def test_attach_guide_urls_happy_annotates_inline_cards(monkeypatch):
    from boerdi.domain import guide_mode
    calls: list = []
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)

    def rec(cards, *, enabled, host):
        calls.append((cards, enabled, host))
        return len(cards)

    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url", rec)
    cards = [{"t": 1}]
    _attach_guide_urls(_req(host="wirlernenonline.de"), cards, None)
    assert len(calls) == 1
    assert calls[0][0] is cards
    assert calls[0][1] is True
    assert calls[0][2] == "wirlernenonline.de"


def test_attach_guide_urls_annotates_canvas_payload_cards(monkeypatch):
    from boerdi.domain import guide_mode
    seen: list = []
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url",
                        lambda cards, *, enabled, host: seen.append(list(cards)))
    payload_cards = [{"t": "canvas"}]
    page_action = {"action": "canvas_show_cards", "payload": {"cards": payload_cards}}
    _attach_guide_urls(_req(host="wirlernenonline.de"), [{"t": "inline"}], page_action)
    assert [{"t": "inline"}] in seen
    assert [{"t": "canvas"}] in seen


def test_attach_guide_urls_ignores_non_canvas_page_action(monkeypatch):
    from boerdi.domain import guide_mode
    seen: list = []
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)
    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url",
                        lambda cards, *, enabled, host: seen.append(list(cards)))
    page_action = {"action": "navigate", "payload": {"cards": [{"t": "canvas"}]}}
    _attach_guide_urls(_req(host="wirlernenonline.de"), [{"t": "inline"}], page_action)
    # only inline cards annotated; the non-canvas payload is left alone
    assert seen == [[{"t": "inline"}]]


def test_attach_guide_urls_swallows_exception(monkeypatch):
    from boerdi.domain import guide_mode
    monkeypatch.setattr(guide_mode, "host_is_allowed", lambda h: True)

    def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(guide_mode, "annotate_cards_with_guide_url", boom)
    # must not raise
    _attach_guide_urls(_req(host="wirlernenonline.de"), [{"t": 1}], None)
