"""Der Verweis der Sitzung auf den aktiven Vorgang und die Kennzeile für die KI (aus
``arbeitsstand`` gelöst, Querschnitts-Review 2026-11-06, Q4) — rein, ohne I/O.

Der Verweis trägt keine Daten: Kennung, Besitz-Streuwert, Titel, Frist, je Teil Version und
Kurztext, mit einem Ablauf dessen Name, Schritt und Status.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Final

from boerdi.db.models import Vorgang
from boerdi.domain.endmarken import entschaerfe_endmarken
from boerdi.services.teil_verweise import NAME as _TEIL_NAME
from boerdi.ui_module.rahmen import zeile

#: In ``session_state["entities"]``: der Verweis auf den aktiven Vorgang (keine Daten).
VERWEIS: Final = "_vorgang"
KENNZEILE_ZEICHEN: Final = 300
TITEL_ZEICHEN: Final = 60


def _besitz(aufrufer: str) -> str:
    """Ein Streuwert der Besitzerin im Verweis — die Kennung selbst steht nicht in der Sitzung."""
    return hashlib.sha256(aufrufer.encode()).hexdigest()[:16]


def verweis_fuer(v: Vorgang, aufrufer: str) -> dict[str, Any]:
    """Der Verweis für die Sitzung — Kennung, Besitz-Streuwert, Titel, Frist, je Teil Version und
    Kurztext; mit einem Ablauf (A1) dessen Name, Schritt und Status."""
    akte = v.akte or {}
    teile = akte.get("teile") or {}
    vw: dict[str, Any] = {
        "id": v.id, "b": _besitz(aufrufer), "titel": zeile(v.titel, 120),
        "bis": v.verfaellt_am.isoformat(),
        "teile": {n: {"v": t.get("version"), "z": zeile(t.get("zusammenfassung"), 120)}
                  for n, t in teile.items()}}
    if isinstance(lauf := akte.get("lauf"), dict):
        # ``fassung`` (A2b): ein Agent-Schritt engt nur ein, solange seine Schritte gelten.
        # ``freigabe_id`` (zweites Review, Z-3): ein offener Plan gilt nur seinem eigenen Lauf.
        vw["lauf"] = {k: zeile(lauf.get(k), 40)
                      for k in ("ablauf", "schritt", "status", "fassung", "start", "freigabe_id")}
        # AS-8a (zweites Review, Befund 1): die Marke der Probe als Wahrheitswert — ``gilt`` liest
        # sie auch aus dem Verweis (Leiste, wartende Schritte); ``zeile`` machte daraus Text.
        if lauf.get("probe") is True:
            vw["lauf"]["probe"] = True
        # Review 13.11.: welche Fragen in diesem Lauf beantwortet sind — nur die Namen der Teile
        # (``treiber.weiter_wahl``), für ``ki_schritt.daten_zeile``; keine Inhalte.
        if isinstance(antworten := lauf.get("antworten"), list):
            vw["lauf"]["antworten"] = [n for n in antworten
                                       if isinstance(n, str) and _TEIL_NAME.match(n)][:20]
    return vw


def verweis(entities: dict[str, Any], aufrufer: str) -> dict[str, Any] | None:
    """Der Verweis, wenn er die Form hat, nicht abgelaufen ist und **dieser** Besitzerin gehört
    (Review V1, Befund 2: nach Ab- oder Ummelden sähe die KI sonst Titel der vorigen Person)."""
    vw = entities.get(VERWEIS)
    if not isinstance(vw, dict) or not isinstance(vw.get("id"), str):
        return None
    if vw.get("b") != _besitz(aufrufer):
        return None
    try:
        bis = datetime.fromisoformat(str(vw.get("bis")))
    except (ValueError, TypeError):
        return None
    if bis.tzinfo is None:
        return None
    return vw if bis > datetime.now(UTC) else None


def kennzeile(entities: dict[str, Any], aufrufer: str) -> str:
    """Eine Zeile über den Arbeitsstand für die KI (≤ 300 Zeichen) — oder leer."""
    vw = verweis(entities, aufrufer)
    if vw is None:
        return ""
    teile = vw.get("teile") if isinstance(vw.get("teile"), dict) else {}
    liste = "; ".join(f"{zeile(n, 30)} v{t.get('v')} ({zeile(t.get('z'), 50)})"
                      for n, t in teile.items() if isinstance(t, dict)) or "noch keine"
    from boerdi.services.ablauf.treiber import WARTEND  # spät: treiber lädt den Arbeitsstand

    lauf = vw.get("lauf") if isinstance(vw.get("lauf"), dict) else None
    # Review AS-7a, Befund 8: die gemeinsame Liste — ein neuer Wartestatus fehlte hier
    ablauf = (f"; Ablauf {lauf.get('ablauf')}: Schritt {lauf.get('schritt')} "
              f"({lauf.get('status')});"
              if lauf and lauf.get("status") in (*WARTEND, "laeuft") else ";")
    # Review 13.11.: der Stand des Ablaufs vor den Teilen — am Ende der gedeckelten Zeile fiel er
    # bei vielen Teilen weg, und der Masterskill richtet sich nach ihm („wartet_wahl“).
    inhalt = entschaerfe_endmarken(
        f"Vorgang „{zeile(vw.get('titel'), TITEL_ZEICHEN)}“{ablauf} Teile: {liste}.")
    # Review V1, Befund 6: eine Klammer im Fremdtext schlösse die Zeile vorzeitig.
    inhalt = inhalt.replace("[", "(").replace("]", ")")
    # Paket V2: wie die KI einen Teil weitergibt, ohne ihn zu kennen (``services/teil_verweise``).
    kopf, ende = "[ARBEITSSTAND — ", ' An Werkzeuge mit {"$teil": "<name>"}.]'

    return kopf + inhalt[:KENNZEILE_ZEICHEN - len(kopf) - len(ende)] + ende


def verweis_weg(entities: dict[str, Any], aufrufer: str) -> None:
    """Den eigenen Verweis entfernen. Ein fremder (nach Ab- oder Ummelden) bleibt verborgen stehen —
    :func:`verweis` liefert ihn dieser Person nie; meldet sich die vorige zurück, gilt er wieder,
    solange die neue Besitzerin nicht selbst einen Vorgang in die Sitzung geholt hat (eine Sitzung
    hält einen Verweis; Review Q3, Befund 11). Ein Verweis ohne Form geht immer."""
    roh = entities.get(VERWEIS)
    if not isinstance(roh, dict) or not isinstance(roh.get("id"), str) \
            or roh.get("b") == _besitz(aufrufer):
        entities.pop(VERWEIS, None)
