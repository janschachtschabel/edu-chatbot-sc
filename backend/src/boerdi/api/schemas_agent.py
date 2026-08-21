"""Ein- und Ausgabe des Agent-Endpunkts (A3a).

Eine eigene Form und nicht ``ChatRequest``: der Gastgeber ist eine Maschine, kein
Mensch im Chat. Er hat keine Sitzung, kein Widget, keinen Seitenkontext — dafür
eine Anweisung, wahlweise Knoten und eine Sammlung, und die Erwartung, ein
**maschinenlesbares** Ergebnis zurückzubekommen. In ``ChatRequest`` gequetscht
wäre jedes zweite Feld unwahr.

``result_schema`` ist absichtlich ein freies Dict: es reist wörtlich in die
Parameter von ``submit_result``, der Anbieter erzwingt die Form, und dieser Code
muss über die Struktur nichts wissen. „Bewerte die Sachrichtigkeit von 0–5" ist
damit ausdrückbar, ohne dass hier je von Sachrichtigkeit die Rede war.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

#: Die Obergrenze von ``get_nodes_details`` (gemessen an der Werkzeug-
#: beschreibung). Der Deckel steht hier am Rand und nicht erst beim Abruf: eine
#: Liste mit 500 IDs ergäbe sonst einen stillen Teilabruf, und der Aufrufer
#: hielte das Ergebnis für vollständig.
MAX_NODE_IDS = 50


class AgentRequest(BaseModel):
    """Der Auftrag eines Gastgebers."""

    #: 200 000 = Skala des ``result_schema``-Deckels (EK10b, 2026-08-21) —
    #: der alte 20 000er-Deckel war der häufigste 422-Grund, wenn Gastgeber
    #: Seitentext in den Auftrag geben. Notbremse, kein Erwartungswert.
    instruction: str = Field(..., max_length=200000)
    #: Die Sammlung, aus der die Anleitungen ('Skills') für diese Aufgabe
    #: kommen. Wird vorab aufgelöst — wer sie mitschickt, will sie genutzt sehen.
    collection_id: str | None = None
    node_ids: list[str] = Field(default_factory=list, max_length=MAX_NODE_IDS)
    result_schema: dict[str, Any] | None = None
    #: ``None`` = die Vorgabe aus ``01-base/engine``. ``execute`` gilt nur mit
    #: persönlicher Anmeldung — siehe ``services/agent_run._limits``.
    write_mode: Literal["propose", "execute"] | None = None
    allow_curation: bool = True
    #: Sprache der Ausgabe (``de``/``en``); ``None`` = die Vorgabe des Hauses.
    locale: str | None = None

    @field_validator("instruction")
    @classmethod
    def _nicht_leer(cls, wert: str) -> str:
        if not wert.strip():
            raise ValueError("instruction darf nicht leer sein")
        return wert


class AgentResponse(BaseModel):
    """Das Ergebnis eines Laufs.

    ``stop_reason`` gehört zur Antwort und nicht ins Protokoll: ein Lauf, der an
    der Frist abgeschnitten wurde, sähe von außen sonst aus wie einer, der
    fertig geworden ist. Wer auswertet, muss beides unterscheiden können.
    """

    text: str
    result: Any = None
    stop_reason: str
    iterations: int
    tools_called: list[str] = Field(default_factory=list)
