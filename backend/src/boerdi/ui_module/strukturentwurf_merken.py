"""Der letzte Strukturentwurf der Sitzung (Paket U2, drittes Review, Befund 2).

Ein Entwurf ist abfragend: nach „Übernehmen“ oder einer getippten Nachricht ist sein Block nur
lesend, und Blöcke stehen nicht im Verlauf, den die KI liest. Damit „ja, vertiefe X“ im nächsten
Zug noch einen Gegenstand hat, merkt sich die Sitzung den letzten Entwurf in
``entities[KEY]`` — nur, was schon durch die Sicherheitsprüfung ging:

- **Woher:** die geprüfte Antwort der Person (:func:`aus_antwort`) oder ein Block, den der Dienst
  in diesem Zug erzeugt hat (:func:`aus_bloecken`). Beides rufen die Antwort-Knoten, also nach
  ``assess``. Die Brücke aus dem Bestand (``services/strukturentwurf_aktion``) schreibt nichts
  (Bestandsknoten erreichen die KI erst, wenn die Person den Entwurf zurückschickt) und vergisst
  einen älteren gemerkten Entwurf.
- **Wie groß:** höchstens :data:`HOECHSTENS_ZEICHEN` als JSON; sonst ohne Beschreibungen und
  Schlagworte (die gehen ohnehin an kein Modell) und mit der Marke :data:`OHNE_TEXTE` — so
  gemerkt taugt er zum Vertiefen, aber nicht zum unveränderten Wiederzeigen (``erneut_zeigen``
  lehnt ab, statt die Texte der Person still zu verlieren).
- **Wie lange:** die :data:`ZUEGE` Züge nach dem, der ihn merkt (:func:`rahmen_fuer_zug` zählt
  herunter; der Zug mit der Antwort selbst zählt nicht, dort steht [ENTWURF DER PERSON]); ein
  neuer Entwurf ersetzt ihn. Die Sitzung unterliegt der Aufbewahrung wie jeder Gesprächsstand.

Rein und ohne I/O; gespeichert wird ``entities`` mit dem übrigen Stand des Zugs.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Final

from boerdi.api.schemas_ui import UiBlock
from boerdi.domain.endmarken import entschaerfe_endmarken
from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_text as st
from boerdi.ui_module.namen import STRUKTURENTWURF

KEY: Final = "_letzter_entwurf"
ZUEGE: Final = 5
HOECHSTENS_ZEICHEN: Final = 60_000
OHNE_TEXTE: Final = "_ohne_texte"
_FELDER: Final = ("titel", "quelle", "thema", "fach", "bildungsstufe", "wurzel_wlo_id",
                  "gekuerzt", "knoten")
RAHMEN_START: Final = (
    "[DEIN LETZTER ENTWURF — so stand die Gliederung zuletzt (Titel und Einrückung). Mit "
    "vorlage: true nimmst du ihn als Grundlage (vertiefen), mit vorlage und erneut_zeigen: true "
    "zeigst du ihn unverändert wieder zum Bearbeiten.]")
RAHMEN_ENDE: Final = "[ENDE ENTWURF]"


def _ohne_texte(knoten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aus = []
    for k in knoten:
        neu = {f: w for f, w in k.items() if f not in ("beschreibung", "keywords", "kinder")}
        if k.get("kinder"):
            neu["kinder"] = _ohne_texte(k["kinder"])
        aus.append(neu)
    return aus


def _merken(entities: dict[str, Any], daten: dict[str, Any]) -> None:
    gemerkt = {f: copy.deepcopy(daten[f]) for f in _FELDER if f in daten}
    if len(json.dumps(gemerkt, ensure_ascii=False)) > HOECHSTENS_ZEICHEN:
        gemerkt["knoten"] = _ohne_texte(gemerkt.get("knoten") or [])
        gemerkt[OHNE_TEXTE] = True
    entities[KEY] = {"daten": gemerkt, "zuege": ZUEGE}


def aus_antwort(entities: dict[str, Any], geprueft: dict[str, Any] | None) -> None:
    """Die geprüfte Antwort auf einen Entwurf merken (sonst nichts)."""
    if geprueft and geprueft.get("modul") == STRUKTURENTWURF and isinstance(
            geprueft.get("daten"), dict):
        _merken(entities, geprueft["daten"])


def aus_bloecken(entities: dict[str, Any], bloecke: list[UiBlock]) -> None:
    """Einen in diesem Zug erzeugten Entwurf merken — den letzten, falls es mehrere gäbe."""
    for block in reversed(bloecke):
        if block.modul == STRUKTURENTWURF and isinstance(block.daten, dict):
            _merken(entities, block.daten)
            return


def vorlage(entities: dict[str, Any]) -> dict[str, Any] | None:
    gemerkt = entities.get(KEY)
    daten = gemerkt.get("daten") if isinstance(gemerkt, dict) else None
    return daten if isinstance(daten, dict) and isinstance(daten.get("knoten"), list) else None


def rahmen(entities: dict[str, Any]) -> str:
    """Der Rahmen mit dem letzten Entwurf für diesen Zug — und ein Zug weniger. Leer, wenn keiner
    gemerkt ist oder seine Züge um sind (dann wird er vergessen)."""
    daten = vorlage(entities)
    if daten is None:
        entities.pop(KEY, None)
        return ""
    gemerkt = entities[KEY]
    zuege = gemerkt.get("zuege") if isinstance(gemerkt.get("zuege"), int) else 0
    if zuege <= 0:
        entities.pop(KEY, None)
        return ""
    gemerkt["zuege"] = zuege - 1
    inhalt = entschaerfe_endmarken(st.kompakt(se.normalisiert(daten)))
    return "\n".join([RAHMEN_START, inhalt, RAHMEN_ENDE])


def ohne_texte(daten: dict[str, Any] | None) -> bool:
    """Ob ``daten`` ein gekürzt gemerkter Entwurf ist (ohne Beschreibungen und Schlagworte)."""
    return isinstance(daten, dict) and daten.get(OHNE_TEXTE) is True


def rahmen_fuer_zug(entities: dict[str, Any], geprueft: dict[str, Any] | None) -> str:
    """Für die Antwort-Knoten: eine geprüfte Antwort merken; der Rahmen des letzten Entwurfs nur
    in den Folgezügen. Im Zug mit der Antwort steht der Entwurf schon als [ENTWURF DER PERSON]
    da — kein zweiter Rahmen, und der Zug zählt nicht zu den :data:`ZUEGE`."""
    if geprueft and geprueft.get("modul") == STRUKTURENTWURF and isinstance(
            geprueft.get("daten"), dict):
        aus_antwort(entities, geprueft)
        return ""
    return rahmen(entities)
