"""Der Abschluss eines Agent-Laufs im Chat — wenn ein Deckel die Antwort verschluckt.

Aus ``graph/nodes/respond_agent`` gelöst (Paket 9, Review Paket 7 — Dateigrößen):
dort steht der Zug, hier, was er tut, wenn der Lauf ohne Text endet — einmal
nachfragen (:func:`abschluss_nachholen`), sonst ein ehrlicher Satz
(:func:`antwort_oder_ersatz`).
"""

from __future__ import annotations

import logging

from boerdi.i18n.bot_text import bot_text
from boerdi.i18n.prompt_language import SPRACHE_DER_PERSON
from boerdi.obs.trace_id import fehlernummer
from boerdi.services import llm
from boerdi.services.agent_loop import AgentRun

logger = logging.getLogger(__name__)


#: Enden, bei denen der Lauf an einen Deckel gestoßen ist statt zu scheitern —
#: der Nutzer kann selbst etwas tun (kleiner schneiden). Alles andere ist ein
#: Fehlschlag und bekommt den Wiederhol-Satz.
GEDECKELT = frozenset({"deadline", "token_budget", "max_iterations", "no_progress"})


def antwort_oder_ersatz(lauf: AgentRun, sprache: str) -> str:
    """Der Antworttext — oder ein ehrlicher Satz, wenn es keinen gibt.

    ``AgentRun.text`` ist nur bei ``text`` und ``submit`` gefüllt; die fünf
    übrigen Enden liefern ihn LEER. Ohne diesen Ersatz bekäme der Nutzer eine
    leere Blase, und ein stiller Ausfall ist der schlechtere von beiden. Der
    Bestandsweg degradiert an derselben Stelle freundlich.

    Geprüft wird der TEXT und nicht der Grund: auch ``stop_reason='text'`` kann
    leer sein, wenn das Modell mit leerem Inhalt antwortet.
    """
    if lauf.text.strip():
        return lauf.text
    if lauf.dokumente or lauf.result is not None:
        # Ein Lauf, der ein Ergebnis GELIEFERT hat, ist nicht gescheitert — ihm
        # fehlt nur der Begleitsatz. Der Deckel-Satz („zu umfangreich, stell sie
        # kleiner geschnitten noch einmal") stünde direkt über einer
        # vollständigen Stundenplanung und würde von ihr widerlegt.
        #
        # ``lauf.result`` zählt seit J1 mit: seit ``liefere_ergebnis`` den Lauf
        # nicht mehr beendet, kann ein Zug das Ergebnis abliefern und DANACH an
        # der Frist enden. Ohne diese Zeile bekäme der Gastgeber ein tadelloses
        # JSON und die Person daneben die Auskunft, es sei nichts geworden.
        logger.info("Agent-Modus: Lieferung ohne Begleitsatz (%d Box(en), "
                    "Ergebnis=%s, Ende=%s)",
                    len(lauf.dokumente), lauf.result is not None, lauf.stop_reason)
        return bot_text(sprache, "agent.delivered")
    if lauf.stop_reason == "error":
        # Paket 18C/D (Review Phase 3): ein Modellfehler — dieselbe Blase wie im Muster-Weg,
        # mit Fehlernummer. Ein Lauf, der nur ohne Text endete, behält den Ersatzsatz.
        logger.info("Agent-Modus: Lauf mit Fehler — Ersatzsatz mit Fehlernummer")
        return bot_text(sprache, "error.answerFailed", nummer=fehlernummer())
    schluessel = "agent.incomplete" if lauf.stop_reason in GEDECKELT else "agent.failed"
    logger.info("Agent-Modus: Lauf ohne Text (Ende=%s) — Ersatzsatz %s",
                lauf.stop_reason, schluessel)
    return bot_text(sprache, schluessel)


ABSCHLUSS_BITTE = (
    "Schreibe jetzt deine Antwort fuer die Person im Chat — ohne weitere "
    "Werkzeug-Aufrufe. Sie hat weder dein Ergebnis noch deine Zwischenschritte "
    "gesehen: sag ihr vollstaendig, was du herausgefunden hast. " + SPRACHE_DER_PERSON
)


async def abschluss_nachholen(
    lauf: AgentRun, messages: list[dict], usage_acc: dict | None,
) -> str:
    """EIN Abschluss-Aufruf, wenn ein Deckel die Antwort verschluckt hat.

    Seit J1 ist die Prosa ein eigener Zug — und damit deckelbar. Live gemessen
    am selben Tag (Hybrid, Sammlung „Optik"): das Ergebnis kam vollstaendig, der
    Lauf riss danach das Token-Budget, und im Chat standen 22 Zeichen. Vorher
    konnte das nicht passieren, weil ``submit_result`` den Text mittrug.

    Die Deckel sind gegen weglaufende **Arbeit** gebaut, nicht gegen die
    Antwort. Genau diese Unterscheidung trifft der Bestandsweg seit P16
    (``tool_loop_fallback``), und dies ist dieselbe Naht: ein Aufruf, keine
    Werkzeuge, eigene Phase in der Kostenschau — ihr Auftauchen meldet den
    gerissenen Deckel und soll in der normalen Antwort nicht untergehen.

    Scheitert er, gibt es ``""`` zurueck: dann greift der ehrliche Ersatzsatz.
    """
    try:
        antwort = await llm.chat_completion(
            messages=[*messages, {"role": "user", "content": ABSCHLUSS_BITTE}],
            temperature=0.4, usage_acc=usage_acc, phase="fallback_summary")
        text = (antwort.choices[0].message.content or "").strip()
    except Exception as e:                       # pragma: no cover - Transportfehler
        logger.warning("Agent-Modus: Abschluss-Aufruf fehlgeschlagen — %s", e)
        return ""
    logger.info("Agent-Modus: Antwort nach Deckel %s nachgeholt (%d Zeichen)",
                lauf.stop_reason, len(text))
    return text
