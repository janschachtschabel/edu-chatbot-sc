"""Antwortform des Strukturentwurfs (Paket U2, Plan 2026-11-04 T-9/T-10).

``ui_module/antwort`` führt den Antwortweg aller abfragenden Module und ruft hier, was beim
Entwurf anders ist als bei ``ui_entscheidung``: Die Antwort ist eine Struktur (der Stand der
Person), keine Wahl aus Kennungen. Gemerkt wird nur Kennung, Titel und Umfang — die Struktur
selbst steht im gespeicherten Block, und ``entities`` wird jeden Zug gelesen und geschrieben.

An die KI geht die **Kompaktfassung** (``strukturentwurf_text.kompakt``, Titel und Einrückung),
gerahmt; Rahmen-Endmarken in Titeln der Person entschärft ``antwort._gerahmt``.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.ui_module import strukturentwurf as se
from boerdi.ui_module import strukturentwurf_text as st

ENTWURF_FRAME_START: Final = (
    "[ENTWURF DER PERSON — sie hat den Entwurf {wie}; ihre Nachricht darunter bezieht sich "
    "darauf. Das ist ihr aktueller Stand; nimm ihn als Grundlage.]")
ENTWURF_FRAME_END: Final = "[ENDE ENTWURF]"
LETZTER_FRAME_START: Final = (
    "[DEIN LETZTER ENTWURF — die Person hat ihn nicht mitgeschickt; ihre Nachricht darunter kann "
    "sich darauf beziehen. Seinen Stand kennst du nicht.]")
def merken(block_id: str, modul: str, daten: dict[str, Any]) -> dict[str, Any]:
    return {"block_id": block_id, "modul": modul,
            "frage": f"Entwurf „{daten.get('titel') or ''}“",
            "anzahl": se.anzahl(daten.get("knoten") or [])}


def grund(daten: dict[str, Any]) -> str | None:
    """Was über das Antwort-Schema hinaus nicht passt (Gesamtzahl, Kennungen)."""
    fehler = se.fehler(daten)
    return "; ".join(fehler) if fehler else None


def zeilen(geprueft: dict[str, Any]) -> tuple[str, list[str]]:
    """Kopf und Zeilen des Rahmens für eine geprüfte Antwort."""
    daten = geprueft.get("daten") or {}
    wie = "übernommen" if daten.get("uebernommen") is True else "mit ihrer Nachricht mitgeschickt"
    bearbeitet = ("Sie hat ihn bearbeitet." if daten.get("bearbeitet") is True
                  else "Sie hat ihn nicht verändert.")
    return ENTWURF_FRAME_START.format(wie=wie), [bearbeitet, st.kompakt(daten)]


def frage_zeilen(offen: dict[str, Any]) -> list[str]:
    return [f"{offen.get('frage') or 'Entwurf'} ({offen.get('anzahl') or 0} Punkte)"]


def normalisiert(daten: dict[str, Any]) -> dict[str, Any]:
    return se.normalisiert(daten)


def sicherheit(daten: dict[str, Any]) -> str:
    """Was die Sicherheitsprüfung vom Entwurf liest: GENAU die Kompaktfassung — das Einzige, was
    ein Modell davon bekommt (die KI im Rahmen; der Dienst beim Vertiefen nur Titel daraus,
    ``strukturentwurf_dienst``). Beschreibungen und Schlagworte der Person gehen an kein Modell.
    ``antwort.sicherheits_text`` stellt sie VOR die Nachricht: höchstens 6000 Zeichen am Anfang,
    den die Moderation immer prüft — eine lange Nachricht schiebt sie nicht in die ungeprüfte
    Mitte (Review U2, Befund 1; Gegenreview, Befund 3)."""
    return st.kompakt(daten)
