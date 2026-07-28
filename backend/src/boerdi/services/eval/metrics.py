"""Eval metric aggregation (port of ALT ``eval_metrics.py``).

Pure computation over finished conversations — no I/O, no LLM, no DB. Three
aggregators, copied verbatim from ALT:

* ``_aggregate`` — the persona x intent score matrix + pattern usage
* ``_aggregate_per_phase`` — token usage per LLM phase incl. cache hit rate
* ``_aggregate_classification_metrics`` — the run-global classification report

The third one is what makes ``/eval/trends`` work: it produces
``tool_compliance_per_pattern``, ``token_usage_aggregate``,
``llm_engine_match_rate``, ``persona_correct_rate`` and ``intent_correct_rate``,
which the trends endpoint turns into its five series. Until this port landed the
key was never written and every series was empty.

Not here, deliberately: ``estimate_cost`` lives in ``eval_service`` (it is HTTP
request math, ported with the endpoint) and the golden scorecard
``aggregate_golden`` lives in the framework-free ``evals/run_golden.py``.

Size note: this file mirrors ALT's module and is therefore over the 300-line
guideline. ``_aggregate_classification_metrics`` is one long straight-line
accumulation over turn fields; splitting it would gain nothing but diff noise
against ALT.
"""

from __future__ import annotations

from typing import Any

from boerdi.services.eval.text_utils import _has_persona_marker, _strip_id


def _aggregate(conversations: list[dict]) -> dict[str, Any]:
    """Build matrix + pattern-usage stats from finished conversations."""
    matrix: dict[str, dict[str, dict[str, Any]]] = {}  # persona -> intent -> {total, count}
    pattern_usage: dict[str, int] = {}
    all_scores: list[float] = []

    for conv in conversations:
        p = conv.get("persona_id", "")
        i = conv.get("intent_id", "")
        matrix.setdefault(p, {}).setdefault(i, {"total": 0.0, "count": 0, "scores": []})
        for turn in conv.get("turns", []):
            judge = turn.get("judge", {})
            if judge:
                score = judge.get("total", 0.0)
                matrix[p][i]["total"] += score
                matrix[p][i]["count"] += 1
                matrix[p][i]["scores"].append(score)
                all_scores.append(score)
            pat = (turn.get("debug", {}) or {}).get("pattern")
            if pat:
                pattern_usage[pat] = pattern_usage.get(pat, 0) + 1

    # Collapse matrix to averages
    matrix_avg: dict[str, dict[str, float]] = {}
    for p, imap in matrix.items():
        matrix_avg[p] = {
            i: round(m["total"] / m["count"], 3) if m["count"] else 0.0
            for i, m in imap.items()
        }

    return {
        "matrix": matrix_avg,
        "pattern_usage": pattern_usage,
        "avg_score": round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0,
        "total_judged_turns": len(all_scores),
    }


def _aggregate_per_phase(conversations: list[dict]) -> dict[str, dict[str, Any]]:
    """A2.1 — sum per-phase token usage across all turns and add per-phase
    cache hit rate. Reads from ``debug.token_usage.per_phase`` (filled by
    ``usage_accumulator_add(..., phase=...)`` in llm_service).
    """
    out: dict[str, dict[str, int]] = {}
    for conv in conversations:
        for turn in conv.get("turns", []):
            tu = (turn.get("debug") or {}).get("token_usage") or {}
            per_phase = tu.get("per_phase") or {}
            if not isinstance(per_phase, dict):
                continue
            for phase, stats in per_phase.items():
                if not isinstance(stats, dict):
                    continue
                slot = out.setdefault(
                    str(phase),
                    {"prompt": 0, "completion": 0, "cached": 0, "calls": 0},
                )
                slot["prompt"] += int(stats.get("prompt") or 0)
                slot["completion"] += int(stats.get("completion") or 0)
                slot["cached"] += int(stats.get("cached") or 0)
                slot["calls"] += int(stats.get("calls") or 0)
    # Round-trip with hit_rate added per phase
    return {
        phase: {
            **stats,
            "hit_rate": (
                round(stats["cached"] / stats["prompt"], 3)
                if stats["prompt"] else 0.0
            ),
        }
        for phase, stats in out.items()
    }


def _aggregate_classification_metrics(
    conversations: list[dict],
) -> dict[str, Any]:
    """Run-globale Klassifikations-Metriken (Phase 1 Pattern-Hint).

    Berechnet pro Run:
      - persona/intent: Soll-Ist-Genauigkeit (expected vs. classified)
      - pattern: Engine-Wahl-Häufigkeit + Judge-Approval-Rate
      - llm_engine_match: wie oft stimmt LLM-Pattern-Hint mit Engine überein?
      - judge_pattern_score je Engine vs LLM-Hint (wenn beide vorhanden)
      - Confusion-Matrizen für persona/intent/pattern

    Persona/Intent-Soll: kommt aus conv["persona_id"]/conv["intent_id"]
    (= das Test-Szenario-Label, das den Bot stimulieren sollte).

    Pattern hat KEIN explizites Soll-Label im Test-Set; wir nutzen den
    Judge-Score `pattern_match >= 2` als Approximation für "Pattern-Wahl
    war korrekt".
    """
    persona_total = persona_correct = 0
    # Welle E (2026-05-23) — Persona-Klassifikator fair messen:
    # Eröffnungen ohne Persona-Marker zählen wir separat, weil dort die
    # einzig sinnvolle Klassifikator-Antwort P-AND ist (= "kein Marker
    # erkennbar"). Eine generische Frage "Was ist OER?" enthält keinen
    # Persona-Anker — wenn die Eval als Soll-Persona P-LEH hinterlegt,
    # ist das Eval-Setup, nicht der Klassifikator, das Problem.
    persona_achievable_total = persona_achievable_correct = 0
    persona_neutral_total = 0  # Eröffnungen ohne Marker, exkl. P-AND
    intent_total = intent_correct = 0
    persona_confusion: dict[str, dict[str, int]] = {}
    intent_confusion: dict[str, dict[str, int]] = {}
    pattern_confusion: dict[str, dict[str, int]] = {}  # llm_hint × engine

    # Welle C Sprint 6 — State-Verlaufs-Analyse (Conversation Flow Machine).
    # state_distribution: wie oft welcher State im Run getriggert wurde
    # state_transitions: prev_state → next_state Häufigkeitsmatrix
    # transition_plausibility_rate: Anteil der prev→next-Übergänge, die in
    #                                der next_likely-Liste des prev-States stehen
    state_distribution: dict[str, int] = {}
    state_transitions: dict[str, dict[str, int]] = {}
    transitions_total = 0
    transitions_plausible = 0

    llm_hint_present = 0
    llm_engine_agree = 0
    llm_pattern_judge_ok = 0      # LLM-Hint passt UND Judge sagt pattern_match=2
    engine_pattern_judge_ok = 0   # Engine-Wahl + Judge sagt pattern_match=2
    judged_turns = 0
    pattern_match_scores: list[int] = []

    # Welle E v3 (2026-05-25) — Judge-Verdict bei Pattern-Disagreement.
    # Wenn engine != hint, fragt der Judge welches besser passt. Wir zählen
    # die Verdicts und erstellen eine Confusion-Matrix der Konflikt-Paare.
    hint_verdict_counts: dict[str, int] = {
        "engine_better": 0, "hint_better": 0,
        "equivalent": 0, "no_disagreement": 0, "": 0,
    }
    # disagreement_pairs[(engine, hint)] = {"hint_better": N, "engine_better": M, "equivalent": K}
    disagreement_pairs: dict[str, dict[str, int]] = {}

    # Tool-Compliance: Pattern verlangt eine `tools`-Liste. Wir prüfen
    # pro Turn, ob mindestens EINES der vom Pattern verlangten Tools auch
    # aufgerufen wurde — das ist ein hartes Indiz für korrekte Pattern-
    # Ausführung. Patterns ohne tools-Liste werden nicht gezählt.
    from boerdi.services.config_loader import load_pattern_definitions as _lp
    _pattern_tools_map: dict[str, list[str]] = {}
    for p in _lp() or []:
        pid = p.get("id")
        tools = p.get("tools") or []
        if pid and isinstance(tools, list):
            _pattern_tools_map[pid] = [t for t in tools if isinstance(t, str)]

    tool_compliance_total = 0
    tool_compliance_ok = 0
    tool_compliance_per_pattern: dict[str, dict[str, int]] = {}  # pid -> {ok, total}

    # Cache-Hit-Rate (Bonus 1) — gemessen aus DebugInfo.token_usage, das der
    # Token-Cost-Accumulator über alle LLM-Calls eines Turns sammelt. Wir
    # aggregieren Run-weit: prompt_tokens, completion_tokens, cached_tokens.
    # cache_hit_rate = cached / prompt zeigt, wie effektiv der OpenAI-Prompt-
    # Cache greift. Niedrige Rate (<0.3) deutet auf instabile Prompt-Prefixes
    # hin (z.B. canvas_state in System-Message statt User-Message).
    sum_prompt_tokens = 0
    sum_completion_tokens = 0
    sum_cached_tokens = 0
    sum_total_calls = 0
    turns_with_usage = 0
    per_model_usage: dict[str, dict[str, int]] = {}

    # Welle E v4 (2026-05-25): Tie-Breaker entfernt — der Hint-Primary-
    # Pfad braucht keinen Score-Race-Override mehr. Die Counter bleiben
    # auf 0, das Aggregat-Feld wird leer ausgegeben (Backward-Compat).
    tie_breaker_applied = 0
    tie_breaker_evaluated = 0
    tie_breaker_overrides: dict[str, int] = {}

    for conv in conversations:
        expected_persona = conv.get("persona_id", "")
        expected_intent = conv.get("intent_id", "")
        for turn in conv.get("turns", []):
            dbg = turn.get("debug", {}) or {}
            judge = turn.get("judge", {}) or {}

            actual_persona = _strip_id(dbg.get("persona", ""))
            actual_intent = _strip_id(dbg.get("intent", ""))
            engine_pattern = _strip_id(dbg.get("pattern", ""))
            llm_hint = (dbg.get("pattern_id_hint") or "").strip()

            # Golden-Flow: per-turn Soll überschreibt conv-Level (Multi-Intent-
            # Flows haben je Turn ein eigenes Soll-Intent). Generative Runs
            # haben keine turn-level Keys → Fallback auf conv-Level. "*" = kein
            # Soll (z. B. Bot-Feedback-Flow ohne feste Persona).
            exp_p = _strip_id(turn.get("expected_persona") or "") or expected_persona
            exp_i = _strip_id(turn.get("expected_intent") or "") or expected_intent
            if exp_p == "*":
                exp_p = ""
            if exp_i == "*":
                exp_i = ""

            # Welle C Sprint 6 — Conversation-Flow-Tracking pro Turn.
            # state_id und prev_state_id wurden vom Simulator gesetzt
            # (simulate_conversation, ~line 580). transition_plausible ist
            # True/False/None (None wenn kein prev_state oder kein
            # next_likely-Eintrag).
            _curr_state = (dbg.get("state_id") or "").strip()
            _prev_state = (dbg.get("prev_state_id") or "").strip()
            _plausible = dbg.get("transition_plausible")
            if _curr_state:
                state_distribution[_curr_state] = (
                    state_distribution.get(_curr_state, 0) + 1
                )
            if _prev_state and _curr_state:
                row = state_transitions.setdefault(_prev_state, {})
                row[_curr_state] = row.get(_curr_state, 0) + 1
                if _plausible is not None:
                    transitions_total += 1
                    if _plausible:
                        transitions_plausible += 1

            # Persona-Confusion + Genauigkeit
            if exp_p and actual_persona:
                persona_total += 1
                if exp_p == actual_persona:
                    persona_correct += 1
                row = persona_confusion.setdefault(exp_p, {})
                row[actual_persona] = row.get(actual_persona, 0) + 1
                # Fair-Score: prüfe ob die Eröffnung überhaupt einen
                # Persona-Marker enthält. Wenn nicht (z.B. "Was ist OER?"
                # mit Soll=P-LEH), ist die einzig korrekte Antwort des
                # Klassifikators P-AND.
                user_msg = (turn.get("user") or "").strip()
                if exp_p == "P-AND":
                    # P-AND erwartet, dass KEINE anderen Marker im Text sind.
                    # _has_persona_marker liefert True wenn das stimmt.
                    if _has_persona_marker(user_msg, "P-AND"):
                        persona_achievable_total += 1
                        if exp_p == actual_persona:
                            persona_achievable_correct += 1
                else:
                    # Non-P-AND: nur achievable wenn der Text einen Marker
                    # der erwarteten Persona enthält.
                    if _has_persona_marker(user_msg, exp_p):
                        persona_achievable_total += 1
                        if exp_p == actual_persona:
                            persona_achievable_correct += 1
                    else:
                        persona_neutral_total += 1

            # Intent-Confusion + Genauigkeit
            if exp_i and actual_intent:
                intent_total += 1
                if exp_i == actual_intent:
                    intent_correct += 1
                row = intent_confusion.setdefault(exp_i, {})
                row[actual_intent] = row.get(actual_intent, 0) + 1

            # LLM-Hint vs Engine-Pattern
            if llm_hint and engine_pattern:
                llm_hint_present += 1
                if llm_hint == engine_pattern:
                    llm_engine_agree += 1
                # Confusion: LLM-Hint × Engine-Wahl (sieht Disagreement-Cluster)
                row = pattern_confusion.setdefault(llm_hint, {})
                row[engine_pattern] = row.get(engine_pattern, 0) + 1

            # Judge-bewertete Pattern-Korrektheit
            pm = judge.get("pattern_match")
            if pm is not None:
                judged_turns += 1
                try:
                    pm_int = int(pm)
                except Exception:
                    pm_int = 0
                pattern_match_scores.append(pm_int)
                if engine_pattern and pm_int >= 2:
                    engine_pattern_judge_ok += 1
                if llm_hint and pm_int >= 2:
                    # Pseudo: hätten wir den LLM-Hint gewählt UND der Judge
                    # findet Engine-Pattern korrekt — nur belastbar wenn
                    # LLM-Hint == Engine. Wenn nicht, wissen wir nicht ob
                    # der LLM-Hint korrekt gewesen wäre. Hier zählen wir
                    # nur die Cases wo LLM == Engine UND Judge sagt OK.
                    if llm_hint == engine_pattern:
                        llm_pattern_judge_ok += 1

            # Welle E v3 (2026-05-25) — Hint-Verdict erfassen.
            #
            # WICHTIG: ``engine_pattern`` kommt aus dem Pattern-Engine-Output
            # mit Label-Suffix ("M15 (Orientierung)"), ``llm_hint`` ist die
            # reine ID ("M15"). Wir vergleichen daher auf den ID-Prefix vor
            # dem ersten Leerzeichen — sonst gibt es Geister-Disagreements
            # für Turns wo Engine und Hint identisch sind.
            engine_id = (engine_pattern or "").split(" ", 1)[0].strip()
            hint_id = (llm_hint or "").split(" ", 1)[0].strip()
            is_agreement = bool(engine_id) and bool(hint_id) and (engine_id == hint_id)

            raw_verdict = (judge.get("pattern_hint_verdict") or "").strip().lower()
            # Forciere ``no_disagreement`` bei Agreement (Judge-Halluzinationen
            # ignorieren — bei engine==hint gibt es per Definition keinen
            # besseren Kandidaten). Bei echtem Disagreement: nimm Judge-Verdict.
            if is_agreement:
                verdict = "no_disagreement"
            elif raw_verdict in ("engine_better", "hint_better", "equivalent"):
                verdict = raw_verdict
            else:
                # Disagreement, aber Judge hat nichts/unbrauchbares geliefert.
                verdict = ""

            if verdict in hint_verdict_counts:
                hint_verdict_counts[verdict] += 1
            else:
                hint_verdict_counts[""] += 1

            # Disagreement-Paare nur bei echtem Disagreement
            if (not is_agreement and engine_id and hint_id
                    and verdict in ("engine_better", "hint_better", "equivalent")):
                key = f"{engine_id} → {hint_id}"
                pair_row = disagreement_pairs.setdefault(key, {})
                pair_row[verdict] = pair_row.get(verdict, 0) + 1

            # Tool-Compliance: Pattern.tools ∩ tools_called
            required_tools = _pattern_tools_map.get(engine_pattern, [])
            if engine_pattern and required_tools:
                actual_tools_raw = dbg.get("tools_called") or []
                # tools_called kann Strings oder Tools-mit-Annotation sein
                # ("search_wlo_collections (prefetch)") — wir matchen auf
                # den Bare-Tool-Namen am Anfang.
                actual_tool_names = set()
                for t in actual_tools_raw:
                    if isinstance(t, str):
                        bare = t.split(" ", 1)[0].strip()
                        if bare:
                            actual_tool_names.add(bare)
                tool_compliance_total += 1
                hit = any(rt in actual_tool_names for rt in required_tools)
                if hit:
                    tool_compliance_ok += 1
                row = tool_compliance_per_pattern.setdefault(
                    engine_pattern, {"ok": 0, "total": 0},
                )
                row["total"] += 1
                if hit:
                    row["ok"] += 1

            # Welle E v4: Tie-Breaker-Telemetrie entfernt (siehe oben).

            # Token-Usage / Cache-Hit-Rate (Bonus 1)
            tu = dbg.get("token_usage") or {}
            if isinstance(tu, dict) and tu:
                pt = int(tu.get("prompt_tokens") or 0)
                ct = int(tu.get("completion_tokens") or 0)
                cached = int(tu.get("cached_tokens") or 0)
                calls = int(tu.get("calls") or 0)
                if pt or ct or calls:
                    sum_prompt_tokens += pt
                    sum_completion_tokens += ct
                    sum_cached_tokens += cached
                    sum_total_calls += calls
                    turns_with_usage += 1
                    # Per-model breakdown
                    for model_name, mu in (tu.get("models") or {}).items():
                        if not isinstance(mu, dict):
                            continue
                        slot = per_model_usage.setdefault(
                            str(model_name),
                            {"prompt": 0, "completion": 0, "cached": 0, "calls": 0},
                        )
                        slot["prompt"] += int(mu.get("prompt") or 0)
                        slot["completion"] += int(mu.get("completion") or 0)
                        slot["cached"] += int(mu.get("cached") or 0)
                        slot["calls"] += int(mu.get("calls") or 0)

    return {
        # Fairer Persona-Score: nur über Eröffnungen mit Persona-Marker.
        # `persona_correct_rate` ist der Roh-Wert (inkl. neutraler Eröffnungen).
        "persona_correct_rate_fair": (
            round(persona_achievable_correct / persona_achievable_total, 3)
            if persona_achievable_total else 0.0
        ),
        "persona_achievable_total": persona_achievable_total,
        "persona_neutral_total": persona_neutral_total,
        "persona_correct_rate": (
            round(persona_correct / persona_total, 3) if persona_total else 0.0
        ),
        "persona_total_judged": persona_total,
        "persona_confusion": persona_confusion,
        "intent_correct_rate": (
            round(intent_correct / intent_total, 3) if intent_total else 0.0
        ),
        "intent_total_judged": intent_total,
        "intent_confusion": intent_confusion,
        # Welle C Sprint 6 — Conversation-Flow-Metriken.
        "state_distribution": state_distribution,
        "state_transitions": state_transitions,
        "transition_plausibility_rate": (
            round(transitions_plausible / transitions_total, 3)
            if transitions_total else 0.0
        ),
        "transitions_total": transitions_total,
        "transitions_plausible": transitions_plausible,
        # Pattern-Hint vs Final-Pattern — wie oft stimmen sie überein?
        #
        # Welle E v4 (2026-05-26): "Engine" in diesen Feldnamen ist die alte
        # Bezeichnung der Override-Pipeline (Safety + Pre-Route-Rules + LLM-
        # Hint + Fallback) — NICHT die früher mal vorhandene 3-Phasen-Score-
        # Engine. Die Felder bleiben aus Backward-Compat (Studio + Trends-
        # Endpoint) — neue Konsumenten nutzen die ``*_final_*``-Aliase unten.
        "llm_hint_present_count": llm_hint_present,
        "llm_engine_match_rate": (
            round(llm_engine_agree / llm_hint_present, 3) if llm_hint_present else 0.0
        ),
        # Alias: das gleiche wie llm_engine_match_rate, mit klarem Namen.
        "llm_hint_final_match_rate": (
            round(llm_engine_agree / llm_hint_present, 3) if llm_hint_present else 0.0
        ),
        "llm_engine_disagreement_count": llm_hint_present - llm_engine_agree,
        "llm_hint_final_disagreement_count": llm_hint_present - llm_engine_agree,
        "pattern_confusion_llm_vs_engine": pattern_confusion,
        "pattern_confusion_llm_vs_final": pattern_confusion,
        # Welle E v3 (2026-05-25) — Judge-Verdict bei Disagreement.
        # Aussagekräftig nur bei genug Disagreement-Cases (>10 sinnvoll).
        "pattern_hint_verdict_counts": hint_verdict_counts,
        "pattern_hint_better_rate": (
            round(
                hint_verdict_counts["hint_better"]
                / max(1, hint_verdict_counts["hint_better"]
                       + hint_verdict_counts["engine_better"]
                       + hint_verdict_counts["equivalent"]),
                3,
            )
        ),
        "pattern_engine_better_rate": (
            round(
                hint_verdict_counts["engine_better"]
                / max(1, hint_verdict_counts["hint_better"]
                       + hint_verdict_counts["engine_better"]
                       + hint_verdict_counts["equivalent"]),
                3,
            )
        ),
        # Klarer benannter Alias (Welle E v4): "Rule-Override besser" statt
        # "Engine besser" — beschreibt was der Counter wirklich misst.
        "pattern_override_better_rate": (
            round(
                hint_verdict_counts["engine_better"]
                / max(1, hint_verdict_counts["hint_better"]
                       + hint_verdict_counts["engine_better"]
                       + hint_verdict_counts["equivalent"]),
                3,
            )
        ),
        "pattern_disagreement_pairs": disagreement_pairs,
        # Judge-Approval pro Strategie
        "engine_pattern_judge_ok_rate": (
            round(engine_pattern_judge_ok / judged_turns, 3) if judged_turns else 0.0
        ),
        # Alias mit klarem Namen.
        "final_pattern_judge_ok_rate": (
            round(engine_pattern_judge_ok / judged_turns, 3) if judged_turns else 0.0
        ),
        # ACHTUNG: aussagekräftig nur als Lower-Bound für die LLM-Strategie,
        # weil wir nur Cases zählen können wo LLM-Hint == Engine. Disagreement-
        # Cases können wir nicht bewerten ohne separate Judge-Calls. Phase 2
        # könnte das durch Re-Judge mit dem LLM-Pattern als Behauptung lösen.
        "llm_pattern_judge_ok_lower_bound": (
            round(llm_pattern_judge_ok / judged_turns, 3) if judged_turns else 0.0
        ),
        "judged_turns": judged_turns,
        "pattern_match_score_distribution": {
            "0": pattern_match_scores.count(0),
            "1": pattern_match_scores.count(1),
            "2": pattern_match_scores.count(2),
        },
        # Tool-Compliance: wieviele Turns mit Pattern.tools auch tatsächlich
        # mind. eines der verlangten Tools aufgerufen haben.
        "tool_compliance_rate": (
            round(tool_compliance_ok / tool_compliance_total, 3)
            if tool_compliance_total else 0.0
        ),
        "tool_compliance_total": tool_compliance_total,
        "tool_compliance_per_pattern": tool_compliance_per_pattern,
        # Token-Cost / Cache-Hit (Bonus 1)
        "token_usage_aggregate": {
            "prompt_tokens": sum_prompt_tokens,
            "completion_tokens": sum_completion_tokens,
            "cached_tokens": sum_cached_tokens,
            "total_llm_calls": sum_total_calls,
            "turns_with_usage": turns_with_usage,
            "cache_hit_rate": (
                round(sum_cached_tokens / sum_prompt_tokens, 3)
                if sum_prompt_tokens else 0.0
            ),
            "avg_prompt_tokens_per_turn": (
                round(sum_prompt_tokens / turns_with_usage, 1)
                if turns_with_usage else 0.0
            ),
            "avg_completion_tokens_per_turn": (
                round(sum_completion_tokens / turns_with_usage, 1)
                if turns_with_usage else 0.0
            ),
            # A2.3 — pro Modell die Cache-Hit-Rate ergänzen, damit man sieht,
            # welcher Modell-Typ den OpenAI-Prompt-Cache wirklich nutzt
            # (gpt-4o-mini cached anders als gpt-5/5.4-mini).
            "per_model": {
                model_name: {
                    **stats,
                    "hit_rate": (
                        round(int(stats.get("cached") or 0)
                              / int(stats.get("prompt") or 1), 3)
                        if int(stats.get("prompt") or 0) else 0.0
                    ),
                }
                for model_name, stats in per_model_usage.items()
            },
            # A2.1 — pro Phase (classify / tool_loop / response /
            # quick_replies / reflection / canvas_*) die Aggregat-Numbers
            # plus Phase-spezifische Cache-Hit-Rate. Zeigt, wo der Cache
            # bricht (oft: response-Phase, weil Tool-Outputs den Prompt
            # variieren).
            "per_phase": _aggregate_per_phase(conversations),
        },
        # Tie-Breaker telemetry (Bonus 2)
        "tie_breaker": {
            "evaluated_turns": tie_breaker_evaluated,
            "applied_count": tie_breaker_applied,
            "applied_rate": (
                round(tie_breaker_applied / tie_breaker_evaluated, 3)
                if tie_breaker_evaluated else 0.0
            ),
            "overrides": tie_breaker_overrides,
        },
    }
