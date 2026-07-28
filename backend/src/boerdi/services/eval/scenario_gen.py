"""Eval scenario generation (port of ALT ``eval_scenario_gen.py``).

Turns each persona x intent combo into realistic opening messages via one LLM
call per combo. The persona POSITIV/NEGATIV marker block is rendered from the
persona definitions at call time (ALT Welle E, 2026-05-25): the generator is fed
from the same source as the classifier prompt, so a marker one side knows the
other side knows too.

Two adaptations from ALT, both deliberate:

* the LLM boundary is ``llm.chat_completion(..., background=True)`` instead of
  ALT's ``get_background_client()`` object chain — same effect (the eval runs on
  the background concurrency bulkhead and cannot starve live traffic);
* the model names resolve **per call** from settings instead of being bound to
  module-level ``os.getenv`` at import time. ALT's own test file lists its
  import-time ``DEFAULT_*_MODEL`` constants as explicitly unpinnable; as
  functions they are ordinary testable code. ALT's ``or "gpt-4o-mini"`` guard is
  kept deliberately: docker-compose passes ``${VAR:-}`` through, so in the
  container the variable is SET BUT EMPTY, and an empty model reaches the
  provider as ``model=""`` (HTTP 400) and kills the whole generation stage.
"""

from __future__ import annotations

import logging
from typing import Any

from boerdi.services.eval.prompts import _SCENARIO_PROMPT
from boerdi.services.eval.text_utils import _has_persona_marker
from boerdi.services.llm import chat_completion
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

# Light by default: gpt-4o-mini is plenty for judging, and the persona simulator
# is realistic enough with it at a fraction of the main chat model's cost.
_MODEL_FALLBACK = "gpt-4o-mini"


def simulator_model() -> str:
    """Model that plays the user (scenario openings + conversation turns)."""
    return get_settings().eval_simulator_model or _MODEL_FALLBACK


def judge_model() -> str:
    """Model that scores a turn. Lives here because it shares the rationale."""
    return get_settings().eval_judge_model or _MODEL_FALLBACK


# Cache für das gerenderte Persona-Markers-Block pro Persona. Wird
# einmal pro Generator-Run gebaut (alle Personas geladen, Cross-References
# berechnet) und dann pro (persona, intent)-Kombi nachgeschlagen.
def _build_persona_markers_block(
    persona: dict[str, Any],
    all_personas: list[dict[str, Any]],
) -> str:
    """Render the persona-specific POSITIV/NEGATIV markers block.

    POSITIV-Marker kommen direkt aus der Persona-MD (``## Positiv-Marker``
    → ``hints``). NEGATIV-Marker kombinieren zwei Quellen:
      1. Die eigene ``anti_hints``-Liste (``## Anti-Marker``)
      2. Die Positiv-Marker ALLER anderen Personas (Cross-Persona-Drift-
         Schutz) — getaggt mit ``(= P-XYZ)``, damit das LLM weiß warum
         der Marker verboten ist.

    Für P-AND (Default-Persona) gilt die Inversionsregel: KEIN Positiv-
    Marker, dafür sind ALLE Marker anderer Personas verboten.
    """
    pid = persona.get("id", "")
    # ``positive_markers`` ist die Welle-E-v2-Quelle, ``hints`` ist der
    # Backward-Compat-Alias (zeigt auf dieselbe Liste).
    pos = persona.get("positive_markers") or persona.get("hints") or []

    # ``anti_markers`` ist jetzt list[{phrase, redirect_to?, rationale?}],
    # die alte ``anti_hints`` (list[str]) bleibt als Fallback für Files,
    # die noch nicht migriert sind.
    own_anti_raw = persona.get("anti_markers") or persona.get("anti_hints") or []
    own_anti: list[str] = []
    for item in own_anti_raw:
        if isinstance(item, dict):
            phrase = str(item.get("phrase") or "").strip()
            if not phrase:
                continue
            redirect_to = str(item.get("redirect_to") or "").strip()
            own_anti.append(f'"{phrase}" (= {redirect_to})' if redirect_to else f'"{phrase}"')
        elif isinstance(item, str) and item.strip():
            own_anti.append(f'"{item.strip()}"')

    # Cross-Persona NEGATIV: Positiv-Marker anderer Personas (max 6 pro
    # andere Persona, damit das Block nicht explodiert).
    cross_neg: list[str] = []
    for other in all_personas:
        other_id = other.get("id", "")
        if not other_id or other_id == pid:
            continue
        other_pos = other.get("positive_markers") or other.get("hints") or []
        for h in other_pos[:6]:
            cross_neg.append(f'"{h}" (= {other_id})')

    parts: list[str] = []

    # P-AND ist Spezialfall: keine eigenen Marker, dafür alle fremden verboten.
    if pid == "P-AND":
        parts.append(
            'POSITIV (Eröffnung soll GENERISCH bleiben, keine Selbst-ID): '
            'z. B. "Was kann ich hier machen?", "ich gucke mal", '
            '"interessehalber", "bin neu hier".'
        )
        if cross_neg:
            parts.append(
                "NEGATIV (jeder klare Marker bricht die P-AND-Anonymität):"
            )
            for m in cross_neg[:20]:
                parts.append(f"  - {m}")
        return "\n".join(parts)

    if pos:
        parts.append(
            "POSITIV (MUSS in der Eröffnung vorkommen):\n  - "
            + "\n  - ".join(f'"{p}"' for p in pos[:15])
        )
    else:
        parts.append("POSITIV: (keine Marker konfiguriert — Eröffnung darf generisch sein)")

    neg_block: list[str] = []
    for a in own_anti[:10]:
        # ``own_anti`` ist bereits formatiert (mit Quotes + optional
        # ``(= P-XYZ)``-Tag), daher kein zusätzliches Quoting hier.
        neg_block.append(f"  - {a}")
    for m in cross_neg[:15]:
        neg_block.append(f"  - {m}")
    if neg_block:
        parts.append("NEGATIV (NICHT verwenden — wuerde andere Persona triggern):")
        parts.extend(neg_block)

    return "\n".join(parts)


async def generate_scenarios(
    personas: list[dict], intents: list[dict], count_per_combo: int = 2,
    progress_cb: Any = None,
) -> list[dict]:
    """Generate realistic opening messages for each (persona, intent) combo.

    Uses an LLM. Every (persona, intent) pair gets ``count_per_combo``
    openings. Returns a flat list of scenario dicts.

    ``progress_cb`` (optional async callable) is invoked with
    ``(combo_idx, total_combos, persona_id, intent_id)`` BEFORE each
    LLM call so callers can publish live progress to the UI. The first
    LLM call alone takes 2–3 s, but with 9×16=144 combos the whole
    stage runs ~5–7 min — without progress hook, the UI shows a stale
    "Generiere Szenarien …" the entire time.
    """
    scenarios: list[dict] = []
    total_combos = len(personas) * len(intents)
    combo_idx = 0
    # Fire serially — keeps cost transparent and avoids provider rate limits
    for p in personas:
        for i in intents:
            combo_idx += 1
            if progress_cb is not None:
                try:
                    await progress_cb(
                        combo_idx, total_combos,
                        p.get("id", ""), i.get("id", ""),
                    )
                except Exception:
                    # Progress hook must never break generation
                    pass
            # Welle E (2026-05-25): persona-Marker-Block und Intent-Trigger
            # kommen jetzt aus den YAML/MD-Dateien — Single Source of Truth
            # mit dem Klassifikator-Prompt. Der Generator weiß durch die
            # zur Laufzeit injizierten POSITIV/NEGATIV-Marker, welche
            # Phrasen er einbauen MUSS (Persona-Signal) und welche er
            # vermeiden MUSS (würde andere Persona triggern).
            markers_block = _build_persona_markers_block(p, personas)
            intent_triggers = ", ".join(
                f'"{tv}"' for tv in (i.get("trigger_verbs") or [])[:12]
            ) or "(keine Trigger-Verben konfiguriert)"
            prompt = _SCENARIO_PROMPT.format(
                count=count_per_combo,
                persona_label=p.get("label", p.get("id", "")),
                persona_desc=p.get("description", "") or "(keine Beschreibung)",
                intent_label=i.get("label", i.get("id", "")),
                intent_desc=(i.get("description") or "")[:400],
                intent_triggers=intent_triggers,
                persona_markers_block=markers_block,
            )
            try:
                resp = await chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=simulator_model(),
                    temperature=0.7,
                    background=True,
                )
                raw = (resp.choices[0].message.content or "").strip()
                # Strip markdown quote blocks, numbered prefixes, bullet chars.
                # Handle models that respond with just one long line too.
                candidates: list[str] = []
                for ln in raw.split("\n"):
                    # Fix 2026-07-10 (B7): erst Bullet + Nummern-Präfix entfernen,
                    # DANN die Quotes strippen. Vorher lief strip('"') zuerst und sah
                    # bei ``- "Frage?"`` nur das schließende Quote (führend stand noch
                    # der Bullet) → das FÜHRENDE Quote überlebte im Opening.
                    ln = ln.strip()
                    ln = ln.lstrip("-•*").strip()
                    # Numbered prefixes like "1." "1)" "1:" — strip at most 3 leading digits
                    if len(ln) > 2 and ln[0].isdigit():
                        for sep in (". ", ") ", ": ", "- "):
                            if sep in ln[:5]:
                                ln = ln.split(sep, 1)[1].strip()
                                break
                    ln = ln.strip('"').strip("'").strip()
                    if ln and len(ln) >= 8:
                        candidates.append(ln)
                lines = candidates[:count_per_combo]
                if not lines:
                    logger.warning(
                        "Scenario generator returned no parseable lines for %s/%s. Raw: %r",
                        p.get("id"), i.get("id"), raw[:200],
                    )
                # ── Persona-Marker-Gate ENTFERNT (2026-05-23) ────────────
                # Im Scenario-Mode ist die Persona durch die Konstruktion
                # (LLM-Prompt mit gewähltem Persona-Tag) **per Definition
                # gesetzt** — eine nachträgliche Substring-Filterung kippt
                # legitim erzeugte Eröffnungen weg, die natürlich
                # formuliert sind und unsere Schlagwort-Liste nicht trifft.
                # Außerdem verzerrte das Gate die Persona-Klassifikator-
                # Messung: Eingaben, die der Klassifikator vielleicht falsch
                # gelabelt hätte, wurden vorab herausgefiltert.
                # Telemetrie-only Logging der Marker-Trefferrate behalten
                # wir, damit Marker-Qualität sichtbar bleibt, ohne zu filtern.
                pid = p.get("id", "")
                _marker_hits = sum(1 for ln in lines if _has_persona_marker(ln, pid))
                if lines and _marker_hits < len(lines):
                    logger.info(
                        "Persona-Marker-Telemetrie %s/%s: %d/%d Eröffnungen "
                        "ohne harten Marker (werden trotzdem behalten).",
                        pid, i.get("id"), len(lines) - _marker_hits, len(lines),
                    )
                for idx, line in enumerate(lines):
                    scenarios.append({
                        "persona_id": pid,
                        "persona_label": p.get("label", ""),
                        "intent_id": i.get("id", ""),
                        "intent_label": i.get("label", ""),
                        "opening": line,
                        "index": idx,
                    })
            except Exception as e:
                logger.warning(
                    "Scenario generation failed for %s/%s: %s",
                    p.get("id"), i.get("id"), e,
                )
    return scenarios
