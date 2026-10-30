"""Der Satz einer gescheiterten Antwort (Paket 18F).

Bekam der Zug keinen LLM-Platz (``llm_parallel.ausgelastet``), ist es kein Fehler, den jemand
im Studio nachschlagen müsste: die Person liest „gerade ausgelastet, versuch es gleich noch
einmal“ — ohne Fehlernummer. Sonst der übliche Satz mit Fehlernummer (Paket 18C/D).
Eine Stelle für Muster-Weg, Werkzeugschleife und Agent-Weg, damit sie nicht auseinanderlaufen.
"""

from __future__ import annotations

from boerdi.i18n.bot_text import bot_text
from boerdi.obs.trace_id import fehlernummer
from boerdi.services.llm_parallel import LlmAusgelastet, ausgelastet, blase_merken


def ausgelastet_text(sprache: str) -> str:
    """Der „ausgelastet“-Satz — die Antwort dieses Zugs ist damit die Blase (Chip „Nochmal
    versuchen“, ``turn_assembly``)."""
    blase_merken()
    return bot_text(sprache, "error.llmBusy")


def antwort_fehlertext(sprache: str, schluessel: str, *, fehler: BaseException | None = None,
                       ausgelastet_lauf: bool | None = None) -> str:
    """``error.llmBusy`` für einen ausgelasteten Zug, sonst ``schluessel`` mit Fehlernummer.

    Es entscheidet, woran die Antwort scheiterte (Review 2026-10-30): ``fehler`` (die Ausnahme)
    bzw. ``ausgelastet_lauf`` (der Agent-Lauf). Der Merker des Zugs gilt nur ohne beides — er
    sagt bloß, dass IRGENDEIN Aufruf keinen Platz bekam, und ein späterer Absturz anderer Art
    hätte sonst „ausgelastet“ ohne Fehlernummer gezeigt."""
    if fehler is not None:
        ist_last = isinstance(fehler, LlmAusgelastet)
    elif ausgelastet_lauf is not None:
        ist_last = ausgelastet_lauf
    else:
        ist_last = ausgelastet()
    if ist_last:
        return ausgelastet_text(sprache)
    return bot_text(sprache, schluessel, nummer=fehlernummer())
