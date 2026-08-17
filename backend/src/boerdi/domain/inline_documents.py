"""Das Ergebnis-Dokument als Werkzeug (D1) — die Box wird geliefert, nicht geraten.

**Warum es das gibt.** ``turn_persist`` entscheidet über die Inline-Box bislang
aus dem Antworttext: Muster ∈ {M09, M10, M11}, mindestens 200 Zeichen, und ein
H1, an dem ``inline_rendering`` Vorspann und Rumpf trennt. Vier Bedingungen, die
zufällig zusammentreffen müssen — und drei davon wählt das Modell frei. Live
gemessen (2026-08-17, Skill „Stunde planen"): das Muster stimmte, der Text war
eine Zusammenfassung ohne Überschrift, und ein fertiger Verlaufsplan fiel weg.

Damit hing die Box auch an der **Schrittzahl**: eine Rückfrage zwischendrin
verschob das Ergebnis in einen Zug, in dem die Vermutung nicht mehr griff. Ein
Zwischenschritt darf ein Arbeitsergebnis nicht kosten.

Hier ruft das Modell stattdessen ``zeige_dokument`` — dieselbe Mechanik wie
``submit_result`` und ``waehle_vorgehen``: ein virtuelles Werkzeug, das die
Schleife am Namen abfängt, bevor irgendein MCP-Aufruf passiert. Titel, Art und
Markdown kommen als Argumente; Länge, Überschrift, Muster und Zug sind
gleichgültig.

**Die Anweisung sitzt an der Werkzeugbeschreibung**, nicht im Fließtext eines
Musters. Ein Muster- oder Skill-Text darf sie verstärken; nötig ist er nicht —
genau das macht die Box unabhängig davon, wie die Redaktion einen Skill
formuliert.

**Rein**: keine I/O, keine App-Abhängigkeiten — dieselbe Heimat wie
``content_types``/``search_intent``. Der Dispatch liegt in den Schleifen.
"""

from __future__ import annotations

from typing import Any, Final

#: Der Name, an dem die Schleifen das Dokument erkennen. Konstante statt
#: Literal, weil ihn mehrere Module vergleichen (hier gebaut, in ``agent_loop``
#: und ``tool_loop`` erkannt) — dieselbe Begründung wie bei ``SUBMIT_RESULT``.
ZEIGE_DOKUMENT: Final = "zeige_dokument"

#: Die Formen, die eine Box annehmen kann — Kennung → Erklärung für das Modell.
#:
#: Die ersten fünf sind der Bestand (``inline_rendering._INLINE_DOC_KIND_BY_PATTERN``
#: plus die zwei, die das Widget schon kennt). Die fünf danach sind der
#: Nutzer-Entscheid vom 2026-08-17: die Formen, die die freigegebenen Skills
#: tatsächlich erzeugen.
#:
#: **Kein Frontend-Zwang.** Gemessen in ``ui/src/inline-doc/inline-doc.ts``:
#: die Box zeigt ``doc.title || fallbackLabel(doc.kind)``, und ``fallbackLabel``
#: hat einen ``default``-Zweig („Inhalt"), das Icon ebenso. Eine unbekannte Art
#: rendert also sauber mit dem gelieferten Titel. Eigene Etiketten und Icons je
#: neuer Art wären Kür — und die kosten einen Widget-Neubau.
DOKUMENT_ARTEN: Final[dict[str, str]] = {
    "lernpfad": "eine Abfolge aufeinander aufbauender Materialien",
    "ki_material": "ein erzeugtes Material (Arbeitsblatt, Quiz, Aufgabenset)",
    "edit": "eine überarbeitete Fassung eines vorher gezeigten Inhalts",
    "bericht": "eine Auswertung oder Pruefzusammenfassung",
    "remix": "eine Zusammenstellung aus vorhandenen Inhalten",
    "stundenplanung": "ein Verlaufsplan fuer EINE Unterrichtsstunde",
    "unterrichtsreihe": "eine Planung ueber mehrere Stunden hinweg",
    "zeugnis": "ein Zeugnis oder eine Beurteilung",
    "dokument": "ein Brief oder ein sonstiges Schriftstueck",
    "kompendialtext": "ein Kompendialtext (Fachtext zu einem Gegenstand)",
}

#: Die Art, auf die eine unbekannte Kennung fällt. Zurückweisen wäre falsch —
#: der Inhalt ist da, nur das Etikett passt nicht.
_RUECKFALL_ART: Final = "dokument"

#: Wie viele Boxen ein Zug tragen darf. Eine muss gehen, mehrere sind die
#: Option (Nutzer-Entscheid): ein Skill, der Verlaufsplan UND Arbeitsblatt
#: liefert, ist der Fall dafür. Der Deckel hält eine Endlosschleife davon ab,
#: die Antwort zu sprengen.
MAX_DOKUMENTE_JE_ZUG: Final = 3

#: Deckel je Dokument. Gedeckelt statt verworfen: wegwerfen vernichtete die
#: Arbeit des ganzen Zuges, kürzen erhält sie sichtbar.
MAX_MARKDOWN_ZEICHEN: Final = 40_000

#: Deckel für den Titel — er steht in einer Kopfzeile, nicht in einem Absatz.
MAX_TITEL_ZEICHEN: Final = 160

_KUERZUNGS_HINWEIS: Final = "\n\n*(gekuerzt — der Inhalt war zu lang)*…"

#: Der Titel wird glatt geschnitten. Er steht in einer KOPFZEILE, und die Box
#: interpoliert ihn (``{{ doc.title }}``, ``inline-documents.component.ts``)
#: statt ihn zu rendern — der erklärende Hinweis des Rumpfes stünde dort samt
#: Leerzeile und Sternchen wörtlich in der Überschrift.
_TITEL_HINWEIS: Final = "…"

_BESCHREIBUNG: Final = (
    "Uebergib ein fertiges Arbeitsergebnis, damit es als eigene Box angezeigt "
    "wird — Verlaufsplan, Unterrichtsreihe, Arbeitsblatt, Lernpfad, Zeugnis, "
    "Brief oder Fachtext.\n\n"
    "WANN: sobald das Ergebnis fertig ist, im selben Zug. Rueckfragen vorher "
    "sind in Ordnung und kosten nichts — entscheidend ist, dass das Ergebnis "
    "hier landet und nicht nur beschrieben wird.\n\n"
    "WIE: ``markdown`` traegt das VOLLSTAENDIGE Ergebnis. Fasse es nicht "
    "zusammen und kuendige es nicht bloss an. Deine Prosa-Antwort daneben ist "
    "nur der Begleitsatz (ein bis zwei Saetze); der Inhalt gehoert in dieses "
    "Werkzeug.\n\n"
    "VERFUEGBARE ARTEN:\n"
)


def dokument_werkzeug() -> dict[str, Any]:
    """Die Werkzeugdefinition — Titel, Art, Markdown, alle drei Pflicht.

    Alle drei sind Pflicht, weil jedes fehlende Feld die Box unbrauchbar macht:
    ohne Titel keine Kopfzeile, ohne Art kein Icon, ohne Markdown kein Inhalt.
    """
    arten = "\n".join(f"- `{art}` — {was}" for art, was in DOKUMENT_ARTEN.items())
    return {
        "type": "function",
        "function": {
            "name": ZEIGE_DOKUMENT,
            "description": _BESCHREIBUNG + arten,
            "parameters": {
                "type": "object",
                "properties": {
                    "titel": {
                        "type": "string",
                        "description": (
                            "Die Ueberschrift der Box, z. B. "
                            "'Unterrichtsverlaufsplan: Einfuehrung in die Optik'."
                        ),
                    },
                    "art": {
                        "type": "string",
                        "enum": list(DOKUMENT_ARTEN),
                        "description": "Die Form des Ergebnisses, siehe Liste oben.",
                    },
                    "markdown": {
                        "type": "string",
                        "description": (
                            "Das vollstaendige Ergebnis als Markdown — Tabellen, "
                            "Listen und Ueberschriften sind erlaubt."
                        ),
                    },
                },
                "required": ["titel", "art", "markdown"],
            },
        },
    }


def _text(wert: object, deckel: int, hinweis: str = _KUERZUNGS_HINWEIS) -> str:
    """Eine gedeckelte Zeichenkette, oder ``""`` wenn es keine war.

    ``hinweis`` steht am Schnitt. Für den Rumpf ist der erklärende Satz richtig
    — dort ist Platz, und ohne ihn sähe der Abbruch nach einem Fehler aus. Für
    den Titel wäre er falsch, siehe :data:`_TITEL_HINWEIS`.
    """
    if not isinstance(wert, str):
        return ""
    sauber = wert.strip()
    if len(sauber) <= deckel:
        return sauber
    return sauber[:deckel].rstrip() + hinweis


def dokument_aus_argumenten(args: object) -> dict[str, Any] | None:
    """Werkzeug-Argumente → Inline-Dokument, oder ``None``.

    ``None`` heisst „das war kein brauchbares Dokument" — der Aufrufer meldet
    das als Werkzeugfehler zurueck und laesst den Lauf weiterlaufen, statt ihn
    abzubrechen (dieselbe Entscheidung wie B8 bei unlesbaren Argumenten).

    Geprueft wird streng, denn Werkzeug-Argumente sind Modell-Ausgabe und damit
    unvertraute Eingabe: Nicht-Zeichenketten fallen heraus, leere Felder
    ebenfalls. Eine unbekannte ``art`` dagegen faellt nur auf
    :data:`_RUECKFALL_ART` zurueck — der Inhalt ist ja da.

    Die Rueckgabe hat genau die Form, die ``InlineDocument`` im Frontend
    erwartet (``kind``/``title``/``content``/``meta``,
    ``ui/src/grouping/message-types.ts``).
    """
    if not isinstance(args, dict):
        return None
    titel = _text(args.get("titel"), MAX_TITEL_ZEICHEN, _TITEL_HINWEIS)
    markdown = _text(args.get("markdown"), MAX_MARKDOWN_ZEICHEN)
    if not titel or not markdown:
        return None
    art = args.get("art")
    art = art if isinstance(art, str) and art in DOKUMENT_ARTEN else _RUECKFALL_ART
    # ``source: tool`` unterscheidet die gelieferte Box von der geratenen —
    # ohne diesen Vermerk liesse sich in den Logs nicht sehen, welcher der
    # beiden Wege den Zug getragen hat.
    return {"kind": art, "title": titel, "content": markdown,
            "meta": {"source": "tool"}}
