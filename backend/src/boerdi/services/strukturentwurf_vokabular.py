"""Fach und Bildungsstufe eines Entwurfs auf das WLO-Vokabular abbilden (Anschluss N2 → N3, Plan
2026-11-19).

Die Prüfer des Entwurfs (``ui_module/strukturentwurf.fach``/``bildungsstufe``) sind rein und
synchron; das Vokabular (``mcp/vokabular_labels``) ist async. Darum gleicht der Dienst den fertigen
Entwurf hier an — Wurzel und jeden Punkt:

- **Treffer** (nur genau oder über einen Alias, ``fach_geprueft``/``stufe_geprueft``; unscharfe
  Treffer zählen fürs Schreiben nicht) → das Label des Vokabulars („Erdkunde“ → „Geografie“). Eine
  Stufe nur, wenn das Label eine der Bildungsstufen des Entwurfs ist (das Schema kennt nur diese).
- **Kein Treffer → leer, mit Hinweis** („Fach „Wirtschaft“ ist nicht im WLO-Vokabular – deshalb
  leer.“; N1/N2-Review, Befund 3). Das Schema des Entwurfs hat kein Hinweisfeld; der Dienst hängt
  die Hinweise an den Text an die KI, die sie der Person nennt. So hält es auch die Vorbelegung
  (N2: nur ein Treffer belegt vor), und ein unbekanntes Fach reiste ohnehin nicht zum MCP mit
  (``werkzeuge._baum_aus_entwurf``, SW-2).
- Ein Punkt mit demselben Wert wie die Wurzel verliert ihn (Regel von ``knoten_aus``).
- **Ohne Vokabular** gelten die Prüfer des Entwurfs — die Werte sind schon geprüft, es ändert sich
  nichts, und es gibt keinen Hinweis.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass, field
from typing import Any, Final

from boerdi.services.mcp import vokabular_labels
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module.rahmen import name_fuer_ki

logger = logging.getLogger(__name__)

_FELDER: Final = ("fach", "bildungsstufe")
_NAME: Final = {"fach": "Fach", "bildungsstufe": "Bildungsstufe"}
_HINWEIS: Final = "{name} „{wert}“ ist nicht im WLO-Vokabular – deshalb leer."


@dataclass(frozen=True, slots=True)
class Angeglichen:
    daten: dict[str, Any]
    #: Je verworfenem Wert ein Satz für die Person (über die KI), ohne Doppel.
    hinweise: list[str] = field(default_factory=list)


async def angleichen(daten: dict[str, Any]) -> Angeglichen:
    """Eine Kopie von ``daten`` mit Fach und Stufe aus dem Vokabular (oder ohne sie) und die
    Hinweise zu verworfenen Werten."""
    neu = copy.deepcopy(daten)
    gemerkt: dict[tuple[str, str], str | None] = {}
    hinweise: list[str] = []

    def verworfen(feld: str, wert: str) -> None:
        satz = _HINWEIS.format(name=_NAME[feld], wert=name_fuer_ki(wert, 60))
        if satz not in hinweise:
            hinweise.append(satz)

    async def label(feld: str, wert: Any) -> str | None:
        if not isinstance(wert, str):
            return None
        if (feld, wert) in gemerkt:
            return gemerkt[(feld, wert)]
        pruefen = (vokabular_labels.fach_geprueft if feld == "fach"
                   else vokabular_labels.stufe_geprueft)
        abbildung = await pruefen(wert)
        ergebnis = se.fach(abbildung.label) if feld == "fach" else abbildung.label
        if feld == "bildungsstufe" and ergebnis is not None and ergebnis not in se.BILDUNGSSTUFEN:
            # Review N3, MINOR 7: nie still — ein Label, das der Entwurf nicht kennt
            logger.info("Entwurf: Stufe %r aus dem Vokabular unbekannt, verworfen", ergebnis[:60])
            verworfen(feld, ergebnis)
            ergebnis = None
        elif abbildung.verworfen:
            verworfen(feld, abbildung.verworfen)
        gemerkt[(feld, wert)] = ergebnis
        return ergebnis

    for feld in _FELDER:
        if feld in neu:
            if wert := await label(feld, neu[feld]):
                neu[feld] = wert
            else:
                neu.pop(feld)
    for k, _ in se.alle(neu.get("knoten") or []):
        for feld in _FELDER:
            if feld in k:
                wert = await label(feld, k[feld])
                if wert and wert != neu.get(feld):
                    k[feld] = wert
                else:
                    k.pop(feld)
    return Angeglichen(neu, hinweise)
