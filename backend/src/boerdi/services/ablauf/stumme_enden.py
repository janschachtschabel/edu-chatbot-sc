"""Plan 2026-11-16, TG-6: kein stummes Ende — ein ``ende`` ohne ``ausstieg`` bedeutet „fertig mit
Ergebnis“ oder die Person hat es gewählt.

Anlass war die Sackgasse „Themenbaum · aus Ordnern“: drei lose Dateien, und der Lauf endete mit
„Ohne Unterordner gibt es noch keinen Themenbaum.“ — ohne Ausweg. Diese Prüfung findet solche
Enden im Graphen der Schritte, ohne Teile oder Bedingungen auszuwerten (jede Regel einer
Verzweigung kann greifen).

Auf jedem Weg vom ersten Schritt trägt der Lauf einen von drei Ständen:

- **ERGEBNIS** — der Lauf hat etwas geschafft. Das zählt beim regulären Weitergehen (nicht über
  ``bei_fehler``) nach einem KI-Schritt, einem Auftrag, einem schreibenden Werkzeug mit Freigabe,
  einem ``seite``-Schritt (die Person ist angekommen) und einem abfragenden Modul, dessen Antwort
  einen Teil außerhalb der Bereitstellung schreibt (``ui_strukturentwurf`` → ``draft``; das
  Upload-Feld stellt nur bereit, ``arbeitsstand_teile.BEREITSTELLUNG``, ``ablage`` und
  ``metadaten``). Ein
  Ergebnis bleibt — was einmal entstanden ist, geht nicht verloren.
- **GEWAEHLT** — zuletzt hat die Person eine Schnellantwort oder Freitext gegeben („Beenden“):
  das Ende ist ihre Entscheidung.
- **NICHTS** — sonst: nach einem gescheiterten Schritt (``bei_fehler``) oder einer Antwort im
  Upload-Feld, ohne dass danach etwas entstand oder gewählt wurde.

Ein ``ende`` ohne ``ausstieg``, das mit NICHTS erreichbar ist, ist **stumm**. Verzweigungen,
Nachrichten ohne Wahl und Dienste ohne Freigabe lassen den Stand, wie er ist — bis auf eine Regel
``wenn_seite``: Die Person ist schon auf der Seite, wie nach der Ankunft an einem ``seite``-Schritt
(die Führung springt so direkt zum Schluss).

Ein Hinweis, kein Befund: eigene Abläufe aus der Zeit davor sollen speichern und laufen wie bisher;
die Seeds hält ein Test frei davon (``tests/test_tg6_themenbaum.py``).
"""

from __future__ import annotations

from typing import Any, Final

from boerdi.domain.config_models.ablauf import AblaufArea, Schritt
from boerdi.services.ablauf.pruefung import MIT_BEI_FEHLER, _normal, _wartet, mit_wahl

NICHTS: Final = 0
GEWAEHLT: Final = 1
ERGEBNIS: Final = 2


def _bereitstellung() -> frozenset[str]:
    from boerdi.services.arbeitsstand_teile import BEREITSTELLUNG

    # Plan 2026-11-17, U5/U6: „Hier im Chat“ schreibt aus dem Upload-Feld auch ``metadaten``
    # (``quelle: chatbot``) — Angaben zu den Dateien der Person, kein Ergebnis eines Laufs (wie
    # ``ablage``). Sonst zählte jedes Upload-Feld als Ergebnis-Modul, kein Ende danach wäre stumm.
    return frozenset(BEREITSTELLUNG) | {"ablage", "metadaten"}


def _ergebnis_modul(s: Schritt, module: dict[str, Any]) -> bool:
    """Schreibt die Antwort dieses Moduls einen Teil außerhalb der Bereitstellung?"""
    schreibt = ((module.get(s.modul or "") or {}).get("vorgang") or {}).get("schreibt") or []
    return any(isinstance(n, str) and n not in _bereitstellung() for n in schreibt)


def _ergebnis_teile(ablauf: AblaufArea, module: dict[str, Any]) -> frozenset[str]:
    """Teile, die ein Ergebnis-Schritt schreibt (die Ausgabe eines KI-Schritts, die Antwort eines
    Ergebnis-Moduls, auch am KI-Schritt, ein Auftrag, ein Werkzeug mit Freigabe)."""
    aus: set[str] = set()
    for s in ablauf.schritte:
        if s.typ == "agent" and s.agent:
            aus |= {s.agent.ausgabe} if s.agent.ausgabe else set()
            werkzeuge = s.agent.werkzeuge
        else:
            werkzeuge = [s.modul or ""] if s.typ == "modul" else []
        for w in werkzeuge:
            schreibt = ((module.get(w) or {}).get("vorgang") or {}).get("schreibt") or []
            aus |= {n for n in schreibt if isinstance(n, str) and n not in _bereitstellung()}
        if s.schreibt and (s.typ == "auftrag" or (s.typ == "werkzeug" and s.freigabe)):
            aus.add(s.schreibt)
    return frozenset(aus)


def _regulaer(s: Schritt, stand: int, module: dict[str, Any]) -> int:
    """Der Stand nach dem regulären Weitergehen von ``s``."""
    if stand == ERGEBNIS:
        return ERGEBNIS
    if mit_wahl(s):
        return GEWAEHLT
    if s.typ in ("agent", "auftrag", "seite") or (s.typ == "werkzeug" and s.freigabe):
        return ERGEBNIS
    if s.typ == "modul" and _wartet(s):
        return ERGEBNIS if _ergebnis_modul(s, module) else NICHTS
    return stand


def stumme_enden(ablauf: AblaufArea, module: dict[str, Any] | None = None) -> list[str]:
    """Die Kennungen der ``ende``-Schritte ohne ``ausstieg``, die ein Lauf stumm erreichen kann —
    in der Reihenfolge der Schritte."""
    if module is None:
        from boerdi.ui_module import katalog

        module = katalog.katalog()
    if not ablauf.schritte:
        return []
    index = {s.id: i for i, s in enumerate(ablauf.schritte)}
    ergebnisse = _ergebnis_teile(ablauf, module)
    gesehen: set[tuple[int, int]] = {(0, NICHTS)}
    offen = [(0, NICHTS)]
    stumm: set[int] = set()
    while offen:
        i, stand = offen.pop()
        s = ablauf.schritte[i]
        if s.typ == "ende":
            if stand == NICHTS and not s.ausstieg:
                stumm.add(i)
            continue
        kanten = [(z, _regulaer(s, stand, module)) for z in _normal(ablauf, i)]
        if s.typ == "verzweigung" and isinstance(s.weiter, list):
            # Führungen: eine Regel ``wenn_seite`` heißt „die Person ist schon dort“ — wie die
            # Ankunft an einem ``seite``-Schritt ein Ergebnis; ``wenn_teil`` auf einen Teil, den
            # nur ein Ergebnis schreibt (etwa ``draft``), heißt „das Ergebnis liegt vor“
            kanten = [(r.dann or r.sonst or "",
                       ERGEBNIS if r.wenn_seite or (r.wenn_teil in ergebnisse) else stand)
                      for r in s.weiter]
        if s.bei_fehler and s.typ in MIT_BEI_FEHLER:
            kanten.append((s.bei_fehler, stand if stand == ERGEBNIS else NICHTS))
        for ziel, neu in kanten:
            if (j := index.get(ziel)) is not None and (j, neu) not in gesehen:
                gesehen.add((j, neu))
                offen.append((j, neu))
    return [ablauf.schritte[i].id for i in sorted(stumm)]
