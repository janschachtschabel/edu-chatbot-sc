"""01-base widget-facing areas (spec §5.3): welcome, widget-modes, header-nav,
device-config, display-rules, context-actions, placeholder-topics, website-tour.
Shapes verified against the ALT tree inventory (2026-07-11).
"""

from typing import Any

from boerdi.domain.config_models._shared import AreaModel


class WelcomeBlock(AreaModel):
    greeting: str = ""
    quick_replies: list[str] = []
    tour_reply: str = ""


class WelcomeArea(AreaModel):
    welcome: WelcomeBlock = WelcomeBlock()


class WidgetModesBlock(AreaModel):
    cards_inline_link_limit: int = 5
    cards_inline_link_title_max: int = 70


class WidgetModesArea(AreaModel):
    widget_modes: WidgetModesBlock = WidgetModesBlock()


class NavButton(AreaModel):
    id: str
    enabled: bool = True
    label: str = ""
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
    font_size_percent: int = 85
    per_pattern: dict[str, bool] = {}
    intro_text: str | None = None


class SingleContentBoxRules(AreaModel):
    enabled: bool = True
    layout: str = "card"
    max_count: int | None = None  # legacy alias of groups.materialien_max


class GroupsRules(AreaModel):
    themenseiten_max: int = 3
    sammlungen_max: int = 3
    materialien_max: int = 3
    materialien_max_lernpfad: int = 5
    webseiten_max: int = 3


class InlineCardLinksRules(AreaModel):
    limit: int = 3
    title_max_chars: int = 70


class QuickRepliesRules(AreaModel):
    max_count: int = 4
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
    kind: str = ""
    action: str | None = None
    url: str | None = None
    params: dict[str, Any] | None = None


class ContextActionsBlock(AreaModel):
    enabled: bool = True
    report_url: str = ""
    greetings: dict[str, str] = {}
    pills: dict[str, list[ContextPill]] = {}
    curate_prompt: str = ""


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
    synonyms: list[str] = []
    page: str | None = None
    angebote: Any = None


class LabelPath(AreaModel):
    label: str = ""
    path: str = ""


class WebsiteTourBlock(AreaModel):
    enabled: bool = True
    base_host: str = ""
    home_path: str = ""
    content_hub: str = ""
    contact_hub: str = ""
    start_label: str = ""
    trigger_phrases: list[str] = []
    flows: list[TourFlow] = []
    intro: str = ""
    nudge: str = ""
    explore: str = ""
    entry: dict[str, str] = {}
    groups: list[TourGroup] = []
    content_sublinks: list[LabelPath] = []
    contact_links: list[LabelPath] = []
    steps: dict[str, Any] = {}


class WebsiteTourArea(AreaModel):
    website_tour: WebsiteTourBlock = WebsiteTourBlock()
