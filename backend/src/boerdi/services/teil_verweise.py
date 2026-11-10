"""Teile des Vorgangs in Werkzeug-Argumenten (Paket V2, Plan 2026-11-05 §3).

Die KI kann einem Werkzeug Daten aus dem Arbeitsstand geben, ohne sie zu kennen: statt des Werts
schreibt sie ``{"$teil": "<name>"}`` (die Namen stehen in der Kennzeile ``[ARBEITSSTAND …]``). Das
Backend setzt den Wert **vor** Schreibsperre und Vorschau ein — die Person sieht, was wirklich
geschrieben würde, und der Fingerabdruck der Abnahme deckt den eingesetzten Wert, nicht den Namen.

Nur die reine Form ``{"$teil": "<name>"}`` (ein Schlüssel, Name nach :data:`NAME`)
**unterhalb** der obersten Ebene ist ein Verweis; alles andere bleibt, wie es ist. Paket K2d-1: dazu
``{"$teil": "<name>", "pfad": "outputs.markdown"}`` — eine Stelle im Teil (Schlüssel und
Listenstellen, mit Punkt getrennt, :data:`PFAD`); fehlt sie, fehlt der Teil (``<name>.<pfad>``).
Fehlt ein Teil (kein Vorgang, kein solcher Teil), wird das Werkzeug nicht gerufen
(:func:`fehlertext`).
Paket AS-Da (Plan 2026-11-09 §5e, R1): eine **Auswahl** aus einem Teil —
``{"$teil": "ablage", "liste": "inhalte", "wo": {"rolle": "struktur"}, "feld": "node_id"}``:
``liste`` (statt ``pfad``) ist die Liste im Teil, ``wo`` filtert ihre Einträge (bis zu
:data:`MAX_WO` Bedingungen Pfad → genau gleicher Wert), ``feld`` zieht je Eintrag eine Stelle
heraus (Einträge ohne sie fallen weg). Das Ergebnis ist immer eine Liste, auch eine leere; ist die
Stelle keine Liste, fehlt der Wert (:func:`aufloesen`). Die Form prüft :func:`auswahl_fehler`.
Verschachtelung über :data:`TIEFE` wird nicht durchsucht. Eingesetzt wird eine Kopie — ein Werkzeug,
das seine Argumente ändert, ändert nie die Akte.

**Wer einen Teil bekommt** (Review V2, Befund 1): nur ein Ziel nach :func:`darf` — ein kuratierendes
WLO-Werkzeug mit Vorschau und Abnahme (die Person sieht und bestätigt den Wert) oder ein UI-Modul,
dessen Manifest den Teil unter ``vorgang.liest`` nennt. Lesende Werkzeuge, auch die fremder
MCP-Server, bekommen nie einen Teil: ein Prompt-Injection-Treffer könnte sonst Ordner- und
Dokumentnamen ohne Zustimmung hinausschicken. Die eine Ausnahme liegt außerhalb dieses Moduls: eine
geprüfte UUID aus den Startdaten der Gastseite setzt ``ablauf/treiber._start_kennungen`` vorher
ein (Entscheid AS-4a, Befund 10) — sie ist kein Inhalt des Arbeitsstands.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Awaitable, Callable
from typing import Any, Final

SCHLUESSEL: Final = "$teil"
PFAD_SCHLUESSEL: Final = "pfad"
#: ``\Z`` statt ``$`` (Review K2d-1, Befund 1): ``$`` ließe bei ``match`` einen Zeilenumbruch am
#: Ende durch — die Prüfung schwiege, der Lauf fände das Glied ``markdown\n`` nicht.
NAME: Final = re.compile(r"^[a-z][a-z0-9_]{1,29}\Z")
#: Paket K2d-1: höchstens acht Glieder aus Buchstaben, Ziffern, ``_`` und ``-``.
PFAD: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}(\.[A-Za-z0-9_-]{1,64}){0,7}\Z")
TIEFE: Final = 6
#: AS-Da: die Schlüssel einer Auswahl und höchstens so viele ``wo``-Bedingungen.
AUSWAHL: Final = frozenset({"liste", "wo", "feld"})
MAX_WO: Final = 5

TeilLader = Callable[[str], Awaitable[Any]]


def verweis(wert: Any) -> tuple[str, str | None] | None:
    """Name und Pfad, wenn ``wert`` ein Verweis ist: ``{"$teil": name}`` oder (K2d-1)
    ``{"$teil": name, "pfad": text}``; sonst ``None``. Die Form von Name und Pfad prüft erst, wer
    einsetzt (ein ungültiger fehlt) bzw. die Prüfung des Ablaufs."""
    if not isinstance(wert, dict) or not isinstance(wert.get(SCHLUESSEL), str):
        return None
    if len(wert) == 1:
        return wert[SCHLUESSEL], None
    if len(wert) == 2 and isinstance(wert.get(PFAD_SCHLUESSEL), str):
        return wert[SCHLUESSEL], wert[PFAD_SCHLUESSEL]
    if ist_auswahl(wert):
        return wert[SCHLUESSEL], wert.get("liste")
    return None


def alle_verweise(wert: Any, *, bis: int = TIEFE, tiefe: int = 0
                  ) -> list[tuple[str, str | None, Any, int]]:
    """Name, Pfad (bei einer Auswahl ihre ``liste``), Verweis-Objekt und Tiefe jedes ``$teil`` in
    ``wert`` — die oberste Ebene hat Tiefe 0, tiefer als ``bis`` wird nicht gesucht. Der eine
    Wanderer für Treiber-Tiefe (``TIEFE``) und die Formprüfungen (größere Tiefe; Querschnitts-Review
    AS-D, Befund 6)."""
    if tiefe > bis:
        return []
    if (v := verweis(wert)) is not None:
        return [(v[0], v[1], wert, tiefe)]
    if isinstance(wert, dict):
        return [n for x in wert.values() for n in alle_verweise(x, bis=bis, tiefe=tiefe + 1)]
    if isinstance(wert, list):
        return [n for x in wert for n in alle_verweise(x, bis=bis, tiefe=tiefe + 1)]
    return []


def ist_auswahl(wert: Any) -> bool:
    """AS-Da: ist ``wert`` ein Verweis mit Auswahl (``liste``/``wo``/``feld``, kein ``pfad``)?
    Die Form der Glieder prüft :func:`auswahl_fehler`; eine falsche Form setzt nichts ein."""
    if not isinstance(wert, dict) or not isinstance(wert.get(SCHLUESSEL), str):
        return False
    rest = set(wert) - {SCHLUESSEL}
    return (bool(rest) and rest <= AUSWAHL
            and all(isinstance(wert[k], str) for k in ("liste", "feld") if k in wert)
            and ("wo" not in wert or isinstance(wert["wo"], dict)))


def auswahl_fehler(wert: Any) -> list[str]:
    """Was an der Form einer Auswahl nicht stimmt (leer: gültig) — für die Prüfung."""
    if not ist_auswahl(wert):
        return []
    fehler = [k for k in ("liste", "feld") if k in wert and not PFAD.match(wert[k])]
    wo = wert.get("wo") or {}
    if len(wo) > MAX_WO:
        fehler.append(f"wo>{MAX_WO}")
    fehler += [f"wo.{str(k)[:40]}" for k, v in wo.items()
               if not isinstance(k, str) or not PFAD.match(k)
               or not (v is None or isinstance(v, str | int | float | bool))]
    return fehler


_FEHLT: Final = object()


def _zahl(x: Any) -> bool:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _genau(a: Any, b: Any) -> bool:
    """Gleich, auch im Typ — ``True`` ist nicht ``1``, ``"1"`` nicht ``1``; Zahlen als Zahl
    (``1.0`` ist ``1``: JSON unterscheidet sie nicht, Review AS-Da, Befund 5)."""
    if _zahl(a) and _zahl(b):
        return a == b
    return type(a) is type(b) and a == b


def _an(eintrag: Any, pfad: str) -> Any:
    """Die Stelle ``pfad`` in ``eintrag`` — :data:`_FEHLT`, wenn es sie nicht gibt; anders als
    :func:`stelle` bleibt ein gespeichertes ``null`` ``None`` (Review AS-Da, Befund 2: ``wo`` mit
    ``null`` sucht Einträge, in denen ``null`` STEHT, nicht solche ohne die Stelle)."""
    for glied in pfad.split("."):
        if isinstance(eintrag, dict) and glied in eintrag:
            eintrag = eintrag[glied]
        elif (isinstance(eintrag, list) and glied.isdigit()
              and (glied == "0" or not glied.startswith("0")) and int(glied) < len(eintrag)):
            eintrag = eintrag[int(glied)]
        else:
            return _FEHLT
    return eintrag


def aufloesen(inhalt: Any, wert: Any) -> Any:
    """Die Stelle eines Verweises im Teil ``inhalt`` — mit Pfad, oder (AS-Da) die Auswahl.
    ``None``: es gibt sie nicht (bzw. die Auswahl trifft auf keine Liste oder ist kaputt)."""
    v = verweis(wert)
    if v is None:
        return None
    if not ist_auswahl(wert):
        return stelle(inhalt, v[1])
    if auswahl_fehler(wert):
        return None
    liste = stelle(inhalt, wert.get("liste"))
    if not isinstance(liste, list):
        return None
    wo = wert.get("wo") or {}
    # nur Objekte können passen — ein Text oder eine Zahl in der Liste hat keine Felder
    treffer = [e for e in liste if isinstance(e, dict)
               and all((x := _an(e, k)) is not _FEHLT and _genau(x, soll)
                       for k, soll in wo.items())]
    if "feld" not in wert:
        return treffer
    return [x for e in treffer if (x := stelle(e, wert["feld"])) is not None]


def _verweis(wert: Any) -> str | None:
    v = verweis(wert)
    return v[0] if v else None


def stelle(inhalt: Any, pfad: str | None) -> Any:
    """Die Stelle ``pfad`` in ``inhalt`` (ohne Pfad der ganze Inhalt); ``None``, wenn es sie nicht
    gibt oder der Pfad keine gültige Form hat. Listenstellen sind Ziffern ohne führende Null (``0``,
    ``12`` — nicht ``01``, Review K2d-1, Befund 3). Steht an der Stelle ``null``, gilt sie wie ein
    fehlender Teil als fehlend (Befund 2: ein Schritt bekommt nie ``null`` statt eines Werts)."""
    if pfad is None:
        return inhalt
    if not PFAD.match(pfad):
        return None
    for glied in pfad.split("."):
        if isinstance(inhalt, dict) and glied in inhalt:
            inhalt = inhalt[glied]
        elif (isinstance(inhalt, list) and glied.isdigit()
              and (glied == "0" or not glied.startswith("0")) and int(glied) < len(inhalt)):
            inhalt = inhalt[int(glied)]
        else:
            return None
    return inhalt


def bezeichnung(name: str, pfad: str | None) -> str:
    """Wie ein fehlender Verweis heißt — ``volltext`` oder ``volltext.outputs.markdown``."""
    return name if pfad is None else f"{name}.{pfad}"


def darf(werkzeug: str, teil: str) -> bool:
    """Darf ``werkzeug`` den Teil ``teil`` bekommen? (siehe Modulkopf)"""
    from boerdi.domain.write_confirm import is_confirmable
    from boerdi.ui_module import katalog

    if is_confirmable(werkzeug):
        return True
    manifest = katalog.katalog().get(werkzeug) or {}
    return teil in ((manifest.get("vorgang") or {}).get("liest") or [])


#: Größter Teil, der an ein Werkzeug der KI geht (als JSON, Bytes).
MAX_BYTES: Final = 64_000


def _zu_gross(inhalt: Any) -> bool:
    return len(json.dumps(inhalt, ensure_ascii=False, default=str).encode()) > MAX_BYTES


async def einsetzen(args: dict[str, Any], teile: TeilLader | None, werkzeug: str | None = None
                    ) -> tuple[dict[str, Any], list[str]]:
    """``args`` mit eingesetzten Teilen und die Namen, die fehlten oder ``werkzeug`` nicht bekommen
    darf (:func:`darf`; ohne ``werkzeug`` keine Prüfung — für den Treiber eines geprüften Ablaufs).
    Ohne Verweis dasselbe Objekt."""
    if not isinstance(args, dict) or not any(alle_verweise(v, tiefe=1) for v in args.values()):
        return args, []
    fehlt: list[str] = []

    async def ersetze(wert: Any, tiefe: int) -> Any:
        if tiefe > TIEFE:
            return wert
        if tiefe > 0 and (v := verweis(wert)) is not None:
            name, pfad = v
            erlaubt = werkzeug is None or darf(werkzeug, name)
            inhalt = (await teile(name) if erlaubt and teile is not None and NAME.match(name)
                      else None)
            # K2d-1: die Freigabe gilt dem Teil, die Grenze unten dem ausgewählten Wert;
            # AS-Da: auch einer Auswahl
            inhalt = aufloesen(inhalt, wert) if inhalt is not None else None
            # Querschnitts-Review 2026-11-06: an ein Werkzeug höchstens ``MAX_BYTES`` — ein
            # Auftragsergebnis (bis 1 MB) läge sonst im Abnahme-Merkposten der Sitzung und käme mit
            # der Vorschau zurück ans Modell. Das gilt auch für einen WLO-Werkzeug-Schritt eines
            # Ablaufs (der Treiber nennt sein Ziel); ohne ``werkzeug`` (Dienst-, Auftrags- und
            # Modul-Schritte des Treibers) geht der ganze Teil (Review Q3, Befund 13).
            if inhalt is None or (werkzeug is not None and _zu_gross(inhalt)):
                fehlt.append(bezeichnung(name, pfad))
                return wert
            return copy.deepcopy(inhalt)
        if isinstance(wert, dict):
            return {k: await ersetze(v, tiefe + 1) for k, v in wert.items()}
        if isinstance(wert, list):
            return [await ersetze(v, tiefe + 1) for v in wert]
        return wert

    neu = await ersetze(args, 0)
    return neu, fehlt


def fehlertext(fehlt: list[str]) -> str:
    namen = ", ".join(sorted(set(fehlt)))[:200]
    return (f"Fehler: {namen} ist im Arbeitsstand nicht vorhanden, für dieses Werkzeug nicht "
            "freigegeben oder zu groß dafür. Rufe es nicht mit diesem Verweis; Teile bekommen nur "
            "Werkzeuge mit Vorschau und Module, die sie lesen.")
