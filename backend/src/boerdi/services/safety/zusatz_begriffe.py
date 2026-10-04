"""Zusätzliche Krisen- und PII-Begriffe aus dem Studio (Paket 4, D8).

``01-base/safety-config`` führte ``extra_crisis_terms`` und ``extra_pii_terms``,
aber nichts las sie — auch ALT nicht (externes Audit F15). Das Regex-Gate prüft
sie jetzt nach seinen eigenen Listen:

- als Begriff ab Wortanfang (``(?<!\\w)``): „klinge" trifft „klingenscharf",
  nicht „verklingen";
- normalisiert wie die Nachricht, danach ``re.escape`` — ein Begriff ist Text,
  kein Muster;
- leere Einträge zählen nicht: eine leere Alternative träfe jede Nachricht.

Übersetzt wird einmal je Stand der Listen, wie bei den Lotsen-Regeln: ändert das
Studio sie, gilt das ab dem nächsten Zug, ohne Neustart. Länge und Anzahl deckelt
das Bereichsmodell (``SafetyConfigArea``).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)

_Muster = re.Pattern[str] | None

#: Der Stand der Listen, aus dem ``_MUSTER`` übersetzt ist.
_QUELLE: tuple[tuple[str, ...], tuple[str, ...]] | None = None
_MUSTER: tuple[_Muster, _Muster] = (None, None)


def _begriffe(roh: object, normalisiere: Callable[[str], str]) -> tuple[str, ...]:
    """Die gepflegten Begriffe, normalisiert, ohne leere und doppelte."""
    out: list[str] = []
    for eintrag in roh if isinstance(roh, list) else []:
        if not isinstance(eintrag, str):
            continue
        begriff = normalisiere(eintrag).strip()
        if begriff and begriff not in out:
            out.append(begriff)
    return tuple(out)


def _als_muster(begriffe: tuple[str, ...]) -> _Muster:
    if not begriffe:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(b) for b in begriffe) + ")")


def zusatz_muster(normalisiere: Callable[[str], str]) -> tuple[_Muster, _Muster]:
    """``(Krise, PII)`` — je ein übersetztes Muster, ``None`` ohne Begriffe.

    ``normalisiere`` ist die Normalisierung der Nachricht; das Gate reicht sie
    herein, damit Begriff und Nachricht auf dieselbe Weise gelesen werden.
    """
    global _QUELLE, _MUSTER
    from boerdi.services import config_loader

    try:
        cfg = config_loader.load_safety_config() or {}
    except Exception as e:  # das Gate darf an seiner Zusatz-Config nie scheitern
        logger.warning("safety: zusätzliche Begriffe nicht geladen (%s)", e)
        return None, None
    quelle = (
        _begriffe(cfg.get("extra_crisis_terms"), normalisiere),
        _begriffe(cfg.get("extra_pii_terms"), normalisiere),
    )
    if quelle != _QUELLE:
        _QUELLE = quelle
        _MUSTER = (_als_muster(quelle[0]), _als_muster(quelle[1]))
    return _MUSTER
