"""Classify system-prompt assembly (P3-2) — port of the assembly half of ALT
``llm_classify_prompt.py`` (``_build_classify_system_prompt`` + the signals /
canvas / classify-overrides / few-shot renderers).

Assembles the config into one system prompt: a long STATIC prefix (personas,
intents, signals, states, entities, patterns, hard-overrides, few-shot) followed
by the DYNAMIC turn-context block — dynamic last so the static prefix stays
identical between turns and the provider prompt-cache hits it.

Deliberate NEU-deviations from ALT (both documented):
- signals read via the loader ``area()`` (raw jsonb) — the public
  ``load_signal_modulations`` strips the ``dimension`` field this block groups by;
- ``simplify:`` the tiktoken prompt-size histogram is omitted — non-behavioural
  telemetry with no tiktoken infra in NEU. The semantic page-context block IS wired
  (R6): ``page_context.get_cached`` + ``render_for_prompt``, off the ``_page_metadata``
  cache the ``page_context_enrich`` node populates; the raw whitelisted one-liner is
  kept alongside it.
"""

from __future__ import annotations

import json

from boerdi.services import page_context
from boerdi.services.classify_prompt_blocks import (
    _render_entities_block,
    _render_intents_block,
    _render_patterns_hint_block,
    _render_personas_block,
    _render_states_block,
)
from boerdi.services.config_loader import (
    area,
    load_classify_overrides_config,
    load_entities,
    load_intents,
    load_pattern_definitions,
    load_persona_definitions,
    load_states,
)

# Whitelisted keys of environment.page_context that may enter the prompt.
_PAGE_CONTEXT_KEYS = (
    "node_id", "collection_id", "search_query", "topic_page_slug",
    "subject_slug", "page_kind", "page_type", "widget", "detection_source",
)


def _render_signals_block() -> str:
    """Render the Signals section grouped by dimension (Tonalität, Verhalten,
    …). Reads the raw ``04-signals/signal-modulations`` area because the public
    ``load_signal_modulations`` drops the ``dimension`` grouping key."""
    sig_defs = area("04-signals/signal-modulations").get("signals") or {}
    if not sig_defs:
        return "\n(keine Signale konfiguriert)\n"
    by_dim: dict[str, list[str]] = {}
    for sig_id, cfg in sig_defs.items():
        dim = cfg.get("dimension", "Unbekannt") if isinstance(cfg, dict) else "Unbekannt"
        by_dim.setdefault(dim, []).append(sig_id)
    return "\n".join(f"{dim}: {', '.join(sigs)}" for dim, sigs in by_dim.items()) + "\n"


def _render_canvas_block(canvas_state: dict | None) -> str:
    """Render the Canvas-context block (only when canvas mode != empty). The
    classifier uses it to recognise edit requests (I06) when the previous bot
    turn rendered an inline document."""
    if not (canvas_state and canvas_state.get("mode")
            and canvas_state.get("mode") != "empty"):
        return ""
    c_title = (canvas_state.get("title") or "").strip()
    c_type = (canvas_state.get("material_type") or "").strip()
    c_mode = canvas_state.get("mode", "")
    c_md = (canvas_state.get("markdown") or "")[:800]
    c_cards = canvas_state.get("cards_count") or 0
    out = ["\n\n## Canvas-Kontext (was der Nutzer gerade sieht)",
           f"Modus: {c_mode}"]
    if c_title:
        out.append(f"Titel: {c_title}")
    if c_type:
        out.append(f"Material-Typ: {c_type}")
    if c_mode == "cards":
        out.append(f"Kachel-Anzahl: {c_cards}")
    if c_md:
        out.append(f"Auszug aus dem Canvas-Dokument:\n{c_md}")
    out.append(
        "\nKRITISCH — Intent-Auswahl bei aktivem Canvas:\n"
        "- Wenn die Nutzernachricht sich auf den Canvas-Inhalt bezieht "
        "(\"hier\", \"das\", \"der Text\", \"die Aufgabe\", \"der Titel\") "
        "ODER Edit-Verben nutzt — IMMER intent_id=\"I06\", "
        "turn_type=\"follow_up\".\n"
        "- I05 (NEU erstellen) ist NUR richtig bei explizitem neuem "
        "Material zu einem ANDEREN Thema (\"Mach mir stattdessen ein "
        "Quiz zu X\").\n"
        "- Meta-Fragen zum Canvas-Inhalt (\"Was bedeutet hier X?\") sind "
        "turn_type=\"clarification\"."
    )
    return "\n".join(out)


def _render_classify_overrides_block(co: dict) -> str:
    """Render Persona-/Intent-/Topic-Hard-Overrides from classify-overrides.
    Empty string when the config is empty (classifier then falls back to the
    persona/intent definitions)."""
    if not co:
        return ""
    out = ["\n## HARD-OVERRIDE-REGELN (überschreiben Persona/Intent-Defaults im Zweifel)\n"]

    pers = co.get("persona_overrides") or []
    if pers:
        out.append("\n### Persona-Override\n")
        for rule in pers:
            persona = rule.get("persona", "")
            trig = rule.get("triggers") or []
            ex_role = rule.get("except_explicit_role") or []
            req_all = rule.get("requires_all") or []
            req_any = rule.get("requires_any") or []
            label_parts = []
            if trig:
                label_parts.append("Tokens {" + ", ".join(f'"{t}"' for t in trig[:12]) + "}")
            if req_all:
                label_parts.append("+ alle von [" + ", ".join(req_all) + "]")
            if req_any:
                label_parts.append("+ eines von [" + ", ".join(req_any) + "]")
            head = " ".join(label_parts) or "(keine Trigger)"
            line = f"- {head} → Persona = {persona}"
            if ex_role:
                line += ", AUSSER explizite Selbst-ID: " + ", ".join(f'„{r}"' for r in ex_role)
            out.append(line + ".\n")

    ints = co.get("intent_overrides") or []
    if isinstance(ints, list) and ints:
        out.append("\n### Intent-Override (Verb-Disambiguation)\n")
        for rule in ints:
            intent = rule.get("intent", "")
            desc = rule.get("description", "")
            trig = rule.get("triggers") or []
            if trig:
                out.append(
                    f"- {desc} → Intent = {intent}. Trigger: "
                    + ", ".join(f"`{t}`" for t in trig[:14])
                    + ".\n"
                )

    conf_rule = (co.get("intent_conflict_rule") or "").strip()
    if conf_rule:
        out.append("\n**Konflikt-Regel:** " + conf_rule + "\n")

    topic = co.get("topic_overrides") or {}
    if topic:
        out.append("\n### Topic-Slot-Override\n")
        phantom = topic.get("phantom_topic_phrases") or {}
        if phantom.get("phrases"):
            out.append(
                "- Phantom-Topic-Phrasen "
                + ", ".join(f'„{p}"' for p in phantom["phrases"][:8])
                + " → extrahiere `topic` als LEERES Feld (führt zu M03-Slot-Klärung).\n"
            )
        fach_fb = topic.get("fach_as_topic_fallback") or {}
        if fach_fb.get("triggers"):
            out.append(
                "- Wenn der User NUR ein Fach nennt ("
                + ", ".join(fach_fb["triggers"][:8])
                + ", ...) ohne konkreteres Thema → extrahiere `fach`=Fach UND `topic`=Fach.\n"
            )

    return "".join(out)


def _render_pattern_disambiguators_block(disambs: list) -> str:
    """Render Pattern-conflict rules (deterministic tie-breaks) from
    classify-overrides."""
    if not disambs:
        return ""
    out = ["\n## PATTERN-KONFLIKTE (deterministische Tie-Breaks)\n"]
    for d in disambs:
        label = d.get("label") or d.get("id", "")
        out.append(f"\n**{label}**\n")
        for r in (d.get("rules") or []):
            out.append(f"- {r}\n")
        for ex in (d.get("examples") or []):
            inp = ex.get("input", "")
            expected = ex.get("expected", "")
            rationale = ex.get("rationale", "")
            line = f"- Beispiel: „{inp}" + "\" → " + expected
            if rationale:
                line += f" ({rationale})"
            out.append(line + "\n")
    return "".join(out)


def _render_fewshot_block(examples: list) -> str:
    """Render binding Few-Shot examples (User → expected pattern)."""
    if not examples:
        return ""
    out = [
        "\n## FEW-SHOT-BEISPIELE (User → erwartetes Pattern)\n",
        "Diese Beispiele sind verbindlich — bei ähnlichen Inputs nimm dasselbe Pattern.\n\n",
    ]
    for i, ex in enumerate(examples, 1):
        inp = ex.get("input", "")
        intent = ex.get("intent", "")
        pat = ex.get("pattern", "")
        note = ex.get("note", "")
        line = f"{i}. „{inp}" + f"\" → {intent}, {pat}"
        if note:
            line += f" ({note})"
        out.append(line + "\n")
    return "".join(out)


def build_classify_system_prompt(
    session_state: dict,
    environment: dict,
    canvas_state: dict | None = None,
) -> str:
    """Assemble the classification system prompt from config.

    Layout: fixed header + static data blocks (personas/intents/signals/states/
    entities/patterns) + hard-overrides + pattern-disambiguators + few-shot +
    dynamic turn-context (last, for prompt-cache stability)."""
    intents = load_intents()
    states = load_states()
    entities = load_entities()
    persona_defs = load_persona_definitions()
    patterns_for_prompt = load_pattern_definitions()

    personas_block = _render_personas_block(persona_defs)
    intents_block = _render_intents_block(intents)
    signals_block = _render_signals_block()
    states_block = _render_states_block(states)
    entities_block = _render_entities_block(entities)
    patterns_block = _render_patterns_hint_block(patterns_for_prompt)

    persona_prompt = ""
    if session_state.get("persona_id"):
        persona_prompt = f"\nAktuelle Persona: {session_state['persona_id']}"

    canvas_prompt = _render_canvas_block(canvas_state)

    # Semantic page-context block (resolved theme-page metadata, cached on
    # session_state["entities"]["_page_metadata"] by the page_context_enrich node).
    try:
        _page_meta = page_context.get_cached(session_state)
        _page_block = page_context.render_for_prompt(_page_meta, environment.get("page_context"))
        # Fallback: MCP resolved nothing (off-platform host page) but the widget's
        # DOM-detector saw visible text — render that as the heuristic block.
        if not _page_block:
            _page_block = page_context.render_raw_for_prompt(environment.get("page_context"))
    except Exception:  # noqa: BLE001 — a page-block failure must never break classification
        _page_block = ""

    _raw_pc = {
        k: v for k, v in (environment.get("page_context") or {}).items()
        if k in _PAGE_CONTEXT_KEYS
    }

    _dynamic_block = (
        f"\n## Aktueller Turn-Kontext\n"
        f"State: {session_state.get('state_id', 'S1')}\n"
        f"Bekannte Entities: {json.dumps(session_state.get('entities', {}))}"
        f"{persona_prompt}\n"
        f"Turn: {session_state.get('turn_count', 0) + 1}\n"
        f"Seite: {environment.get('page', '/')}\n"
        f"Seitenkontext (Rohdaten): {json.dumps(_raw_pc)}\n"
        f"Device: {environment.get('device', 'desktop')}"
        f"{canvas_prompt}\n"
        f"{_page_block}"
    ).rstrip()

    _static_block = (
        "\n## Personas (WICHTIG: Genau zuordnen!)\n"
        + personas_block
        + "\n## Intents\n"
        + intents_block
        + "\n## Signale\n"
        + signals_block
        + "\n## States\n"
        + states_block
        + "\n## Entities\n"
        + entities_block
        + "\n## Patterns (Hint-Feld, optional)\n"
        + patterns_block
        + "\nRufe classify_input auf mit den erkannten Werten."
    )

    header = (
        "Du bist der Klassifikations-Modul des WLO-Chatbots.\n"
        "Analysiere die Nutzernachricht und klassifiziere sie in die "
        "Input-Dimensionen Persona, Intent, Signale, State, Entities. "
        "Optional: Pattern-Hint + Tool-Hint.\n"
    )

    co = load_classify_overrides_config()
    override_block = _render_classify_overrides_block(co)
    pattern_disambig_block = _render_pattern_disambiguators_block(
        co.get("pattern_disambiguators") or []
    )
    fewshot_block = _render_fewshot_block(co.get("few_shot_examples") or [])

    return (
        header
        + _static_block
        + override_block
        + pattern_disambig_block
        + fewshot_block
        + _dynamic_block
    )
