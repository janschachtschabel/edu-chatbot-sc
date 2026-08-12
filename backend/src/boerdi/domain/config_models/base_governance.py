"""01-base governance areas: safety-config, policy, privacy-config,
quality-log-config, guide-mode, classify-overrides, tone-modifiers,
card-pipeline. Shapes verified against the ALT tree inventory (2026-07-11).
"""

from typing import Any

from boerdi.domain.config_models._shared import AreaModel


class SafetyPreset(AreaModel):
    moderation: str = ""
    legal_classifier: str = ""
    prompt_injection: bool = False


class EscalationBlock(AreaModel):
    mode: str = ""
    provider: str = ""
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
    security_level: str = "standard"
    presets: dict[str, SafetyPreset] = {}
    extra_crisis_terms: list[str] = []
    extra_pii_terms: list[str] = []
    crisis_blocked_tools: list[str] = []
    crisis_pattern: str = ""
    threat_pattern: str = ""
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
    persona: str = ""
    triggers: list[str] = []
    except_explicit_role: list[str] = []
    requires_all: list[str] = []
    requires_any: list[str] = []


class IntentOverride(AreaModel):
    id: str
    description: str = ""
    intent: str = ""
    triggers: list[str] = []


class FewShotExample(AreaModel):
    input: str
    intent: str = ""
    pattern: str = ""
    note: str | None = None


class ClassifyOverridesArea(AreaModel):
    persona_overrides: list[PersonaOverride] = []
    intent_overrides: list[IntentOverride] = []
    intent_conflict_rule: str = ""
    topic_overrides: dict[str, Any] = {}
    pattern_disambiguators_legacy: list[dict[str, Any]] = []
    few_shot_examples: list[FewShotExample] = []


class ToneModifier(AreaModel):
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
