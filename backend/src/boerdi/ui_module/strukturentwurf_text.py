"""Texte des Strukturentwurfs (Paket U2, Plan 2026-11-04 T-9).

- :func:`textfassung` — eingerückte Markdown-Liste für Widgets, die das Modul nicht kennen.
- :func:`kompakt` — Titel und Einrückung, gedeckelt: so sieht die KI einen mitgeschickten
  Entwurf im Folgezug (anders als der Bestand darf der Entwurf zur KI — er stammt von ihr bzw.
  von der Person).
- :func:`quittung` — das kurze Werkzeug-Ergebnis an die KI im Zug, der den Entwurf zeigt.

Rein und ohne I/O.
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.ui_module.strukturentwurf import alle, anzahl

#: Zeichen der Kompaktfassung (≈ 1500 Token): reicht für ~250 kurze Titel.
KOMPAKT_ZEICHEN: Final = 6000
_KOPF: Final = {"ki": "Entwurf (KI)", "wlo": "Entwurf (aus WLO)"}


def kopf(daten: dict[str, Any]) -> str:
    """„Entwurf (KI): Titel“ — nie wie Bestand (T-2)."""
    return f"{_KOPF.get(str(daten.get('quelle')), _KOPF['ki'])}: {daten.get('titel') or ''}"


def textfassung(daten: dict[str, Any]) -> str:
    zeilen = [f"**{kopf(daten)}**", ""]
    for k, ebene in alle(daten.get("knoten") or []):
        beschreibung = f" — {k['beschreibung']}" if k.get("beschreibung") else ""
        zeilen.append(f"{'  ' * (ebene - 1)}- {k['titel']}{beschreibung}")
    return "\n".join(zeilen)


def _zeilen(daten: dict[str, Any]) -> list[tuple[str | None, str]]:
    angaben = [str(daten.get(f)) for f in ("fach", "bildungsstufe") if daten.get(f)]
    zeilen: list[tuple[str | None, str]] = [
        (None, f"{daten.get('titel') or ''}{' (' + ', '.join(angaben) + ')' if angaben else ''}")]
    for k, ebene in alle(daten.get("knoten") or []):
        offen = " (Unterthemen fehlen noch)" if k.get("ausstehend") else ""
        zeilen.append((k.get("id"), f"{'  ' * (ebene - 1)}- {k['titel']}{offen}"))
    return zeilen


def _sichtbar(daten: dict[str, Any], deckel: int) -> tuple[list[tuple[str | None, str]], bool]:
    """Die Zeilen, die in den Deckel passen (Umbrüche und das „…“ zählen mit), und ob gekürzt."""
    zeilen = _zeilen(daten)
    if len("\n".join(z for _, z in zeilen)) <= deckel:
        return zeilen, False
    behalten: list[tuple[str | None, str]] = []
    laenge = -1
    for zeile in zeilen:
        if laenge + 1 + len(zeile[1]) > deckel - 2:
            break
        behalten.append(zeile)
        laenge += 1 + len(zeile[1])
    return behalten or zeilen[:1], True


def kompakt(daten: dict[str, Any], deckel: int = KOMPAKT_ZEICHEN) -> str:
    """Titel des Entwurfs und eine Zeile je Knoten (eingerückt); am Deckel endet sie mit „…“."""
    zeilen, gekuerzt = _sichtbar(daten, deckel)
    text = "\n".join(z for _, z in zeilen)
    return f"{text}\n…" if gekuerzt else text


def sichtbare_ids(daten: dict[str, Any], deckel: int = KOMPAKT_ZEICHEN) -> set[str]:
    """Die Punkte, die in der Kompaktfassung stehen — nur sie sah die KI (und die Prüfung)
    (Gegenreview U2, Befund 3)."""
    return {kennung for kennung, _ in _sichtbar(daten, deckel)[0] if kennung}


def quittung(daten: dict[str, Any]) -> str:
    oben = daten.get("knoten") or []
    offen = sum(1 for k, _ in alle(oben) if k.get("ausstehend"))
    noch = f", {offen} noch ohne Unterthemen" if offen else ""
    titel = "; ".join(k["titel"] for k in oben)
    return (f"OK: Der Entwurf „{daten.get('titel') or ''}“ steht unter deiner Antwort als "
            f"bearbeitbare Gliederung ({len(oben)} Themen oben, {anzahl(oben)} Punkte{noch}). "
            f"Erste Ebene: {titel}. Die Person bearbeitet ihn dort und übernimmt ihn oder "
            "schreibt dir; dann bekommst du ihren Stand. Dein Zug endet hier — rufe kein "
            "weiteres Werkzeug.")
