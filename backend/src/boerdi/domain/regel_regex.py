"""Regex aus dem Studio, angewandt auf Chat-Nachrichten — mit Zeitgrenze.

Zwei Bereiche tragen Muster, die das Studio pflegt und die jede Nachricht eines
beliebigen Clients durchläuft: die Lotsen-Regeln (``02-domain/guide-rules``,
``message_rules[].pattern``) und die Policy-Regeln (``01-base/policy``,
``match.message_regex``). Mit ``re`` lief ein ungünstiges Muster wie
``^(\\w+\\s?)*$`` exponentiell und hielt den Worker fest (Review Paket 4,
2026-10-04; Paket 6, B1).

Der Motor ist ``regex`` (Apache-2.0 AND CNRI-Python): weitgehend ``re``-gleich,
dazu eine Zeitgrenze je Suche. Läuft sie ab, gilt das Muster für diese Nachricht
als nicht getroffen. Speichern und Laufzeit übersetzen mit demselben Motor —
sonst hieße „gespeichert“ nicht „greift“.
"""

from __future__ import annotations

import logging

import regex

logger = logging.getLogger(__name__)

#: Ein ungültiges Muster — für ``except`` beim Speichern und Übersetzen.
RegexFehler = regex.error

#: Höchstdauer einer Suche in Sekunden. Gewöhnliche Regeln brauchen Mikrosekunden;
#: die Grenze trifft nur Muster, die zurückspringen, bis der Worker steht.
FRIST_S = 0.05


def uebersetze(muster: str, *, ignore_case: bool = True) -> regex.Pattern:
    """``muster`` übersetzen; ein ungültiges wirft :data:`RegexFehler`."""
    return regex.compile(muster, regex.IGNORECASE if ignore_case else 0)


def trifft(muster: regex.Pattern, text: str) -> bool:
    """Trifft ``muster`` irgendwo in ``text``? Nach :data:`FRIST_S` gilt: nein.

    Das Log nennt das Muster, nie den Text — der stammt von der Person.
    """
    try:
        return muster.search(text, timeout=FRIST_S) is not None
    except TimeoutError:
        logger.warning("Regel-Regex %r: Zeitgrenze von %g s erreicht, gilt als kein Treffer",
                       muster.pattern, FRIST_S)
        return False
