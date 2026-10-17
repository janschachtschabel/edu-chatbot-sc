"""Kennungen der Ordner-Dokumente und was beim Löschen geschützt bleibt.

Muster (``03-patterns/``) und Personas (``04-personas/``) tragen ihre Kennung im
Frontmatter; die Laufzeit findet sie darüber, nicht über den Schlüssel. Drei
Wege schreiben oder löschen solche Dokumente: das Studio (``config``,
``config_documents``), das Löschen (``config_documents``) und das
Wiederherstellen (``config_snapshots``).

Bis Paket 9 prüfte nur das Studio die Kennungen, und nur der Lösch-Endpunkt
schützte feste Bereiche und die Sicherheitsmuster. Ein exaktes Wiederherstellen
aus einer Teil-Sicherung löschte M01 und die Sicherheits-Konfiguration — die
Moderation lief danach mit ``mode: off`` —, und eine Sicherung konnte M01
umbenennen oder doppelt anlegen (Review Paket 7, MAJOR 5 und MINOR 32). Die
Regeln stehen deshalb hier, einmal für alle drei Wege.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, NamedTuple

from boerdi.api.config_guards import _single_group_leaf, is_restorable_area_key
from boerdi.services import config_loader as cl
from boerdi.services.config_loader.personas import _persona_slug

#: Krise und Bedrohung: das Regex-Gate erzwingt diese fest
#: (``services/safety/regex_gate.py``), die Moderation ihre Vorgabe.
SICHERHEITS_MUSTER: Final = ("M01", "M02")
#: Buchstaben, Ziffern, ``-`` und ``_``, ohne Leerzeichen: die Laufzeit nimmt das
#: erste Wort einer Kennung (``quick_reply_policy``, ``quality_events``).
KENNUNG: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
SICHERHEIT: Final = "01-base/safety-config"


def schluessel_fuer(group: str, kennung: str) -> str:
    """Wo das Dokument mit dieser Kennung liegt — für Personas dort, wo die
    Laufzeit es sucht."""
    if group == "04-personas":
        return f"{group}/{_persona_slug(kennung)}"
    return f"{group}/{kennung.lower()}"


def gruppe_von(key: str) -> str | None:
    """Die Gruppe eines Ordner-Dokuments — genau ein Blatt darunter, nach der
    Regel von ``config_guards._single_group_leaf`` (kein leeres, kein ``.``)."""
    return key.split("/", 1)[0] if _single_group_leaf(key) else None


def kennung_von(data: object) -> str:
    fm = data.get("frontmatter") if isinstance(data, dict) else None
    return str(fm.get("id") or "").strip() if isinstance(fm, dict) else ""


def sicherheits_kennungen_aus(cfg: object) -> set[str]:
    """Die Kennungen (klein) der Muster, die Krise und Bedrohung erzwingen: fest
    M01/M02, dazu ``crisis_pattern``/``threat_pattern`` der Sicherheits-Konfiguration."""
    werte = cfg if isinstance(cfg, dict) else {}
    namen = {*SICHERHEITS_MUSTER, str(werte.get("crisis_pattern") or ""),
             str(werte.get("threat_pattern") or "")}
    return {n.lower() for n in namen if n}


async def sicherheits_kennungen() -> set[str]:
    """Wie :func:`sicherheits_kennungen_aus` — die Konfiguration aus der Datenbank
    gelesen, nicht aus dem Cache einer Replika."""
    gelesen = await cl.read_area(SICHERHEIT)
    return sicherheits_kennungen_aus(gelesen[0] if gelesen else None)


def ist_fest(key: str) -> bool:
    """Ein fester Bereich der Registry (``01-base/policy`` …): ohne ihn fiele der
    Lader still auf Vorgaben zurück, und der nächste Start legte ihn aus dem Seed
    wieder an — zurücksetzen geht über den Auslieferungsstand."""
    from boerdi.domain.config_models import model_for

    return gruppe_von(key) is None and model_for(key) is not None


def ist_sicherheitsmuster(key: str, data: object, kennungen: set[str]) -> bool:
    return gruppe_von(key) == "03-patterns" and kennung_von(data).lower() in kennungen


def loeschbar(key: str, data: object, kennungen: set[str]) -> bool:
    """Darf ``key`` gelöscht werden — im Studio wie beim exakten Wiederherstellen?

    Muster, Personas und Bereiche ohne Modell (etwa ein Tippfehler aus dem
    Rohtext): ja. Feste Bereiche, Sicherheitsmuster (``kennungen``) und Schlüssel,
    die kein Wiederherstellen schreiben dürfte: nein.
    """
    return (is_restorable_area_key(key) and not ist_fest(key)
            and not ist_sicherheitsmuster(key, data, kennungen))


class Einwand(NamedTuple):
    """Was gegen eine Kennung spricht — ``art`` „vergeben“ oder „ungueltig“."""

    art: str
    meldung: str
    werte: dict[str, str]


def kennungs_einwand(
    neu: Mapping[str, object], bestand: Mapping[str, object], kennungen: set[str],
) -> Einwand | None:
    """Der erste Einwand gegen die Kennungen der Dokumente in ``neu`` — oder ``None``.

    ``bestand`` ist der Stand, auf den geschrieben wird (ohne, was derselbe
    Vorgang löscht); ``neu`` sind die geschriebenen Bereiche. Geprüft wie im
    Editor: die Form, die die Laufzeit liest; bei einer Persona der passende
    Schlüssel; ein Sicherheitsmuster behält seine Kennung (umbenannt fände das
    Erzwingen bei Krise es nicht mehr); eine Kennung je Gruppe, ohne Rücksicht
    auf Groß/Klein. Andere Bereiche und Dokumente ohne Kennung passieren.
    """
    ergebnis = {**bestand, **neu}
    belegt: dict[tuple[str, str], list[str]] = {}
    for key, data in ergebnis.items():
        if (group := gruppe_von(key)) and (kennung := kennung_von(data)):
            belegt.setdefault((group, kennung.lower()), []).append(key)
    for key, data in neu.items():
        group, kennung = gruppe_von(key), kennung_von(data)
        if group is None:
            continue
        # Vor dem Durchlass für Dokumente ohne Kennung (Review Paket 9, MAJOR 5): ein
        # geleertes M01 überspränge der Lader, und das Erzwingen bei Krise fände es
        # nicht mehr.
        bisher = kennung_von(bestand.get(key))
        if (group == "03-patterns" and bisher.lower() in kennungen
                and bisher.lower() != kennung.lower()):
            return Einwand("ungueltig", "documents.idSafety", {"id": bisher})
        if not kennung:
            continue
        if not KENNUNG.fullmatch(kennung):
            return Einwand("ungueltig", "documents.idInvalid", {"id": kennung})
        if group == "04-personas" and schluessel_fuer(group, kennung) != key:
            return Einwand("ungueltig", "documents.personaKey", {
                "id": kennung, "area": key, "expected": schluessel_fuer(group, kennung)})
        andere = [k for k in belegt[(group, kennung.lower())] if k != key]
        if andere:
            return Einwand("vergeben", "documents.idTaken", {
                "id": kennung, "other": kennung_von(ergebnis[andere[0]]), "area": andere[0]})
    return None


def kennungs_kollisionen(
    neu: Mapping[str, object], bestand: Mapping[str, object],
) -> set[str]:
    """Die Bereiche aus ``neu``, deren Kennung sich nicht verwenden lässt (schon vergeben,
    ungültig, Sicherheitsmuster …) — für den Werksabgleich (Paket 12, Review #6), der solche
    Bereiche überspringt statt abzubrechen.

    Einer nach dem anderen gegen den Bestand plus die schon angenommenen: auch zwei neue mit
    derselben Kennung fallen auf.
    """
    sicher = sicherheits_kennungen_aus(bestand.get(SICHERHEIT))
    stand = dict(bestand)
    kollidiert: set[str] = set()
    for area in sorted(neu):
        if kennungs_einwand({area: neu[area]}, stand, sicher):
            kollidiert.add(area)
        else:
            stand[area] = neu[area]
    return kollidiert

