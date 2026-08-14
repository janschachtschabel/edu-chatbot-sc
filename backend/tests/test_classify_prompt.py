"""P3-2: classify system-prompt renderers — port of ALT
llm_classify_prompt.py (system-prompt half; the tool half is replaced by
instructor auto-generation, spec §3-2).

Two layers:
- pure per-dimension renderers (hand-crafted dicts, no store) — deterministic,
  CI-safe, pin the exact ALT output format;
- assembly + signals against a bound store (minimal FakeStore for CI + a real
  ALT-tree parity pin for "D1-Zeit:").
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from boerdi.services import config_loader as cl
from boerdi.services.classify_prompt import (
    _render_canvas_block,
    _render_classify_overrides_block,
    _render_fewshot_block,
    _render_pattern_disambiguators_block,
    _render_signals_block,
    build_classify_system_prompt,
)
from boerdi.services.classify_prompt_blocks import (
    _render_entities_block,
    _render_intents_block,
    _render_patterns_hint_block,
    _render_personas_block,
    _render_states_block,
)

ALT_TREE = Path(r"C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\backend\chatbots\wlo\v1")


# ── pure per-dimension renderers (no store) ────────────────────────────────
def test_personas_empty_defaults_to_p_and() -> None:
    assert _render_personas_block([]) == "\n(keine Personas konfiguriert — defaulte zu P-AND.)\n"


def test_personas_renders_markers_and_discriminators() -> None:
    out = _render_personas_block([{
        "id": "P-LEH", "label": "Lehrkraft",
        "description": "Lehrkräfte planen Unterricht.",
        "positive_markers": ["meine Klasse", "Unterrichtseinheit"],
        "anti_markers": [{"phrase": "Statistik", "redirect_to": "P-AND"}],
        "discriminators": [{"vs": "P-LER", "rule": "Lehrer lehrt, Schüler lernt"}],
    }])
    assert "Explizite Selbst-ID dominiert IMMER" in out  # generic head, once
    assert "### P-LEH — Lehrkraft" in out
    assert "Lehrkräfte planen Unterricht." in out
    assert 'Positiv-Marker: "meine Klasse", "Unterrichtseinheit"' in out
    assert 'Anti-Marker (NICHT diese Persona): "Statistik" → P-AND' in out
    assert "Diskriminatoren:" in out and "  - vs. P-LER: Lehrer lehrt, Schüler lernt" in out


def test_personas_hints_alias_fallback() -> None:
    out = _render_personas_block([{"id": "P-AND", "label": "Allgemein", "hints": ["neutral"]}])
    assert 'Positiv-Marker: "neutral"' in out


def test_intents_renders_triggers_negatives_examples() -> None:
    out = _render_intents_block([{
        "id": "I05", "label": "Erstellen", "description": "Neues Material.",
        "trigger_verbs": ["erstelle", "generiere"],
        "negative_triggers": [
            {"phrase": "kürzer", "redirect_to": "I06", "when": "canvas aktiv", "rationale": "Edit"},
        ],
        "discriminators": [{"vs": "I04", "rule": "neu vs vorhanden", "example_a": "A→I05"}],
        "examples": ["Mach ein Quiz"],
    }])
    assert "Intent-Übersicht: I05 (Erstellen)" in out
    assert "INTENT-REGELN" in out
    assert "### I05 — Erstellen" in out
    assert 'Trigger-Verben: "erstelle", "generiere"' in out
    assert 'Negativ-Trigger:' in out
    assert '  - "kürzer" → I06 (wenn canvas aktiv) — Edit' in out
    assert "  - vs. I04: neu vs vorhanden" in out and "      Bsp: A→I05" in out
    assert "Beispiele:" in out and '  - "Mach ein Quiz"' in out


def test_intents_empty() -> None:
    assert _render_intents_block([]) == "\n(keine Intents konfiguriert)\n"


def test_states_renders_criteria() -> None:
    out = _render_states_block([{
        "id": "S2", "label": "Klärung", "description": "Slot fehlt.",
        "selection_criteria": ["ein Slot fehlt"],
    }])
    assert "STATE-REGELN" in out
    assert "- S2 (Klärung)" in out and "  Slot fehlt." in out
    assert "  Wahl-Kriterien:" in out and "    - ein Slot fehlt" in out


def test_entities_renders_examples_and_discriminator() -> None:
    out = _render_entities_block([{
        "id": "fach", "description": "Schulfach",
        "positive_examples": [{"text": "Mathe", "value": "Mathematik"}],
        "negative_examples": [{"text": "Klasse 5", "rationale": "Stufe"}],
        "discriminators": [{"vs": "thema", "rule": "Fach≠Thema"}],
    }])
    assert "ENTITY-REGELN" in out
    assert "- fach: Schulfach" in out
    assert '    - "Mathe" → Mathematik' in out
    assert "  Negativ-Beispiele (Slot bleibt leer):" in out
    assert '    - "Klasse 5" — Stufe' in out
    assert "  Diskriminator vs. thema: Fach≠Thema" in out


def test_patterns_hint_renders_structured_fields() -> None:
    out = _render_patterns_hint_block([{
        "id": "M15", "label": "Orientierung", "short_purpose": "Hilft bei Orientierung.",
        "when_to_use": ["unklar"], "when_not_to_use": ["klar"],
        "trigger_phrases": ["was kannst du"],
        "discriminators": [{"vs": "M03", "rule": "orient vs slot", "example": "e"}],
    }])
    assert "PATTERN-HINT (PRIMÄR" in out
    assert "### M15 — Orientierung" in out and "_Zweck:_ Hilft bei Orientierung." in out
    assert "**Einsetzen wenn:**" in out and "  - unklar" in out
    assert "**NICHT einsetzen wenn:**" in out and "  - klar" in out
    assert "Typische User-Phrasen:" in out and "was kannst du" in out
    assert "**Tie-Breaks:**" in out and "  - vs **M03**: orient vs slot" in out


def test_canvas_empty_modes_render_nothing() -> None:
    assert _render_canvas_block(None) == ""
    assert _render_canvas_block({"mode": "empty"}) == ""
    assert _render_canvas_block({}) == ""


def test_canvas_material_mode_renders_edit_rule() -> None:
    out = _render_canvas_block({
        "mode": "material", "title": "Quiz", "material_type": "quiz", "markdown": "# Q",
    })
    assert "## Canvas-Kontext" in out
    assert "Modus: material" in out and "Titel: Quiz" in out and "Material-Typ: quiz" in out
    assert "Auszug aus dem Canvas-Dokument:" in out
    assert 'intent_id="I06"' in out


def test_overrides_empty() -> None:
    assert _render_classify_overrides_block({}) == ""


def test_overrides_renders_all_sections() -> None:
    out = _render_classify_overrides_block({
        "persona_overrides": [{
            "persona": "P-LEH", "triggers": ["meine klasse"],
            "except_explicit_role": ["ich bin schüler"],
        }],
        "intent_overrides": [
            {"intent": "I06", "description": "Edit-Verben", "triggers": ["kürzer"]},
        ],
        "intent_conflict_rule": "Negativ vor Positiv",
        "topic_overrides": {
            "phantom_topic_phrases": {"phrases": ["irgendwas"]},
            "fach_as_topic_fallback": {"triggers": ["Mathe"]},
        },
    })
    assert "HARD-OVERRIDE-REGELN" in out
    assert "### Persona-Override" in out and "→ Persona = P-LEH" in out
    assert "AUSSER explizite Selbst-ID" in out
    assert "### Intent-Override" in out and "→ Intent = I06" in out
    assert "**Konflikt-Regel:** Negativ vor Positiv" in out
    assert "### Topic-Slot-Override" in out and "Phantom-Topic" in out


def test_disambiguators_empty_and_rendered() -> None:
    assert _render_pattern_disambiguators_block([]) == ""
    out = _render_pattern_disambiguators_block([{
        "label": "M03 vs M15", "rules": ["wenn slot fehlt → M03"],
        "examples": [{"input": "hi", "expected": "M15", "rationale": "kein slot"}],
    }])
    assert "PATTERN-KONFLIKTE" in out and "**M03 vs M15**" in out
    assert "- wenn slot fehlt → M03" in out
    assert "M15" in out and "kein slot" in out


def test_fewshot_empty_and_rendered() -> None:
    assert _render_fewshot_block([]) == ""
    out = _render_fewshot_block([
        {"input": "Mach ein Quiz", "intent": "I05", "pattern": "M07", "note": "canvas"},
    ])
    assert "FEW-SHOT-BEISPIELE" in out
    assert "Mach ein Quiz" in out and "I05, M07" in out and "(canvas)" in out


# ── assembly + signals against a bound store ───────────────────────────────
class _FakeStore:
    def __init__(self, areas: dict[str, dict[str, Any]]) -> None:
        self.areas = areas

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)

    def clear_cache(self, area: str | None = None) -> None:  # pragma: no cover - unused
        self.areas.clear() if area is None else self.areas.pop(area, None)


_MIN_AREAS: dict[str, dict[str, Any]] = {
    "04-intents/intents": {"intents": [
        {"id": "I03", "label": "Suchen", "description": "Material suchen.",
         "trigger_verbs": ["suche"]},
    ]},
    "04-states/states": {"states": [
        {"id": "S1", "label": "Orientierung", "description": "Kein Anliegen.",
         "selection_criteria": ["offen"]},
    ]},
    "04-entities/entities": {"entities": [{"id": "fach", "description": "Schulfach"}]},
    "04-signals/signal-modulations": {"signals": {
        "zeitdruck": {"dimension": "D1-Zeit", "label": "Zeitdruck"},
        "effizient": {"dimension": "D1-Zeit", "label": "Effizient"},
        "unsicher": {"dimension": "D2-Sicherheit", "label": "Unsicher"},
    }},
    "04-personas/leh": {"frontmatter": {
        "id": "P-LEH", "label": "Lehrkraft", "description": "Plant Unterricht.",
        "positive_markers": ["meine Klasse"]}, "body": "# H\nprosa"},
    "03-patterns/m15": {"frontmatter": {
        "id": "M15", "label": "Orientierung", "short_purpose": "Orientierung geben."},
        "body": "# H\n"},
    "01-base/classify-overrides": {
        "persona_overrides": [{"persona": "P-LEH", "triggers": ["meine klasse"]}],
        "few_shot_examples": [{"input": "hallo", "intent": "I03", "pattern": "M15"}],
    },
}


@pytest.fixture()
def bound_min_store():
    cl.bind_store(_FakeStore({k: dict(v) for k, v in _MIN_AREAS.items()}))
    yield
    cl.bind_store(None)


def test_signals_block_groups_by_dimension(bound_min_store) -> None:
    out = _render_signals_block()
    assert "D1-Zeit: zeitdruck, effizient" in out
    assert "D2-Sicherheit: unsicher" in out


def test_signals_block_empty_when_unbound() -> None:
    cl.bind_store(None)
    assert _render_signals_block() == "\n(keine Signale konfiguriert)\n"


def test_assembly_has_all_sections_in_static_then_dynamic_order(bound_min_store) -> None:
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "entities": {}, "turn_count": 0},
        {"page": "/", "device": "desktop", "page_context": {}},
    )
    for header in ("## Personas", "## Intents", "## Signale", "## States",
                   "## Entities", "## Patterns", "## Aktueller Turn-Kontext"):
        assert header in prompt, f"missing {header}"
    # static prefix precedes the dynamic turn-context (prompt-cache ordering)
    assert prompt.index("## Personas") < prompt.index("## Aktueller Turn-Kontext")
    assert "Rufe classify_input auf" in prompt
    assert "FEW-SHOT-BEISPIELE" in prompt  # overrides area drove the fewshot block


def test_assembly_dynamic_block_reflects_session_state(bound_min_store) -> None:
    prompt = build_classify_system_prompt(
        {"state_id": "S2", "entities": {"fach": "Mathe"}, "turn_count": 2,
         "persona_id": "P-LEH"},
        {"page": "/faecher/mathe", "device": "mobile",
         "page_context": {"node_id": "abc", "secret": "drop"}},
    )
    assert "State: S2" in prompt
    assert "Turn: 3" in prompt  # turn_count + 1
    assert "Seite: /faecher/mathe" in prompt
    assert "Device: mobile" in prompt
    assert "Aktuelle Persona: P-LEH" in prompt
    assert '"node_id": "abc"' in prompt  # whitelisted raw page-context key
    assert "secret" not in prompt  # non-whitelisted key dropped


def test_assembly_canvas_context_included_when_active(bound_min_store) -> None:
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "entities": {}, "turn_count": 0},
        {"page": "/", "device": "desktop", "page_context": {}},
        canvas_state={"mode": "material", "title": "AB", "markdown": "# x"},
    )
    assert "## Canvas-Kontext" in prompt and 'intent_id="I06"' in prompt


# ── semantic page-context block (P3) ───────────────────────────────────────
def test_page_context_resolved_block_in_dynamic(bound_min_store) -> None:
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "turn_count": 0,
         "entities": {"_page_metadata": {"title": "Optik", "unresolved": False}}},
        {"page": "/", "device": "desktop",
         "page_context": {"page_kind": "collection", "collection_id": "C1"}},
    )
    assert "## Aktuelle Seite — Sammlung (edu-sharing)" in prompt
    assert "Titel: Optik" in prompt
    # the block sits in the dynamic turn-context, after the static prefix
    assert prompt.index("## Personas") < prompt.index("## Aktuelle Seite —")


def test_page_context_raw_fallback_when_unresolved(bound_min_store) -> None:
    # no _page_metadata → get_cached None → render_for_prompt "" → raw fallback
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "entities": {}, "turn_count": 0},
        {"page": "/", "device": "desktop",
         "page_context": {"page_kind": "content", "page_text": "Sichtbarer Seitentext."}},
    )
    assert "## Inhalt der aktuellen Seite (Heuristik)" in prompt
    assert "Sichtbarer Seitentext." in prompt  # DOM text the raw one-liner whitelist drops


def test_no_page_context_block_when_nothing(bound_min_store) -> None:
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "entities": {}, "turn_count": 0},
        {"page": "/", "device": "desktop", "page_context": {}},
    )
    assert "## Aktuelle Seite —" not in prompt
    assert "## Inhalt der aktuellen Seite (Heuristik)" not in prompt


def test_page_context_block_failure_is_swallowed(bound_min_store, monkeypatch) -> None:
    from boerdi.services import classify_prompt as cp

    def boom(_ss):
        raise RuntimeError("cache read blew up")

    monkeypatch.setattr(cp.page_context, "get_cached", boom)
    prompt = build_classify_system_prompt(
        {"state_id": "S1", "entities": {"_page_metadata": {"title": "Optik"}}, "turn_count": 0},
        {"page": "/", "device": "desktop", "page_context": {"page_kind": "collection"}},
    )
    # a page-block failure must not break classification — the prompt still assembles
    assert "## Personas" in prompt
    assert "## Aktuelle Seite —" not in prompt


# ── real ALT-tree parity pin ───────────────────────────────────────────────
@pytest.mark.skipif(not ALT_TREE.exists(), reason="ALT-Baum nicht vorhanden (CI)")
def test_real_config_signals_pin_d1_zeit() -> None:
    import asyncio

    from boerdi.services import seed_io

    store = _FakeStore({})

    async def _put(area: str, data: dict, updated_by: str = "") -> int:
        store.areas[area] = data
        return 1

    asyncio.run(seed_io.import_tree(ALT_TREE, _put))
    cl.bind_store(store)
    try:
        prompt = build_classify_system_prompt(
            {"state_id": "S1", "entities": {}, "turn_count": 0},
            {"page": "/", "device": "desktop", "page_context": {}},
        )
        assert "D1-Zeit:" in prompt  # real signal-modulations dimension label
        for header in ("## Personas", "## Intents", "## Signale", "## States",
                       "## Entities", "## Patterns", "## Aktueller Turn-Kontext"):
            assert header in prompt
    finally:
        cl.bind_store(None)


# ── Review-Befund 2026-08-14: der Klassifikator ist der DRITTE Verbraucher ──


def test_der_klassifikator_bekommt_den_skillkatalog_nicht(bound_min_store) -> None:
    """``render_for_prompt`` speist drei Prompts, nicht zwei.

    Muster-Engine und Agent-Schleife SOLLEN den Bestand sehen. Der
    Klassifikator nicht: er wählt ein Muster und ruft keine Skills auf. Gemessen
    waren es +2 232 Zeichen je Klassifikation — und vor allem formt es seinen
    Prompt, wofür der Plan ausdrücklich einen Golden-Lauf verlangt.

    Der Seitenblock selbst bleibt (Titel, IDs) — abgeschaltet wird nur der
    Bestandsabschnitt.
    """
    state = {
        "state_id": "S1", "turn_count": 0,
        "entities": {"_page_metadata": {
            "title": "Geometrische Optik",
            "context_facts": {
                "materials": 35, "skills": 28,
                "skill_titles": ["Stunde planen"],
            },
        }},
    }
    prompt = build_classify_system_prompt(
        state,
        {"page": "/", "device": "desktop",
         "page_context": {"page_kind": "collection", "collection_id": "C1"}},
    )
    assert "Geometrische Optik" in prompt          # Seitenblock bleibt
    assert "Bestand dieser Sammlung" not in prompt
    assert "Stunde planen" not in prompt
