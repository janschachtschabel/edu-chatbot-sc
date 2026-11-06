"""Auslöser ``agent`` (Paket A2a): die KI schlägt einen Ablauf vor — gestartet wird per Knopf.

- :func:`werkzeug`: das virtuelle Agent-Werkzeug ``ablauf_vorschlagen`` — nur, wenn ein aktiver
  Ablauf den Auslöser ``agent`` trägt; die Kennungen als Aufzählung (die Schleife prüft die
  Argumente gegen das Schema), Titel, ``wann`` und ``nicht_wann`` in der Beschreibung.
- Die Schleife merkt sich die Kennung (:data:`MAX_JE_ZUG`, ``AgentRun.ablauf_vorschlaege``) und ruft
  nichts; :func:`schnellantworten` macht daraus beim Zusammenstellen die Knopf-Schnellantwort
  ``__action__|<Titel>|ablauf_starten|{"ablauf": id}``, die das Widget schon kennt. So formuliert
  die KI nie selbst einen Knopf, und der Start läuft wie jeder Knopf durch Preflight und
  Sicherheitsprüfung.

``direkt`` (sofort starten) bleibt offen: es bräuchte Treiber-Ausgabe mitten in der Agent-Antwort.
"""

from __future__ import annotations

import json
from typing import Any, Final

from boerdi.services.ablauf import ausloeser

NAME: Final = "ablauf_vorschlagen"
#: Im ``session_state``: die Kennungen dieses Zugs, gelesen (und entfernt) beim Zusammenstellen.
SITZUNG_KEY: Final = "_ablauf_vorschlaege"
MAX_JE_ZUG: Final = 1
_MAX_SCHNELLANTWORTEN: Final = 4
_LABEL_ZEICHEN: Final = 60

QUITTUNG: Final = ("Vorschlag angenommen: unter deiner Antwort erscheint ein Knopf, mit dem die "
                   "Person den Ablauf startet. Sag ihr in einem Satz, was er tut; starte selbst "
                   "nichts und beschreibe keine Schritte im Voraus.")
SCHON_VORGESCHLAGEN: Final = "Ein Ablauf ist in diesem Zug schon vorgeschlagen."


def _titel(ablauf: Any, lang: str) -> str:
    return ((ablauf.titel.get(lang) or "").strip() or (ablauf.titel.get("de") or "").strip()
            or ablauf.id)


def werkzeug(lang: str) -> dict[str, Any] | None:
    ablaeufe = ausloeser.vorschlaege()
    if not ablaeufe:
        return None
    zeilen = []
    for a in ablaeufe:
        zeile = f"- {a.id}: {_titel(a, lang)}"
        if a.wann:
            zeile += f" — passt, wenn: {'; '.join(a.wann)}"
        if a.nicht_wann:
            zeile += f" — nicht, wenn: {'; '.join(a.nicht_wann)}"
        zeilen.append(zeile)
    beschreibung = (
        "Schlage der Person einen festen Ablauf vor, wenn ihr Anliegen genau zu einem der "
        "folgenden passt. Das Werkzeug startet nichts: unter deiner Antwort erscheint ein Knopf, "
        "und die Person entscheidet. Höchstens einmal je Antwort.\n" + "\n".join(zeilen))
    return {"type": "function", "function": {
        "name": NAME, "description": beschreibung,
        "parameters": {"type": "object", "additionalProperties": False, "required": ["ablauf"],
                       "properties": {"ablauf": {"type": "string",
                                                 "enum": [a.id for a in ablaeufe]}}}}}


def merken(vorgeschlagen: list[str], ablauf_id: str) -> str:
    """Die Kennung (schon gegen das Schema geprüft) merken — Quittung für das Modell."""
    if len(vorgeschlagen) >= MAX_JE_ZUG:
        return SCHON_VORGESCHLAGEN
    vorgeschlagen.append(ablauf_id)
    return QUITTUNG


def schnellantworten(ids: list[str] | None, lang: str) -> list[str]:
    """Knopf-Schnellantworten für die vorgeschlagenen Kennungen — nur, was noch vorschlagbar ist."""
    vorschlagbar = {a.id: a for a in ausloeser.vorschlaege()}
    aus: list[str] = []
    for ablauf_id in ids or []:
        if (a := vorschlagbar.get(ablauf_id)) is None:
            continue
        label = _titel(a, lang).replace("|", "/")[:_LABEL_ZEICHEN]
        aus.append(f"__action__|{label}|ablauf_starten|"
                   + json.dumps({"ablauf": a.id}, ensure_ascii=False))
    return aus


def anhaengen(quick_replies: list[str] | None, vorschlaege: list[str] | None, *,
              hoechstens: int | None = None) -> list[str]:
    """Die Knöpfe zuerst, insgesamt höchstens vier (wie der Relevanz-Rückfall) bzw. die Höchstzahl
    des Gastgebers."""
    if not vorschlaege:
        return list(quick_replies or [])
    grenze = min(_MAX_SCHNELLANTWORTEN, hoechstens) if hoechstens else _MAX_SCHNELLANTWORTEN
    rest = [q for q in quick_replies or [] if q not in vorschlaege]
    return [*vorschlaege, *rest][:grenze]
