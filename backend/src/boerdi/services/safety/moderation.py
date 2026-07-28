"""Safety stage 2 — omni-moderation via ``litellm.amoderation``.

Port of ALT ``safety_service._openai_moderate`` + ``llm_provider.get_moderation_client``
(3-branch credential routing). Deliberate transport deviation (see
``docs/plans/p3-llm-transport-contract.md`` §"Moderation-Client"): the concrete
HTTP call moves from a bespoke ``AsyncOpenAI`` client to ``litellm.amoderation``;
the credential routing (which key/base/header per provider) is preserved 1:1.

Fail-open by design: a missing credential or any error returns ``{}`` so the
regex gate stays the hard safety floor (moderation is free but best-effort).
"""

from __future__ import annotations

import logging
from typing import Any

import litellm

from boerdi.services.llm_models import get_provider
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_MOD_MODEL = "omni-moderation-latest"
_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"

# Patchable network boundary (tests replace this with a fake).
_amoderation = litellm.amoderation


def _moderation_target() -> tuple[str, str, dict[str, str] | None] | None:
    """Resolve ``(api_base, api_key, extra_headers)`` for the moderation endpoint,
    or ``None`` to skip moderation (regex floor). Port of ALT
    ``get_moderation_client`` branch logic:

    - ``openai``: native OpenAI key, else ``None``.
    - ``b-api-openai``: B-API passthrough when ``B_API_KEY`` is set (the extended
      B-API proxies ``/moderations``); else a native OpenAI side-channel when
      ``OPENAI_API_KEY`` is set; else ``None``.
    - ``b-api-academiccloud`` (and any other): native OpenAI side-channel only
      (AcademicCloud has no moderation endpoint); ``None`` without an OpenAI key.
    """
    s = get_settings()
    provider = get_provider()
    openai_key = s.openai_api_key.get_secret_value().strip()
    # ALT get_moderation_client normalises the native base (strip + rstrip "/")
    # before the default fallback — mirror it so a trailing-slash OPENAI_BASE_URL
    # never yields a `…/v1//moderations` URL.
    openai_base = (s.openai_base_url or "").strip().rstrip("/") or _DEFAULT_OPENAI_BASE
    native = (openai_base, openai_key, None)

    if provider == "openai":
        return native if openai_key else None
    if provider == "b-api-openai":
        b_key = s.b_api_key.get_secret_value().strip()
        if b_key:
            base = s.b_api_base_url.rstrip("/") + "/openai"
            return base, b_key, {"X-API-KEY": b_key}
        return native if openai_key else None
    # b-api-academiccloud and any other provider: native side-channel only.
    return native if openai_key else None


def _as_mapping(value: Any) -> dict[str, Any]:
    """Kategorien/Scores als dict — egal ob LiteLLM sie als dict oder als Modell
    liefert.

    Am 2026-07-27 live gemessen (omni-moderation-latest): ``results[0]`` ist ein
    ``OpenAIModerationResult``-**Objekt**, aber ``categories`` und
    ``category_scores`` darin sind **plain dicts**. Der Port las hier
    ``.model_dump()`` — richtig für ALTs nativen OpenAI-Client, falsch über
    LiteLLM. Folge: jeder echte Aufruf lief in den Fail-Open-Zweig, die
    Moderationsstufe war im Betrieb tot, und weil die Test-Attrappe die
    Objekt-Form nachbaute, blieb die Suite grün. Die Modell-Form wird weiter
    bedient, weil sie bei anderen Anbietern vorkommen kann.
    """
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    return dump() if callable(dump) else dict(value)


async def moderate(message: str) -> dict[str, Any]:
    """Run omni-moderation over ``message`` (capped at 4000 chars).

    Returns ``{"flagged": bool, "categories": {cat: bool}, "scores": {cat: float}}``
    on success, or ``{}`` on any error / when no credential is available. Free of
    charge on OpenAI.
    """
    target = _moderation_target()
    if target is None:
        return {}
    api_base, api_key, extra_headers = target
    try:
        kwargs: dict[str, Any] = {
            "model": _MOD_MODEL,
            "input": message[:4000],
            "api_key": api_key,
            "api_base": api_base,
        }
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        result = await _amoderation(**kwargs)
        r = result.results[0]
        return {
            "flagged": bool(r.flagged),
            "categories": {k: bool(v) for k, v in _as_mapping(r.categories).items()},
            "scores": {k: float(v) for k, v in _as_mapping(r.category_scores).items()},
        }
    except Exception as e:  # noqa: BLE001 — fail-open by design (regex floor stays)
        logger.warning("moderation failed: %s", e)
        return {}
