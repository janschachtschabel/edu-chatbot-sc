"""Schalter des laufenden Betriebs: Studio-Feld, die Umgebung geht vor (Paket 7, S1–S3).

Fast-Modus, Token-Streaming und die Schnellantworten des Agenten waren bis
Paket 7 reine Umgebungsvariablen. Jetzt stehen sie im Studio
(``01-base/engine`` → ``betrieb``) und wirken ohne Neustart. Ist die
Umgebungsvariable gesetzt, gilt sie: für einen Betrieb ohne Studio und als
Notbremse, die keine Studio-Änderung aushebelt. Ungesetzt heißt ``None``
(bzw. ``""`` beim Tarif) — ein leerer Wert aus compose zählt dank
``env_ignore_empty`` als ungesetzt.
"""

from __future__ import annotations

from boerdi.services.config_loader.engine import load_engine
from boerdi.settings import get_settings

#: Die OpenAI-Stufe, die der Studio-Schalter Fast-Modus setzt.
FAST_TARIF = "fast"


def token_streaming() -> bool:
    """Wird die Antwort Stück für Stück ins Widget gestreamt? (S2, Vorgabe an)"""
    umgebung = get_settings().chat_token_streaming
    if umgebung is not None:
        return umgebung
    return load_engine().betrieb.token_streaming


def agent_schnellantworten() -> bool:
    """Schreibt der Agent die Schnellantworten im Antwort-Aufruf mit? (S3, Vorgabe aus)"""
    umgebung = get_settings().agent_inline_quick_replies
    if umgebung is not None:
        return umgebung
    return load_engine().betrieb.agent_schnellantworten


def gastkonto_schreibt() -> bool:
    """Darf der Bot ohne persönliche Anmeldung mit dem Dienst-Block schreiben? (S4)

    Nur im Studio, ohne Umgebungsvariable: die Erlaubnis soll an einer Stelle
    stehen, an der man sie sieht. Die Regel selbst: ``services/schreibrecht``.
    """
    return load_engine().betrieb.gastkonto_schreibt


def service_tier() -> str:
    """Der OpenAI-Tarif — ``""`` heißt Standard (S1). Ob er gesendet wird
    (nur OpenAI direkt, gpt-5/gpt-6), entscheidet ``services/llm``."""
    umgebung = get_settings().llm_service_tier
    if umgebung:
        return umgebung
    return FAST_TARIF if load_engine().betrieb.fast_modus else ""
