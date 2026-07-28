"""P3-3 (slice): reasoning-marker filter — port of ALT llm_reasoning_filters.py.

Pure text processing (framework-free domain): strips chain-of-thought that
leaked into the visible ``content`` field, both from finished text and live
from a token stream (holding back a safety tail so a tag split across chunks
never leaks).
"""

from __future__ import annotations

from boerdi.domain.reasoning_filters import (
    ThinkSafeStreamer,
    strip_reasoning_markers,
)


# ── strip_reasoning_markers ────────────────────────────────────────────────
def test_fast_path_returns_clean_text_unchanged() -> None:
    text = "Hier ist deine Antwort ohne Denk-Block."
    assert strip_reasoning_markers(text) is text  # identity: no work done


def test_empty_input() -> None:
    assert strip_reasoning_markers("") == ""


def test_closed_think_block_removed() -> None:
    assert strip_reasoning_markers(
        "<think>geheime Gedanken</think>Sichtbare Antwort.") == "Sichtbare Antwort."


def test_thinking_and_reasoning_variants() -> None:
    assert strip_reasoning_markers("<thinking>x</thinking>A") == "A"
    assert strip_reasoning_markers("<reasoning>y</reasoning>B") == "B"


def test_unclosed_think_tail_discarded() -> None:
    # model ran into the token limit mid-reasoning (finish_reason=length)
    assert strip_reasoning_markers("Antwort.\n<think>halb gedacht und dann") == "Antwort."


def test_unicode_think_variant() -> None:
    assert strip_reasoning_markers("◁think▷denk◁/think▷Antwort") == "Antwort"
    assert strip_reasoning_markers("Text ◁think▷abgeschnitten") == "Text"


def test_harmony_markers_neutralized() -> None:
    got = strip_reasoning_markers("<|channel|>final<|message|>Hallo assistantfinal")
    assert "channel" not in got and "assistantfinal" not in got
    assert "Hallo" in got


def test_case_insensitive_and_attributes() -> None:
    assert strip_reasoning_markers('<THINK foo="bar">z</THINK>Antwort') == "Antwort"


# ── ThinkSafeStreamer ──────────────────────────────────────────────────────
def _collect() -> tuple[list[str], ThinkSafeStreamer]:
    out: list[str] = []
    return out, ThinkSafeStreamer(out.append)


def test_streamer_clean_model_emits_everything_by_flush() -> None:
    out, s = _collect()
    for ch in "Hallo, wie kann ich helfen?":
        s(ch)
    s.flush()
    assert "".join(out) == "Hallo, wie kann ich helfen?"


def test_streamer_holds_back_tail_until_flush() -> None:
    out, s = _collect()
    s("Kurz")  # shorter than the 16-char holdback -> nothing emitted yet
    assert "".join(out) == ""
    s.flush()
    assert "".join(out) == "Kurz"


def test_streamer_never_leaks_think_block_across_chunks() -> None:
    out, s = _collect()
    # tag arrives split across chunks; content must never surface
    for chunk in ["Antwort. <", "thi", "nk>ge", "heim</th", "ink>", " Ende"]:
        s(chunk)
    s.flush()
    joined = "".join(out)
    assert "geheim" not in joined and "think" not in joined
    assert joined == "Antwort.  Ende"


def test_streamer_callback_errors_do_not_crash() -> None:
    def boom(_piece: str) -> None:
        raise RuntimeError("sink down")

    s = ThinkSafeStreamer(boom)
    s("some long enough text to emit a stable prefix now")
    s.flush()  # must not raise


def test_streamer_none_callback_is_noop() -> None:
    s = ThinkSafeStreamer(None)
    s("anything")
    s.flush()  # no callback, no error
