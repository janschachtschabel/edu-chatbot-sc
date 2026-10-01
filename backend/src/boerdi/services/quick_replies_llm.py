"""LLM quick-reply generator (P3-3, port of ALT llm_quick_replies.py):
``generate_quick_replies`` — transport, parsing, dedupe and the ``max_chars``
filter. The system prompt itself and the persona capability-hint menus live in
the sibling ``quick_replies_prompt`` (precedent: ``classify_prompt`` /
``response_prompt_builder``), which reads no config: every config value the
prompt names is read here and handed over as an argument.

NEU-deviations (documented):
- transport goes through ``llm.chat_completion`` (routing/semaphore/usage);
- ``get_state_directive`` is imported here as a module name so tests patch it
  at ``quick_replies_llm.get_state_directive`` (ALT patched ``ls.``);
- ``simplify:`` the semantic page-context line is deferred with the rest of
  page_context_service (its own later package); the seam is marked in
  ``quick_replies_prompt.build_system_prompt``;
- ``simplify:`` ``_analytical_personas`` reads the persona-priorities config
  directly — a minimal stand-in for ALT ``canvas_types.get_analytical_personas``
  (this is its first consumer; the canvas package should own it later).
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.i18n import DEFAULT, Locale
from boerdi.services import llm
from boerdi.services import quick_replies_prompt as _prompt
from boerdi.services.config_loader import (
    get_state_directive,
    load_canvas_persona_priorities,
    load_display_rules_config,
)
from boerdi.services.guide_qr_injector import GUIDE_QR_PREFIX

_logger = logging.getLogger(__name__)

# Vorgabe fuer ``display_rules.quick_replies.max_chars``: wie lang ein
# Vorschlag hoechstens sein darf. Gemessen und nicht geraten — die
# Beispiel-Vorschlaege in ``quick_replies_prompt`` reichen bis 47 Zeichen.
QR_MAX_CHARS_DEFAULT = 48

# ALT canvas_types._DEFAULT_ANALYTICAL_PERSONAS — fallback when the config
# area is empty/unbound.
_DEFAULT_ANALYTICAL_PERSONAS: frozenset[str] = frozenset({"P-ENT", "P-RED"})


def _analytical_personas() -> frozenset[str]:
    """Persona IDs that see analytical material-types first in quick replies.
    Reads 05-canvas/persona-priorities via the loader; defaults when empty."""
    items = load_canvas_persona_priorities().get("analytical_personas") or []
    if not items:
        return _DEFAULT_ANALYTICAL_PERSONAS
    return frozenset(str(x).strip() for x in items if x)


def _capability_hints_for_persona(
    persona_id: str, in_canvas: bool, has_topic: bool,
) -> list[str]:
    """Return a focused subset of capability hints for the quick-reply LLM.
    The menus and the filtering live in ``quick_replies_prompt``; which personas
    count as analytical is a config read and stays on this side."""
    return _prompt.select_capability_hints(
        persona_id, in_canvas, has_topic, _analytical_personas(),
    )


def _max_chars() -> int:
    """Der Zeichen-Deckel aus ``display_rules.quick_replies.max_chars``.

    ``0`` schaltet ihn ab. Ist die Config nicht lesbar, gilt die Vorgabe —
    eine unerreichbare Config darf keine ungebremsten Pillen bedeuten."""
    try:
        rules = (load_display_rules_config() or {}).get("quick_replies") or {}
        return max(0, int(rules.get("max_chars", QR_MAX_CHARS_DEFAULT) or 0))
    except Exception:
        _logger.debug("quick_replies.max_chars unlesbar; nehme Vorgabe", exc_info=True)
        return QR_MAX_CHARS_DEFAULT


def _display_length(reply: str) -> int:
    """Wie lang die Pille WIRKT.

    Bei einem Lotsen-Chip (``__guide__|Anzeigetext|URL``) steht im Knopf nur
    der Anzeigetext (``ui/chips/guide-qr.ts``); zaehlte die URL mit, fiele
    jeder Lotsen-Chip durch den Deckel."""
    text = reply.strip()
    if text.startswith(GUIDE_QR_PREFIX):
        # ``partition`` liefert ohne Trenner den ganzen Rest als Label — genau
        # das, was ``guideQuickReplyLabel`` dann auch anzeigt.
        text = text[len(GUIDE_QR_PREFIX):].partition("|")[0]
    return len(text.strip())


def filtere_vorschlaege(vorschlaege: list[str], *, anzahl: int, max_zeichen: int) -> list[str]:
    """Die EINE Regel für Schnellantworten — aus dem eigenen Aufruf wie aus dem
    Antwort-Aufruf (``respond_to_user``, Plan 2026-09-30).

    Dubletten (ohne Rücksicht auf Groß-/Kleinschreibung) und Vorschläge über
    ``max_zeichen`` fallen weg. Verworfen und NICHT gekürzt: der Pillentext IST
    die Nachricht, die der Klick abschickt (``sendMessage`` im Widget), ein
    abgeschnittener Satz wäre schlimmer als eine Pille weniger. ``max_zeichen``
    0 heißt: kein Deckel.

    Zurück gehen höchstens ``anzahl`` Vorschläge — plus vorn höchstens EIN Lotse,
    der keinen Platz kostet (Paket A, Agent-Runde 2): er wird nie eine Pille
    (ohne ``host`` entfernt ihn ``_attach_guide_qr``, sonst wird er ein Link im
    Text), belegte aber einen Platz; bei ``max_count: 2`` blieb im Tor E-5 so
    eine Pille statt zwei.
    """
    gesehen: set[str] = set()
    behalten: list[str] = []
    zu_lang = 0
    for vorschlag in vorschlaege:
        schluessel = vorschlag.lower()
        if not schluessel or schluessel in gesehen:
            continue
        if max_zeichen and _display_length(vorschlag) > max_zeichen:
            zu_lang += 1
            continue
        gesehen.add(schluessel)
        behalten.append(vorschlag)
    if zu_lang:
        # Nur die Anzahl, nicht der Text: der Vorschlag trägt das Thema des
        # Nutzers und gehört damit nicht ungefiltert ins Log.
        _logger.info(
            "quick_replies.max_chars: %d Vorschlag/Vorschlaege ueber %d Zeichen verworfen",
            zu_lang, max_zeichen,
        )
    lotse = [v for v in behalten if v.startswith(GUIDE_QR_PREFIX)][:1]
    return lotse + [v for v in behalten if not v.startswith(GUIDE_QR_PREFIX)][:anzahl]


async def generate_quick_replies(
    message: str,
    response_text: str,
    classification: dict[str, Any],
    session_state: dict,
    usage_acc: dict[str, Any] | None = None,
    count: int = 4,
    lang: Locale = DEFAULT,
) -> list[str]:
    """Generate ``count`` context-aware quick reply suggestions using the LLM —
    plus at most one guide line (``__guide__|…``) that does not count.

    ``usage_acc`` is optional — when threaded through, the call's tokens are
    accounted under phase ``"quick_replies"`` so the eval aggregator can break
    out QR cost separately. ``count`` (1–6, default 4) is set per pattern by
    the caller. Best-effort: any LLM/parse failure yields ``[]`` rather than
    breaking the surrounding response."""
    count = max(1, min(6, int(count or 4)))
    # Eine Ersatzzeile (Paket A, Agent-Runde 2): zu lange Vorschläge werden
    # verworfen, nicht gekürzt — ohne Ersatz kostete jeder eine Pille (Tor E-5:
    # 0 oder 1 statt 2). Zurück gehen höchstens ``count``.
    angefragt = count + 1
    persona_id = classification.get("persona_id", "P-AND")
    intent_id = classification.get("intent_id", "")
    state_id = classification.get("next_state", session_state.get("state_id", "S1"))
    entities = classification.get("entities", {}) or {}
    # Drop internal keys (prefix _) — they would confuse the LLM.
    public_entities = {k: v for k, v in entities.items() if not str(k).startswith("_")}

    in_canvas = state_id == "S3"
    thema = public_entities.get("thema") or public_entities.get("topic") or ""
    fach = public_entities.get("fach") or ""
    has_topic = bool(thema or fach)
    capability_hints = _capability_hints_for_persona(persona_id, in_canvas, has_topic)
    filled_hints = _prompt.fill_capability_hints(capability_hints, thema, fach)

    # State-specific QR directive (bot_directive from 04-states/states.yaml).
    _qr_state_meta = get_state_directive(state_id) or {}

    # Der Laengen-Deckel steht im Prompt UND im Filter unten — dieselbe Zahl,
    # eine Quelle. Ein Prompt ohne Nachpruefung ist eine Bitte, keine Zusage.
    budget = _max_chars()

    system = _prompt.build_system_prompt(
        count=angefragt,
        persona_id=persona_id,
        intent_id=intent_id,
        state_id=state_id,
        in_canvas=in_canvas,
        public_entities=public_entities,
        state_meta=_qr_state_meta,
        filled_hints=filled_hints,
        budget=budget,
        lang=lang,
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Nutzernachricht: {message}\n\nBot-Antwort: {response_text[:500]}"},
    ]

    try:
        resp = await llm.chat_completion(
            messages=messages,
            temperature=0.6,
            max_tokens=max(80, 40 * angefragt),
            usage_acc=usage_acc,
            phase="quick_replies",
        )
        text = strip_reasoning_markers(resp.choices[0].message.content or "")
        replies = [
            line.strip().lstrip("-•*0123456789. ")
            for line in text.strip().split("\n") if line.strip()
        ]
        return filtere_vorschlaege(replies, anzahl=count, max_zeichen=budget)
    except Exception:
        _logger.warning("quick-reply generation failed; returning none", exc_info=True)
        return []
