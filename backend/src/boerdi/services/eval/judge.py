"""LLM-as-Judge for one eval turn (port of ALT ``eval_judge.py`` + GV4).

``judge_turn`` scores a single turn on 0-2 axes (intent fit, persona tone,
pattern match, safety, info quality — plus ``auftrag_erfuellt`` when a
``soll_angebot`` is handed in) and rules on the LLM-hint-vs-engine pattern
disagreement. The three ``_build_*_expectations`` helpers render what the
judge is told to expect straight from config — pattern rules, persona
tonality/anti-markers, intent triggers — so editing a persona moves the
rubric with it instead of leaving the judge on stale prompt text.

GV4 honesty rules (2026-08-22, Plan §5):

* ``pattern_match`` is **None** when no real pattern (M01–M20) ran — the
  agent loop reports none, hybrid none before its pattern pick. Until GV4
  the judge got "(Pattern AGENT nicht in 03-patterns/ gefunden)" as its
  rubric and scored into the void. ``total`` normalises over the axes that
  WERE scored.
* A dead judge call **raises** ``JudgeError`` instead of degrading to
  all-zero scores: the silent zero punished the bot for a judge outage and
  dragged the run average (an ALT weakness the port carried over). Callers
  mark the turn ``judge_failed``; one bad turn still must not abort a run
  of hundreds — that protection now lives at the call sites.

Adaptations from ALT: the LLM boundary is ``llm.chat_completion(...,
background=True)``, and the judge model resolves per call via
``scenario_gen.judge_model()`` (see that module's note on empty compose vars).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from boerdi.services.eval.prompts import _JUDGE_PROMPT, _SOLL_ANGEBOT_BLOCK
from boerdi.services.eval.scenario_gen import judge_model
from boerdi.services.eval.text_utils import _strip_id
from boerdi.services.llm import chat_completion

logger = logging.getLogger(__name__)


class JudgeError(RuntimeError):
    """The judge call failed (transport error or unparseable reply)."""


#: Ein ECHTES Muster ist eine M-Nummer (M01–M20). "?", "", "AGENT" und das
#: synthetische "HYBRID" sind keine — dort lief kein Muster, und eine
#: Muster-Bewertung wäre eine Bewertung ins Leere.
_ECHTES_MUSTER = re.compile(r"M\d{2}")

_KEIN_MUSTER_RUBRIK = (
    "(kein Muster gelaufen — dieser Zug lief ohne Muster-Engine, z. B. über "
    "die Agent-Schleife; pattern_match wird nicht bewertet)"
)


def _build_pattern_expectations(pattern_id: str) -> str:
    """Welle E v3+ (2026-05-25): inject the pattern's purpose AND its hard
    rules so the judge knows BOTH what the pattern is supposed to do AND
    what's forbidden.

    Vorher (Welle E v3): nur core_rule + forbidden_phrases + anti_patterns
    → Judge wusste was VERBOTEN ist aber nicht was POSITIV erwartet wird.
    Folge: M15 (Orientierung) wurde mit "fehlende Material-Liste"
    bestraft, obwohl M15 explizit KEINE Material-Liste zeigen soll.

    Jetzt: ``short_purpose`` (was tut das Pattern), ``response_type``
    (answer/material/route etc.) und ``default_length`` (kurz/mittel/lang)
    werden vorangestellt, damit der Judge die Antwort-Form korrekt
    einschätzt.

    Returns a human-readable block ready for f-string interpolation, OR
    "(kein Pattern-Datensatz)" if the pattern_id isn't known.
    """
    if not pattern_id or pattern_id == "?":
        return "(kein Pattern-Datensatz — Bewertung ohne Pattern-Erwartungen)"
    from boerdi.services.config_loader import load_pattern_definitions
    pat = next(
        (p for p in load_pattern_definitions() if p.get("id") == pattern_id),
        None,
    )
    if not pat:
        return f"(Pattern {pattern_id} nicht in 03-patterns/ gefunden)"
    parts: list[str] = []

    # ── POSITIVE Erwartungen (was tut dieses Pattern?) ──
    sp = (pat.get("short_purpose") or "").strip()
    label = (pat.get("label") or pattern_id).strip()
    if sp:
        parts.append(f"Was tut {pattern_id} ({label}):\n{sp}")
    else:
        parts.append(f"Pattern: {pattern_id} ({label})")

    # Antwort-Form-Hinweise
    form_bits: list[str] = []
    rt = (pat.get("response_type") or "").strip()
    dl = (pat.get("default_length") or "").strip()
    om = (pat.get("output_mode") or "").strip()
    if rt:
        form_bits.append(f"response_type={rt}")
    if dl:
        form_bits.append(f"default_length={dl}")
    if om:
        form_bits.append(f"output_mode={om}")
    if form_bits:
        parts.append("Erwartete Antwort-Form: " + ", ".join(form_bits))

    # Kernregel (HART)
    cr = (pat.get("core_rule") or "").strip()
    if cr:
        parts.append(f"Kernregel (HART):\n{cr}")

    # Welle E v4+7 (2026-05-26): strukturierte Pattern-Auswahl-Regeln
    # für den Judge — when_to_use + when_not_to_use + discriminators
    # erlauben semantische pattern_match-Bewertung statt nur „ist
    # core_rule eingehalten".
    wtu = pat.get("when_to_use") or []
    if wtu:
        parts.append(
            "Pattern ist passend wenn (when_to_use):\n"
            + "\n".join(f"- {x}" for x in wtu[:6])
        )
    wntu = pat.get("when_not_to_use") or []
    if wntu:
        parts.append(
            "Pattern ist NICHT passend wenn (when_not_to_use):\n"
            + "\n".join(f"- {x}" for x in wntu[:6])
        )
    discs = pat.get("discriminators") or []
    if discs:
        disc_lines = []
        for d in discs[:5]:
            vs = d.get("vs", "")
            rule = d.get("rule", "")
            if vs and rule:
                disc_lines.append(f"- vs {vs}: {rule}")
        if disc_lines:
            parts.append(
                "Tie-Breaks zu anderen Patterns:\n" + "\n".join(disc_lines)
            )

    # Verbotene Formulierungen
    fp = pat.get("forbidden_phrases") or []
    if fp:
        parts.append(
            "Verbotene Formulierungen (Bot darf diese Wortlaute NICHT verwenden):\n"
            + "\n".join(f'- "{p}"' for p in fp[:15])
        )

    # Anti-Patterns
    ap = pat.get("anti_patterns") or []
    if ap:
        parts.append(
            "Anti-Patterns (Bot darf diese Strategien NICHT befolgen):\n"
            + "\n".join(f"- {p}" for p in ap[:10])
        )

    parts.append(
        "→ ``pattern_match`` bewertet AUSSCHLIESSLICH, ob das gewählte\n"
        "Pattern semantisch zur Nutzeranfrage passt — NICHT ob die\n"
        "Antwort inhaltlich umfangreich/perfekt ist. Wenn die Anfrage\n"
        "zum Pattern-Zweck oben passt und die Kernregel eingehalten\n"
        "wurde, ist pattern_match=2 angemessen, auch wenn die Antwort\n"
        "verbessert werden könnte (das gehört in ``info_quality``).\n"
        "Wenn das Pattern semantisch falsch gewählt wurde (z. B. ein\n"
        "Orientierungs-Pattern bei einer konkreten Material-Anfrage),\n"
        "ist pattern_match=0 oder 1 — und das gehört in ``issues``\n"
        "konkret beschrieben."
    )
    return "\n\n".join(parts)


def _build_persona_expectations(persona_id: str) -> str:
    """Welle E v3+ (2026-05-25): inject the persona's tonality modifiers + key
    style rules into the judge prompt — der Judge bewertet sonst persona_tone
    nur anhand des Persona-Labels und rät bei Duzen/Siezen.

    Returns a human-readable block or fallback string.
    """
    if not persona_id or persona_id == "?":
        return "(keine Persona-Erwartungen)"
    from boerdi.services.config_loader import load_persona_definitions
    p = next(
        (x for x in load_persona_definitions() if x.get("id") == persona_id),
        None,
    )
    if not p:
        return f"(Persona {persona_id} nicht gefunden)"
    parts: list[str] = []

    label = (p.get("label") or persona_id).strip()
    desc = (p.get("description") or "").strip()
    if desc:
        parts.append(f"{persona_id} ({label}): {desc}")

    style_bits: list[str] = []
    tone = (p.get("tone") or "").strip()
    formality = (p.get("formality") or "").strip()
    override = bool(p.get("override"))
    if tone:
        style_bits.append(f"Tonfall: {tone}")
    if formality:
        f_label = {
            "duzen": "MUSS duzen",
            "siezen": "MUSS siezen",
            "wie_user": "Anrede des Users übernehmen",
            "neutral": "neutral (weder duzen noch siezen)",
        }.get(formality, formality)
        style_bits.append(f"Anrede: {f_label}")
    if override:
        style_bits.append("override: Modifier schlägt Pattern-Default")
    if style_bits:
        parts.append("Erwartete Tonalität: " + " · ".join(style_bits))

    rules = p.get("rules") or []
    if rules:
        parts.append("Antwort-Regeln:\n" + "\n".join(f"- {r}" for r in rules[:6]))

    parts.append(
        "→ ``persona_tone`` bewertet OB der Bot tonal/anredemäßig zur "
        "erwarteten Persona-Erwartung oben passt. Bei expliziten Formality-"
        "Regeln (duzen/siezen) ist Verstoß sofort persona_tone=0."
    )
    return "\n\n".join(parts)


def _build_intent_expectations(intent_id: str) -> str:
    """Welle E v3+ (2026-05-25): inject the intent's trigger phrases + main
    discriminators, so the judge knows ob die Bot-Antwort das richtige Anliegen
    bedient hat — nicht nur ob die Klassifikation passt.
    """
    if not intent_id or intent_id == "?":
        return "(keine Intent-Erwartungen)"
    from boerdi.services.config_loader import load_intents
    it = next(
        (x for x in load_intents() if x.get("id") == intent_id),
        None,
    )
    if not it:
        return f"(Intent {intent_id} nicht gefunden)"
    parts: list[str] = []

    label = (it.get("label") or intent_id).strip()
    desc = (it.get("description") or "").strip()
    if desc:
        parts.append(f"{intent_id} ({label}): {desc[:300]}")

    trig = it.get("trigger_verbs") or []
    if trig:
        parts.append("Trigger-Verben/-Phrasen: " + ", ".join(f'"{t}"' for t in trig[:10]))

    discs = it.get("discriminators") or []
    if discs:
        lines: list[str] = []
        for d in discs[:3]:
            vs = d.get("vs", "?")
            rule = d.get("rule", "")
            lines.append(f"- vs {vs}: {rule}")
        parts.append("Diskriminatoren:\n" + "\n".join(lines))

    return "\n\n".join(parts) if parts else f"(Intent {intent_id} ohne Details)"


async def judge_turn(
    persona: dict, intent: dict, user_msg: str, bot_response: str,
    debug: dict, *, soll_angebot: str | None = None,
) -> dict[str, Any]:
    """LLM-as-Judge score for one turn. Returns dict with the axis scores +
    notes; raises :class:`JudgeError` when the judge itself fails (GV4).

    ``soll_angebot`` (GV4, golden runs only): the turn's documented
    ``must_offer``. When set, the prompt gains the SOLL-ANGEBOT block and the
    result the axis ``auftrag_erfuellt`` (0-2). Generative runs pass None and
    are unchanged.
    """
    # Welle E v3 (2026-05-25): Hint-Wert + Reasoning für Disagreement-Bewertung.
    # debug.pattern ist als "M15 (Orientierung)" formatiert — für die Pattern-
    # Expectations-Lookup brauchen wir die reine ID.
    engine_pattern_raw = debug.get("pattern", "?") or "?"
    engine_pattern_id = _strip_id(engine_pattern_raw) or engine_pattern_raw
    muster_lief = bool(_ECHTES_MUSTER.fullmatch(engine_pattern_id))
    hint_id = (debug.get("pattern_id_hint") or "").strip()
    hint_reasoning = (debug.get("pattern_reasoning") or "").strip()
    hint_label = hint_id if hint_id else "—"
    reasoning_block = (
        f"\n  Hint-Begründung: {hint_reasoning[:200]}"
        if hint_id and hint_reasoning else ""
    )
    prompt = _JUDGE_PROMPT.format(
        persona_label=persona.get("label", ""),
        persona_desc=(persona.get("description") or "")[:300],
        intent_label=intent.get("label", ""),
        intent_desc=(intent.get("description") or "")[:300],
        user_msg=user_msg[:800],
        bot_response=bot_response[:1500],
        debug_persona=debug.get("persona", "?"),
        debug_intent=debug.get("intent", "?"),
        debug_pattern=engine_pattern_raw,
        debug_pattern_hint=hint_label,
        debug_pattern_hint_reasoning=reasoning_block,
        debug_safety=debug.get("safety", "?"),
        debug_tools=debug.get("tools_called", []),
        # Expectations-Lookup MUSS die reine ID nutzen — sonst findet
        # ``_build_pattern_expectations`` das Pattern nie und der Judge
        # bekommt "(Pattern X (Label) nicht in 03-patterns/ gefunden)".
        # GV4: lief KEIN Muster, gibt es keine Rubrik zu suchen — der Judge
        # erfährt das ausdrücklich statt einer Nicht-gefunden-Floskel.
        pattern_expectations=(
            _build_pattern_expectations(engine_pattern_id)
            if muster_lief else _KEIN_MUSTER_RUBRIK
        ),
        # Welle E v3+ (2026-05-25): Persona+Intent-Erwartungen mit den
        # strukturierten Frontmatter-Daten (Tonalität, Trigger, Anti-Marker).
        # Wir nutzen die SCENARIO-erwartete Persona/Intent (was im Test-Setup
        # vorgesehen war), nicht das vom Bot klassifizierte — der Judge soll
        # gegen die Soll-Erwartung prüfen.
        persona_expectations=_build_persona_expectations(persona.get("id") or ""),
        intent_expectations=_build_intent_expectations(intent.get("id") or ""),
    )
    if soll_angebot:
        prompt += _SOLL_ANGEBOT_BLOCK.format(soll=soll_angebot[:500])
    try:
        resp = await chat_completion(
            messages=[{"role": "user", "content": prompt}],
            model=judge_model(),
            temperature=0.0,
            response_format={"type": "json_object"},
            background=True,
        )
        raw = (resp.choices[0].message.content or "").strip()
        data = json.loads(raw) if raw else None
    except Exception as e:
        # GV4: werfen statt Null-Punkte — die Aufrufer markieren den Turn als
        # ``judge_failed``. Ein stilles data={} sah aus wie ein 0-Punkte-Bot.
        raise JudgeError(f"Judge-Aufruf fehlgeschlagen: {e}") from e
    achsen = ["intent_fit", "persona_tone", "pattern_match", "safety", "info_quality"]
    if soll_angebot:
        achsen.append("auftrag_erfuellt")
    # Review 2026-08-22 (Runde 2): leeres ``content`` wurde zu ``"{}"`` und ein
    # Nicht-Objekt (JSON-Array) zu einem AttributeError AUSSERHALB des try —
    # beides umging den GV4-Vertrag oben. Kein Objekt mit mindestens einem
    # Achsen-Wert heißt: da hat niemand geurteilt (der Anbieter liefert
    # nachweislich leere content-Felder, siehe #268).
    if not isinstance(data, dict) or not any(k in data for k in achsen):
        raise JudgeError(
            "Judge-Antwort unbrauchbar: kein JSON-Objekt mit Achsen-Werten "
            f"(content={raw[:80]!r})"
        )
    # Coerce + clamp
    out: dict[str, Any] = {}
    for k in achsen:
        v = data.get(k, 0)
        try:
            v = int(v)
        except Exception:
            v = 0
        out[k] = max(0, min(2, v))
    if not muster_lief:
        out["pattern_match"] = None  # nicht bewertet, nicht 0
    out["notes"] = str(data.get("notes", ""))[:300]
    # Structured issue lists — keep each entry short, cap list length
    out["issues"] = [str(x)[:200] for x in (data.get("issues") or [])][:8]
    out["missing_info"] = [str(x)[:200] for x in (data.get("missing_info") or [])][:8]
    # Welle E v3 (2026-05-25): LLM-Hint vs Engine — Judge entscheidet bei
    # Disagreement, welches Pattern besser gepasst hätte.
    verdict = str(data.get("pattern_hint_verdict", "")).strip().lower()
    if verdict not in ("engine_better", "hint_better", "equivalent", "no_disagreement"):
        # Fix 2026-07-10 (B2): ungültiges/fehlendes Verdict → neutraler Fallback
        # ``no_disagreement`` (der einzige wertungsfreie gültige Verdict), egal ob
        # ein Hint vorlag. Vorher blieb bei vorhandenem Hint ein LEERER String
        # stehen, der als "" persistiert wurde und keinen sinnvollen Aggregat-Wert
        # lieferte.
        verdict = "no_disagreement"
    out["pattern_hint_verdict"] = verdict
    # Welle E v4+6 (2026-05-26): Filter Judge-Halluzinations-Floskel raus
    # — wenn der Judge den Prompt-Erklaerungstext "Engine und Hint sind
    # identisch, kein Vergleich noetig" wortwoertlich als reasoning
    # gibt, droppen wir das (war keine Bewertung sondern Verdict-Definition).
    # Fallback im Studio greift dann auf `notes`.
    _raw_reason = str(data.get("pattern_hint_reasoning", "")).strip()
    _hallu_floskel = (
        "engine und hint sind identisch",
        "kein vergleich nötig",
        "kein vergleich notig",
        "kein vergleich noetig",
    )
    if any(f in _raw_reason.lower() for f in _hallu_floskel):
        # Ungenutzte Pseudo-Begründung — leer schreiben, damit Studio
        # auf notes-Fallback greift.
        _raw_reason = ""
    out["pattern_hint_reasoning"] = _raw_reason[:300]
    # Overall score 0.0-1.0, equal weights — normalisiert über die BEWERTETEN
    # Achsen (GV4): eine None-Achse darf den Schnitt weder drücken (als 0
    # gezählt) noch verwässern (als Nenner gezählt).
    bewertet = [out[k] for k in achsen if isinstance(out[k], int)]
    out["total"] = (
        round(sum(bewertet) / (2.0 * len(bewertet)), 3) if bewertet else 0.0
    )
    return out
