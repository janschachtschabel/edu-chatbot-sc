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

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

#: Name eines UI-Moduls: ``ui_`` plus Kleinbuchstaben, Ziffern, Unterstrich (Paket U1).
UI_MODUL_NAME = r"^ui_[a-z0-9_]{2,40}$"


class UiBlock(BaseModel):
    """Ein Aufruf eines UI-Moduls in einer Bot-Antwort (Paket U1).

    ``text`` ist die Textfassung: Sie steht da, wo das Widget das Modul nicht kennt (ältere
    Widgets, ``/api/agent``). Anzeigende Blöcke sind ``nur_anzeige``; ein abfragender ist
    ``offen``, bis die Person antwortet.
    """

    block_id: str = Field(pattern=r"^[a-z0-9]{8,32}$")
    modul: str = Field(pattern=UI_MODUL_NAME)
    version: int = Field(ge=1, le=99)
    art: Literal["anzeigen", "abfragen"]
    daten: dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    status: Literal["offen", "beantwortet", "nur_anzeige", "veraltet"] | None = None
    antwort: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _status_nach_art(self) -> UiBlock:
        if self.status is None:
            self.status = "offen" if self.art == "abfragen" else "nur_anzeige"
        return self


class UiAntwort(BaseModel):
    """Die Antwort der Person auf einen abfragenden Block (Paket U1-d1), an der Anfrage.

    ``daten`` folgt dem Antwort-Schema des Moduls (``manifest.antwort``); geprüft wird im ersten
    Knoten des Zugs gegen die offene Frage der Sitzung (``services/ui_antwort``). Passt sie nicht,
    fällt sie weg, und ``message`` zählt wie getippt. ``message`` bleibt die lesbare Antwort —
    sie ist die Nutzerblase und steht so im Verlauf.
    """

    block_id: str = Field(pattern=r"^[a-z0-9]{8,32}$")
    daten: dict[str, Any] = Field(default_factory=dict)


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
    # Seit U1-b2 steht die Box vollständig als Block; diese gekürzte Fassung liest das Widget seit
    # U1-b3 nicht mehr. Intern bleibt sie der Kontext des Folgezugs (``agent_zugblock``).
    dokumente: list[dict[str, Any]] = Field(
        default_factory=list, json_schema_extra={"deprecated": True},
        description="Veraltet seit U1-b2 — die Boxen stehen als ui_inhaltsrahmen in ui_bloecke.")
    topic_page_view: dict[str, Any] | None = None
    # Nur für den Folgezug, der eine Antwort aus dem Verlauf liest — nie beim Wiederherstellen
    # nach dem Neuladen ausführen, sonst liefe die Änderung ein zweites Mal
    # (``domain/prepared_write``).
    prepared_write: dict[str, Any] | None = None
    # Paket U1: die UI-Module dieser Antwort — live und im Verlauf.
    ui_bloecke: list[UiBlock] = Field(default_factory=list)
