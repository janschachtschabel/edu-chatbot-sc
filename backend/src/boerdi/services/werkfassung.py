"""Werksfassung und eigene Fassung eines Konfigurationsbereichs (Paket 12) — rein, ohne I/O.

Die Werksfassung ist der Seed im Image (``CONFIG_SEED_DIR``), die gelebte Fassung steht in
``config_areas``. Je Bereich merkt sich die Datenbank in ``werk_hash``, auf welcher Werksfassung er
zuletzt stand. Daraus folgt der Status — berechnet, nie gespeichert:

=================== ==========================================================================
``werk``             gleicht der aktuellen Werksfassung
``werk-veraltet``    gleicht der Werksfassung, auf der er stand; die ist inzwischen neuer —
                     unberührt, der Werksabgleich hebt ihn an
``eigen``            angepasst, beruht auf der aktuellen Werksfassung
``eigen-neues-werk`` angepasst, die Werksfassung hat sich seither geändert (oder die Basis ist
                     unbekannt: Bestand vor Paket 12)
``nur-eigen``        kein Werksbereich (im Studio angelegt)
``werk-entfernt``    Werksbereich, im Studio gelöscht
``werk-fehlt``       Werksbereich, nie angelegt
=================== ==========================================================================

Die sichere Richtung: unberührt ist ein Bereich nur, wenn sein Inhalt genau der gemerkten
Werksfassung gleicht. Was sich nicht sicher zuordnen lässt, gilt als eigen und wird nie
überschrieben.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Final

WERK: Final = "werk"
WERK_VERALTET: Final = "werk-veraltet"
EIGEN: Final = "eigen"
EIGEN_NEUES_WERK: Final = "eigen-neues-werk"
NUR_EIGEN: Final = "nur-eigen"
WERK_ENTFERNT: Final = "werk-entfernt"
WERK_FEHLT: Final = "werk-fehlt"

#: ``updated_by`` der Wege, die die Werksfassung schreiben. Steht er an einem Bereich ohne gemerkte
#: Basis (Bestand vor Paket 12), ist dessen Inhalt seit dem Import nachweislich unberührt.
AUS_DEM_WERK: Final = frozenset({"import", "seed-apply", "seed-apply-cli", "werksabgleich"})


def pruefsumme(data: Any) -> str:
    """SHA-256 über kanonisches JSON — unabhängig von der Schlüssel-Reihenfolge."""
    kanonisch = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def status(
    *, data: dict[str, Any] | None, werk_hash: str | None, werk: dict[str, Any] | None,
    entfernt: bool, updated_by: str = "",
) -> str:
    """Der Status eines Bereichs (siehe Modulkopf). ``data`` ist die gelebte Fassung oder ``None``,
    ``werk`` die aktuelle Werksfassung oder ``None``, ``updated_by`` der letzte Schreiber."""
    if data is None:
        return WERK_ENTFERNT if entfernt else WERK_FEHLT
    if werk is None:
        return NUR_EIGEN
    if data == werk:
        return WERK
    aktuell = pruefsumme(werk)
    if werk_hash is not None and werk_hash != aktuell and pruefsumme(data) == werk_hash:
        return WERK_VERALTET
    if werk_hash is None and updated_by in AUS_DEM_WERK:
        return WERK_VERALTET
    return EIGEN if werk_hash == aktuell else EIGEN_NEUES_WERK


@dataclass
class WerksabgleichPlan:
    """Was ein Werksabgleich tut. ``schreiben``: Bereich → Werksfassung (fehlend oder unberührt
    veraltet); ``zuordnen``: Bereich → Prüfsumme (gleicht schon, Basis wird nur gemerkt);
    ``neues_werk``: angepasste Bereiche mit neuer Werksfassung — bleiben, das Studio zeigt sie."""

    schreiben: dict[str, dict[str, Any]] = field(default_factory=dict)
    #: Die beim Lesen gesehene Version je zu schreibendem Bereich (``None``: fehlte) — das
    #: Schreiben ist darauf bedingt (Review #2).
    versionen: dict[str, int | None] = field(default_factory=dict)
    #: Alter Inhalt, der beim Anheben stillgelegt wird: nur, wenn allein die Import-Kennung den
    #: Bereich als unberührt ausweist (keine Basis) — es kann ein eigener Baum gewesen sein
    #: (Review 2 #4). Die Anhebung bleibt so im Studio umkehrbar.
    parken: dict[str, dict[str, Any]] = field(default_factory=dict)
    zuordnen: dict[str, str] = field(default_factory=dict)
    neues_werk: list[str] = field(default_factory=list)
    neu: int = 0

    def bericht(self) -> dict[str, int]:
        return {"neu": self.neu, "aktualisiert": len(self.schreiben) - self.neu,
                "zugeordnet": len(self.zuordnen), "neues_werk": len(self.neues_werk)}


def plane_werksabgleich(
    seed: dict[str, dict[str, Any]], zeilen: dict[str, dict[str, Any]], *, entfernt: set[str],
) -> WerksabgleichPlan:
    """Fehlende Werksbereiche anlegen (außer im Studio gelöschten), unberührte veraltete anheben,
    gleichende zuordnen — angepasste nie anfassen. ``zeilen``: Bereich → ``{data, werk_hash,
    updated_by, version}`` aus der Datenbank."""
    plan = WerksabgleichPlan()
    for area in sorted(seed):
        werk = seed[area]
        zeile = zeilen.get(area)
        if zeile is None:
            if area not in entfernt:
                plan.schreiben[area] = werk
                plan.versionen[area] = None
                plan.neu += 1
            continue
        stand = status(data=zeile["data"], werk_hash=zeile.get("werk_hash"), werk=werk,
                       entfernt=False, updated_by=zeile.get("updated_by") or "")
        if stand == WERK_VERALTET:
            plan.schreiben[area] = werk
            plan.versionen[area] = zeile.get("version")
            if zeile.get("werk_hash") is None:
                plan.parken[area] = zeile["data"]
        elif stand == WERK and zeile.get("werk_hash") != pruefsumme(werk):
            plan.zuordnen[area] = pruefsumme(werk)
        elif stand == EIGEN_NEUES_WERK:
            plan.neues_werk.append(area)
    return plan


@dataclass(frozen=True)
class Fassung:
    """Was zu einem Bereich gespeichert ist: gelebter Inhalt und seine Basis, dazu die
    stillgelegte eigene Fassung und deren Basis (``eigene_basis``)."""

    data: dict[str, Any] | None
    werk_hash: str | None
    eigene: dict[str, Any] | None
    eigene_basis: str | None


class UmschaltEinwand(Exception):
    """Umschalten geht nicht — ``meldung`` ist der Schlüssel des Textes (``i18n``)."""

    def __init__(self, meldung: str) -> None:
        super().__init__(meldung)
        self.meldung = meldung


def umschalten(ziel: str, vorher: Fassung, *, werk: dict[str, Any] | None) -> Fassung:
    """Der Stand nach dem Umschalten — so, dass nie eine Fassung verloren geht (Review #1/#8).

    ``werk``: die gelebte Fassung wird stillgelegt, außer sie ist selbst Werksinhalt (aktuell oder
    veraltet). Läge dann schon eine andere eigene Fassung still, ginge eine verloren →
    ``fassung.zweiEigene``. Ein gelöschter Bereich (``data is None``) kommt einfach zurück.
    ``eigen``: tauscht — die stillgelegte wird gelebt, eine abweichende gelebte wird stillgelegt.
    ``geprueft``: nur die Basis wird die aktuelle Werksfassung (eigene Fassung bleibt gelebt).
    Jede Fassung reist mit ihrer Basis, damit „neue Werksfassung verfügbar“ erhalten bleibt.
    """
    if ziel == "werk":
        if werk is None:
            raise UmschaltEinwand("fassung.keinWerk")
        if vorher.data is None:
            return Fassung(werk, pruefsumme(werk), vorher.eigene, vorher.eigene_basis)
        stand = status(data=vorher.data, werk_hash=vorher.werk_hash, werk=werk, entfernt=False)
        if stand in (WERK, WERK_VERALTET):
            return Fassung(werk, pruefsumme(werk), vorher.eigene, vorher.eigene_basis)
        if vorher.eigene is not None and vorher.eigene != vorher.data:
            raise UmschaltEinwand("fassung.zweiEigene")
        return Fassung(werk, pruefsumme(werk), vorher.data, vorher.werk_hash)
    if ziel == "geprueft":
        # Review 2 #5: die eigene Fassung bleibt, die aktuelle Werksfassung gilt als gesehen —
        # sonst stünde Bestand ohne Basis für immer auf „neue Werksfassung verfügbar“.
        if werk is None or vorher.data is None or status(
                data=vorher.data, werk_hash=vorher.werk_hash, werk=werk,
                entfernt=False) != EIGEN_NEUES_WERK:
            raise UmschaltEinwand("fassung.nichtsZuPruefen")
        return Fassung(vorher.data, pruefsumme(werk), vorher.eigene, vorher.eigene_basis)
    if vorher.data is None or vorher.eigene is None:
        raise UmschaltEinwand("fassung.keineEigene")
    stand = status(data=vorher.data, werk_hash=vorher.werk_hash, werk=werk, entfernt=False)
    if stand in (WERK, WERK_VERALTET):
        return Fassung(vorher.eigene, vorher.eigene_basis, None, None)
    return Fassung(vorher.eigene, vorher.eigene_basis, vorher.data, vorher.werk_hash)
