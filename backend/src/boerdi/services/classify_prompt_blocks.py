"""Per-dimension classify-prompt renderers (P3-2) — 1:1 port of the
persona/intent/state/entity/pattern block renderers from ALT
``llm_classify_prompt.py`` (Welle E YAML-driven renderers).

Pure functions over already-loaded config lists (no store access) so the
output is byte-identical to ALT for the same config. The assembly, signals,
canvas and override renderers live in ``classify_prompt.py``; the tool half
of the ALT module is replaced by instructor auto-generation (spec §3-2).

Kept as one module (slightly over the ~300-line guide): the five renderers are
siblings with a single reason to change — the classify-prompt output format —
so splitting them on an arbitrary line would fragment one responsibility and
make parity-diffing against the ALT source harder, not easier.
"""

from __future__ import annotations

# Max-Limits pro Renderer — verhindern, dass eine versehentlich groß editierte
# Config den Prompt explodieren lässt. Werte weit genug für realistische
# Konfigurationen, begrenzen aber Worst-Case-Token-Costs sichtbar.
_MAX_HINTS_PER_PERSONA = 40
_MAX_ANTI_HINTS_PER_PERSONA = 20
_MAX_DISCRIMINATORS_PER_DIM = 8
_MAX_TRIGGER_VERBS = 20
_MAX_NEGATIVE_TRIGGERS = 8
_MAX_POSITIVE_EXAMPLES = 8
_MAX_NEGATIVE_EXAMPLES = 12
_MAX_EXAMPLES_PER_INTENT = 6


def _render_personas_block(persona_defs: list[dict]) -> str:
    """Render the Personas section from persona definitions. The generic
    instruction block (how to use the markers, when self-ID trumps everything)
    is emitted ONCE at the top, not duplicated per persona."""
    if not persona_defs:
        return "\n(keine Personas konfiguriert — defaulte zu P-AND.)\n"

    head = (
        "PERSONA-REGELN (gelten für alle Personas, Daten unten):\n"
        "- Erkenne Personas SOWOHL durch EXPLIZITE Selbst-Aussagen "
        "(\"Ich bin Lehrer:in / Politikerin / Journalist\") als auch durch "
        "IMPLIZITE Sprach-Marker (Positiv-Marker-Liste pro Persona).\n"
        "\n"
        "**HARTE OVERRIDE-Regel: Explizite Selbst-ID dominiert IMMER.**\n"
        "Sobald der User sagt \"Ich bin X\" / \"als X\" / \"ich bin "
        "X:in\" / \"als X:in\" (z.B. \"ich bin Schüler:in\", \"als Lehrkraft\", "
        "\"ich bin Mutter\"), ist die Persona = X. Diese Self-ID übersteuert\n"
        "JEDE konkurrierende Topic-Wahl im gleichen Satz, auch wenn der Rest\n"
        "nach einer anderen Persona klingt.\n"
        "Beispiel: \"Ich bin Schüler:in und lerne für meine Klausur. Hilf mir\n"
        "einen Lernpfad für meine Unterrichtseinheit zu bauen.\" → "
        "**P-LER** (NICHT P-LEH, obwohl \"Unterrichtseinheit\" P-LEH-Marker ist).\n"
        "Bei Self-ID: turn_type=\"correction\" UND persona_confidence>=0.9.\n"
        "\n"
        "- Anti-Marker (False-Positive-Schutz) NIE als Positiv-Treffer "
        "verwenden — sie sagen, was eine Persona NICHT eindeutig macht.\n"
        "- Intent ≠ Persona: ein Anfrage-Thema (z.B. \"Statistiken\", "
        "\"Bildungspolitik\") bestimmt nicht die Persona — Persona kommt "
        "aus Sprachstil + Selbst-ID + Kontext.\n"
        "- Mehrere starke Positiv-Marker EINER Persona schlagen einzelne "
        "konkurrierende Marker einer anderen — Beispiel: 2× P-LER-Marker "
        "(\"kapiere nicht\" + \"Schritt für Schritt\") überstimmt eine vage "
        "Frage zu \"Feedback geben\" → bleib bei P-LER.\n"
        "- Im Zweifel P-AND — aber NICHT vorschnell. Die Persona ist gesetzt, "
        "sobald ENTWEDER (a) EIN eindeutiger ROLLEN-Marker vorliegt, der die "
        "Rolle des Sprechers benennt statt nur ein Thema (z.B. \"meine "
        "Unterrichtsstunde/-einheit planen\", \"für meine Klasse\", \"ich "
        "unterrichte\", \"als Schulleitung\", \"als Abgeordneter\") → DIESE "
        "Persona; ODER (b) MIND. 2 schwächere Positiv-Marker derselben Persona "
        "zusammenkommen. NUR Themen-Wörter ohne Rollen-/Ich-Bezug (z.B. "
        "\"Lehrplan\", \"Schulentwicklung\", \"Statistik\", \"Bildungspolitik\") "
        "bleiben für sich P-AND.\n"
    )

    parts: list[str] = [head, ""]
    for p in persona_defs:
        pid = p.get("id", "")
        if not pid:
            continue
        block: list[str] = [f"### {pid} — {p.get('label', '')}"]
        if p.get("description"):
            block.append(p["description"])

        # bevorzugt ``positive_markers`` (neuer Name), fallback ``hints`` (Alias).
        pos = (p.get("positive_markers") or p.get("hints") or [])[
            :_MAX_HINTS_PER_PERSONA
        ]
        if pos:
            block.append("Positiv-Marker: " + ", ".join(f'"{h}"' for h in pos))

        # ``anti_markers`` ist list[{phrase, redirect_to?, rationale?}];
        # ``anti_hints`` (legacy list[str]) als Fallback.
        anti_raw = p.get("anti_markers") or p.get("anti_hints") or []
        anti_lines: list[str] = []
        for item in anti_raw[:_MAX_ANTI_HINTS_PER_PERSONA]:
            if isinstance(item, dict):
                phrase = str(item.get("phrase") or "").strip()
                if not phrase:
                    continue
                rt = str(item.get("redirect_to") or "").strip()
                anti_lines.append(f'"{phrase}"' + (f" → {rt}" if rt else ""))
            elif isinstance(item, str) and item.strip():
                anti_lines.append(f'"{item.strip()}"')
        if anti_lines:
            block.append("Anti-Marker (NICHT diese Persona): " + ", ".join(anti_lines))

        # Discriminators: list[{vs, rule, example_a?, example_b?}]; kompakt.
        disc_raw = p.get("discriminators") or []
        disc_lines: list[str] = []
        for d in disc_raw[:_MAX_DISCRIMINATORS_PER_DIM]:
            if isinstance(d, dict) and d.get("vs"):
                vs = str(d["vs"]).strip()
                rule = str(d.get("rule") or "").strip()
                disc_lines.append(f"vs. {vs}: {rule}" if rule else f"vs. {vs}")
            elif isinstance(d, str) and d.strip():
                disc_lines.append(d.strip())
        if disc_lines:
            block.append("Diskriminatoren:")
            block.extend(f"  - {line}" for line in disc_lines)

        parts.append("\n".join(block))
    return "\n\n".join(parts) + "\n"


def _render_intents_block(intent_defs: list[dict]) -> str:
    """Render the Intents section. The generic instruction block (Negativ- >
    Positiv-Trigger, edit-verb + canvas → I06) is emitted ONCE at the top."""
    if not intent_defs:
        return "\n(keine Intents konfiguriert)\n"

    intent_summary = ", ".join(
        f"{i.get('id', '?')} ({i.get('label', '')})" for i in intent_defs
    )

    head = (
        f"Intent-Übersicht: {intent_summary}\n\n"
        "INTENT-REGELN (gelten für alle Intents, Daten unten):\n"
        "- Trigger-Verben sind starke Pro-Signale, ABER Negativ-Trigger "
        "schlagen Positiv-Trigger. Prüfe zuerst die Negativ-Trigger.\n"
        "- Wenn ein Negativ-Trigger matcht, route zu `redirect_to` und "
        "wähle DEN Intent statt diesem.\n"
        "- Diskriminatoren beantworten Cross-Intent-Verwechslungen — "
        "konsultiere sie immer bei mehreren plausiblen Intents.\n"
        "- Bei Edit-Verben (kürzer/ausführlicher/ergänze/…) und aktivem "
        "Canvas-Inhalt: IMMER der Edit-Intent (I06), egal welche Material-"
        "Typ-Wörter im Satz stehen.\n"
        "- Im Zweifel: konservativ klassifizieren, lieber turn_type "
        "\"clarification\" als ein falscher Intent.\n"
    )

    parts: list[str] = [head, ""]
    for i in intent_defs:
        iid = i.get("id", "")
        if not iid:
            continue
        block: list[str] = [f"### {iid} — {i.get('label', '')}"]
        if i.get("description"):
            block.append(str(i["description"]).strip())

        triggers = (i.get("trigger_verbs") or [])[:_MAX_TRIGGER_VERBS]
        if triggers:
            block.append("Trigger-Verben: " + ", ".join(f'"{t}"' for t in triggers))

        neg = (i.get("negative_triggers") or [])[:_MAX_NEGATIVE_TRIGGERS]
        if neg:
            block.append("Negativ-Trigger:")
            for n in neg:
                if not isinstance(n, dict):
                    continue
                phrase = n.get("phrase", "").strip()
                target = n.get("redirect_to", "").strip()
                rationale = n.get("rationale", "").strip()
                when = n.get("when", "").strip()
                line = f'  - "{phrase}" → {target}' if target else f'  - "{phrase}"'
                if when:
                    line += f" (wenn {when})"
                if rationale:
                    line += f" — {rationale}"
                block.append(line)

        disc = (i.get("discriminators") or [])[:_MAX_DISCRIMINATORS_PER_DIM]
        if disc:
            block.append("Diskriminatoren:")
            for d in disc:
                if not isinstance(d, dict):
                    continue
                vs = d.get("vs", "").strip()
                rule = d.get("rule", "").strip()
                ex_a = d.get("example_a", "").strip()
                ex_b = d.get("example_b", "").strip()
                if vs and rule:
                    block.append(f"  - vs. {vs}: {rule}")
                if ex_a:
                    block.append(f"      Bsp: {ex_a}")
                if ex_b:
                    block.append(f"      Bsp: {ex_b}")

        examples = (i.get("examples") or [])[:_MAX_EXAMPLES_PER_INTENT]
        if examples:
            block.append("Beispiele:")
            block.extend(f'  - "{e}"' for e in examples)

        parts.append("\n".join(block))
    return "\n\n".join(parts) + "\n"


def _render_states_block(state_defs: list[dict]) -> str:
    """Render the States section (id, label, description, Wahl-Kriterien)."""
    if not state_defs:
        return "\n(keine States konfiguriert)\n"

    head = (
        "STATE-REGELN (Conversation-Phase wählen):\n"
        "- Wähle den State, der den AKTUELLEN Turn beschreibt — nicht "
        "den letzten oder erwarteten.\n"
        "- Wahl-Kriterien pro State unten beachten.\n"
        "- Default-Übergang: Slot komplett → S3, Slot fehlt → S2, "
        "kein konkretes Anliegen → S1.\n"
    )

    parts: list[str] = [head, ""]
    for s in state_defs:
        sid = s.get("id", "")
        if not sid:
            continue
        block: list[str] = [f"- {sid} ({s.get('label', '')})"]
        desc = (s.get("description") or "").strip()
        if desc:
            block.append(f"  {desc}")
        criteria = s.get("selection_criteria") or []
        if criteria:
            block.append("  Wahl-Kriterien:")
            block.extend(f"    - {c}" for c in criteria)
        parts.append("\n".join(block))
    return "\n".join(parts) + "\n"


def _render_entities_block(entity_defs: list[dict]) -> str:
    """Render the Entities section (Slot-Extraction rules + examples)."""
    if not entity_defs:
        return "\n(keine Entities konfiguriert)\n"

    head = (
        "ENTITY-REGELN (Slot-Extraction):\n"
        "- Slots IMMER LEER lassen, wenn der erwartete Wert nicht "
        "eigenständig im Satz steht. Lieber leer als Substring-Klau.\n"
        "- Diskriminatoren unten zeigen Cross-Slot-Fallstricke "
        "(z.B. fach vs thema).\n"
        "- Positiv-Beispiele zeigen erwartete Werte; "
        "Negativ-Beispiele zeigen, wann der Slot LEER bleiben muss.\n"
    )

    parts: list[str] = [head, ""]
    for e in entity_defs:
        eid = e.get("id", "")
        if not eid:
            continue
        desc = (e.get("description") or e.get("label") or "").strip().replace("\n", " ")
        block: list[str] = [f"- {eid}: {desc}"]

        pos = (e.get("positive_examples") or [])[:_MAX_POSITIVE_EXAMPLES]
        if pos:
            block.append("  Positiv-Beispiele:")
            for ex in pos:
                if not isinstance(ex, dict):
                    continue
                t = ex.get("text", "").strip()
                v = ex.get("value", "").strip()
                if t and v:
                    block.append(f'    - "{t}" → {v}')

        neg = (e.get("negative_examples") or [])[:_MAX_NEGATIVE_EXAMPLES]
        if neg:
            block.append("  Negativ-Beispiele (Slot bleibt leer):")
            for ex in neg:
                if not isinstance(ex, dict):
                    continue
                t = ex.get("text", "").strip()
                r = ex.get("rationale", "").strip()
                if t:
                    block.append(f'    - "{t}" — {r}' if r else f'    - "{t}"')

        disc = (e.get("discriminators") or [])[:_MAX_DISCRIMINATORS_PER_DIM]
        if disc:
            for d in disc:
                if not isinstance(d, dict):
                    continue
                vs = d.get("vs", "").strip()
                rule = d.get("rule", "").strip()
                if vs and rule:
                    block.append(f"  Diskriminator vs. {vs}: {rule}")

        parts.append("\n".join(block))
    return "\n".join(parts) + "\n"


def _render_patterns_hint_block(pattern_defs: list[dict]) -> str:
    """Render the Patterns-hint section. ``pattern_id_hint`` is the PRIMARY
    pattern selector (not a tie-breaker): id + label + purpose + when_to_use /
    when_not_to_use / trigger_phrases / discriminators per pattern."""
    if not pattern_defs:
        return "\nPattern-Hint: (keine Patterns geladen — Hint-Feld leer lassen)\n"

    head = (
        "PATTERN-HINT (PRIMÄR — wählt das Antwort-Muster):\n"
        "- Wähle das Pattern, das die beste Reaktion für die Anfrage "
        "darstellt. Dein Hint ist die Pattern-Wahl, nicht nur Telemetrie.\n"
        "- Routing-Rules können in eindeutigen Edge-Cases übersteuern "
        "(z. B. I05 ohne Thema → M03 Slot-Klärung).\n"
        "- Lass das Feld nur leer, wenn keine Pattern-Beschreibung "
        "wirklich passt — dann greift M15 (Orientierung) als Fallback.\n"
        "- `pattern_reasoning`: 1–2 Sätze, warum dieses Pattern und "
        "welche 1 Alternative noch in Frage kam.\n"
    )

    lines: list[str] = []
    for p in pattern_defs:
        pid = p.get("id")
        if not pid:
            continue
        label = p.get("label", "")
        purpose = (p.get("short_purpose") or "").strip().replace("\n", " ")
        if not purpose:
            purpose = (p.get("core_rule") or "").strip().replace("\n", " ")
            if len(purpose) > 100:
                purpose = purpose[:97] + "…"
        lines.append(f"\n### {pid} — {label}")
        if purpose:
            lines.append(f"_Zweck:_ {purpose}")

        wtu = p.get("when_to_use") or []
        if wtu:
            lines.append("**Einsetzen wenn:**")
            for it in wtu[:5]:
                lines.append(f"  - {it}")

        wntu = p.get("when_not_to_use") or []
        if wntu:
            lines.append("**NICHT einsetzen wenn:**")
            for it in wntu[:5]:
                lines.append(f"  - {it}")

        trigs = p.get("trigger_phrases") or []
        if trigs:
            lines.append(
                "**Typische User-Phrasen:** "
                + " · ".join(f"„{t}" + '"' for t in trigs[:5])
            )

        discs = p.get("discriminators") or []
        if discs:
            lines.append("**Tie-Breaks:**")
            for d in discs[:5]:
                vs = d.get("vs", "")
                rule = d.get("rule", "")
                ex = d.get("example", "")
                line = f"  - vs **{vs}**: {rule}"
                if ex:
                    line += f" _Beispiel:_ {ex}"
                lines.append(line)

    return head + "\n" + "\n".join(lines) + "\n"
