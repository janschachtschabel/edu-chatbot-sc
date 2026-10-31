"""Speech proxy endpoints (public, capped, rate-limited P1-4). Port of ALT
``app/routers/speech.py``: a capability probe plus STT (transcribe) and TTS
(synthesize) proxies to the configured OpenAI-compatible audio service.

The HTTP rate limit is the ``@public_rate_limit`` decorator (P1-4, pinned in
test_ratelimit.py) — it replaces ALT's in-band ``_rate_limit_or_429`` and runs
before the body. The body keeps ALT's safety floor, in order: read + cap the
input (413) → enablement gate (503) → upstream call, with internal upstream
errors folded to a generic 502 (no detail leaks to the public client). No
database — all upstream logic lives in ``services/speech_proxy.py``; the router
only does HTTP translation.
"""

from __future__ import annotations

import math
import re
from typing import Annotated, Final

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from boerdi.api.ratelimit import public_rate_limit
from boerdi.api.turn_auth import uebernimm_llm_schluessel
from boerdi.services.speech_proxy import (
    MAX_AUDIO_BYTES,
    MAX_TTS_CHARS,
    SpeechEingabeFehler,
    SpeechProxyError,
    speech_disabled_reason,
    speech_enabled,
    synthesize_speech,
    transcribe_audio,
)

public_router = APIRouter(prefix="/api/speech", tags=["speech"])

# Paket 19 (Audit M-16): die Felder vor jedem bezahlten Aufruf prüfen. Geprüft im Rumpf statt
# per ``Literal``/``Form(ge=…)``: das hielte das eingefrorene OpenAPI-Dokument nicht still.
#: Die Stimmen der OpenAI-Sprachausgabe (``tts-1``/``gpt-4o-mini-tts``); das Widget sendet ``nova``.
STIMMEN: Final = frozenset({
    "alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer",
    "verse", "marin", "cedar",
})
_SPRACHE = re.compile(r"[a-z]{2}(-[A-Z]{2})?")
TEMPO_MIN, TEMPO_MAX = 0.25, 4.0


def _eingabefehler(fehler: SpeechEingabeFehler, text: str) -> HTTPException:
    """Der Anbieter wies die Eingabe zurück: 415 für das Format, sonst 400 — nie 502."""
    return HTTPException(status_code=415 if fehler.status == 415 else 400, detail=text)


@public_router.get("/status")
@public_rate_limit
def speech_status(request: Request, response: Response) -> dict:
    """Public capability probe — tells the widget whether STT/TTS is available
    so it can show/hide the mic + speaker buttons instead of firing into the
    void (ALT speech.py::speech_status).

    ``response`` is the FastAPI-injected response: ``@public_rate_limit`` runs
    with ``headers_enabled`` and, for a dict-returning endpoint, injects the
    ``X-RateLimit-*`` headers into it — slowapi raises without a real Response to
    write to (extension.py::_inject_headers), so the parameter is required even
    though the body never touches it."""
    # Paket 17: ein durchgereichter Schlüssel zählt mit; eine Auskunft, kein Zug (keine Pflicht).
    uebernimm_llm_schluessel(request, pflicht=False)
    return {"enabled": speech_enabled(), "reason": speech_disabled_reason()}


@public_router.post("/transcribe")
@public_rate_limit
async def transcribe(
    request: Request,
    response: Response,
    audio: Annotated[UploadFile, File()],
    language: Annotated[str, Form()] = "de",
) -> dict:
    """Transcribe uploaded audio to text (STT).

    Reads at most ``MAX_AUDIO_BYTES + 1`` and rejects an oversized upload with
    413 BEFORE any enablement/upstream work — the cost + memory DoS floor (ALT
    Audit T3). Then gates on enablement (503) and proxies to the STT service;
    all-models-failed becomes a generic 502.

    ``response`` is the FastAPI-injected response the rate-limit decorator writes
    its ``X-RateLimit-*`` headers into on the (dict-returning) success path —
    required, see ``speech_status``. The 413/503/502 paths raise before it is used.
    """
    uebernimm_llm_schluessel(request)  # Paket 17
    if not _SPRACHE.fullmatch(language):
        raise HTTPException(status_code=422, detail="language: Form „de“ oder „de-DE“.")
    # Bounded read (max cap+1) — a huge upload must neither pin memory nor reach
    # the paid upstream.
    content = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(content) > MAX_AUDIO_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio zu groß (max {MAX_AUDIO_BYTES // (1024 * 1024)} MB).",
        )
    if not speech_enabled():
        raise HTTPException(status_code=503, detail=speech_disabled_reason())
    try:
        return await transcribe_audio(content, audio.filename, language)
    except SpeechEingabeFehler as err:
        raise _eingabefehler(err, "Audio wurde nicht angenommen.") from err
    except SpeechProxyError as err:
        raise HTTPException(
            status_code=502, detail="Spracherkennung fehlgeschlagen."
        ) from err


@public_router.post("/synthesize")
@public_rate_limit
async def synthesize(
    request: Request,
    text: Annotated[str, Form()],
    voice: Annotated[str, Form()] = "nova",
    speed: Annotated[float, Form()] = 1.0,
) -> dict:
    """Synthesize text to speech (TTS).

    Caps the input at ``MAX_TTS_CHARS`` (413) before the enablement gate (503)
    and the upstream call, mirroring ALT's order. On success returns raw
    ``audio/mpeg`` bytes — NOT JSON; the ``-> dict`` stub annotation is kept for
    the P7 contract, and FastAPI returns the ``Response`` as-is. An upstream
    failure becomes a generic 502.
    """
    uebernimm_llm_schluessel(request)  # Paket 17
    if voice not in STIMMEN:
        raise HTTPException(status_code=422, detail="voice: unbekannte Stimme.")
    if not (math.isfinite(speed) and TEMPO_MIN <= speed <= TEMPO_MAX):
        raise HTTPException(status_code=422, detail="speed: 0.25 bis 4.0.")
    if len(text) > MAX_TTS_CHARS:
        raise HTTPException(
            status_code=413, detail=f"Text zu lang (max {MAX_TTS_CHARS} Zeichen)."
        )
    if not speech_enabled():
        raise HTTPException(status_code=503, detail=speech_disabled_reason())
    try:
        audio_bytes = await synthesize_speech(text, voice, speed)
    except SpeechEingabeFehler as err:
        raise _eingabefehler(err, "Text wurde nicht angenommen.") from err
    except SpeechProxyError as err:
        raise HTTPException(
            status_code=502, detail="Sprachsynthese fehlgeschlagen."
        ) from err
    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Content-Disposition": "inline; filename=speech.mp3"},
    )
