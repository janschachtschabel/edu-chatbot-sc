"""01-base governance areas: safety-config, policy, privacy-config,
quality-log-config, guide-mode, classify-overrides, tone-modifiers,
card-pipeline. Shapes verified against the ALT tree inventory (2026-07-11).
"""

import logging
from typing import Annotated, Any, Final

from pydantic import AfterValidator, BeforeValidator, Field

from boerdi.domain.config_models._shared import AreaModel, Catalog, Choices, Textarea
from boerdi.settings import get_settings, ist_lockerer, pruefe_drosselgrenze

_logger = logging.getLogger(__name__)

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
    # ``provider`` gestrichen (Paket 7, L7): auch ``none`` schaltete nichts ab —
    # welcher Dienst moderiert, folgt aus dem LLM-Anbieter (``safety/moderation.py``).
    # ``True`` wie der Rückfall in ``services/safety/service.py`` (Audit
    # 2026-09-29, 6.9): mit ``False`` zeigte das Studio beide Schalter aus,
    # während sie wirkten.
    legal_classifier: bool = True
    thresholds: dict[str, float] = {}
    hard_block_categories: list[str] = []
    downgrade_false_positives: bool = True


class RateLimitWindow(AreaModel):
    enabled: bool = True
    requests_per_minute: int = 0
    requests_per_hour: int = 0


class RateLimitsBlock(AreaModel):
    enabled: bool = False
    per_session: RateLimitWindow = RateLimitWindow()
    per_ip: RateLimitWindow = RateLimitWindow()
    ip_whitelist: list[str] = []
    blocked_message: Annotated[str, Textarea()] = ""
    # C1-g2c: leer heißt „nicht gepflegt" — dann zeigt der Bot den deutschen
    # Satz, nie eine leere Blase.
    blocked_message_en: Annotated[str, Textarea()] = ""


def _zug_grenze(wert: str) -> str:
    """Leer = ``RATE_LIMIT_CHAT``; sonst dieselbe Form wie dort — ein Tippfehler wird beim
    Speichern abgewiesen, nicht erst je Zug still übergangen (Paket 19, M-4)."""
    if not wert.strip():
        return wert
    pruefe_drosselgrenze(wert, "turn_limits")
    vorgabe = get_settings().rate_limit_chat
    if ist_lockerer(wert, vorgabe):
        # Review, Punkt 7: gespeichert wird trotzdem — die Redaktion darf lockern, im Log steht es.
        _logger.warning("turn_limits=%r ist lockerer als RATE_LIMIT_CHAT=%r", wert, vorgabe)
    return wert


#: Eine Zug-Grenze im Studio: ``120/minute``, ``10/second;500/hour``, ``off`` oder leer.
_ZugGrenze = Annotated[str, AfterValidator(_zug_grenze)]


class TurnLimitsBlock(AreaModel):
    """Die äußere HTTP-Grenze der Züge je IP (Paket 19, M-4 / Entscheid P19-E3) — für
    ``/api/chat``, ``/api/chat/stream``, ``/api/agent`` und ``/api/agent/stream``, je Route
    gezählt. Leer heißt ``RATE_LIMIT_CHAT`` (``services/config_loader.load_turn_limits``).
    „Angemeldet“ gilt nur für eine vom MCP bestätigte Person oder einen Zug der Anlage."""

    anonymous: _ZugGrenze = ""
    authenticated: _ZugGrenze = ""


def _keine_wahrheitswerte(wert: Any) -> Any:
    """Lax gelesen wird aus ``true`` eine 1 — eine Frist von einem Tag (Paket 9)."""
    if isinstance(wert, bool):
        raise ValueError("Tage als Zahl angeben, nicht als ja/nein")
    return wert


#: Aufbewahrungsfrist in Tagen, 0 = unbegrenzt — seit Paket 8 (A) durchgesetzt
#: (``services/aufbewahrung``). Die Grenze VOR dem Validator: dahinter schriebe
#: pydantic ``"ge"`` statt ``"minimum"`` ins Schema, das Studio kennte sie nicht.
_Tage = Annotated[int, Field(ge=0), BeforeValidator(_keine_wahrheitswerte)]


class SafetyLoggingBlock(AreaModel):
    enabled: bool = True
    log_all_turns: bool = False
    # Wie im Auslieferungsstand (Paket 9, Review Paket 7 MINOR 15: Modell und Seed
    # gingen auseinander). Paket 19 (P19-E4, Nutzer 2026-10-31): 30 statt 90 Tage — die
    # Einträge halten 500 Zeichen der Nachricht und die IP, so lange wie der Verlauf.
    retention_days: _Tage = 30


#: D-14 (Nutzer, 2026-09-27): die Antwort des Agent-Endpunkts auf eine Krise —
#: im Studio frei konfigurierbar, vorbelegt mit dem Verweis an Familie und
#: Einrichtung. Bewusst ohne Telefonnummern: eine Nummer im Code wäre eine
#: Behauptung, die niemand pflegt. Der Chat antwortet weiter über das Muster M01.
KRISENTEXT_VORGABE = (
    "Es tut mir leid, dass es dir gerade nicht gut geht. Bitte wende dich an "
    "deine Familie oder an die Ansprechperson in deiner Einrichtung — du musst "
    "das nicht allein tragen."
)
KRISENTEXT_VORGABE_EN = (
    "I'm sorry you're going through a hard time. Please reach out to your "
    "family or to the contact person at your institution — you don't have to "
    "carry this alone."
)


#: Ein zusätzlicher Krisen- oder PII-Begriff — Text, kein Muster.
_Begriff = Annotated[str, Field(max_length=100)]


class SafetyConfigArea(AreaModel):
    # Bewusst ohne Auswahl: die Stufe zeigt auf einen Schlüssel in `presets`
    # derselben Datei, und `presets` ist eine offene Zuordnung — wer dort eine
    # eigene Stufe anlegt, muss sie auch setzen können. Für die fünf
    # ausgelieferten gibt es ohnehin die eigene Studio-Ansicht.
    security_level: str = "standard"
    presets: dict[str, SafetyPreset] = {}
    # Paket 4, D8: Begriffe, die das Regex-Gate nach seinen eigenen Listen
    # prüft (`services/safety/zusatz_begriffe.py`). Gedeckelt, weil jeder
    # Begriff bei jeder Nachricht geprüft wird.
    extra_crisis_terms: list[_Begriff] = Field(default=[], max_length=200)
    extra_pii_terms: list[_Begriff] = Field(default=[], max_length=200)
    crisis_blocked_tools: list[Annotated[str, Catalog("tools")]] = []
    crisis_pattern: Annotated[str, Catalog("patterns")] = ""
    threat_pattern: Annotated[str, Catalog("patterns")] = ""
    # AG-4 Teil B: der Text des Agent-Endpunkts bei einer Krise. Leer heißt
    # „nicht gepflegt" — dann gilt die Vorgabe, nie eine leere Antwort.
    crisis_message: Annotated[str, Textarea()] = KRISENTEXT_VORGABE
    crisis_message_en: Annotated[str, Textarea()] = KRISENTEXT_VORGABE_EN
    escalation: EscalationBlock = EscalationBlock()
    # ``confidence_adjustments`` gestrichen (Paket 7, P4): ``outcome_service``
    # rechnet mit festen Werten.
    rate_limits: RateLimitsBlock = RateLimitsBlock()
    # Paket 19 (M-4): die HTTP-Grenze der Züge, getrennt anonym/angemeldet (``api/ratelimit``).
    turn_limits: TurnLimitsBlock = TurnLimitsBlock()
    logging: SafetyLoggingBlock = SafetyLoggingBlock()


class PolicyRule(AreaModel):
    id: str
    description: Annotated[str, Textarea()] = ""
    match: dict[str, Any] = {}
    effect: dict[str, Any] = {}


class PolicyArea(AreaModel):
    rules: list[PolicyRule] = []


class PrivacyLoggingBlock(AreaModel):
    messages: bool = True
    memory: bool = True
    quality: bool = True
    # Der Lader gibt True fest zurück (Audit-Pfad) — `x-fixed` lässt das Studio
    # einen gesperrten Schalter „fest aktiv" zeigen statt eines, der sich
    # wirkungslos auf „aus" stellen ließe (ST-6).
    safety: bool = Field(default=True, json_schema_extra={"x-fixed": True})
    # Paket 8 (Nutzer 2026-10-09): Frist der Gesprächsverläufe — Nachrichten und
    # Sitzungsgedächtnis; Sitzungen und ihre Verbrauchszahlen bleiben.
    retention_days: _Tage = 30


class PrivacyConfigArea(AreaModel):
    logging: PrivacyLoggingBlock = PrivacyLoggingBlock()


class QualityLoggingBlock(AreaModel):
    enabled: bool = True
    retention_days: _Tage = 180  # wie im Auslieferungsstand (Paket 9)


class QualityAlertsBlock(AreaModel):
    tight_race_threshold: float = 0.0
    degradation_rate_warn: float = 0.0
    empty_entity_rate_warn: float = 0.0


class QualityLogConfigArea(AreaModel):
    logging: QualityLoggingBlock = QualityLoggingBlock()
    alerts: QualityAlertsBlock = QualityAlertsBlock()


class GuideModeBlock(AreaModel):
    # ``default_enabled`` gestrichen (Paket 7, P4): das Widget hat keinen
    # Lotsen-Schalter mehr, der Lotse ist dort immer an.
    max_guide_targets_per_turn: int = 5
    # ST-2c: Grenze = Kappung im Lader (config_loader/safety.py)
    max_guide_quick_replies: int = Field(default=2, ge=1, le=3)
    url_fields_priority: list[str] = []
    allowed_hosts: list[str] = []
    trusted_domains: list[str] = []


class GuideModeArea(AreaModel):
    guide_mode: GuideModeBlock = GuideModeBlock()


class PersonaOverride(AreaModel):
    id: str
    description: Annotated[str, Textarea()] = ""
    # Ein Vorschlagsfeld, kein Auswahlfeld: `*` ist hier ein zulässiger Wert
    # (Platzhalter für „jede Persona") und steht in keinem Katalog.
    persona: Annotated[str, Catalog("personas")] = ""
    triggers: list[str] = []
    except_explicit_role: list[str] = []
    requires_all: list[str] = []
    requires_any: list[str] = []


class IntentOverride(AreaModel):
    id: str
    description: Annotated[str, Textarea()] = ""
    intent: Annotated[str, Catalog("intents")] = ""
    triggers: list[str] = []


class FewShotExample(AreaModel):
    input: str
    intent: Annotated[str, Catalog("intents")] = ""
    pattern: Annotated[str, Catalog("patterns")] = ""
    note: str | None = None


class CurationReroute(AreaModel):
    """Netz unter dem Klassifikator für Kurations-Aufträge (Paket 10, S-7) —
    die Regel steht in ``domain/kuration_umleitung``."""
    enabled: bool = True
    verbs: list[str] = []
    objects: list[str] = []
    question_words: list[str] = []


class ClassifyOverridesArea(AreaModel):
    persona_overrides: list[PersonaOverride] = []
    intent_overrides: list[IntentOverride] = []
    intent_conflict_rule: Annotated[str, Textarea()] = ""
    topic_overrides: dict[str, Any] = {}
    pattern_disambiguators_legacy: list[dict[str, Any]] = []
    few_shot_examples: list[FewShotExample] = []
    curation_reroute: CurationReroute = CurationReroute()


#: Ab diesem Betrag verschiebt ``length_bias`` die Länge um eine Stufe
#: (``pattern_engine._apply_length_bias``). EINE Zahl für Engine und
#: Studio-Regler (ST-2h) — sonst läge die Anzeige still neben der Wirkung.
LENGTH_BIAS_STEP: Final = 0.15
#: Der Regler im Studio: Schritte von 0,05, Zonen an den Schwellen.
LENGTH_BIAS_SLIDER: Final = {
    "x-widget": "slider", "x-step": 0.05,
    "x-thresholds": [-LENGTH_BIAS_STEP, LENGTH_BIAS_STEP],
}


class ToneModifier(AreaModel):
    # Bewusst OHNE Auswahl, obwohl der Vorrat klein aussieht: `formality` wird
    # in `completion_messages` gegen ("sie","siezen","formal","foermlich")
    # geprüft — mehr Werte, als jeder Kommentar nennt. `card_text_mode` hatte
    # bis 2026-09-27 zwei Vokabulare (Lader vs. Antwort-Prompt); seitdem gilt
    # minimal|reference|highlight (`config_loader/tone.py`). Die Auswahl dafür
    # ist offen — sie ändert das Studio-Formular (Fixture).
    tone: str = "locker"
    # ST-2c: Grenze = Kappung im Lader (config_loader/tone.py)
    length_bias: float = Field(
        default=0.0, ge=-0.3, le=0.3, json_schema_extra=LENGTH_BIAS_SLIDER,
    )
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
    #: Welches Repositorium dieser Chatbot bedient. Leer = die Umgebungs-
    #: variable ``REPO_BASE_URL`` gilt (Vorgabe: Staging, siehe
    #: ``settings.repo_base_url``); gesetzt gewinnt dieser Wert. Er muss zu dem
    #: passen, was der MCP-Server befragt — sonst werden Treffer des einen
    #: Systems unter Adressen des anderen ausgeliefert (Befund 2026-08-19).
    #: Die Angabe gehört in die Konfiguration, damit im Studio
    #: nachlesbar ist, gegen welches Repositorium der Bot läuft, statt es aus
    #: der Deploy-Umgebung zu erraten (Nutzer-Vorgabe 2026-08-14).
    repo_base_url: str = ""


class CardPipelineArea(AreaModel):
    card_pipeline: CardPipelineBlock = CardPipelineBlock()
