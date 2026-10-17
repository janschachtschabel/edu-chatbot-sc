"""Die Nachrichtenfolge für die AcademicCloud vorbereiten (E-AC, Paket 7).

Seit Paket B/E-E (Responses-Plan 2026-09-29) steht der Seitenkontext gerahmt als
user-Nachricht vor dem Verlauf. Beginnt der Verlauf mit der Person oder ist er
leer, folgen zwei user-Nachrichten aufeinander — wie schon vorher bei einer
verwaisten Nutzernachricht im Verlauf. Dasselbe gibt es auf der anderen Seite:
der Kontext-Gruß speichert eine Bot-Nachricht ohne Frage, nach einer Antwort und
seit T2 nach dem alten Gruß beim Sprachwechsel (Review Paket 7, B-4). OpenAI nimmt
beides an (gemessen). Chat-Vorlagen offener Modelle verlangen teils den strengen
Wechsel user/assistant (ältere Mistral-Vorlagen werfen sonst). Die eingestellten
AcademicCloud-Modelle ließen sich am 2026-10-09 nicht proben: das Chat-Modell
antwortete 503 („Model pricing unavailable“), die Probe danach lief ins
Ratenlimit (429).

Deshalb legt der Transport gleiche Rollen hintereinander dort zusammen, mit
Leerzeile getrennt — inhaltlich dasselbe, und der Rahmen bleibt im Text erhalten.
Nur Text: Teile-Listen (Bilder, Dateien) und Werkzeugaufrufe bleiben, wie sie sind.
"""

from __future__ import annotations

from typing import Any


def _ist_text(nachricht: dict[str, Any]) -> bool:
    return (nachricht.get("role") in ("user", "assistant")
            and isinstance(nachricht.get("content"), str)
            and not nachricht.get("tool_calls"))


def rollenfolge_zusammenlegen(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aufeinanderfolgende Texte derselben Rolle (user oder assistant) als EINER,
    mit Leerzeile getrennt.

    Gibt dieselbe Liste zurück, wenn es nichts zusammenzulegen gibt; die Eingabe
    wird nie verändert.
    """
    aus: list[dict[str, Any]] = []
    for nachricht in messages:
        vorige = aus[-1] if aus else None
        if (vorige is not None and _ist_text(nachricht) and _ist_text(vorige)
                and nachricht["role"] == vorige["role"]):
            aus[-1] = {**vorige, "content": f"{vorige['content']}\n\n{nachricht['content']}"}
        else:
            aus.append(nachricht)
    return messages if len(aus) == len(messages) else aus
