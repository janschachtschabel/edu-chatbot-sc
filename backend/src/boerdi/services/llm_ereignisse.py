"""Meldungen der LLM-Engstelle (Paket 18F): abgelehnter Schlüssel, abgelaufene Platz-Frist.

Gerufen aus ``services/llm_parallel.platz`` — durch die gehen Chat, Einbettung, Klassifikator
und Strom (Moderation und Sprache haben eigene Wege), also erfasst EINE Stelle diese Aufrufe.
Hier statt in ``obs/``, weil die Meldung den Anbieter und die Herkunft des Schlüssels braucht
(``llm_models``, ``llm_auth``).

**Der Schlüssel steht nie im Log, auch nicht über den Text des Anbieters** („Incorrect API key
provided: sk-…“) — die Zeile nennt Anbieter, Route und Quelle.
"""

from __future__ import annotations

import logging

import httpx

from boerdi.obs import metrics
from boerdi.obs.drossel import gedrosselt
from boerdi.obs.log_format import ausnahme_text
from boerdi.services import llm_auth
from boerdi.services.llm_models import get_provider
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

#: Höchstens eine Zeile je Minute und Anbieter/Quelle — ein falscher Schlüssel träfe jeden Aufruf.
_ABSTAND_S = 60.0

# Jede mögliche Reihe von Anfang an mit 0 (Review 2026-10-30): ``increase()`` in der Alarmregel
# sieht sonst den ersten 401 nicht — die Reihe entstünde erst mit ihm.
for _anbieter, _quelle in (("openai", "openai_api_key"),
                           ("b-api-openai", "b_api_key"), ("b-api-openai", "weitergereicht"),
                           ("b-api-academiccloud", "b_api_key"),
                           ("b-api-academiccloud", "weitergereicht")):
    metrics.LLM_SCHLUESSEL_ABGELEHNT.labels(_anbieter, _quelle)


def ist_abgelehnter_schluessel(fehler: BaseException) -> bool:
    """Ist ``fehler`` — oder eine Ursache, ein Kontext, ein Versuch von instructor — eine 401?"""
    offen: list[BaseException | None] = [fehler]
    gesehen: set[int] = set()
    while offen:
        e = offen.pop()
        if e is None or id(e) in gesehen:
            continue
        gesehen.add(id(e))
        if getattr(e, "status_code", None) == 401:
            return True
        offen += [e.__cause__, e.__context__]
        # instructor verpackt die Fehler seiner Versuche (Klassifikator).
        offen += [getattr(v, "exception", None) for v in getattr(e, "failed_attempts", None) or []]
    return False


def schluessel_quelle() -> str:
    """Woher der Schlüssel dieses Aufrufs kam (``llm.route``): ``openai_api_key`` bei OpenAI
    direkt, hinter der b-api der vom Proxy ``weitergereicht``e oder ``b_api_key``."""
    if get_provider() == "openai":
        return "openai_api_key"
    return "weitergereicht" if llm_auth.hat_zug_schluessel() else "b_api_key"


def melde_schluessel_abgelehnt() -> None:
    """Zähler und eine gedrosselte Zeile. ERROR beim eigenen Schlüssel — der Betrieb muss ihn
    tauschen; WARNING beim weitergereichten, das ist der Schlüssel des Aufrufers."""
    anbieter, quelle = get_provider(), schluessel_quelle()
    metrics.LLM_SCHLUESSEL_ABGELEHNT.labels(anbieter, quelle).inc()
    stufe = logging.WARNING if quelle == "weitergereicht" else logging.ERROR
    gedrosselt(logger, stufe, f"schluessel:{anbieter}:{quelle}", _ABSTAND_S,
               "llm_schluessel_abgelehnt anbieter=%s route=%s quelle=%s — der Anbieter weist "
               "den Schlüssel ab (401)", anbieter,
               (get_settings().b_api_route or "-") if anbieter.startswith("b-api") else "-",
               quelle)


def melde_platz_frist(frist_s: float) -> None:
    """Zähler und eine gedrosselte Zeile: ein Zug bekam binnen der Frist keinen Platz."""
    metrics.LLM_PLATZ_FRIST.inc()
    gedrosselt(logger, logging.WARNING, "platz_frist", _ABSTAND_S,
               "llm_platz_frist frist_s=%g — kein LLM-Platz frei, der Zug gilt als ausgelastet",
               frist_s)


class LlmFristAbgelaufen(TimeoutError):  # noqa: N818 — Name wie ``LlmAusgelastet``
    """Die EIGENE Frist eines LLM-Aufrufs lief ab (``llm.chat_completion(frist_s=…)``,
    ``CLASSIFY_TIMEOUT_S``). Paket 19 (N-16, Review): nur sie gilt als vorübergehend — ein
    anderer ``TimeoutError`` (etwa asyncpg ``command_timeout`` aus der RAG-Abfrage) bleibt ein
    Fehler mit Traceback. Unterklasse, damit ``except TimeoutError`` weiter greift."""

    #: Ausgang in ``boerdi_llm_calls_total`` (``obs/metrics.llm_messung``, Review 19-5): die
    #: eigene Frist ist kein Anbieterfehler — sonst stiege die Fehlerquote, die der Alarm liest.
    metrik_ausgang = "abbruch"


#: Paket 19 (N-16): Frist und 429 — Betrieb, kein Programmfehler. Nach Namen wie in
#: ``obs/log_format``: litellm erbt von den openai-Klassen (``Timeout`` von ``APITimeoutError``).
_VORUEBERGEHEND = frozenset({"openai.RateLimitError", "openai.APITimeoutError"})
#: ``APIConnectionError`` nur mit einem Netzfehler in der Kette (Review): LiteLLM bildet JEDE
#: Ausnahme ohne HTTP-Status darauf ab, auch einen eigenen ``TypeError`` — das Original steht
#: dann nur in ``__context__``.
_VERBINDUNG = "openai.APIConnectionError"
_NETZ_NAMEN = frozenset({"aiohttp.client_exceptions.ClientError"})


def _namen(e: BaseException) -> set[str]:
    return {f"{k.__module__}.{k.__qualname__}" for k in type(e).__mro__}


def _netzfehler_in_kette(fehler: BaseException) -> bool:
    """Steht in ``__cause__``/``__context__`` ein Netzfehler (httpx, aiohttp, ``OSError`` samt
    ``ssl.SSLError`` und ``ConnectionError``)?"""
    offen = [fehler.__cause__, fehler.__context__]
    gesehen: set[int] = set()
    while offen:
        e = offen.pop()
        if e is None or id(e) in gesehen or len(gesehen) >= 10:
            continue
        gesehen.add(id(e))
        if isinstance(e, httpx.TransportError | OSError) or _namen(e) & _NETZ_NAMEN:
            return True
        offen += [e.__cause__, e.__context__]
    return False


def _einzeln_voruebergehend(e: BaseException) -> bool:
    if isinstance(e, LlmFristAbgelaufen):
        return True
    namen = _namen(e)
    if namen & _VORUEBERGEHEND:
        return True
    return _VERBINDUNG in namen and _netzfehler_in_kette(e)


def ist_voruebergehend(fehler: BaseException) -> bool:
    """Ein vorübergehender Anbieterfehler — auch als Ursache einer Hülle (instructor)."""
    e: BaseException | None = fehler
    for _ in range(5):
        if e is None:
            return False
        if _einzeln_voruebergehend(e):
            return True
        e = e.__cause__
    return False


def melde_voruebergehend(log: logging.Logger, ort: str, fehler: BaseException) -> None:
    """Eine WARNING ohne Traceback, höchstens eine je Minute, Ort und Art (Paket 19, N-16) —
    vorher ``logger.exception`` je Zug. Den Alarm tragen die LLM-Metriken."""
    gedrosselt(log, logging.WARNING, f"llm_voruebergehend:{ort}:{type(fehler).__name__}",
               _ABSTAND_S, "%s: Anbieter vorübergehend nicht verfügbar (%s)", ort,
               ausnahme_text(fehler))
