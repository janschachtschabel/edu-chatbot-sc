"""``ui`` — der öffentliche Teil einer Antwort (Paket 18C/D, Phase 3).

Was das Widget braucht, um eine Antwort darzustellen und nach dem Neuladen wiederherzustellen —
und nichts weiter. Persona, Signale, Entitäten, Spur, Zugakte und jedes künftige Diagnosefeld
stehen nur im Debug-Block, den seit Phase 4 allein das Studio bekommt. Ein eigenes Modell statt
eines Filters: ein neues Feld im Debug-Block ist damit von selbst nicht öffentlich
(Vertragstest ``tests/test_publikum.py``).

Die Wiederherstellungsfelder füllt nur der Verlauf; live kommen dieselben Daten als eigene
Felder der Antwort (``query_metas``, ``web_links``, ``topic_page`` …). Ausnahme ``type_focus``:
es steht in keinem eigenen Feld und kommt seit Phase 4 auch live (``turn_persist``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UiInfo(BaseModel):
    """Öffentlicher Teil einer Antwort; alle Felder optional, Vorgabe leer."""

    pattern: str = ""
    intent: str = ""
    state: str = ""
    tools_called: list[str] = Field(default_factory=list)
    modulations: dict[str, Any] = Field(default_factory=dict)
    # nur im Verlauf (``type_focus`` auch live)
    query_metas: list[dict[str, Any]] = Field(default_factory=list)
    web_links: list[dict[str, Any]] = Field(default_factory=list)
    type_focus: str = ""
    dokumente: list[dict[str, Any]] = Field(default_factory=list)
    topic_page_view: dict[str, Any] | None = None
    # Nur für den Folgezug, der eine Antwort aus dem Verlauf liest — nie beim Wiederherstellen
    # nach dem Neuladen ausführen, sonst liefe die Änderung ein zweites Mal
    # (``domain/prepared_write``).
    prepared_write: dict[str, Any] | None = None
