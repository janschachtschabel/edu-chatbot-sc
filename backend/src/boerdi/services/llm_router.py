"""Der b-api-Router als Ziel des Chat-Modells (Paket 17, Phase A).

``B_API_ROUTE`` nennt eine Route des b-api-Routers (``/api/v1/llm/router``). Sie ersetzt
nur den Namen, unter dem das eingestellte Chat-Modell hinausgeht; Parameterregeln,
Responses-Weg und Preis bleiben die des Chat-Modells — eine Route bündelt laut b-api nur
Modelle EINER Familie. Alles, was nicht das Chat-Modell ist (Einbettungen, Moderation,
Sprache, ein eigenes ``EVAL_JUDGE_MODEL``/``EVAL_SIMULATOR_MODEL``), bleibt auf ``/openai``;
Judge und Simulator ohne eigenes Modell SIND das Chat-Modell und folgen der Route.

Eigenes Modul, weil ``llm.py`` an der 300-Zeilen-Grenze steht (wie ``llm_weg``).
"""

from __future__ import annotations

from boerdi.services.llm_models import get_chat_model, get_provider
from boerdi.settings import get_settings


def router_route(model: str) -> str | None:
    """Der Routenname, unter dem ``model`` über den b-api-Router geht — sonst ``None``.

    Nur das eingestellte Chat-Modell und nur bei ``b-api-openai``.
    """
    name = get_settings().b_api_route.strip()
    if not name or get_provider() != "b-api-openai" or model != get_chat_model():
        return None
    return name


def antwort_modell(gemeldet: str, resolved: str) -> str:
    """Der Modellname, unter dem eine Antwort gebucht wird.

    Unter einer Route meldet LiteLLM den Routennamen als ``model`` — das antwortende
    Upstream-Modell geht verloren (live gemessen 2026-10-20). Gebucht wird dann unter dem
    Regel-Modell ``resolved``, auch wenn die Route auf ihre Reserve auswich: deren Preis ist
    von außen nicht erkennbar.
    """
    if gemeldet and gemeldet == router_route(resolved):
        return resolved
    return gemeldet
