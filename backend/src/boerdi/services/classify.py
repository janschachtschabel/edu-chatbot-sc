"""Structured classification via instructor (P3-2, spec §3-2).

ALT ``classify_input`` (llm_service.py) forced a hand-built tool + tool_choice
and hand-parsed the arguments. Per spec §3-2 the NEU path uses
``instructor.from_litellm`` → ``ClassificationResult``: instructor auto-
generates the tool from the model and runs validation-retries, replacing the
hand-parsing. The valid IDs the ALT tool carried as enums are carried by the
system prompt instead (classify_prompt.py enumerates every persona / intent /
state / entity / pattern).

Parity preserved:
- the history window history[-10:] — since Paket 9 the message order is
  [system (static)] + [framed page, if any] + history[-10:] + [turn context] +
  [user] (Review Paket 7, MAJOR 10);
- temperature/verbosity gating reuses ``llm.build_chat_kwargs`` (a placeholder
  tool marker selects its tool-call branch, then is stripped — instructor
  injects its own tool);
- provider routing + timeout + num_retries + the shared concurrency bulkhead
  come via ``llm.wire_transport`` — the same stamp (incl. b-api
  cache-bust) as every chat turn;
- Layer-A fallback reproduces ALT: on retry exhaustion, salvage the valid
  subset of the model's raw tool args via ``model_construct``.

Patchable network boundary: ``_acreate`` (AsyncInstructor.create_with_completion).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from types import SimpleNamespace
from typing import Any

import instructor
import litellm
from instructor import Mode
from instructor.core import InstructorRetryException
from pydantic import ValidationError

from boerdi.api.schemas import ClassificationResult
from boerdi.obs import usage as _usage
from boerdi.obs.zeiten import seit_ms
from boerdi.services import llm as _llm
from boerdi.services import prompt_ablage, seitenkontext_prompt
from boerdi.services.classify_prompt import (
    build_classify_system_prompt,
    build_classify_turn_context,
    klassifikator_rohdaten,
)
from boerdi.services.llm_models import get_chat_model, get_provider
from boerdi.services.llm_nachrichten import nachrichten_fuer
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
    system = build_classify_system_prompt()
    # Paket 13 (A5): fester Prompt (ohne Zug-Kontext, Paket 9) als Prüfsumme im Merkposten.
    prompt_ablage.merke(usage_acc, "classify.system", system)
    messages: list[dict] = [{"role": "system", "content": system}]
    # E-E (Plan 2026-09-29, Nutzer-Entscheid 2026-10-09): die Seite gerahmt vor
    # dem Verlauf statt im Systemprompt — knapp, denn der Klassifikator wählt nur
    # ein Muster (ohne Bestand, 3 000 Zeichen je Textabschnitt, EK10). Seit Paket 9
    # samt den Rohdaten der Seite (Pfad, Kennungen, Suchbegriff).
    seite = seitenkontext_prompt.seiten_daten(
        session_state, environment.get("page_context"), include_stock=False,
        text_budget=3000, rohdaten=klassifikator_rohdaten(environment))
    if seite:
        messages.append({"role": "user", "content": seite})
    messages.extend(history[-_HISTORY_CAP:])
    # Paket 9 (Review Paket 7, MAJOR 10): der Zug-Kontext direkt vor der Frage —
    # Systemteil, Seite und Verlauf bleiben ein Präfix, das der Cache trifft.
    messages.append({"role": "user", "content": build_classify_turn_context(
        session_state, environment, canvas_state)})
    messages.append({"role": "user", "content": message})
    # Die Nachrichten gehen an ``wire_transport`` vorbei (instructor) — ihre Form
    # je Anbieter (E-AC) bekommen sie deshalb hier.
    messages = nachrichten_fuer(get_provider(), messages)

    model = get_chat_model()
    kwargs = _llm.build_chat_kwargs(
        model=model, messages=messages, tools=_TOOL_GATING_MARKER, temperature=0.1,
    )
    kwargs.pop("messages")
    kwargs.pop("tools", None)
    # Derselbe Stempel wie jeder Chat-Zug — seit dem Cache-Paket (2026-08-21)
    # inklusive b-api-Cache-Bust. Die frühere Zeilen-Kopie ließ genau den aus:
    # eine falsch gecachte Klassifikation klebte an identischen Folgezügen
    # (Review-Befund).
    _llm.wire_transport(model, kwargs)

    t0 = time.perf_counter()
    # Die Frist gilt dem Aufruf, nicht dem Warten auf einen Platz (wie bei der
    # Moderation): unter Last soll ein Zug warten statt ohne Klassifikation weiter.
    frist = get_settings().classify_timeout_s
    # Erst nach der Platzvergabe angelegt: ``asyncio.timeout`` setzt den Fristbeginn
    # beim Anlegen.
    grenze: asyncio.Timeout | None = None
    try:
        async with _llm.semaphore():
            grenze = asyncio.timeout(frist)
            async with grenze:
                result, raw = await _acreate(
                    messages=messages,
                    response_model=ClassificationResult,
                    max_retries=2,
                    **kwargs,
                )
    except TimeoutError:
        if grenze is None or not grenze.expired():
            raise
        # Paket 10 (Audit M-5): ``assess`` fängt das und nimmt die Vorgabe.
        raise TimeoutError(f"Klassifikation: keine Antwort binnen {frist:g} s") from None
    except InstructorRetryException as exc:
        _logger.warning("classify validation exhausted: %s", exc)
        # Die gescheiterten Versuche kosteten trotzdem (Paket 4, C1; F09):
        # instructor liefert ihren Verbrauch an der Ausnahme mit.
        _buche_fehlversuche(exc, usage_acc, t0)
        return _salvage(exc)

    if usage_acc is not None:
        _usage.add_usage(usage_acc, _usage.extract_usage(raw), "classify", ms=seit_ms(t0))
    return result


def _buche_fehlversuche(
    exc: InstructorRetryException, usage_acc: dict[str, Any] | None, t0: float,
) -> None:
    """Den Verbrauch der gescheiterten Versuche als ``classify`` buchen."""
    if usage_acc is None:
        return
    letzte = getattr(exc, "last_completion", None)
    verbrauch = _usage.extract_usage(SimpleNamespace(
        usage=getattr(exc, "total_usage", None),
        model=getattr(letzte, "model", "") or ""))
    if verbrauch["prompt"] or verbrauch["completion"]:
        _usage.add_usage(usage_acc, verbrauch, "classify", ms=seit_ms(t0))


def _salvage(exc: InstructorRetryException) -> ClassificationResult:
    """ALT Layer-A: keep the valid subset of the model's raw tool args; invalid
    fields take schema defaults. The raw args live on the last completion after
    instructor's retries are exhausted; if none can be recovered, return pure
    schema defaults.

    Jedes Feld wird einzeln geprüft (Paket 4, C1; externes Audit F10). ALT nahm
    ``model_construct`` und filterte damit nur die Feldnamen — gerade die Werte,
    an denen instructor gescheitert war, kamen so durch (``entities`` als Liste
    endete in ``merge`` in einer Ausnahme). Der Fehler ist aus ALT übernommen.
    """
    raw = _extract_tool_args(getattr(exc, "last_completion", None))
    if not raw:
        return ClassificationResult()
    gueltig: dict[str, Any] = {}
    for feld, wert in raw.items():
        if feld not in ClassificationResult.model_fields:
            continue
        try:
            ClassificationResult.model_validate({feld: wert})
        except ValidationError:
            _logger.info("classify salvage: Feld %s verworfen (ungültig)", feld)
            continue
        gueltig[feld] = wert
    return ClassificationResult.model_validate(gueltig)


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
