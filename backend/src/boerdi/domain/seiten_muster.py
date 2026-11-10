"""Pfadmuster für Führungen (Paket AS-7a, Plan 2026-11-09 §5m, F-3).

Ein Muster beginnt mit ``/`` und kennt nur ``*`` als Platzhalter (beliebig viele Zeichen, auch
``/``). Verglichen wird der normalisierte Pfad der Seite — ohne Herkunft, Anfrage und Anker,
klein geschrieben, ohne Schrägstrich am Ende (wie die Tour, ``domain/tour._norm_path``). Keine
regulären Ausdrücke: Die Redaktion liest die Muster wie die Wendungen der Text-Auslöser. Der
Vergleich ist linear (:func:`_passt_eins`) und die Seite gekappt, sodass weder Muster noch eine
lange Seite des Clients einen Rückschritt-Sturm (ReDoS) auslösen.

Rein, ohne Abhängigkeiten außerhalb von ``domain``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from boerdi.domain.tour import _norm_path

#: Höchstens so viele Muster je Liste (Schritt, Regel, Auslöser).
MAX_MUSTER: Final = 10
#: Höchstens so lang ist ein Muster.
MAX_ZEICHEN: Final = 200
#: So viel einer Seite wird verglichen (Review AS-7a, Befund 1).
MAX_SEITE: Final = 1000
#: Erlaubte Zeichen: Pfad-Zeichen und ``*`` — keine Klammern, kein ``?`` (fnmatch-Sonderzeichen,
#: die die Redaktion nicht meint).
#: Ohne Komma (Querschnitts-Review AS-7, Befund 9): der Regel-Editor trennt Muster an Kommas.
_ERLAUBT: Final = re.compile(r"^/[A-Za-z0-9._~%!$&'()+;=:@/*-]*$")


def normalisiert(seite: str | None) -> str:
    """Der verglichene Pfad: ``https://host/A/?x#y`` → ``/a``; leer → ``/``. Gekappt auf
    :data:`MAX_SEITE` (Review AS-7a, Befund 1): die Seite schickt der Client."""
    return _norm_path((seite or "/")[:2 * MAX_SEITE])[:MAX_SEITE]


def _passt_eins(pfad: str, muster: str) -> bool:
    """Glob mit ``*`` in linearer Zeit (Review AS-7a, Befund 1): Anfang und Ende fest, die
    Mittelstücke der Reihe nach mit ``str.find`` — das früheste Vorkommen zu nehmen ist für ``*``
    immer richtig, und es gibt kein Zurückgehen wie bei ``.*`` in ``re``."""
    if muster.endswith("/*") and pfad == (muster[:-2] or "/"):
        # Zweites Review AS-7a, Befund 1: der Pfad wird ohne Schrägstrich am Ende verglichen —
        # ``/mitmachen/*`` meint auch die Einstiegsseite ``/mitmachen/``
        return True
    teile = muster.split("*")
    if len(teile) == 1:
        return pfad == muster
    anfang, *mitte, ende = teile
    if len(pfad) < len(anfang) + len(ende) or not pfad.startswith(anfang) or not pfad.endswith(
            ende):
        return False
    pos, grenze = len(anfang), len(pfad) - len(ende)
    for stueck in mitte:
        if not stueck:
            continue
        treffer = pfad.find(stueck, pos, grenze)
        if treffer < 0:
            return False
        pos = treffer + len(stueck)
    return True


def passt(seite: str | None, muster: Iterable[str]) -> bool:
    """Passt die Seite zu einem der Muster? Ungültige Muster passen nie."""
    pfad = normalisiert(seite)
    return any(not fehler(m) and _passt_eins(pfad, normalisiert(m)) for m in muster)


def fehler(muster: str) -> str | None:
    """Warum ein Muster ungültig ist — ein Code (``leer``, ``lang``, ``form``; die Prüfung übersetzt
    ihn, Querschnitts-Review AS-7, Befund 6) — oder ``None``."""
    if not isinstance(muster, str) or not muster.strip():
        return "leer"
    if len(muster) > MAX_ZEICHEN:
        return "lang"
    if not _ERLAUBT.match(muster.strip()):
        return "form"
    return None
