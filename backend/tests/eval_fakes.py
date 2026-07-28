"""Shared LLM double for the eval-engine tests (E4–E6).

The eval engine's only outbound LLM boundary is ``llm.chat_completion``, which
each consumer imports into its own module namespace — so a test patches
``boerdi.services.eval.<module>.chat_completion`` with one of these.

ALT's equivalent faked ``get_background_client()`` and mimicked the whole
``client.chat.completions.create`` object chain; NEU only needs a callable,
since ``chat_completion`` already *is* the seam.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any


class FakeLLM:
    """Callable stand-in for ``chat_completion``.

    ``replies`` are handed out in order and exhaust to ``""``; ``exc`` makes
    every call raise instead. Recorded kwargs land in ``calls``.
    """

    def __init__(
        self, replies: list[str] | None = None, exc: BaseException | None = None
    ) -> None:
        self.calls: list[dict[str, Any]] = []
        self.replies = list(replies or [])
        self.exc = exc

    async def __call__(self, **kwargs: Any) -> Any:
        # Copy ``messages`` at call time: the conversation simulator appends to
        # and pops from the SAME list object, so without a copy a test would
        # inspect the mutated state instead of what the provider actually saw.
        if isinstance(kwargs.get("messages"), list):
            kwargs = dict(kwargs, messages=list(kwargs["messages"]))
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        content = self.replies.pop(0) if self.replies else ""
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
