"""Ein- und Ausgabe des Agent-Endpunkts (A3a).

Eine eigene Form und nicht ``ChatRequest``: der Gastgeber ist eine Maschine, kein
Mensch im Chat. Er hat keine Sitzung, kein Widget, keinen Seitenkontext — dafür
eine Anweisung, wahlweise Knoten und eine Sammlung, und die Erwartung, ein
**maschinenlesbares** Ergebnis zurückzubekommen. In ``ChatRequest`` gequetscht
wäre jedes zweite Feld unwahr.

``result_schema`` ist absichtlich ein freies Dict: es reist wörtlich in die
Parameter von ``submit_result``, und dieser Code muss über die Struktur nichts
wissen. „Bewerte die Sachrichtigkeit von 0–5" ist damit ausdrückbar, ohne dass
hier je von Sachrichtigkeit die Rede war. Der Anbieter erzwingt die Form NICHT
(kein ``strict``); geprüft wird das Ergebnis deshalb in der Schleife
(``domain/ergebnis_schema``, Paket 4 A3), das Schema selbst schon hier.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from boerdi.api.schemas_result import pruefe_ergebnis_schema

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

    @field_validator("result_schema")
    @classmethod
    def _gueltiges_schema(cls, wert: dict[str, Any] | None) -> dict[str, Any] | None:
        # Nur die Gültigkeit, kein Größendeckel: der bleibt hier bewusst offen
        # (siehe ``api/schemas.MAX_RESULT_SCHEMA_CHARS``).
        return None if wert is None else pruefe_ergebnis_schema(wert)


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


class MasterSkillStatus(BaseModel):
    """Der Master-Skill, wie das Studio ihn zeigt (AG-2) — nur lesend.

    Er bleibt im Repositorium: ``edit_url`` öffnet ihn im md-editor des
    Repositoriums, ``view_url`` zeigt den Knoten (Paket F, 2026-09-29; bis dahin
    führte ``edit_url`` auf die Render-Seite). ``sha256`` und ``length``
    beschreiben den Text im Speicher dieses Prozesses, ``text`` ist derselbe
    Wortlaut. ``None`` heißt: keine Kennung gepflegt oder Abruf gescheitert (dann
    steht der Grund in ``last_error``).
    """

    enabled: bool
    node_id: str
    cached: bool
    fetched_at: str | None = None
    length: int | None = None
    sha256: str | None = None
    last_error: str | None = None
    ttl_seconds: int
    text: str | None = None
    edit_url: str | None = None
    view_url: str | None = None
