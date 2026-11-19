"""Zuordnung Datei → Punkt im Entwurf ``aus_inhalten`` (Paket N3, Plan 2026-11-19).

Der Entwurf aus den Materialien der Person (``metadaten.als_dokument``) nennt je oberem Punkt die
Kennungen ``aN`` der Materialien, die das Modell ihm zuordnet (``abschnitte``). Hier werden daraus
Verweise im Format des Ordner-Wegs (TG-3f, ``strukturentwurf_ordner``): ``inhalte: [{i, name,
node_id?}]`` je Punkt.

- **node_id geht vor:** trägt das Material eine (Teil ``metadaten`` aus ``metadaten_lesen``) oder
  kennt die Ablage derselben Auswahl eine zu seiner ``i`` (``node_ids``), steht sie im Eintrag —
  so ist der Inhalt in edu-sharing wiederzufinden. Sonst trägt er die feste Nummer ``i`` der
  Auswahl (Chat-Weg, nur Namen). Der Name ist immer der Titel des Materials.
- **Nachziehen über Einbettungen:** Materialien, die das Modell keinem Punkt gibt (oder nur mit
  unbekannter Kennung), gehen an den ähnlichsten oberen Punkt — Material: Titel, Beschreibung,
  Schlagworte; Punkt: Titel, Beschreibung, Titel der Unterpunkte. Nur ab der gemessenen Schwelle
  des Modells (``strukturentwurf_naehe``); darunter stehen sie in ``nicht_zugeordnet`` (Wurzel des
  Entwurfs). Ein Aufruf für alle Texte, in der Frist des Dienstes; fällt er aus, bleibt es ohne
  Nachziehen — kein Fehler.
- Ein Eintrag ohne feste Nummer ``i`` (Stapel vor TG-3b) fällt weg: das Format verlangt ``i``, und
  beim Speichern verknüpft der Server node_ids nur über ``i`` (``arbeitsstand``).

Rein bis auf die Einbettungs-Naht ``einbetten`` (Texte → Vektoren).
"""

from __future__ import annotations

import copy
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Final

from boerdi.services.ablauf import metadaten
from boerdi.services.strukturentwurf_naehe import (  # noqa: F401 — Naht und Werte auch von hier
    MINDEST_REST_S,
    PHASE,
    SCHWELLEN,
    Einbetten,
    einbetten_mit,
    kosinus,
    naechste,
    schwelle,
)
from boerdi.ui_module import strukturentwurf as se

_NODE: Final = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                          r"[0-9a-fA-F]{12}$")
_QUELLE_BLOCK: Final = re.compile(r"^[a-z0-9]{8,32}$")
_SCHLAGWORTE: Final = 10


@dataclass(frozen=True, slots=True)
class Material:
    kennung: str
    eintrag: dict[str, Any]
    text: str


@dataclass(frozen=True, slots=True)
class Zuordnung:
    """Der Entwurf mit ``inhalte`` und die Zahlen: vom Modell, von der Einbettung zugeordnet,
    übrig (``nicht_zugeordnet``)."""

    daten: dict[str, Any]
    modell: int = 0
    einbettung: int = 0
    uebrig: int = 0


def _zeile(wert: Any) -> str:
    return " ".join(str(wert or "").split())


def _nummer(e: dict[str, Any]) -> int | None:
    i = e.get("i")
    return i if isinstance(i, int) and not isinstance(i, bool) and 0 <= i <= 4999 else None


def _node_id(wert: Any) -> str | None:
    return wert if isinstance(wert, str) and _NODE.match(wert) else None


def metadaten_ids(teil: Any) -> dict[int, str]:
    """``i`` → node_id aus dem Teil ``metadaten`` (nach ``metadaten_lesen``; ein lokaler Teil trägt
    keine) — nur gültige Nummern und Kennungen."""
    return {i: k for e in metadaten.materialien(teil) or []
            if (i := _nummer(e)) is not None and (k := _node_id(e.get("node_id")))}


def materialien(teil: Any, node_ids: dict[int, str] | None = None) -> list[Material]:
    """Die Materialien mit fester Nummer, mit Kennung ``aN`` wie in ``metadaten.als_dokument``."""
    aus: list[Material] = []
    for n, e in enumerate(metadaten.materialien(teil) or [], 1):
        if (i := _nummer(e)) is None:
            continue
        titel = _zeile(e.get("titel"))[:se.TITEL_ZEICHEN] or f"Material {n}"
        eintrag: dict[str, Any] = {"i": i, "name": titel}
        if node_id := _node_id(e.get("node_id")) or (node_ids or {}).get(i):
            eintrag["node_id"] = node_id
        schlagworte = [_zeile(w) for w in e.get("schlagworte") or [] if isinstance(w, str)]
        zeilen = [titel, _zeile(e.get("beschreibung"))]
        if schlagworte := [w for w in schlagworte if w][:_SCHLAGWORTE]:
            zeilen.append("Schlagworte: " + ", ".join(schlagworte))
        aus.append(Material(f"a{n}", eintrag, "\n".join(z for z in zeilen if z)))
    return aus


def punkt_text(knoten: dict[str, Any]) -> str:
    """Titel, Beschreibung und die Titel der Unterpunkte — der Text eines Punkts."""
    zeilen = [_zeile(knoten.get("titel")), _zeile(knoten.get("beschreibung"))]
    unter = [_zeile(k.get("titel")) for k, _ in se.alle(knoten.get("kinder") or [])]
    if unter := [u for u in unter if u]:
        zeilen.append("Unterpunkte: " + ", ".join(unter))
    return "\n".join(z for z in zeilen if z)


async def zuordnen(daten: dict[str, Any], teil: Any, *, einbetten: Einbetten | None = None,
                   node_ids: dict[int, str] | None = None, frist_ende: float | None = None,
                   modell: str | None = None) -> Zuordnung:
    """Eine Kopie von ``daten`` mit ``inhalte`` je oberem Punkt und ``nicht_zugeordnet`` — aus
    den ``abschnitte`` des Modells, nachgezogen über ``einbetten`` (bis ``frist_ende``, eine
    Zeit der Ereignisschleife). ``node_ids``: ``i`` → node_id der Ablage derselben Auswahl
    (``strukturentwurf_ordner.knoten_ids``). ``modell``: das Einbettungsmodell (Vorgabe: das
    eingestellte) — es bestimmt die Schwelle."""
    neu = copy.deepcopy(daten)
    if isinstance(block := teil.get("block_id") if isinstance(teil, dict) else None, str) \
            and _QUELLE_BLOCK.match(block):
        neu["quelle_block"] = block
    mats = materialien(teil, node_ids)
    oben = [k for k in neu.get("knoten") or [] if isinstance(k, dict)]
    if not mats or not oben:
        return Zuordnung(neu)
    je_kennung = {m.kennung: m for m in mats}
    je_punkt: list[list[Material]] = []
    for k in oben:
        ids = k.get("abschnitte") if isinstance(k.get("abschnitte"), list) else []
        je_punkt.append([je_kennung[i] for i in dict.fromkeys(ids) if i in je_kennung])
    vom_modell = {m.kennung for liste in je_punkt for m in liste}
    offen = [m for m in mats if m.kennung not in vom_modell]
    if modell is None and offen and einbetten is not None:
        from boerdi.services.llm_models import get_embed_model

        modell = get_embed_model()
    stellen = await naechste([punkt_text(k) for k in oben], [m.text for m in offen], einbetten,
                             modell=modell or "", frist_ende=frist_ende) or [None] * len(offen)
    uebrig: list[Material] = []
    for m, stelle in zip(offen, stellen, strict=True):
        if stelle is None:
            uebrig.append(m)
        else:
            je_punkt[stelle].append(m)
    _eintragen(neu, oben, je_punkt, uebrig)
    return Zuordnung(neu, len(vom_modell), len(offen) - len(uebrig), len(uebrig))


async def node_ids_der_auswahl(teil: Any, teile: Callable[[str], Awaitable[Any]] | None
                               ) -> dict[int, str]:
    """``i`` → node_id aus dem Teil ``ablage`` — nur, wenn Auswahl (``struktur``), Ablage und der
    Teil ``metadaten`` zum selben Upload-Feld gehören (wie ``werkzeuge._ordner_als_entwurf``)."""
    from boerdi.services.arbeitsstand_teile import gebunden
    from boerdi.ui_module.strukturentwurf_ordner import knoten_ids

    block = teil.get("block_id") if isinstance(teil, dict) else None
    if teile is None or not isinstance(block, str) or not block:
        return {}
    struktur, ablage = await teile("struktur"), await teile("ablage")
    if not gebunden(struktur, ablage) or struktur.get("block_id") != block:
        return {}
    return knoten_ids(ablage)


def _eintragen(neu: dict[str, Any], oben: list[dict[str, Any]],
               je_punkt: list[list[Material]], uebrig: list[Material]) -> None:
    """Die Verweise an Punkte und Wurzel — bis zur Grenze des Entwurfs (``gekuerzt``)."""
    platz = se.HOECHSTENS_INHALTE

    def nimm(liste: list[Material]) -> list[dict[str, Any]]:
        nonlocal platz
        if len(liste) > platz:
            neu["gekuerzt"] = True
        genommen = [dict(m.eintrag) for m in liste[:max(platz, 0)]]
        platz -= len(genommen)
        return genommen

    for k, liste in zip(oben, je_punkt, strict=True):
        if inhalte := nimm(liste):
            k["inhalte"] = inhalte
    if rest := nimm(uebrig):
        neu["nicht_zugeordnet"] = rest
