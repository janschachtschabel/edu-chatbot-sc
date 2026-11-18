"""Der Satz einer gescheiterten Antwort (Paket 18F).

Bekam der Zug keinen LLM-Platz (``llm_parallel.ausgelastet``), ist es kein Fehler, den jemand
im Studio nachschlagen müsste: die Person liest „gerade ausgelastet, versuch es gleich noch
einmal“ — ohne Fehlernummer. Sonst der übliche Satz mit Fehlernummer (Paket 18C/D).
Eine Stelle für Muster-Weg, Werkzeugschleife und Agent-Weg, damit sie nicht auseinanderlaufen.
"""

from __future__ import annotations

from boerdi.i18n.bot_text import bot_text
from boerdi.obs.trace_id import fehlernummer
from boerdi.services.llm_auth import KeinDelegationsToken, delegation_beendet, zug_art
from boerdi.services.llm_ereignisse import ist_abgelehnter_schluessel
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
    hätte sonst „ausgelastet“ ohne Fehlernummer gezeigt.

    Paket D (E6): im Delegationsbetrieb der b-api ohne Fehlernummer — eine 401 oder ein
    unbrauchbares Token heißt „Anmeldung der Seite abgelaufen, bitte neu laden“; ein mit dem
    Auflegen beendetes Token ist der Vermerk „Verbindung brach ab“ im Verlauf."""
    if (satz := _delegations_satz(sprache, fehler)) is not None:
        return satz
    if fehler is not None:
        ist_last = isinstance(fehler, LlmAusgelastet)
    elif ausgelastet_lauf is not None:
        ist_last = ausgelastet_lauf
    else:
        ist_last = ausgelastet()
    if ist_last:
        return ausgelastet_text(sprache)
    return bot_text(sprache, schluessel, nummer=fehlernummer())


def _ohne_token(fehler: BaseException | None) -> KeinDelegationsToken | None:
    """``KeinDelegationsToken`` — auch als Ursache einer Hülle (wenige Glieder tief)."""
    for _ in range(5):
        if fehler is None or isinstance(fehler, KeinDelegationsToken):
            return fehler
        fehler = fehler.__cause__ or fehler.__context__
    return None


def _delegations_satz(sprache: str, fehler: BaseException | None) -> str | None:
    if (ohne := _ohne_token(fehler)) is not None:
        return bot_text(sprache, "error.connectionLost" if ohne.grund == "beendet"
                        else "error.delegationExpired")
    if fehler is not None and zug_art() == "delegation" and ist_abgelehnter_schluessel(fehler):
        # Review D, Befund 4: nach dem Auflegen ist die 401 das Ende der Anfrage, kein Ablauf
        return bot_text(sprache, "error.connectionLost" if delegation_beendet()
                        else "error.delegationExpired")
    return None
