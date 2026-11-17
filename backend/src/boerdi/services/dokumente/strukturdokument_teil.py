"""Der Teil ``strukturdokument`` im Vorgang (Plan 2026-11-16, TG-3d/TG-3e) — rein, ohne I/O.

Datenmodell des Nutzers (16.11.): Strukturdokumente sind von Inhalten getrennt, weil man von ihnen
später den Volltext verarbeitet. Der Teil trägt nie den Text, nur **Verweise** — eine Liste von
Einträgen ``{name, quelle, ref}``:

- ``quelle: chatbot`` — anonym im Chatbot umgewandelt (``POST /api/ui/dokumente``); ``ref`` ist
  ``dokument:<id>`` (der Text liegt 24 h an der Sitzung, ``dokument_uploads``);
- ``quelle: wlo`` — ein Knoten mit der Rolle ``struktur`` aus dem Teil ``ablage``; ``ref`` ist
  seine ``node_id`` (den Volltext erzeugt das Repositorium, gelesen wird er nur).

Feinentscheid: Der Wert ist ``{"dokumente": [...]}`` statt einer nackten Liste — jeder andere Teil
ist ein Objekt (Kurzbeschreibung, Titel, Prüfung der Teile lesen ``dict``).

Den Text liefert der Leser ``dokumente/strukturdokument`` (``text``), je nach Quelle. Der Teil
``document`` (ein Dokument, ``wlo.dokument-verweis@1``) bleibt als Rückwärts-Teil daneben.
"""

from __future__ import annotations

import re
from typing import Any, Final

TEIL: Final = "strukturdokument"
TYP: Final = "wlo.strukturdokumente@1"
FELD: Final = "dokumente"
CHATBOT: Final = "chatbot"
WLO: Final = "wlo"
#: Fünf anonym (``dokumente/ablage.MAX_JE_SITZUNG``) und fünf über WLO — der Teil bleibt so weit
#: unter der Grenze der Akte (``vorgaenge.INLINE_BYTES``).
HOECHSTENS: Final = 10
NAME_ZEICHEN: Final = 200
DOKUMENT_PRAEFIX: Final = "dokument:"
_NODE: Final = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"


def _zeile(wert: Any, deckel: int) -> str:
    return " ".join(str(wert).split())[:deckel] if wert is not None else ""


def _node_id(wert: Any) -> str | None:
    return wert if isinstance(wert, str) and re.match(_NODE, wert) else None


def chatbot(upload_id: str, name: Any) -> dict[str, str]:
    return {"name": _zeile(name, NAME_ZEICHEN) or "Dokument", "quelle": CHATBOT,
            "ref": f"{DOKUMENT_PRAEFIX}{upload_id}"}


def wlo(node_id: str, name: Any) -> dict[str, str]:
    return {"name": _zeile(name, NAME_ZEICHEN) or "Dokument", "quelle": WLO, "ref": node_id}


def upload_id(eintrag: dict[str, Any]) -> str | None:
    """Die Kennung des Sitzungsdokuments eines ``chatbot``-Eintrags (sonst ``None``)."""
    ref = eintrag.get("ref")
    if eintrag.get("quelle") != CHATBOT or not isinstance(ref, str):
        return None
    return ref.removeprefix(DOKUMENT_PRAEFIX) if ref.startswith(DOKUMENT_PRAEFIX) else None


def _gueltig(e: Any) -> dict[str, str] | None:
    if not isinstance(e, dict) or not isinstance(e.get("ref"), str):
        return None
    if e.get("quelle") == CHATBOT and upload_id(e):
        return chatbot(e["ref"].removeprefix(DOKUMENT_PRAEFIX), e.get("name"))
    if e.get("quelle") == WLO and _node_id(e.get("ref")):
        return wlo(e["ref"], e.get("name"))
    return None


def eintraege(wert: Any) -> list[dict[str, str]]:
    """Die gültigen Einträge eines Teils (unbekannte Formen fallen weg, doppelte Verweise auch)."""
    roh = wert.get(FELD) if isinstance(wert, dict) else None
    aus: list[dict[str, str]] = []
    for e in roh if isinstance(roh, list) else []:
        if (g := _gueltig(e)) and g["ref"] not in {a["ref"] for a in aus}:
            aus.append(g)
    return aus[:HOECHSTENS]


def hat_wlo(wert: Any) -> bool:
    """Trägt der Teil einen ``wlo``-Eintrag? Eine Antwort des Upload-Felds hat nie einen."""
    return any(e["quelle"] == WLO for e in eintraege(wert))


def wert(liste: list[dict[str, str]]) -> dict[str, Any]:
    return {FELD: eintraege({FELD: liste})}


def zusammenfassung(liste: list[dict[str, str]]) -> str:
    """Kurzbeschreibung für Leiste und ``[ARBEITSSTAND]`` — Zahl und Namen, nie Text."""
    namen = ", ".join(f"„{_zeile(e.get('name'), 40)}“" for e in liste[:3])
    mehr = f" und {len(liste) - 3} weitere" if len(liste) > 3 else ""
    zahl = "1 Strukturdokument" if len(liste) == 1 else f"{len(liste)} Strukturdokumente"
    return f"{zahl}: {namen}{mehr}" if liste else "keine Strukturdokumente"


def aus_ablage(ablage: Any) -> list[dict[str, str]]:
    """TG-3e (mit WLO): jeder abgelegte Knoten mit der Rolle ``struktur`` aus dem Teil ``ablage``
    — auch aus einem ersetzten Stapel (``frueher``: die Knoten liegen weiter in WLO). Review
    TG-3d–f, MINOR 4: der aktuelle Stapel zuerst, ``frueher`` nur, solange unter
    :data:`HOECHSTENS` Platz ist — sonst verdrängten alte Knoten die eben abgelegten."""
    if not isinstance(ablage, dict):
        return []
    aus: list[dict[str, str]] = []
    for e in ablage.get("inhalte") or []:
        if (isinstance(e, dict) and e.get("rolle") == "struktur" and e.get("stand") == "stored"
                and _node_id(e.get("node_id"))):
            aus.append(wlo(e["node_id"], e.get("name") or e.get("titel")))
    for e in reversed(ablage.get("frueher") or []):          # die jüngsten früheren zuerst
        if isinstance(e, dict) and e.get("rolle") == "struktur" and _node_id(e.get("node_id")):
            aus.append(wlo(e["node_id"], e.get("titel")))
    return eintraege({FELD: aus})


def mit_chatbot(alt: Any, neu: list[dict[str, str]]) -> dict[str, Any]:
    """Nach dem Lesen (TG-3d): die gelesenen Dokumente ersetzen die ``chatbot``-Einträge, die
    ``wlo``-Einträge bleiben."""
    return wert([*neu, *(e for e in eintraege(alt) if e["quelle"] == WLO)])


def mit_ablage(alt: Any, ablage: Any) -> dict[str, Any] | None:
    """Nach der Ablage (TG-3e): die ``wlo``-Einträge aus ``ablage``, die ``chatbot``-Einträge
    bleiben. ``None``, wenn sich nichts ändert (kein Schreiben, keine neue Fassung)."""
    vorher = eintraege(alt)
    knoten = aus_ablage(ablage)
    if not knoten and not any(e["quelle"] == WLO for e in vorher):
        return None
    # MINOR 4: gelesene (höchstens fünf) zuerst, dann die Knoten bis zur Grenze
    neu = wert([*(e for e in vorher if e["quelle"] == CHATBOT), *knoten])
    return None if neu[FELD] == vorher else neu


def ohne(alt: Any, refs: set[str]) -> dict[str, Any]:
    """Der Teil ohne die Einträge mit diesen Verweisen (ein Dokument ging, Datenschutz)."""
    return wert([e for e in eintraege(alt) if e["ref"] not in refs])
