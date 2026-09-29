"""05-knowledge/* + 02-domain/guide-rules + eval/gold-flows areas.
rag-config is the ONLY YAML whose root is a plain area-name mapping.
"""

from typing import Annotated, Any

from pydantic import RootModel

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices, Textarea


class RagAreaDef(AreaModel):
    #: S1: Auswahl statt Freitext. Der Wert entscheidet ueber den MUSTER-Weg —
    #: ``always`` holt den Bereich vor dem ersten Modellzug, ``on-demand`` erst
    #: auf Zuruf. Ein Tippfehler nahm den Bereich bis dahin still aus der
    #: Nutzung: ``load_rag_config`` behaelt nur Eintraege MIT ``mode``, und ein
    #: leeres Textfeld sagte das niemandem.
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


class McpServer(AreaModel):
    id: str
    name: str = ""
    description: Annotated[str, Textarea()] = ""
    enabled: bool = True
    url: str | None = None
    tools: list[str] = []


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


class GoldTurn(AreaModel):
    message: Annotated[str, Textarea()] = ""
    expect: dict[str, Any] = {}


class GoldFlow(AreaModel):
    id: str = ""
    persona: Annotated[str, Catalog("personas")] = ""
    title: str = ""
    intents: list[Annotated[str, Catalog("intents")]] = []
    turns: list[GoldTurn] = []
    # AG-5: der Einbettungs-Kontext, den der Gold-Runner bei JEDEM Zug als
    # ``ChatRequest.environment`` mitschickt (Seitenkontext, ``master_skill``,
    # ``tool_mode``, Gastgeber-Auftrag …). Frei gehalten wie ``expect``: geprüft
    # wird serverseitig gegen ``Environment``, ein ungültiger Wert wird zum
    # Chat-Fehler des Zuges und nicht zu einem stillen Weglassen.
    environment: dict[str, Any] = {}


class GoldFlowsArea(AreaModel):
    version: int = 1
    flows: list[GoldFlow] = []
