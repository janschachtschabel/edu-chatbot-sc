"""01-base governance areas: safety-config, policy, privacy-config,
quality-log-config, guide-mode, classify-overrides, tone-modifiers,
card-pipeline. Shapes verified against the ALT tree inventory (2026-07-11).
"""

from typing import Annotated, Any

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices

#: Wann die jeweilige Prüfstufe läuft. Gemessen im Seed 2026-08-13; ``smart``
#: kommt beim Rechts-Klassifikator vor, bei der Moderation nur ``never``/
#: ``always`` — die Stufe kann es aber (``escalation.mode`` nutzt alle drei).
_WHEN = ("never", "smart", "always")


class SafetyPreset(AreaModel):
    moderation: Annotated[str, Choices(*_WHEN)] = ""
    legal_classifier: Annotated[str, Choices(*_WHEN)] = ""
    prompt_injection: bool = False
    # Die Feinstellungen der oberen Stufen. Sie stehen seit jeher im Seed
    # (strict, paranoid) und werden von ``services/safety/service.py``
    # ausgewertet, waren aber nicht modelliert — das Studio meldete sie als
    # unbekannt und liess sie nur im Rohtext-Reiter zu.
    #
    # Die Vorgaben sind exakt die, die ``_resolve_preset`` einsetzt, wenn ein
    # Preset den Schlüssel weglässt (service.py:66-68). Eine andere Zahl hier
    # hiesse: das Formular zeigt etwas anderes an, als der Code anwendet.
    legal_trigger_override: bool = False
    threshold_multiplier: float = 1.0
    double_check: bool = False


class EscalationBlock(AreaModel):
    # Beide Vorräte stehen als Kommentar im Seed (`01-base/safety-config.yaml`)
    # — hier stehen sie so, dass das Studio sie anbieten kann.
    mode: Annotated[str, Choices("off", "smart", "always")] = ""
    provider: Annotated[str, Choices("openai", "none")] = ""
    legal_classifier: bool = False
    thresholds: dict[str, float] = {}
    hard_block_categories: list[str] = []
    downgrade_false_positives: bool = False


class RateLimitWindow(AreaModel):
    enabled: bool = True
    requests_per_minute: int = 0
    requests_per_hour: int = 0


class RateLimitsBlock(AreaModel):
    enabled: bool = False
    per_session: RateLimitWindow = RateLimitWindow()
    per_ip: RateLimitWindow = RateLimitWindow()
    ip_whitelist: list[str] = []
    blocked_message: str = ""
    # C1-g2c: leer heißt „nicht gepflegt" — dann zeigt der Bot den deutschen
    # Satz, nie eine leere Blase.
    blocked_message_en: str = ""


class SafetyLoggingBlock(AreaModel):
    enabled: bool = True
    log_all_turns: bool = False
    retention_days: int = 30


class SafetyConfigArea(AreaModel):
    # Bewusst ohne Auswahl: die Stufe zeigt auf einen Schlüssel in `presets`
    # derselben Datei, und `presets` ist eine offene Zuordnung — wer dort eine
    # eigene Stufe anlegt, muss sie auch setzen können. Für die fünf
    # ausgelieferten gibt es ohnehin die eigene Studio-Ansicht.
    security_level: str = "standard"
    presets: dict[str, SafetyPreset] = {}
    extra_crisis_terms: list[str] = []
    extra_pii_terms: list[str] = []
    crisis_blocked_tools: list[Annotated[str, Catalog("tools")]] = []
    crisis_pattern: Annotated[str, Catalog("patterns")] = ""
    threat_pattern: Annotated[str, Catalog("patterns")] = ""
    escalation: EscalationBlock = EscalationBlock()
    confidence_adjustments: dict[str, float] = {}
    rate_limits: RateLimitsBlock = RateLimitsBlock()
    logging: SafetyLoggingBlock = SafetyLoggingBlock()


class PolicyRule(AreaModel):
    id: str
    description: str = ""
    match: dict[str, Any] = {}
    effect: dict[str, Any] = {}


class PolicyArea(AreaModel):
    rules: list[PolicyRule] = []


class PrivacyLoggingBlock(AreaModel):
    messages: bool = True
    memory: bool = True
    quality: bool = True
    safety: bool = True  # loader forces True regardless (audit trail)


class PrivacyConfigArea(AreaModel):
    logging: PrivacyLoggingBlock = PrivacyLoggingBlock()


class QualityLoggingBlock(AreaModel):
    enabled: bool = True
    retention_days: int = 30


class QualityAlertsBlock(AreaModel):
    tight_race_threshold: float = 0.0
    degradation_rate_warn: float = 0.0
    empty_entity_rate_warn: float = 0.0


class QualityLogConfigArea(AreaModel):
    logging: QualityLoggingBlock = QualityLoggingBlock()
    alerts: QualityAlertsBlock = QualityAlertsBlock()


class GuideModeBlock(AreaModel):
    default_enabled: bool = True
    max_guide_targets_per_turn: int = 5
    max_guide_quick_replies: int = 2
    url_fields_priority: list[str] = []
    allowed_hosts: list[str] = []
    trusted_domains: list[str] = []


class GuideModeArea(AreaModel):
    guide_mode: GuideModeBlock = GuideModeBlock()


class PersonaOverride(AreaModel):
    id: str
    description: str = ""
    # Ein Vorschlagsfeld, kein Auswahlfeld: `*` ist hier ein zulässiger Wert
    # (Platzhalter für „jede Persona") und steht in keinem Katalog.
    persona: Annotated[str, Catalog("personas")] = ""
    triggers: list[str] = []
    except_explicit_role: list[str] = []
    requires_all: list[str] = []
    requires_any: list[str] = []


class IntentOverride(AreaModel):
    id: str
    description: str = ""
    intent: Annotated[str, Catalog("intents")] = ""
    triggers: list[str] = []


class FewShotExample(AreaModel):
    input: str
    intent: Annotated[str, Catalog("intents")] = ""
    pattern: Annotated[str, Catalog("patterns")] = ""
    note: str | None = None


class ClassifyOverridesArea(AreaModel):
    persona_overrides: list[PersonaOverride] = []
    intent_overrides: list[IntentOverride] = []
    intent_conflict_rule: str = ""
    topic_overrides: dict[str, Any] = {}
    pattern_disambiguators_legacy: list[dict[str, Any]] = []
    few_shot_examples: list[FewShotExample] = []


class ToneModifier(AreaModel):
    # Bewusst OHNE Auswahl, obwohl der Vorrat klein aussieht: `formality` wird
    # in `completion_messages` gegen ("sie","siezen","formal","foermlich")
    # geprüft — mehr Werte, als jeder Kommentar nennt. Und `card_text_mode` ist
    # an zwei Stellen UNTERSCHIEDLICH dokumentiert (`config_areas.py`:
    # minimal|kurz|explanation|ausfuehrlich, `pattern_engine.py`:
    # minimal|reference|highlight). Eine Auswahl wäre hier eine Behauptung.
    tone: str = "locker"
    length_bias: float = 0.0
    formality: str = "wie_user"
    card_text_mode: str = "minimal"
    override: bool = False


class ToneModifiersArea(AreaModel):
    default_modifier: ToneModifier = ToneModifier()


class CardPipelineBlock(AreaModel):
    pool_size: int = 20
    llm_curation_pool: int = 15
    final_selection_size: int = 5
    enable_llm_curation: bool = True
    min_displayed_cards: int = 5
    known_repo_hosts: list[str] = []


class CardPipelineArea(AreaModel):
    card_pipeline: CardPipelineBlock = CardPipelineBlock()
