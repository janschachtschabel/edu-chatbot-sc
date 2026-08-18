"""Das maschinenlesbare Ergebnis als eigener Kanal (J1) — geliefert, nicht beendet.

**Warum es das gibt.** Bis zum 2026-08-17 trug ``submit_result`` beides in EINEM
Aufruf — ``text`` für den Menschen, ``result`` für die Gastanwendung — und
beendete den Lauf in derselben Bewegung. Danach gab es keinen Zug mehr, in dem
Prosa hätte entstehen können. Live gemessen (Sammlung „Optik", Hybrid, Schema mit
einem Feld ``befund``): **196 Zeichen im Chat gegen 1932 im Ergebnis**. Das ist
keine Modell-Laune, sondern die Bauform: zwei Aufgaben teilen sich einen Aufruf,
und das Feld, das der Gastgeber ausdrücklich benannt hat, gewinnt.

Hier ist das Ergebnis ein **eigener Kanal**, virtuell wie ``zeige_dokument`` und
``waehle_vorgehen``: die Schleife fängt den Namen ab, notiert das Ergebnis und
läuft **weiter**. Die Antwort für die Person entsteht danach als gewöhnlicher
Zug, und der Lauf endet über ``stop_reason='text'`` wie jeder andere.

**Der Unterschied zum Dokument-Werkzeug ist der Wortlaut, und er ist kein
Detail.** Eine Dokument-Box steht IM Chat — deshalb sagt ``zeige_dokument``
ausdrücklich, die Prosa daneben sei nur ein Begleitsatz. Das Ergebnis dagegen
geht an die Anwendung und ist auf dem Bildschirm **unsichtbar**. Denselben Satz
hier zu wiederholen, hieße die gemessene Lücke festzuschreiben.

**``submit_result`` bleibt unverändert** — es gehört jetzt ``/api/agent``: dort
gibt es keinen Chat, ``text`` IST die Lieferung, und das Ende am Werkzeug ist
richtig. Zwei Namen statt eines Schalters, weil es zwei Bedeutungen sind; ein
Name, der mal beendet und mal nicht, wäre die teurere Sparsamkeit.

**Rein**: keine I/O, keine App-Abhängigkeiten — dieselbe Heimat wie
``inline_documents``. Der Dispatch liegt in der Schleife.
"""

from __future__ import annotations

from typing import Any, Final

#: Der Name, an dem die Schleife das Ergebnis erkennt. Konstante statt Literal,
#: weil ihn mehrere Module vergleichen — dieselbe Begründung wie bei
#: ``ZEIGE_DOKUMENT`` und ``SUBMIT_RESULT``.
LIEFERE_ERGEBNIS: Final = "liefere_ergebnis"

_BESCHREIBUNG: Final = (
    "Uebergib das maschinenlesbare Ergebnis an die Anwendung, in der dieser Chat "
    "eingebettet ist.\n\n"
    "WANN: sobald du es hast, und genau einmal. Ist die Nachricht bloss Gespraech "
    "(Begruessung, Rueckfrage), ruf es NICHT.\n\n"
    "DANACH GEHT ES WEITER: dieses Werkzeug beendet den Lauf nicht. Schreibe im "
    "Anschluss deine gewoehnliche Antwort fuer die Person im Chat — und zwar "
    "VOLLSTAENDIG. Die Person sieht dieses Ergebnis NICHT; es geht an die "
    "Anwendung und nicht auf ihren Bildschirm. Alles, was sie wissen soll, muss "
    "in deiner Antwort stehen. Ein Verweis darauf ist keine Antwort."
)

_RESULT_BESCHREIBUNG: Final = (
    "Das Ergebnis als Objekt, in der Form, die der Gastgeber verlangt hat."
)

#: Die Rückmeldung nach einer Lieferung. Sie ist keine Höflichkeit: ohne sie
#: wüsste das Modell nicht, ob das Ergebnis angekommen ist. Und sie wiederholt
#: die Pflicht zur vollen Antwort, weil die Beschreibung des Werkzeugs zu diesem
#: Zeitpunkt schon einige tausend Zeichen zurückliegt.
ERGEBNIS_UEBERNOMMEN: Final = (
    "Uebernommen — das Ergebnis ist an die Anwendung uebergeben. Schreibe jetzt "
    "deine Antwort fuer die Person im Chat. Sie hat das Ergebnis NICHT gesehen: "
    "sag ihr vollstaendig, was du herausgefunden hast."
)

#: Die Antwort auf einen zweiten Aufruf. Das erste Ergebnis bleibt stehen —
#: ein Modell, das dasselbe zweimal liefert, hat den Auftrag erfüllt und nur die
#: Bestätigung überlesen; es soll schreiben, nicht noch einmal liefern.
BEREITS_GELIEFERT: Final = (
    "Es liegt bereits ein Ergebnis vor; dieser Aufruf wurde verworfen. Schreibe "
    "jetzt deine Antwort fuer die Person im Chat."
)

ERGEBNIS_UNBRAUCHBAR: Final = (
    "Fehler: ``result`` muss ein Objekt sein. Wiederhole den Aufruf mit einem "
    "Objekt in der verlangten Form."
)


def ergebnis_werkzeug(result_schema: dict[str, Any] | None = None) -> dict[str, Any]:
    """Die Werkzeugdefinition — **ein** Feld, und das ist der ganze Punkt.

    Kein ``text`` daneben: genau die Nachbarschaft der beiden Felder in einem
    Aufruf hat die gemessene Lücke erzeugt. Die Prosa hat jetzt ihren eigenen
    Zug und braucht hier keinen Platz.

    Ohne Schema ist ``result`` ein freies Objekt — der Gastgeber bekommt dann,
    was das Modell für nennenswert hält. Mit Schema reist es **wörtlich** in die
    Parameter, und der Anbieter erzwingt die Form über seine eigene
    Werkzeug-Validierung; dieser Code muss über die Struktur nichts wissen.
    """
    return {
        "type": "function",
        "function": {
            "name": LIEFERE_ERGEBNIS,
            "description": _BESCHREIBUNG,
            "parameters": {
                "type": "object",
                "properties": {
                    "result": result_schema or {
                        "type": "object",
                        "description": _RESULT_BESCHREIBUNG,
                    },
                },
                "required": ["result"],
            },
        },
    }


def ergebnis_aus_argumenten(args: object) -> dict[str, Any] | None:
    """Werkzeug-Argumente → Ergebnis-Objekt, oder ``None``.

    ``None`` heisst „das war kein brauchbares Ergebnis" — der Aufrufer meldet es
    als Werkzeugfehler zurueck und laesst den Lauf weiterlaufen, statt ihn
    abzubrechen (dieselbe Entscheidung wie bei ``dokument_aus_argumenten``).

    Nur Objekte: ``ChatResponse.result`` ist ``dict | None``, eine Liste kaeme
    also ohnehin nie beim Gastgeber an. Sie hier abzuweisen sagt dem Modell,
    dass etwas nicht stimmt — bis 2026-08-17 fiel sie stumm heraus, und ein
    Gastgeber sah dann eine leere Antwort ohne jeden Hinweis.
    """
    if not isinstance(args, dict):
        return None
    ergebnis = args.get("result")
    return ergebnis if isinstance(ergebnis, dict) else None
