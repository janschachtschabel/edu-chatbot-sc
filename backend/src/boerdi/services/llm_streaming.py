"""Streaming twin of ``llm.chat_completion`` (P15 prerequisite, port of ALT
llm_streaming.py): ``_stream_completion`` plus its reconstruction dataclasses
``_StreamedMessage``/``_StreamedToolCall``/``_StreamedChoice``/
``_StreamedResponse`` and the progressive JSON-arg parser
``_RespondToUserExtractor`` — all class bodies ALT-verbatim.

Two NEU-deviations vs ALT, both at the transport seam of ``_stream_completion``
(chunk consumption + reconstruction are verbatim):
- ALT received PRE-BUILT chat kwargs and streamed over the module ``client``
  singleton. Eiserne Regel 3 forbids module-global clients, so NEU takes the
  same SEMANTIC kwargs as ``llm.chat_completion`` and does ``build_chat_kwargs``
  + ``wire_transport`` + ``llm._acompletion`` itself (network patch point stays
  ``llm._acompletion``). The live concurrency semaphore is held for the WHOLE
  stream consumption — ALT's bulkhead was the httpx pool, which a stream also
  occupied end-to-end; releasing after connect would leak concurrency.
- ALT's ``_make_think_safe_on_token(on_token)`` factory is NEU
  ``ThinkSafeStreamer(on_token)`` from domain/reasoning_filters (same
  callable + ``flush()`` protocol).

Seit dem Plan Token-Streaming (2026-10-03) weicht NEU in zwei weiteren Punkten
ab: freier Inhaltstext geht nicht mehr an ``on_token``, und der Extraktor läuft
hinter ``ThinkSafeStreamer`` und dekodiert Unicode-Escapes (``_escape_at``).

Boundary: the tool loop imports ``_stream_completion`` as a top-level name —
tests driving the loop patch it on ``services.tool_loop`` (ALT convention);
tests driving THIS module patch ``llm._acompletion``.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from boerdi.domain.reasoning_filters import ThinkSafeStreamer
from boerdi.services import llm

_logger = logging.getLogger(__name__)


class _StreamedMessage:
    """Lightweight stand-in for ``ChatCompletionMessage`` produced by
    streaming. Has the attributes ``content``, ``tool_calls`` (each with
    ``id``, ``function.name``, ``function.arguments``), and ``role``.

    The non-streaming code path consumes ``resp.choices[0].message`` via
    these attributes; this class provides them so the existing tool-loop
    body can run unchanged regardless of streaming on/off.
    """
    def __init__(self) -> None:
        self.role: str = "assistant"
        self.content: str | None = None
        self.tool_calls: list[Any] | None = None


class _StreamedToolCall:
    """Stand-in for an OpenAI ``ChoiceDeltaToolCall``-rolled-up object."""
    def __init__(self, tc_id: str = "", name: str = "", arguments: str = "") -> None:
        self.id = tc_id
        self.type = "function"
        self.function = type("Fn", (), {"name": name, "arguments": arguments})()


class _StreamedChoice:
    def __init__(self) -> None:
        self.message = _StreamedMessage()
        self.finish_reason: str | None = None


class _StreamedResponse:
    """Stand-in for ``ChatCompletion`` reconstructed from a streamed call."""
    def __init__(self) -> None:
        self.choices: list[_StreamedChoice] = [_StreamedChoice()]
        self.usage: Any = None
        self.model: str = ""


_RUECKSTRICH = chr(92)


def _hex(ziffern: str) -> int:
    try:
        return int(ziffern, 16)
    except ValueError:
        return -1


def _escape_at(buf: str, i: int) -> tuple[str, int | None]:
    """Das JSON-Escape ab ``buf[i]`` (dem Rückstrich): ``(Zeichen, Index danach)``,
    oder ``("", None)``, solange es noch nicht vollständig im Puffer steht.

    NEU gegen ALT (Audit 2026-09-29, Plan Token-Streaming T1): ALT übersetzte nur
    die Ein-Zeichen-Escapes, ein Unicode-Escape (Rückstrich, ``u``, vier
    Hexziffern) kam ohne Rückstrich beim Client an. Dekodiert wird mit ``json``;
    ein Surrogatpaar wird zusammengesetzt, ein einsames Surrogat sichtbar ersetzt.
    """
    if i + 1 >= len(buf):
        return "", None
    if buf[i + 1] != "u":
        laenge = 2
    elif len(buf) < i + 6:
        return "", None
    elif not 0xD800 <= _hex(buf[i + 2:i + 6]) <= 0xDBFF:
        laenge = 6
    elif len(buf) < i + 8:
        return "", None
    elif buf[i + 6:i + 8] != _RUECKSTRICH + "u":
        laenge = 6  # einsames hohes Surrogat
    elif len(buf) < i + 12:
        return "", None
    else:
        laenge = 12
    try:
        zeichen = json.loads('"' + buf[i:i + laenge] + '"')
    except ValueError:
        return chr(0xFFFD), i + laenge
    return "".join(chr(0xFFFD) if 0xD800 <= ord(z) <= 0xDFFF else z for z in zeichen), i + laenge


class _RespondToUserExtractor:
    """Progressive parser for the ``respond_to_user`` tool's JSON args.

    The tool schema is ``{text: str, quick_replies: list[str]}``, and the
    LLM emits the ``text`` field FIRST (we declared it first). As argument
    chunks stream in, we incrementally extract characters of the ``text``
    string and forward them to ``on_token`` — so the user sees the answer
    fill in token-by-token, exactly as if the model had emitted plain
    content.

    We do NOT try to parse the closing ``quick_replies`` array
    incrementally — those land in one shot at the end (and the caller can
    json.loads the full args string post-stream).

    State machine: scan for ``"text":`` then ``"`` (skipping whitespace);
    forward characters until an unescaped ``"``; ignore everything after.
    """
    def __init__(self, on_token: Any) -> None:
        self._buf = ""
        self._on_token = on_token
        self._scan_pos = 0       # next char index to inspect
        self._mode = "search"    # search | text | done

    def feed(self, chunk: str) -> None:
        if not chunk or self._mode == "done":
            self._buf += chunk or ""
            return
        self._buf += chunk
        # ── Phase 1: search for "text" key opening quote ──
        if self._mode == "search":
            # Find ``"text"`` followed by optional whitespace + ``:`` + ws + ``"``
            idx = self._buf.find('"text"', self._scan_pos)
            if idx < 0:
                # not yet present — wait for more chunks
                self._scan_pos = max(0, len(self._buf) - 8)  # keep last few chars in case "text" straddles boundary  # noqa: E501
                return
            cur = idx + len('"text"')
            # Skip whitespace + ``:`` + whitespace
            while cur < len(self._buf) and self._buf[cur] in " \t\n":
                cur += 1
            if cur >= len(self._buf):
                return  # need more
            if self._buf[cur] != ":":
                # Malformed — ``"text"`` not as a key. Skip past and keep searching.
                self._scan_pos = cur
                return
            cur += 1
            while cur < len(self._buf) and self._buf[cur] in " \t\n":
                cur += 1
            if cur >= len(self._buf):
                return  # need more
            if self._buf[cur] != '"':
                # The text value isn't a string (could be null) — give up streaming.
                self._mode = "done"
                return
            # Found opening quote of the text value
            self._scan_pos = cur + 1
            self._mode = "text"

        # ── Phase 2: stream characters until the unescaped closing quote ──
        if self._mode == "text":
            buf = self._buf
            out: list[str] = []
            i = self._scan_pos
            while i < len(buf):
                ch = buf[i]
                if ch == '"':
                    # Closing quote — text field complete
                    self._mode = "done"
                    i += 1
                    break
                if ch != _RUECKSTRICH:
                    out.append(ch)
                    i += 1
                    continue
                zeichen, weiter = _escape_at(buf, i)
                if weiter is None:
                    break  # Escape noch unvollständig — der nächste Chunk bringt den Rest
                out.append(zeichen)
                i = weiter
            self._scan_pos = i
            if out:
                try:
                    self._on_token("".join(out))
                except Exception:
                    _logger.debug("on_token callback failed", exc_info=True)

    @property
    def buffer(self) -> str:
        return self._buf


async def _stream_completion(
    on_token: Any,
    **kwargs: Any,
) -> _StreamedResponse:
    """Streaming mirror of ``llm.chat_completion`` (same semantic kwargs).

    Returns a ``_StreamedResponse`` that the existing non-streaming code
    path consumes via the same attributes (``choices[0].message.content``,
    ``choices[0].message.tool_calls``, ``choices[0].finish_reason``).

    Tokens are forwarded via ``on_token(text_chunk)`` only for the ``text``
    field of a ``respond_to_user`` call: ``_RespondToUserExtractor`` reads it
    from the streamed JSON args, ``ThinkSafeStreamer`` keeps reasoning markers
    out. Plain ``delta.content`` is accumulated into the message but NOT
    forwarded (Plan Token-Streaming, E-S1 — a preamble before tool calls would
    flash and vanish). Other tool calls accumulate silently.
    """
    built = llm.build_chat_kwargs(**kwargs)
    resolved = built["model"]
    llm.wire_transport(resolved, built)
    # Force stream + ask for usage in the final chunk (OpenAI 2024+).
    built["stream"] = True
    built["stream_options"] = {"include_usage": True}

    aggregate = _StreamedResponse()
    msg = aggregate.choices[0].message
    content_parts: list[str] = []
    # Live-Streaming-Schutz: <think>…</think> wird schon WÄHREND des Streamens
    # unterdrückt (nicht erst im finalen Text). Saubere Modelle streamen 1:1.
    _safe_on_token = ThinkSafeStreamer(on_token)
    # tc_index → {"id": str, "name": str, "args_buf": str, "extractor": _RespondToUserExtractor | None}  # noqa: E501
    tool_calls_accum: dict[int, dict[str, Any]] = {}

    async with llm.semaphore():
        stream = await llm._acompletion(**built)
        async for chunk in stream:
            # Final chunk in OpenAI's stream often carries the cumulative usage
            # (only when stream_options.include_usage is set). Capture it so
            # extract_usage works below just like for non-streaming responses.
            if getattr(chunk, "usage", None) is not None:
                aggregate.usage = chunk.usage
            if getattr(chunk, "model", None):
                aggregate.model = llm.antwort_modell(chunk.model, resolved)
            if not chunk.choices:
                continue
            ch0 = chunk.choices[0]
            delta = getattr(ch0, "delta", None)
            if ch0.finish_reason:
                aggregate.choices[0].finish_reason = ch0.finish_reason
            if delta is None:
                continue
            if getattr(delta, "role", None):
                msg.role = delta.role
            if getattr(delta, "content", None):
                # Gesammelt, nicht gesendet (Plan Token-Streaming, E-S1): eine
                # Vorrede vor Werkzeugaufrufen blitzte sonst auf und verschwände.
                content_parts.append(delta.content)
            if getattr(delta, "tool_calls", None):
                for tc_delta in delta.tool_calls:
                    idx = getattr(tc_delta, "index", 0) or 0
                    slot = tool_calls_accum.setdefault(idx, {
                        "id": "", "name": "", "args_buf": "", "extractor": None,
                    })
                    if getattr(tc_delta, "id", None):
                        slot["id"] = tc_delta.id
                    fn = getattr(tc_delta, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            slot["name"] = fn.name
                            # Lazily attach the JSON-stream extractor for respond_to_user
                            if slot["name"] == "respond_to_user" and slot["extractor"] is None:
                                slot["extractor"] = _RespondToUserExtractor(_safe_on_token)
                                # Replay any args we received before the name arrived
                                if slot["args_buf"]:
                                    slot["extractor"].feed(slot["args_buf"])
                        if getattr(fn, "arguments", None):
                            slot["args_buf"] += fn.arguments
                            if slot["extractor"] is not None:
                                slot["extractor"].feed(fn.arguments)

    # Live-Stream-Filter leeren — letzten Sicherheits-Tail (Hold-back) freigeben.
    _safe_on_token.flush()
    # Reconstitute the message
    if content_parts:
        msg.content = "".join(content_parts)
    if tool_calls_accum:
        ordered = [tool_calls_accum[k] for k in sorted(tool_calls_accum.keys())]
        msg.tool_calls = [
            _StreamedToolCall(slot["id"], slot["name"], slot["args_buf"])
            for slot in ordered
        ]
    return aggregate
