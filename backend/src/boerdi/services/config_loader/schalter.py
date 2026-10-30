"""Schalter aus gespeicherter Konfiguration lesen — mit der Regel des Gates (Paket 18E, N1).

Das Gate prüft einen Bereich mit seinem Pydantic-Modell im Lax-Modus, speichert aber das
Rohdokument (``api/config_guards.modell_fehler``). ``messages: "false"`` — im Rohtext-Editor
gequotet — passiert es, weil Pydantic ``"false"`` als ``False`` liest; ``bool("false")`` ist
dagegen ``True``. Die Lader lasen bis 18E mit ``bool(…)`` und schalteten so ein, was „aus“ war.
Hier gilt dieselbe Regel wie im Gate: ``TypeAdapter(bool)``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from pydantic import TypeAdapter, ValidationError

from boerdi.obs.drossel import gedrosselt

logger = logging.getLogger(__name__)

_BOOL = TypeAdapter(bool)

#: Für ``.get(name, FEHLT)``: der Schlüssel fehlt — anders als ein gespeichertes ``null``.
FEHLT: Any = object()


def als_schalter(wert: Any, vorgabe: bool, *, name: str, streng: bool = False) -> bool:
    """``wert`` als Schalter, wie das Gate ihn liest; :data:`FEHLT` → ``vorgabe``, ebenso
    ``None`` — außer bei ``streng``: dort ist ein gespeichertes ``null`` unbrauchbar (Review
    18E-1: ``bool(None)`` war „aus“, die Vorgabe wäre „an“).

    Ein unbrauchbarer Wert (gibt es nur in Altbestand oder nach einer Änderung an der
    Datenbank vorbei) ergibt ``vorgabe`` und eine Warnung je Schalter und Prozess — mit dem
    Typ, nicht dem Wert. ``streng`` wirft stattdessen ``ValueError``: für Schalter, bei denen
    die Vorgabe die falsche Richtung wäre (Datenschutz, siehe ``safety.load_privacy_config``).
    """
    if wert is FEHLT or (wert is None and not streng):
        return vorgabe
    try:
        return _BOOL.validate_python(wert)
    except ValidationError:
        if streng:
            raise ValueError(f"{name}: kein Schalterwert ({type(wert).__name__})") from None
        gedrosselt(logger, logging.WARNING, f"schalter:{name}", math.inf,
                   "Konfiguration %s ist kein Schalterwert (%s) — es gilt die Vorgabe %s",
                   name, type(wert).__name__, vorgabe)
        return vorgabe
