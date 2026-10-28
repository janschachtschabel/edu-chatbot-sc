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

import asyncio
import logging
from typing import Any

import litellm

from boerdi.obs import metrics
from boerdi.obs.trace_id import ausgehende_koepfe
from boerdi.services import llm_parallel
from boerdi.services.llm_auth import b_api_schluessel
from boerdi.services.llm_models import get_provider
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

_MOD_MODEL = "omni-moderation-latest"
_DEFAULT_OPENAI_BASE = "https://api.openai.com/v1"
# Obergrenze je Moderations-Aufruf (Audit 2026-09-29). ``litellm.amoderation``
# baut seinen OpenAI-Client ohne Zeitlimit (``httpx.Timeout(None)``) und reicht
# ``timeout`` nicht durch: ein Anbieter, der annimmt und nie antwortet, hielt
# sonst jeden Zug samt Sitzungssperre an. Üblich sind weit unter einer Sekunde;
# die Stufe ist fail-open, nach der Frist gilt „kein Befund" (Regex-Boden bleibt).
# Sie gilt für das Warten auf einen der eigenen Plätze und den Aufruf zusammen
# (Review Paket 9; ``_mit_platz``).
_MOD_TIMEOUT_SECONDS = 8.0

#: Die 13 Kategorien von omni-moderation-latest in der Schreibweise, die der
#: Seed (``escalation.thresholds``/``hard_block_categories``) und der Code
#: prüfen: API-Name mit "_" statt "-" (``self-harm/intent`` → ``self_harm/intent``).
_KATEGORIEN = (
    "harassment", "harassment/threatening", "hate", "hate/threatening",
    "illicit", "illicit/violent", "self_harm", "self_harm/instructions",
    "self_harm/intent", "sexual", "sexual/minors", "violence", "violence/graphic",
)
#: SDK-Feldname → Kategorie (``self_harm_intent`` → ``self_harm/intent``).
_AUS_SDK_NAME = {k.replace("/", "_"): k for k in _KATEGORIEN}

#: Abschnittslänge je Moderationseingabe, Überlappung benachbarter Abschnitte (ein Wort
#: auf der Grenze steht so ganz in einem) und Obergrenze der Abschnitte je Aufruf.
_ABSCHNITT = 4000
_UEBERLAPPUNG = 200
_MAX_ABSCHNITTE = 8

#: Ob der fehlende Zugang schon einmal gemeldet wurde (eine Warnung je Prozess).
_ohne_zugang_gemeldet = False

# Patchable network boundary (tests replace this with a fake).
_amoderation = litellm.amoderation


def _moderation_target() -> tuple[str, str, dict[str, str] | None] | None:
    """Resolve ``(api_base, api_key, extra_headers)`` for the moderation endpoint,
    or ``None`` to skip moderation (regex floor). Port of ALT
    ``get_moderation_client`` branch logic:

    - ``openai``: native OpenAI key, else ``None``.
    - ``b-api-openai``: B-API passthrough with the turn's key (forwarded by the b-api
      proxy, else ``B_API_KEY`` — Paket 17, one Bearer header); else a native OpenAI
      side-channel when ``OPENAI_API_KEY`` is set; else ``None``.
    - ``b-api-academiccloud``: ``None`` — AcademicCloud has no moderation
      endpoint (B-API ``/academiccloud/moderations`` → 404, measured 2026-10-09),
      and since Paket 7 (L5, user decision 2026-10-09) the messages no longer go
      to OpenAI instead: whoever chose AcademicCloud keeps them there. The regex
      floor stays.
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
        # Paket 17 (B3): der Schlüssel des Zuges (b-api-Proxy) vor ``B_API_KEY``, als
        # einziger Kopf (``Authorization: Bearer``, vom SDK aus ``api_key`` gebaut).
        b_key = b_api_schluessel()
        if b_key:
            base = s.b_api_base_url.rstrip("/") + "/openai"
            return base, b_key, ausgehende_koepfe() or None  # Paket 17 (D4): Trace-ID
        return native if openai_key else None
    if provider == "b-api-academiccloud":
        return None
    # any other provider: native side-channel only.
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


def _kategorie(key: str) -> str:
    """Eine Schreibweise je Kategorie — die, mit der Seed und Code prüfen.

    Befund 2026-09-27 (golden-20260927-131857-e6b-an-3.json, nachgestellt mit
    openai 2.45.0): das OpenAI-SDK legt die API-Namen neben seinen Feldnamen als
    Extras ab, ``model_dump()`` liefert also jede Unterkategorie ZWEIMAL —
    ``self_harm_intent`` und ``self-harm/intent``. Geprüft wurde aber
    ``self_harm/intent``, eine Form, die in keiner der beiden vorkommt: die
    Schwelle 0,25 für Suizid-Absicht und die harte Kategorie griffen nie (ALT
    las dasselbe ``model_dump()`` und hatte denselben Fehler). Beide Formen
    landen jetzt auf derselben Kategorie; ein unbekannter API-Name folgt
    derselben Regel, ein unbekannter SDK-Feldname bleibt, wie er ist.
    """
    k = key.replace("-", "_")
    return _AUS_SDK_NAME.get(k, k)


async def _mit_platz(kwargs: dict[str, Any]) -> Any:
    """Der Aufruf in einem der eigenen Plätze der Moderation (Paket 9). Am
    Anbieter-Deckel wartete sie hinter Antwort-Strömen, bis ihre Frist ablief, und
    unter Last ging jede Nachricht ungeprüft durch (Review Paket 7, MAJOR 8;
    Begründung im Kopf von ``services/llm_parallel``).

    Die Frist gilt für Warten und Aufruf zusammen (Review Paket 9, MAJOR 4): hängt
    der Anbieter, belegt jeder Aufruf seinen Platz bis zur Frist, und ohne Grenze
    für das Warten stauten sich die Züge dahinter — jeder mit seiner Sitzungssperre.
    In den eigenen Plätzen stehen nur kurze Moderationen; mehr als eine Frist wartet
    deshalb keiner."""
    async with asyncio.timeout(_MOD_TIMEOUT_SECONDS), llm_parallel.moderations_semaphore():
        return await _amoderation(**kwargs)


def _abschnitte(message: str) -> tuple[list[str], bool]:
    """Die Nachricht in Abschnitte der Länge, die omni-moderation verträgt, und ob
    sie damit ganz geprüft wird.

    Bis Paket 18 sah die Stufe nur die ersten 4000 Zeichen, und eine Chat-Nachricht
    hat keine eigene Längengrenze: ein harmloser Vorspann schob den Inhalt aus dem
    Blick (Prüfung 2026-10-28). Mehrere Abschnitte gehen in EINEM Aufruf hinaus
    (``input`` als Liste), die Wartezeit bleibt also gleich. Sind es mehr als
    :data:`_MAX_ABSCHNITTE`, gehen Anfang und Ende hinaus, und die Prüfung gilt als
    teilweise (Review 18: Inhalt ab Zeichen 32 000 blieb sonst ungeprüft)."""
    schritt = _ABSCHNITT - _UEBERLAPPUNG
    teile = [message[i:i + _ABSCHNITT]
             for i in range(0, max(len(message) - _UEBERLAPPUNG, 1), schritt)]
    if len(teile) <= _MAX_ABSCHNITTE:
        return teile, True
    logger.warning("moderation: message has %d chars, only the first and last %d sections "
                   "are checked", len(message), _MAX_ABSCHNITTE // 2)
    haelfte = _MAX_ABSCHNITTE // 2
    return teile[:haelfte] + teile[-haelfte:], False


def _zusammengefasst(results: list[Any]) -> dict[str, Any]:
    """Ein Befund über alle Abschnitte: markiert, wenn ein Abschnitt es ist; je
    Kategorie der höchste Wert."""
    kategorien: dict[str, bool] = {}
    werte: dict[str, float] = {}
    for r in results:
        for k, v in _as_mapping(r.categories).items():
            kat = _kategorie(k)
            kategorien[kat] = kategorien.get(kat, False) or bool(v)
        for k, v in _as_mapping(r.category_scores).items():
            kat = _kategorie(k)
            werte[kat] = max(werte.get(kat, 0.0), float(v))
    return {
        "flagged": any(bool(r.flagged) for r in results),
        "categories": kategorien,
        "scores": werte,
    }


async def moderate(message: str) -> dict[str, Any]:
    """Run omni-moderation over ``message`` (in sections of 4000 chars, see
    ``_abschnitte``).

    Returns ``{"flagged": bool, "categories": {cat: bool}, "scores": {cat: float}}``
    on success (plus ``"teilweise": True`` when only start and end of a very long
    message were checked), or ``{}`` when the message stayed UNCHECKED (any error, an
    incomplete answer, or no credential). ``{}`` never means "clean": ``service``
    records it as a failed stage (Paket 18A). Free of charge on OpenAI.
    """
    global _ohne_zugang_gemeldet
    target = _moderation_target()
    if target is None:
        metrics.sicherheitsstufe("openai_moderation", "keine_zugangsdaten")
        if not _ohne_zugang_gemeldet:
            # Einmal je Prozess: ein Setup ohne Moderation ist ein Zustand, kein
            # Ereignis — aber er darf nicht stumm sein (Prüfung 2026-10-28).
            logger.warning("moderation not configured for provider %s — messages pass "
                           "without moderation (regex floor only)", get_provider())
            _ohne_zugang_gemeldet = True
        return {}
    api_base, api_key, extra_headers = target
    teile, ganz = _abschnitte(message)
    try:
        kwargs: dict[str, Any] = {
            "model": _MOD_MODEL,
            "input": teile[0] if len(teile) == 1 else teile,
            "api_key": api_key,
            "api_base": api_base,
        }
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        result = await _mit_platz(kwargs)
        ergebnisse = list(result.results)
        if len(ergebnisse) != len(teile):
            # Review 18: eine leere Liste wurde sonst zu „sauber“ zusammengefasst.
            raise ValueError(f"{len(ergebnisse)} results for {len(teile)} sections")
        befund = _zusammengefasst(ergebnisse)
    except Exception as e:  # noqa: BLE001 — fail-open by design (regex floor stays)
        # Mit Art: ``str(TimeoutError())`` ist leer, das Log sagte nur „failed: “.
        logger.warning("moderation skipped, message passes unchecked: %s: %s",
                       type(e).__name__, e)
        metrics.sicherheitsstufe("openai_moderation", "fehler")
        return {}
    if not ganz:
        befund["teilweise"] = True
    metrics.sicherheitsstufe("openai_moderation", "ok" if ganz else "teilweise")
    return befund
