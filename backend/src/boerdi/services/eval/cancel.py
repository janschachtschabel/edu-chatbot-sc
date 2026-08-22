"""Das Abbruch-Signal beider Lauf-Familien.

Ein eigenes Blatt-Modul ohne Abhängigkeiten, weil ``scenario_gen`` es kennen
muss: dort steht der einzige Ort im Lauf-Weg, der Ausnahmen aus dem
Fortschritts-Rückruf bewusst verschluckt („Progress hook must never break
generation"). Läge die Klasse in ``run_store``, zöge der reine Generator die
gesamte DB-Schicht in seinen Import — läge sie in ``runner``, wäre der Import
zirkulär.

**Warum eine Ausnahme und kein Rückgabewert:** der Abbruch muss aus dem
Fortschritts-Rückruf heraus wirken, und der wird an vier Stellen tief im
Runner aufgerufen. Ein Rückgabewert müsste durch jede davon durchgereicht
werden.
"""

from __future__ import annotations


class RunCancelled(Exception):
    """Der Lauf wurde von außen gestoppt oder gelöscht — kein Fehler.

    Wer sie fängt, beendet still: die Zeile trägt ihren Endstand bereits
    (``cancelled``) oder ist weg. Ein ``failed`` daraus zu machen wäre falsch,
    denn gemessen wurde alles bis zum letzten Prüfpunkt.
    """
