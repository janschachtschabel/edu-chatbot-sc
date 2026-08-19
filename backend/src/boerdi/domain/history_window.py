"""Der Gesprächsverlauf, wie er in einen Prompt gehört (H8-3).

Bisher war der Verlauf nur nach **Anzahl** gedeckelt (``history[-10:]``) und
nicht nach Größe. Über 490 gespeicherte Nachrichten gemessen: Median 95 Zeichen,
p95 3 904, Maximum 8 190. Der Regelfall ist also leicht — der Randfall aber
10 × 8 190 Zeichen ≈ 20 500 Token, und die stehen im Prompt **jeder Runde** der
Agent-Schleife, bevor der Lauf ein einziges Werkzeug gerufen hat.

**Die jüngste Nachricht hat Vorfahrt, und das ist der Kern.** Ein Deckel, der
alle Nachrichten gleich behandelt, spart Token und nimmt der iterativen
Nachbearbeitung (M11: „mach den zweiten Punkt kürzer") ihren Gegenstand. Also:
die letzte Nachricht behält viel Raum, ältere wenig, und wenn die Summe trotzdem
zu groß ist, fällt das **Älteste** heraus. Die jüngste bleibt immer — ein Zug
ganz ohne Verlauf wäre schlimmer als einer mit gekürztem.

Gekürzt wird **sichtbar**: der Hinweis sagt dem Modell, dass es einen Ausschnitt
liest. Stillschweigend gekürzter Text sieht wie ein vollständiger aus, und das
Modell würde über einen Abschnitt urteilen, den es nie gesehen hat.

**Die Messung oben hat ein Verfallsdatum, und das ist wichtig.** Sie entstand,
als ``ChatRequest.message`` noch bei 10 000 Zeichen gedeckelt war — das Maximum
von 8 190 konnte die Grenze gar nicht überschreiten. Seit dem Wegfall des
Deckels (2026-08-18) ist die Nachricht nach oben offen: eine Gastanwendung
reicht ganze Seiteninhalte herein. Die Zahlen beschreiben also weiter den
Regelfall, aber nicht mehr den schlimmsten. Genau deshalb deckelt dieses Fenster
nach ZEICHEN und nicht nach einem Vielfachen einer gemessenen Nachrichtengröße:
es hält auch, wenn die Eingabe jede Annahme sprengt.

Rein und ohne I/O: der Aufrufer entscheidet, welchen Verlauf er hereingibt.
"""

from __future__ import annotations

from typing import Any, Final

#: Raum für die jüngste Nachricht. Großzügig, weil sich Rückfragen auf sie
#: beziehen — sie ist der Gegenstand des nächsten Zuges, nicht bloß Kontext.
MAX_ZEICHEN_JUENGSTE: Final = 4000

#: Raum für alle älteren. Knapp: sie stiften Zusammenhang („worüber sprechen
#: wir"), und dafür reicht der Anfang einer Antwort.
MAX_ZEICHEN_AELTERE: Final = 1200

#: Deckel über das ganze Fenster. Bindet, bevor 10 × ``MAX_ZEICHEN_AELTERE``
#: zusammenkommen — bei zehn langen Zügen fällt also der Anfang des Gesprächs weg.
MAX_ZEICHEN_GESAMT: Final = 9000

KUERZUNGS_HINWEIS: Final = "\n[… Rest dieser Nachricht gekürzt]"


def _gekuerzt(inhalt: object, deckel: int) -> str:
    text = inhalt if isinstance(inhalt, str) else ""
    if len(text) <= deckel:
        return text
    return text[:deckel].rstrip() + KUERZUNGS_HINWEIS


def verlaufs_fenster(
    history: list[dict[str, Any]],
    *,
    max_nachrichten: int,
    juengste: int = MAX_ZEICHEN_JUENGSTE,
    aeltere: int = MAX_ZEICHEN_AELTERE,
    gesamt: int = MAX_ZEICHEN_GESAMT,
) -> list[dict[str, Any]]:
    """Der Verlauf, gedeckelt nach Anzahl **und** Zeichen.

    Kopiert jede Nachricht, die es kürzt — ``ctx.history`` gehört dem Zug und
    wird noch anderswo gelesen (``assess``, ``context_greeting``).
    """
    fenster = list(history[-max_nachrichten:]) if max_nachrichten > 0 else []
    if not fenster:
        return []

    beschnitten = [
        {**m, "content": _gekuerzt(m.get("content"),
                                   juengste if i == len(fenster) - 1 else aeltere)}
        for i, m in enumerate(fenster)
    ]

    # Von vorn wegwerfen, bis die Summe passt — aber nie die letzte Nachricht.
    while len(beschnitten) > 1 and sum(len(m["content"]) for m in beschnitten) > gesamt:
        beschnitten.pop(0)
    return beschnitten
