"""Was die Person zuletzt gesehen hat — ein Block je Zug für die Agent-Schleife.

Paket C der zweiten Agent-Runde (Plan 2026-09-28). Im Tor E-5 scheiterten vier
Züge daran, dass der Agent den vorigen Zug nicht sah: „zeig mir jetzt die
Lösungen“ fand kein Quiz, „der erste Treffer“ keine Kennung.

**Quelle ist der Verlauf** (Review 2026-09-29). Die gezeigten Karten stehen an der
gespeicherten Antwort ohnehin im ausgelieferten Endstand (``turn_persist`` zieht
die Zeile nach der Kürzung nach); die gezeigten Boxen legt
:func:`dokumente_fuer_die_nachricht` gedeckelt dazu (``debug._dokumente``). An der
Nachricht gelten der Datenschutz-Schalter ``logging.messages`` und jedes Löschen
von selbst. Die erste Fassung hielt die Boxen im Sitzungszustand — vorbei an
beidem —, las die Materialien aus der Fundliste vor der Kürzung und kappte lange
Dokumente ohne Vermerk.

**Rückblick:** die jüngste Antwort mit Karten bzw. mit Boxen unter den letzten
:data:`RUECKBLICK` Antworten — „die Lösungen dazu“ findet das Quiz auch nach einer
Zwischenfrage, aber nicht mehr am Ende eines langen Gesprächs.

**Als Daten gerahmt** (``domain/untrusted_text``, D4): Titel kommen aus dem
Repositorium, Dokumente aus eigenen Antworten, die Volltexte Dritter enthalten
können. Jede Rumpfzeile ist ein Zitat (``> ``), damit ein ``## …`` im Dokument
keinen Prompt-Abschnitt beginnt. ``respond_agent`` setzt den Block an den Anfang
der Nachricht der Person, nicht in einen System-Block.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.untrusted_text import GESEHEN_FRAME_END, GESEHEN_FRAME_START

#: An der gespeicherten Antwort, neben den übrigen internen ``debug``-Schlüsseln.
DOKUMENTE_DEBUG_KEY: Final = "_dokumente"
MAX_DOKUMENTE: Final = 3
#: Je Dokument an der Nachricht — der Verlauf wird in jedem Zug geladen.
DOKUMENT_ZEICHEN: Final = 6000
#: Alle Dokumente zusammen im Block — er geht in jeder Runde der Schleife mit.
BLOCK_DOKUMENT_ZEICHEN: Final = 6000
MAX_MATERIALIEN: Final = 10
#: So viele Antworten zurück sucht der Block nach Karten und nach Boxen.
RUECKBLICK: Final = 3
GEKUERZT: Final = "[… gekürzt]"
_MAX_LERNARTEN: Final = 3
_TITEL_ZEICHEN: Final = 150


def _zeile(wert: object, deckel: int = _TITEL_ZEICHEN) -> str:
    """Eine Zeile: ein Umbruch im Repositoriumstext darf im Block keine eigene
    Zeile — etwa eine Überschrift — erzeugen."""
    return " ".join(wert.split())[:deckel] if isinstance(wert, str) else ""


def _feld(eintrag: Any, name: str) -> Any:
    return eintrag.get(name) if isinstance(eintrag, dict) else getattr(eintrag, name, None)


def _objekte(wert: object) -> list[dict[str, Any]]:
    return [e for e in wert if isinstance(e, dict)] if isinstance(wert, list) else []


def dokumente_fuer_die_nachricht(dokumente: list[Any]) -> list[dict[str, Any]]:
    """Die gezeigten Boxen eines Zugs, gedeckelt — für ``debug._dokumente`` der Antwort.

    ``gekuerzt`` hält fest, dass gekappt wurde: sonst sähe der nächste Zug einen
    Torso und hielte ihn für vollständig („überarbeite den Plan“).
    """
    gemerkt = []
    for dokument in dokumente:
        inhalt = _feld(dokument, "content")
        if not isinstance(inhalt, str) or not inhalt.strip():
            continue
        inhalt = inhalt.strip()
        gemerkt.append({
            "kind": _zeile(_feld(dokument, "kind")),
            "title": _zeile(_feld(dokument, "title")),
            "content": inhalt[:DOKUMENT_ZEICHEN],
            "gekuerzt": len(inhalt) > DOKUMENT_ZEICHEN,
        })
    return gemerkt[:MAX_DOKUMENTE]


def _antworten(verlauf: list[Any]) -> list[dict[str, Any]]:
    """Die letzten :data:`RUECKBLICK` Antworten, jüngste zuerst."""
    return [m for m in reversed(verlauf)
            if isinstance(m, dict) and m.get("role") == "assistant"][:RUECKBLICK]


def _karten(antworten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return next((k for k in (_objekte(a.get("cards")) for a in antworten) if k), [])


def _dokumente(antworten: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for antwort in antworten:
        debug = antwort.get("debug")
        dokumente = _objekte(debug.get(DOKUMENTE_DEBUG_KEY)) if isinstance(debug, dict) else []
        if dokumente:
            return dokumente
    return []


def _materialien(karten: list[dict[str, Any]]) -> str:
    zeilen = []
    for karte in [k for k in karten if k.get("node_type", "content") == "content"]:
        arten = karte.get("learning_resource_types")
        arten = [a for a in map(_zeile, arten if isinstance(arten, list) else []) if a]
        zeilen.append(
            f"{len(zeilen) + 1}. „{_zeile(karte.get('title'))}“ "
            f"({', '.join(arten[:_MAX_LERNARTEN]) or 'Material'}) — "
            f"nodeId: {_zeile(karte.get('node_id'), 64)}")
    zeilen = zeilen[:MAX_MATERIALIEN]
    return "\n".join(["Materialien (in der gezeigten Reihenfolge):", *zeilen]) if zeilen else ""


def _sammlungen(karten: list[dict[str, Any]]) -> str:
    zeilen = [f"- „{_zeile(k.get('title'))}“ — nodeId: {_zeile(k.get('node_id'), 64)}"
              for k in karten if k.get("node_type", "content") != "content"][:MAX_MATERIALIEN]
    return "\n".join(["Sammlungen und Themenseiten:", *zeilen]) if zeilen else ""


def _dokument_teile(dokumente: list[dict[str, Any]]) -> list[str]:
    teile, rest = [], BLOCK_DOKUMENT_ZEICHEN
    for dokument in dokumente:
        inhalt = dokument.get("content") if isinstance(dokument.get("content"), str) else ""
        if not inhalt:
            continue
        gezeigt = inhalt[:max(rest, 0)]
        rest -= len(gezeigt)
        zeilen = [f"Dokument „{_zeile(dokument.get('title'))}“ ({_zeile(dokument.get('kind'))}):",
                  *(f"> {z}" if z else ">" for z in gezeigt.splitlines())]
        if len(gezeigt) < len(inhalt) or dokument.get("gekuerzt") is True:
            zeilen.append(GEKUERZT)
        teile.append("\n".join(zeilen))
    return teile


def zuletzt_gezeigt(verlauf: list[Any] | None) -> str:
    """Der gerahmte Block — oder ``""``, wenn die letzten Antworten nichts zeigten."""
    antworten = _antworten(verlauf or [])
    karten = _karten(antworten)
    teile = [t for t in (_materialien(karten), _sammlungen(karten)) if t]
    teile += _dokument_teile(_dokumente(antworten))
    if not teile:
        return ""
    return "\n\n".join([GESEHEN_FRAME_START, *teile, GESEHEN_FRAME_END])
