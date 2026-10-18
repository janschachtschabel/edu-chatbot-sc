"""05-knowledge/* + 02-domain/guide-rules + eval/gold-flows areas.
rag-config is the ONLY YAML whose root is a plain area-name mapping.
"""

from typing import Annotated, Any

from pydantic import Field, RootModel

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices, Textarea


class RagAreaDef(AreaModel):
    #: S1: Auswahl statt Freitext. Der Wert entscheidet ueber den MUSTER-Weg —
    #: ``always`` holt den Bereich vor dem ersten Modellzug, ``on-demand`` erst
    #: auf Zuruf. Leer = im Muster-Weg nur, wo ein Muster den Bereich ausdruecklich
    #: nennt; die Agent-Schleife liest allein ``agent`` (Paket 15, A4).
    mode: Annotated[str, Choices("always", "on-demand")] = ""
    description: Annotated[str | None, Textarea()] = None
    #: Q (2026-08-18): darf die Agent-Schleife diesen Bereich
    #: durchsuchen? Vorgabe ``True`` — „alle Bereiche fuer den Agenten"
    #: (Nutzer-Vorgabe). Steht NEBEN ``mode`` und ersetzt ihn nicht: ``mode``
    #: steuert den Muster-Weg (Vorabruf oder Abruf auf Zuruf), dieses Feld
    #: allein die Schleife. Ein Feld fuer beides koennte „im Muster vorab, in
    #: der Schleife gar nicht" nicht ausdruecken. Gelesen von
    #: ``services/agent_knowledge.fuer_die_schleife``.
    agent: bool = True


class RagConfigArea(RootModel[dict[str, RagAreaDef]]):
    pass


class RagAbruf(AreaModel):
    """Werte der Wissenssuche, gelesen von ``rag/retrieval.get_retrieval_settings``.

    Leer = die Vorgabe des Codes (``_RAG_DEFAULTS``: 10 / 0,30 / 3000); eine
    gesetzte Umgebungsvariable (``RAG_TOP_K`` …) geht vor. Grenzen und Typen sind
    die des Lesers — bis Paket 7 fiel ein Wert außerhalb still auf die Vorgabe
    zurück, bis Paket 9 einer im falschen Typ (``"20"``, ``True``): darum streng.
    """

    top_k: int | None = Field(default=None, ge=1, le=50, strict=True)
    min_score: float | None = Field(default=None, ge=0, le=1, strict=True)
    max_chars_per_area: int | None = Field(default=None, ge=0, strict=True)


class RagRetrievalArea(AreaModel):
    """``01-base/rag-retrieval`` (Paket 7, P4): gelesen schon immer, pflegbar erst
    mit diesem Modell (ST-5 Befund 2)."""

    retrieval: RagAbruf = Field(default_factory=RagAbruf)


class McpWerkzeugSchema(AreaModel):
    """Ein Werkzeug eines weiteren Servers, übernommen aus „Server prüfen“ (Paket 11, E).
    Angeboten wird es nur mit ``read_only`` (``domain/fremdwerkzeug``)."""

    name: str
    description: Annotated[str, Textarea()] = ""
    input_schema: dict[str, Any] = {}
    #: ``annotations.readOnlyHint`` des Servers — nur ein ausdrückliches ``true``.
    read_only: bool = False


class McpServer(AreaModel):
    id: str
    name: str = ""
    description: Annotated[str, Textarea()] = ""
    enabled: bool = True
    url: str | None = None
    tools: list[str] = []
    # Paket 7 (S5): Werkzeuge dieses Servers, die das Modell nicht bekommt.
    # ``None`` = Vorgabe (``search_skill`` verborgen), eine Liste ersetzt sie
    # (``domain/werkzeug_freigabe``). ``tools`` sagt nur, wer ein Werkzeug bedient.
    werkzeuge_aus: list[str] | None = None
    # Paket 11 (E): übernommene Werkzeuge eines weiteren Servers (nicht beim WLO-Server).
    tool_schemas: list[McpWerkzeugSchema] = []


class McpServersArea(AreaModel):
    servers: list[McpServer] = []


class MessageRule(AreaModel):
    pattern: Annotated[str, Textarea()] = ""
    label: str = ""
    # C1-g2a: die englische Beschriftung des Lotsen-Chips. Leer = nicht
    # gepflegt; die Wahl trifft `guide_qr_injector` im Zug, nicht der Loader.
    label_en: str = ""
    url: str = ""
    priority: int = 50


class RagAreaRule(AreaModel):
    label: str = ""
    url: str = ""
    brand_pattern: Annotated[str, Textarea()] = ""


class GuideRulesArea(AreaModel):
    message_rules: list[MessageRule] = []
    # Die SCHLÜSSEL sind RAG-Bereichsnamen, nicht die Werte — dafür gibt es im
    # generischen Formular (noch) keine Vorschlagsliste. Bewusst so belassen:
    # ein Katalog am Wert würde hier auf das Falsche zeigen.
    rag_area_rules: dict[str, RagAreaRule] = {}


#: Paket 13 (B): wofür ein Golden-Zug steht — Spalten der Matrix „Zielgruppe × Anwendungsfall“.
#: Dieselbe Liste prüft der Runner vor dem Lauf (``evals/run_golden.ANWENDUNGSFAELLE``).
ANWENDUNGSFAELLE: tuple[str, ...] = (
    "suchen", "zusammenstellen", "erzeugen", "ueberarbeiten", "zeigen", "erklaeren",
    "wlo_wissen", "orientieren", "kuratieren", "rueckmeldung", "schutz", "sonstiges",
)


class GoldTurn(AreaModel):
    message: Annotated[str, Textarea()] = ""
    # Pflicht, sobald der Zug in einem Lauf steht — geprüft beim Laufstart (``validate_flows``).
    anwendungsfall: Annotated[str, Choices(*ANWENDUNGSFAELLE)] = ""
    expect: dict[str, Any] = {}


class GoldFlow(AreaModel):
    id: str = ""
    persona: Annotated[str, Catalog("personas")] = ""
    title: str = ""
    # Paket 13 (B): was ein guter Verlauf leistet — für den Ablauf-Judge, ein bis drei Sätze.
    erwartung: Annotated[str, Textarea()] = ""
    intents: list[Annotated[str, Catalog("intents")]] = []
    turns: list[GoldTurn] = []
    # AG-5: der Einbettungs-Kontext, den der Gold-Runner bei JEDEM Zug als
    # ``ChatRequest.environment`` mitschickt (Seitenkontext, ``master_skill``,
    # ``tool_mode``, Gastgeber-Auftrag …). Frei gehalten wie ``expect``: geprüft
    # wird serverseitig gegen ``Environment``, ein ungültiger Wert wird zum
    # Chat-Fehler des Zuges und nicht zu einem stillen Weglassen.
    environment: dict[str, Any] = {}
    # Paket 7 (K3): läuft nur, wenn man den Flow ausdrücklich wählt — nicht in einem
    # Lauf über „alle“ (Studio: leere Auswahl, Kommandozeile: ohne ``--only``).
    auf_abruf: bool = False


class GoldFlowsArea(AreaModel):
    version: int = 1
    flows: list[GoldFlow] = []
