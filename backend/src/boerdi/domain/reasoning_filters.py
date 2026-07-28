"""Reasoning-marker filters for LLM output (P3-3, port of ALT
llm_reasoning_filters.py). Framework-free domain: pure text processing +
one streamer with only an instance buffer.

Strips chain-of-thought that leaked into the visible ``content`` field —
finished text (``strip_reasoning_markers``) and live token streams
(``ThinkSafeStreamer``, which holds back a safety tail so a tag split across
chunks never leaks). Reasoning in a separate ``reasoning``/``reasoning_content``
field is untouched — the answer path only reads ``message.content``.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

_logger = logging.getLogger(__name__)

_THINK_BLOCK_RE = re.compile(
    r"<(think|thinking|reasoning)\b[^>]*>.*?</\1\s*>", re.DOTALL | re.IGNORECASE
)
# Open think-tag without a close (model ran into the token limit mid-reasoning):
# discard everything from the tag onward.
_THINK_OPEN_TAIL_RE = re.compile(
    r"<(think|thinking|reasoning)\b[^>]*>.*\Z", re.DOTALL | re.IGNORECASE
)
_THINK_UNI_BLOCK_RE = re.compile(r"◁think▷.*?◁/think▷", re.DOTALL)
_THINK_UNI_TAIL_RE = re.compile(r"◁think▷.*\Z", re.DOTALL)
_HARMONY_MARKERS = (
    "<|channel|>", "<|message|>", "<|start|>", "<|end|>",
    "<|im_start|>", "<|im_end|>", "assistantfinal",
)


def strip_reasoning_markers(text: str) -> str:
    """Remove chain-of-thought leaked into visible ``content``:
    closed ``<think>…</think>`` / ``<thinking>`` / ``<reasoning>`` blocks, an
    unclosed ``<think>…`` tail, the unicode ``◁think▷…◁/think▷`` variant, and
    gpt-oss harmony channel markers. Clean text returns unchanged (fast path)."""
    if not text:
        return text
    if "<" not in text and "◁" not in text and "assistantfinal" not in text:
        return text
    out = _THINK_BLOCK_RE.sub("", text)
    out = _THINK_OPEN_TAIL_RE.sub("", out)
    out = _THINK_UNI_BLOCK_RE.sub("", out)
    out = _THINK_UNI_TAIL_RE.sub("", out)
    for marker in _HARMONY_MARKERS:
        out = out.replace(marker, "")
    return out.strip()


class ThinkSafeStreamer:
    """Live streaming guard: keeps ``<think>…</think>`` out of the token stream,
    not just out of the final text.

    Per chunk the visible text is re-derived from the WHOLE accumulation via
    ``strip_reasoning_markers`` (single source of truth, robust against tags
    split across chunk boundaries). Only the STABLE prefix is forwarded — all
    but a safety tail of ``_HOLDBACK`` chars that could still be the start of a
    marker (e.g. ``<thi`` before ``<think>`` is complete). ``flush()`` releases
    the remainder at stream end.
    """

    _HOLDBACK = 16  # ≥ longest marker ("assistantfinal"=14, "<reasoning"=10)

    def __init__(self, on_token: Callable[[str], None] | None):
        self._on = on_token
        self._acc = ""
        self._emitted = 0  # visible chars already sent

    def _emit(self, visible: str, target_len: int) -> None:
        end = min(target_len, len(visible))
        if self._on is None or end <= self._emitted:
            return
        piece = visible[self._emitted:end]
        if not piece:
            return
        try:
            self._on(piece)
        except Exception:
            _logger.debug("stream callback failed", exc_info=True)
        self._emitted = end

    def __call__(self, chunk: str) -> None:
        if chunk:
            self._acc += chunk
        if self._on is None:
            return
        visible = strip_reasoning_markers(self._acc)
        self._emit(visible, len(visible) - self._HOLDBACK)

    def flush(self) -> None:
        if self._on is None:
            return
        visible = strip_reasoning_markers(self._acc)
        self._emit(visible, len(visible))
