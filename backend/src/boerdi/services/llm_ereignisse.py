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

from boerdi.obs import metrics
from boerdi.obs.drossel import gedrosselt
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
