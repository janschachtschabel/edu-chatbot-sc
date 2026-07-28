"""Behaviour pins for ``domain/widget_modes`` (port of ALT
``chat_widget_modes._widget_modes``): the widget-embed-mode backward-compat echo.

Welle E reduced the embed modes to nothing; ``_widget_modes`` now always echoes
the four legacy layout flags as ``True`` so downstream postprocess/routing code
that still reads them keeps working. The function ignores its ``req`` argument
entirely — the pins nail the exact static contract and that input-independence.

ALT's sibling ``_display_rules`` is deliberately NOT ported: NEU already bypasses
that thin wrapper (``domain/quick_reply_policy`` calls ``load_display_rules_config``
directly), so re-creating it would duplicate an already-bypassed decision.
"""

from __future__ import annotations

from boerdi.domain import widget_modes as wm


def test_returns_all_four_compat_flags_true():
    assert wm._widget_modes(object()) == {
        "cards_enabled": True,
        "canvas_enabled": True,
        "inline_result_grouping": True,
        "quick_replies_enabled": True,
    }


def test_result_keys_and_values_are_exactly_the_four_bools():
    result = wm._widget_modes(object())
    assert set(result) == {
        "cards_enabled",
        "canvas_enabled",
        "inline_result_grouping",
        "quick_replies_enabled",
    }
    assert all(v is True for v in result.values())


def test_output_is_independent_of_the_request_argument():
    # The compat echo is static; two different stand-in requests (even None)
    # must produce an identical dict.
    assert wm._widget_modes(None) == wm._widget_modes(object())
