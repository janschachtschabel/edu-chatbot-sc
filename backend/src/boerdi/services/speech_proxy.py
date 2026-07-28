"""STT/TTS proxy to the configured OpenAI-compatible audio service (P7 port of
ALT ``app/routers/speech.py`` upstream logic).

The router (``api/speech.py``) owns the trust boundary — rate limit (decorator),
upload/text caps (413), enablement gate (503). Everything that talks to the
paid upstream lives here: provider resolution, the STT model fallback chain, and
the single TTS call. NO database.

Transport: ALT used the OpenAI SDK client. NEU has no SDK client (chat runs over
LiteLLM), so we call the OpenAI-compatible ``/audio/{transcriptions,speech}``
endpoints directly with ``httpx``. The provider base URL + auth are resolved via
``services.llm.route`` (the single source of provider routing: OpenAI →
``Authorization: Bearer``, B-API → additional ``X-API-KEY``), so speech and chat
never drift apart. The network round-trip is the module attribute ``_post`` so
tests can replace it without hitting the network.

Secrets: the resolved key goes into the request headers only — never logged.
"""

from __future__ import annotations

import logging
import os

import httpx

from boerdi.services.llm import route
from boerdi.services.llm_models import get_provider
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

# T3 (ALT Audit 2026-07-05): hard caps for the PUBLIC speech endpoints so they
# cannot call the paid audio upstream unbounded (cost / memory DoS). Enforced by
# the router BEFORE any upstream/enablement work.
MAX_TTS_CHARS = 2000
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB

# STT fallback chain used when the primary model errors (unsupported format,
# quota, model access). Ordered most→least capable — ALT verbatim.
STT_FALLBACKS = ["gpt-4o-transcribe", "whisper-1"]

# Domain prompt biases the STT model towards WLO / OER / German school
# vocabulary (keeps "Bord-Rechnung" → "Bruchrechnung", "Wie loh online" →
# "WirLernenOnline", …). Under ~224 tokens (OpenAI's prompt-field limit).
# ALT verbatim.
WLO_DOMAIN_PROMPT = (
    "Thema: Bildung, Schule, Unterricht, offene Bildungsressourcen (OER). "
    "Plattformen: WLO, WirLernenOnline, edu-sharing, Klexikon, Serlo, ZUM, "
    "Khan Academy, Wikipedia. Rollen: Lehrkraft, Lehrer, Lehrerin, "
    "Lernende, Schüler, Schülerin, Eltern. Inhaltstypen: Arbeitsblatt, "
    "Video, Bild, Quiz, Kurs, Interaktives Medium, Unterrichtsplan, "
    "Audio, Podcast. Bildungsstufen: Grundschule, Sekundarstufe I, "
    "Sekundarstufe II, Hochschule, Berufliche Bildung, Primarstufe, "
    "Elementarbereich. Fächer: Mathematik, Bruchrechnung, Algebra, "
    "Deutsch, Englisch, Französisch, Biologie, Photosynthese, "
    "Zellteilung, Chemie, Physik, Informatik, Geschichte, Erdkunde, "
    "Geographie, Politik, Kunst, Musik, Sport, Religion, Ethik."
)

# Multipart content-type by audio suffix (ALT derived the temp-file suffix from
# the filename and let the SDK set the part type; here we set it explicitly).
_AUDIO_CONTENT_TYPES = {
    ".webm": "audio/webm",
    ".weba": "audio/webm",
    ".mp3": "audio/mpeg",
    ".mpga": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".flac": "audio/flac",
}


class SpeechProxyError(Exception):
    """Upstream STT/TTS call failed. The router maps this to a generic 502 so no
    upstream detail leaks to the public client (ALT Audit N-9)."""


def speech_enabled() -> bool:
    """Whether STT/TTS is available for the active provider (port of ALT
    ``llm_provider.speech_enabled`` with a NEU provider-split — see below).

    * ``openai`` → True iff an OpenAI key is configured (speech talks straight
      to the OpenAI-compatible endpoint).
    * ``b-api-openai`` → True only with explicit opt-in ``B_API_AUDIO=1`` AND a
      ``B_API_KEY`` (the extended B-API ``/openai`` mode proxies OpenAI audio,
      same key as chat).
    * ``b-api-academiccloud`` (and any other) → always False: AcademicCloud has
      no OpenAI audio endpoints, so speech is honestly excluded here instead of
      enabled-then-502. NEU deviation vs ALT (which treated all ``b-api-*``
      alike); for STT/TTS use ``b-api-openai`` or ``openai``.

    ``SPEECH_FORCE_ENABLE=1`` forces True (debug / transition).
    """
    s = get_settings()
    if s.speech_force_enable:
        return True
    provider = get_provider()
    if provider == "openai":
        return bool(s.openai_api_key.get_secret_value().strip())
    if provider == "b-api-openai":
        return s.b_api_audio and bool(s.b_api_key.get_secret_value().strip())
    # b-api-academiccloud + any other: no OpenAI audio endpoint → excluded.
    return False


def speech_disabled_reason() -> str:
    """Short reason for the UI/API when speech is off (empty when enabled). NEU
    deviation vs ALT ``llm_provider.speech_disabled_reason``: split by provider so
    the AcademicCloud hint no longer wrongly suggests ``B_API_AUDIO`` (which
    cannot enable audio there)."""
    if speech_enabled():
        return ""
    provider = get_provider()
    if provider == "b-api-openai":
        return (
            "Sprachfunktion ist bei B-API-Anbindung standardmäßig "
            "deaktiviert (Kostenschutz). Aktivierung: B_API_AUDIO=1 setzen "
            "— die B-API (openai-Modus) unterstützt OpenAI-Audio (STT/TTS)."
        )
    if provider == "b-api-academiccloud":
        return (
            "Sprachfunktion ist bei AcademicCloud nicht verfügbar "
            "(kein OpenAI-Audio-Endpunkt). Für STT/TTS LLM_PROVIDER=b-api-openai "
            "oder openai verwenden."
        )
    return "Sprachfunktion nicht verfügbar (kein OpenAI-Key konfiguriert)."


def _audio_content_type(filename: str | None) -> str:
    suffix = os.path.splitext(filename or "")[1].lower()
    return _AUDIO_CONTENT_TYPES.get(suffix, "application/octet-stream")


def _auth_headers(model: str) -> tuple[str, dict[str, str]]:
    """(api_base, headers) for ``model`` under the active provider. Reuses the
    chat transport's provider routing so auth never drifts: Bearer <api_key>
    plus the B-API ``X-API-KEY`` when present."""
    _, api_base, api_key, extra_headers = route(model)
    headers = {"Authorization": f"Bearer {api_key}"}
    if extra_headers:
        headers.update(extra_headers)
    return api_base, headers


async def _post(
    url: str,
    *,
    headers: dict[str, str],
    timeout: float,
    data: dict | None = None,
    files: dict | None = None,
    json: dict | None = None,
) -> httpx.Response:
    """The single network boundary — one short-lived client per call. Tests
    replace this attribute to run offline."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, headers=headers, data=data, files=files, json=json)


async def transcribe_audio(content: bytes, filename: str | None, language: str) -> dict:
    """Transcribe ``content`` to text via the STT service, trying the primary
    model then ``STT_FALLBACKS`` in order (ALT loop). Returns
    ``{"text": ..., "model": ...}`` for the first model that succeeds. Raises
    :class:`SpeechProxyError` when every model fails — the router turns that into
    a generic 502. Callers must enforce the size cap + enablement first."""
    s = get_settings()
    primary = s.stt_model
    timeout = s.llm_read_timeout
    files = {"file": (filename or "audio.webm", content, _audio_content_type(filename))}

    last_error: Exception | None = None
    for model in [primary, *STT_FALLBACKS]:
        try:
            api_base, headers = _auth_headers(model)
            resp = await _post(
                f"{api_base}/audio/transcriptions",
                headers=headers,
                timeout=timeout,
                data={
                    "model": model,
                    "language": language,
                    "prompt": WLO_DOMAIN_PROMPT,
                    "response_format": "text",
                },
                files=files,
            )
            resp.raise_for_status()
            # response_format="text" → the body IS the transcript.
            text = resp.text
            if model != primary:
                logger.info("STT fell back to %r (primary %r failed)", model, primary)
            return {"text": text, "model": model}
        except Exception as e:
            last_error = e
            logger.warning("STT model %r failed: %s — trying next", model, e)
            continue
    # Internal detail stays server-side only (ALT Audit N-9).
    logger.error("Alle STT-Modelle fehlgeschlagen: %s", last_error)
    raise SpeechProxyError("STT failed for all models")


async def synthesize_speech(text: str, voice: str, speed: float) -> bytes:
    """Synthesize ``text`` to speech via the TTS service, returning the raw
    audio bytes (``audio/mpeg``). Raises :class:`SpeechProxyError` on any upstream
    failure — the router turns that into a generic 502. Callers must enforce the
    length cap + enablement first."""
    s = get_settings()
    model = s.tts_model
    api_base, headers = _auth_headers(model)
    try:
        resp = await _post(
            f"{api_base}/audio/speech",
            headers=headers,
            timeout=s.llm_read_timeout,
            json={"model": model, "voice": voice, "input": text, "speed": speed},
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        # Internal detail stays server-side only (ALT Audit N-9).
        logger.exception("TTS-Synthese fehlgeschlagen")
        raise SpeechProxyError("TTS failed") from e
