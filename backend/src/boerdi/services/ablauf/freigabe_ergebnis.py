"""Das Ergebnis einer eingelösten Freigabe, wie es in den Lauf geht (Paket S; Querschnitts-Review
AS-D, Befund 3: eine Quelle für den Zug ``freigabe_zug`` und die Simulation).

Ohne Schlüsselfelder und ohne ``confirm``-Block (Review S2/S3, Befund 11: das Ergebnis wird ein
Teil). Sind alle Einträge gescheitert, gibt es keins — der Lauf geht zu ``bei_fehler`` (Review S4,
Befund 7: ``complete`` heißt „nichts mehr offen“, nicht „geklappt“). Rein, ohne I/O.
"""

from __future__ import annotations

from typing import Any

from boerdi.domain.write_confirm import SCHLUESSEL_FELDER


def ohne_schluessel(wert: Any, tiefe: int = 0) -> Any:
    if tiefe > 8:
        return None
    if isinstance(wert, dict):
        return {k: ohne_schluessel(v, tiefe + 1) for k, v in wert.items()
                if k not in SCHLUESSEL_FELDER and k != "confirm"}
    if isinstance(wert, list):
        return [ohne_schluessel(v, tiefe + 1) for v in wert]
    return wert


#: Status eines Plan-Eintrags, bei denen sicher nichts geschehen ist.
_NICHT_GESCHEHEN = frozenset({"failed", "not_stored"})


def alle_gescheitert(ergebnis: Any) -> bool:
    """Teilweise Fehler stehen im Teil; nur wenn jeder Eintrag gescheitert ist, gilt der Schritt
    als gescheitert. ``not_stored`` (SW-3, ``wlo_submit_contents``: mit Erfolg beantwortet, aber
    nicht in der Warteschlange) zählt wie ``failed`` — sonst liefe der Lauf weiter, als sei
    eingereicht. ``proposed`` zählt NICHT als gescheitert: Die Vorschau hat gesagt, dass
    vorgeschlagen statt aufgenommen wird, und die Person hat dem zugestimmt."""
    if not isinstance(ergebnis, dict):
        return False
    eintraege = next((ergebnis[k] for k in ("items", "nodes", "pairs")
                      if isinstance(ergebnis.get(k), list) and ergebnis[k]), None)
    return bool(eintraege) and all(isinstance(e, dict) and e.get("status") in _NICHT_GESCHEHEN
                                   for e in eintraege)


def fuer_lauf(ergebnis: dict[str, Any]) -> dict[str, Any] | None:
    """``ergebnis`` ohne Schlüssel — oder ``None``, wenn alle Einträge gescheitert sind."""
    sauber = ohne_schluessel(ergebnis)
    return None if alle_gescheitert(sauber) else sauber
