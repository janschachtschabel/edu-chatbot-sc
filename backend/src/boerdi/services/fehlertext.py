"""Der Satz einer gescheiterten Antwort (Paket 18F).

Bekam der Zug keinen LLM-Platz (``llm_parallel.ausgelastet``), ist es kein Fehler, den jemand
im Studio nachschlagen müsste: die Person liest „gerade ausgelastet, versuch es gleich noch
einmal“ — ohne Fehlernummer. Sonst der übliche Satz mit Fehlernummer (Paket 18C/D).
Eine Stelle für Muster-Weg, Werkzeugschleife und Agent-Weg, damit sie nicht auseinanderlaufen.
"""

from __future__ import annotations

from boerdi.i18n.bot_text import bot_text
from boerdi.obs.trace_id import fehlernummer
from boerdi.services.llm_parallel import ausgelastet, blase_merken


def antwort_fehlertext(sprache: str, schluessel: str) -> str:
    """``error.llmBusy`` für einen ausgelasteten Zug, sonst ``schluessel`` mit Fehlernummer."""
    if ausgelastet():
        blase_merken()
        return bot_text(sprache, "error.llmBusy")
    return bot_text(sprache, schluessel, nummer=fehlernummer())
