"""Structured classification via instructor (P3-2, spec §3-2).

ALT ``classify_input`` (llm_service.py) forced a hand-built tool + tool_choice
and hand-parsed the arguments. Per spec §3-2 the NEU path uses
``instructor.from_litellm`` → ``ClassificationResult``: instructor auto-
generates the tool from the model and runs validation-retries, replacing the
hand-parsing. The valid IDs the ALT tool carried as enums are carried by the
system prompt instead (classify_prompt.py enumerates every persona / intent /
state / entity / pattern).

Parity preserved:
- messages = [system] + history[-10:] + [user];
- temperature/verbosity gating reuses ``llm.build_chat_kwargs`` (a placeholder
  tool marker selects its tool-call branch, then is stripped — instructor
  injects its own tool);
- provider routing + timeout + num_retries + the shared concurrency bulkhead
  are wired exactly like ``llm.chat_completion``;
- Layer-A fallback reproduces ALT: on retry exhaustion, salvage the valid
  subset of the model's raw tool args via ``model_construct``.

Patchable network boundary: ``_acreate`` (AsyncInstructor.create_with_completion).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import instructor
import litellm
from instructor import Mode
from instructor.core import InstructorRetryException

from boerdi.api.schemas import ClassificationResult
from boerdi.obs import usage as _usage
from boerdi.services import llm as _llm
from boerdi.services.classify_prompt import build_classify_system_prompt
from boerdi.services.llm_models import get_chat_model
from boerdi.settings import get_settings

_logger = logging.getLogger(__name__)

_HISTORY_CAP = 10

# instructor over LiteLLM. Mode.TOOLS = forced named-tool-choice internally →
# matches ALT's forced tool_choice. Module singleton (no network at build).
_client = instructor.from_litellm(litellm.acompletion, mode=Mode.TOOLS)
# Network boundary — tests replace this.
_acreate = _client.chat.completions.create_with_completion

# instructor injects the tool itself; this placeholder only makes
# build_chat_kwargs take its *tool-call* gating branch exactly as ALT's
# forced-tool classify. Stripped before use — die echte Werkzeug-Liste kommt von
# instructor. WAS der Zweig dann sendet, entscheidet die Modellgruppe (W12b,
# llm_models._GROUPS): bei gpt-5.4 faellt `reasoning_effort` weg, bei
# gpt-5.6-luna MUSS er mit, sonst weist die API die ganze Klassifikation ab.
_TOOL_GATING_MARKER = [{"type": "function", "function": {"name": "classify_input"}}]


async def classify_input(
    message: str,
    history: list[dict],
    session_state: dict,
    environment: dict,
    canvas_state: dict | None = None,
    usage_acc: dict[str, Any] | None = None,
) -> ClassificationResult:
    """Classify the user message into the input dimensions (validated
    ClassificationResult). Falls back to the ALT Layer-A salvage / schema
    defaults so the pipeline never breaks."""
    system = build_classify_system_prompt(session_state, environment, canvas_state)
    messages: list[dict] = [{"role": "system", "content": system}]
    messages.extend(history[-_HISTORY_CAP:])
    messages.append({"role": "user", "content": message})

    model = get_chat_model()
    kwargs = _llm.build_chat_kwargs(
        model=model, messages=messages, tools=_TOOL_GATING_MARKER, temperature=0.1,
    )
    kwargs.pop("messages")
    kwargs.pop("tools", None)
    litellm_model, api_base, api_key, extra_headers = _llm.route(model)
    kwargs["model"] = litellm_model
    kwargs["api_base"] = api_base
    kwargs["api_key"] = api_key
    kwargs["timeout"] = get_settings().llm_read_timeout
    kwargs["num_retries"] = 2
    if extra_headers is not None:
        kwargs["extra_headers"] = extra_headers

    try:
        async with _llm.semaphore():
            result, raw = await _acreate(
                messages=messages,
                response_model=ClassificationResult,
                max_retries=2,
                **kwargs,
            )
    except InstructorRetryException as exc:
        _logger.warning("classify validation exhausted: %s", exc)
        return _salvage(exc)

    if usage_acc is not None:
        _usage.add_usage(usage_acc, _usage.extract_usage(raw), "classify")
    return result


def _salvage(exc: InstructorRetryException) -> ClassificationResult:
    """ALT Layer-A: keep the valid subset of the model's raw tool args
    (model_construct); missing/invalid fields take schema defaults. The raw
    args live on the last completion after instructor's retries are exhausted;
    if none can be recovered, return pure schema defaults."""
    raw = _extract_tool_args(getattr(exc, "last_completion", None))
    if not raw:
        return ClassificationResult()
    return ClassificationResult.model_construct(**{
        k: v for k, v in raw.items() if k in ClassificationResult.model_fields
    })


def _extract_tool_args(completion: Any) -> dict | None:
    """Pull the tool-call arguments dict out of a raw chat completion, or None
    when the shape is unexpected / the JSON is malformed."""
    try:
        args = completion.choices[0].message.tool_calls[0].function.arguments
    except (AttributeError, IndexError, TypeError):
        return None
    if isinstance(args, dict):
        return args
    try:
        data = json.loads(args)
    except (TypeError, ValueError):
        return None
    return data if isinstance(data, dict) else None
