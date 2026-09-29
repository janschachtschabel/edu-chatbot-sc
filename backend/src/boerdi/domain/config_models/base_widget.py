"""01-base widget-facing areas (spec §5.3): welcome, widget-modes, header-nav,
device-config, display-rules, context-actions, placeholder-topics, website-tour.
Shapes verified against the ALT tree inventory (2026-07-11).

**C1-g1a — die zweite Sprache als Suffix je Schlüssel.** Redaktioneller Text,
den der Nutzer im Chat liest, bekommt ein optionales ``*_en`` neben dem
deutschen Feld (Nutzer-Entscheid 2026-08-04). Leer heißt „nicht gepflegt" —
das Widget fällt dann je Schlüssel auf das deutsche zurück. Der Suffix statt
eines ``en``-Blocks, damit das generische Studio-Formular die Felder ohne
Sonderbehandlung nebeneinander rendert und ein neuer Schlüssel nur an einer
Stelle gepflegt wird.
"""

from typing import Annotated, Any

from pydantic import Field

from boerdi.domain.config_models._shared import AreaModel, Choices, Marker, Primary, Textarea


class WelcomeBlock(AreaModel):
    # ST-4: Begrüßungstext und Start-Chips sind der Inhalt — vor den Grundwerten
    greeting: Annotated[str, Textarea(), Primary()] = ""
    # ST-2i: je Start-Chip ein Radio „Als Tour-Chip" — schreibt tour_reply
    quick_replies: Annotated[list[str], Marker("tour_reply"), Primary()] = []
    tour_reply: str = ""
    greeting_en: Annotated[str, Textarea()] = ""
    quick_replies_en: Annotated[list[str], Marker("tour_reply_en")] = []
    tour_reply_en: str = ""


class WelcomeArea(AreaModel):
    welcome: WelcomeBlock = WelcomeBlock()


class WidgetModesBlock(AreaModel):
    # ST-2c: Grenze = Kappung im Lader (config_loader/widget.py)
    cards_inline_link_limit: int = Field(default=5, ge=1, le=6)
    cards_inline_link_title_max: int = Field(default=70, ge=30, le=200)


class WidgetModesArea(AreaModel):
    widget_modes: WidgetModesBlock = WidgetModesBlock()


class NavButton(AreaModel):
    id: str
    enabled: bool = True
    label: str = ""
    label_en: str = ""
    icon: str = "explore"
    url: str = ""
    new_tab: bool = False


class HeaderNavBlock(AreaModel):
    buttons: list[NavButton] = []


class HeaderNavArea(AreaModel):
    header_nav: HeaderNavBlock = HeaderNavBlock()


class DeviceConfigArea(AreaModel):
    device_max_items: dict[str, int] = {}
    persona_formality: dict[str, str] = {}


class InlineDocumentsRules(AreaModel):
    enabled: bool = True
    # ST-2c: Grenze = Kappung im Lader (config_loader/widget.py)
    font_size_percent: int = Field(default=85, ge=70, le=100)
    per_pattern: dict[str, bool] = {}
    # Je Muster-ID eine Vorlage — so liest es der Lader (config_loader/widget.py),
    # so las es ALT. Als EIN Text bestand ein Eintrag die Prüfung beim Speichern
    # und ließ danach jede Antwort scheitern (Befund 2026-09-27).
    intro_text: dict[str, str] | None = None


class SingleContentBoxRules(AreaModel):
    enabled: bool = True
    layout: str = "card"
    # legacy alias of groups.materialien_max
    max_count: int | None = Field(default=None, ge=1, le=8)


class GroupsRules(AreaModel):
    # ST-2c: Grenzen = Kappung im Lader (config_loader/widget.py, `_grp_int`)
    themenseiten_max: int = Field(default=3, ge=1, le=20)
    sammlungen_max: int = Field(default=3, ge=1, le=20)
    materialien_max: int = Field(default=3, ge=1, le=8)
    materialien_max_lernpfad: int = Field(default=5, ge=1, le=8)
    webseiten_max: int = Field(default=3, ge=1, le=30)


class InlineCardLinksRules(AreaModel):
    # ST-2c: Grenze = Kappung im Lader (config_loader/widget.py)
    limit: int = Field(default=3, ge=1, le=6)
    title_max_chars: int = Field(default=70, ge=30, le=200)


class QuickRepliesRules(AreaModel):
    # ST-2c: Grenze = Kappung im Lader (config_loader/widget.py)
    max_count: int = Field(default=4, ge=0, le=6)
    # Wie lang eine Pille sein darf, in ZEICHEN. Der Vorgabewert 48 ist
    # gemessen, nicht geraten: die Beispiel-Vorschlaege im Generator-Prompt
    # selbst reichen bis 47 Zeichen. 0 = kein Deckel. Wirkt beim Erzeugen
    # (``services/quick_replies_llm``) — zu lange Vorschlaege werden
    # verworfen, nie gekuerzt.
    max_chars: int = 48
    inline_fallback_enabled: bool = True


class PromptAnzeigeKonsistenz(AreaModel):
    enabled: bool = True
    exclude_patterns: list[str] = []


class DisplayRulesBlock(AreaModel):
    inline_documents: InlineDocumentsRules = InlineDocumentsRules()
    single_content_box: SingleContentBoxRules = SingleContentBoxRules()
    groups: GroupsRules = GroupsRules()
    inline_card_links: InlineCardLinksRules = InlineCardLinksRules()
    quick_replies: QuickRepliesRules = QuickRepliesRules()
    prompt_anzeige_konsistenz: PromptAnzeigeKonsistenz = PromptAnzeigeKonsistenz()


class DisplayRulesArea(AreaModel):
    display_rules: DisplayRulesBlock = DisplayRulesBlock()


class ContextPill(AreaModel):
    label: str
    # C1-g2b: leer = nicht gepflegt. Bei `kind: text` ist die Beschriftung
    # zugleich die Nachricht, die der Klick sendet — sie muss deshalb in der
    # Sprache des Nutzers stehen, nicht nur lesbar sein.
    label_en: str = ""
    kind: str = ""
    #: Auswahl statt Freitext: ``graph/nodes/preflight`` verzweigt auf genau
    #: diese vier Namen und laesst alles andere still durchfallen — der Knopf
    #: taete dann nichts, und niemand sagte es. Die Liste ist mit dem Dispatch
    #: gepaart; ein Waechter prueft sie gegen den ausgelieferten Seed.
    action: Annotated[str, Choices(
        "browse_collection", "curate_collection",
        "generate_learning_path", "show_content_text",
    )] | None = None
    url: str | None = None
    params: dict[str, Any] | None = None


class ContextActionsBlock(AreaModel):
    enabled: bool = True
    report_url: str = ""
    # Unsere eigenen Seiten — exakte Hostnamen oder `*.example.com`. Entscheidet
    # bei einer Seite, die der URL-Erkenner nicht einordnen kann, zwischen
    # „eigene Startseite" und „fremde Seite" (dort bietet der Bot später die
    # Erschliessung an). Leer heisst: alles gilt als fremd.
    own_hosts: list[str] = []
    greetings: dict[str, Annotated[str, Textarea()]] = {}
    # Parallel zu `greetings`, je Seitenart. Ein eigenes Feld statt Schlüssel
    # mit Suffix, weil die Schlüssel hier Seitenarten benennen (collection /
    # content / topic) — dort gehört keine Sprache hinein.
    greetings_en: dict[str, Annotated[str, Textarea()]] = {}
    pills: dict[str, list[ContextPill]] = {}
    # Zweite Lesart von `external` — die Seite liegt schon im Bestand. Bewusst
    # KEINE eigene Seitenart in `greetings`/`pills`: sonst könnte ein Widget sie
    # als `page_kind` senden und würde begrüßt.
    duplicate_greeting: str = ""
    duplicate_greeting_en: str = ""
    duplicate_pill_label: str = ""
    duplicate_pill_label_en: str = ""
    curate_prompt: Annotated[str, Textarea()] = ""


class ContextActionsArea(AreaModel):
    context_actions: ContextActionsBlock = ContextActionsBlock()


class PlaceholderTopicsArea(AreaModel):
    placeholder_topics: list[str] = []
    min_topic_length: int = 3


class TourFlow(AreaModel):
    id: str
    weg: str = ""
    bedeutung: str = ""
    tour_einstieg: str = ""


class TourGroup(AreaModel):
    id: str
    label: str = ""
    # Die Beschriftung ist zugleich der Chip-Text, der als Antwort zurückkommt
    # (C1-g2d). ``synonyms`` bleibt bewusst deutsch — das macht das Matching zur
    # Vereinigung statt zu einer Umschaltung.
    label_en: str = ""
    synonyms: list[str] = []
    page: str | None = None
    angebote: Any = None


class LabelPath(AreaModel):
    label: str = ""
    label_en: str = ""
    path: str = ""


class WebsiteTourBlock(AreaModel):
    enabled: bool = True
    base_host: str = ""
    home_path: str = ""
    content_hub: str = ""
    contact_hub: str = ""
    # Ohne englisches Gegenstück, mit Grund: ``start_label`` hat weder in NEU
    # noch in ALT einen Leser — die Tour startet über ``tour_reply`` aus der
    # Begrüßungs-Config (C1-g1a/b).
    start_label: str = ""
    trigger_phrases: list[str] = []
    flows: list[TourFlow] = []
    intro: Annotated[str, Textarea()] = ""
    intro_en: Annotated[str, Textarea()] = ""
    nudge: Annotated[str, Textarea()] = ""
    nudge_en: Annotated[str, Textarea()] = ""
    explore: Annotated[str, Textarea()] = ""
    explore_en: Annotated[str, Textarea()] = ""
    # ``entry`` und ``steps`` sind freie Dicts — dort reisen die ``_en``-
    # Schlüssel ohne Modelländerung mit (wie ``effect`` in C1-g2c).
    entry: dict[str, Annotated[str, Textarea()]] = {}
    groups: list[TourGroup] = []
    content_sublinks: list[LabelPath] = []
    contact_links: list[LabelPath] = []
    steps: dict[str, Any] = {}


class WebsiteTourArea(AreaModel):
    website_tour: WebsiteTourBlock = WebsiteTourBlock()
