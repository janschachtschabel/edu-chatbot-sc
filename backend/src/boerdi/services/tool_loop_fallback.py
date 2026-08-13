"""Abschluss-Fallback des Tool-Loops (P16, Port aus ALT ``llm_tool_loop.py``).

Aus ``tool_loop`` herausgelöst: der einzige Pfad, der greift, wenn die Schleife
ihre Iterationsgrenze reisst, ohne fertigen Text zu liefern. Er hat mit dem Lauf
selbst nichts zu tun — er räumt hinter ihm auf — und wird von ``generate``
direkt gerufen, nicht aus der Schleife heraus.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.services import llm

_logger = logging.getLogger(__name__)


async def _max_iterations_fallback(
    messages: list[dict],
    all_cards: list[dict],
    tools_called: list[str],
    outcomes: list,
    usage_acc: dict[str, Any] | None = None,
) -> tuple[str, list[dict], list[str], list]:
    """Abschluss-Fallback (P16) fuer ``generate_response``: der Tool-Loop hat
    max_iterations erreicht, ohne finalen Text zu liefern. Jeder Pfad liefert
    das finale ``(response_text, wlo_cards, tools_called, outcomes)``-Tupel.

    ``usage_acc`` bucht den Zusammenfassungs-Aufruf unter der eigenen Phase
    ``fallback_summary`` (K1f). Eigene Phase statt ``response``, weil ihr
    Auftauchen zugleich meldet, dass dieser Zug die Iterationsgrenze gerissen
    hat — das ist ein Qualitaetssignal, das in der Kostenschau nicht in der
    normalen Antwort untergehen soll. Der Aufruf ist trotz kurzer Ausgabe
    nicht klein: er haengt die GANZE bisherige Nachrichtenkette an.
    """
    # Fallback: if max_iterations reached without final text, generate a
    # short closing summary based on whatever we found.
    if all_cards:
        try:
            summary_resp = await llm.chat_completion(
                messages=messages + [{
                    "role": "user",
                    "content": (
                        "Bitte fasse jetzt KURZ (1–2 Sätze) zusammen, was du gefunden "
                        "hast — ohne weitere Tool-Aufrufe. Sprich den Nutzer direkt an."
                    ),
                }],
                temperature=0.4,
                usage_acc=usage_acc,
                phase="fallback_summary",
            )
            text = strip_reasoning_markers((summary_resp.choices[0].message.content or "").strip())
            if text:
                return text, all_cards, tools_called, outcomes
        except Exception as e:
            _logger.warning("Fallback summary failed: %s", e)
        return (
            f"Ich habe {len(all_cards)} passende Materialien für dich gefunden — "
            "schau sie dir gerne an:",
            all_cards, tools_called, outcomes,
        )
    return "Ich konnte leider keine Antwort generieren.", all_cards, tools_called, outcomes
