"""P2-3: port of ALT tests/test_config_loader_surface.py — pins the public
loader surface (41 zero-arg loaders + arg-taking helpers + guards).

Adaptations to the DB-backed facade (documented, not weakenings):
- loaders read a BOUND store's cache — fixture seeds an in-memory store
  from the REAL ALT tree (skips when the sibling repo is absent);
- write_config_file is async (DB write) — called via asyncio.run;
- the ALT cache test pinned refill-consistency after invalidate; NEU refill
  is preload() (NOTIFY-driven in prod), so the test re-seeds explicitly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from boerdi.services import config_loader as cl
from boerdi.services import seed_io

ALT_TREE = Path(r"C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\backend\chatbots\wlo\v1")

pytestmark = pytest.mark.skipif(not ALT_TREE.exists(), reason="ALT-Baum nicht vorhanden (CI)")

ZERO_ARG_CONTRACT: dict[str, type] = {
    "card_pipeline_v2_enabled": bool,
    "get_all_rag_areas": list,
    "get_always_on_rag_areas": list,
    "get_enabled_mcp_servers": list,
    "get_on_demand_rag_areas": list,
    "get_repo_base_url": str,
    "list_config_files": list,
    "load_base_persona": str,
    "load_canvas_create_triggers": dict,
    "load_canvas_edit_triggers": dict,
    "load_canvas_material_types": list,
    "load_canvas_persona_priorities": dict,
    "load_canvas_type_aliases": dict,
    "load_card_pipeline_config": dict,
    "load_classify_overrides_config": dict,
    "load_device_config": dict,
    "load_display_rules_config": dict,
    "load_domain_rules": str,
    "load_entities": list,
    "load_gold_flows": list,
    "load_guardrails": str,
    "load_guide_mode_config": dict,
    "load_guide_rules_config": dict,
    "load_header_nav_config": dict,
    "load_intents": list,
    "load_mcp_servers": list,
    "load_pattern_definitions": list,
    "load_persona_definitions": list,
    "load_placeholder_topics_config": dict,
    "load_policy_config": dict,
    "load_privacy_config": dict,
    "load_quality_log_config": dict,
    "load_rag_config": dict,
    "load_safety_config": dict,
    "load_signal_modulations": tuple,
    "load_states": list,
    "load_tie_breaker_config": dict,
    "load_tone_modifiers_config": dict,
    "load_website_tour_config": dict,
    "load_welcome_config": dict,
    "load_widget_modes_config": dict,
}


class FakeStore:
    """In-memory ConfigStore look-alike (get_cached/cached_areas/clear/put)."""

    def __init__(self) -> None:
        self.areas: dict[str, dict[str, Any]] = {}

    async def put(self, area: str, data: dict, updated_by: str = "") -> int:
        self.areas[area] = data
        return 1

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)

    def clear_cache(self, area: str | None = None) -> None:
        if area is None:
            self.areas.clear()
        else:
            self.areas.pop(area, None)


def _seed() -> FakeStore:
    store = FakeStore()
    asyncio.run(seed_io.import_tree(ALT_TREE, store.put))
    return store


@pytest.fixture(scope="module")
def seeded_store():
    store = _seed()
    cl.bind_store(store)
    yield store
    cl.bind_store(None)


@pytest.mark.parametrize("name,expected_type", sorted(ZERO_ARG_CONTRACT.items()))
def test_zero_arg_loader_return_type(seeded_store, name, expected_type):
    fn = getattr(cl, name, None)
    assert callable(fn), f"öffentliche Funktion {name} fehlt"
    assert isinstance(fn(), expected_type)


@pytest.mark.parametrize("name", [
    "load_intents", "load_states", "load_entities",
    "load_canvas_material_types", "load_pattern_definitions",
])
def test_list_loader_items_have_id(seeded_store, name):
    items = getattr(cl, name)()
    assert isinstance(items, list) and items, f"{name} sollte nicht-leer sein"
    for it in items:
        assert isinstance(it, dict)
        assert it.get("id"), f"{name}: Item ohne 'id'"


def test_persona_definitions_items_are_dicts_with_description(seeded_store):
    personas = cl.load_persona_definitions()
    assert personas and all(
        isinstance(p, dict) and "description" in p for p in personas
    )


def test_signal_modulations_shape(seeded_store):
    table, order = cl.load_signal_modulations()
    assert isinstance(table, dict)
    assert isinstance(order, list)


def test_get_state_directive_returns_dict_for_known_state(seeded_store):
    first = cl.load_states()[0]["id"]
    assert isinstance(cl.get_state_directive(first), dict)


def test_load_persona_prompt_returns_str_for_known_persona(seeded_store):
    first = cl.load_persona_definitions()[0]["id"]
    assert isinstance(cl.load_persona_prompt(first), str)


def test_rewrite_repo_host_returns_str(seeded_store):
    assert isinstance(
        cl.rewrite_repo_host("https://redaktion.openeduhub.net/x"), str
    )


@pytest.mark.parametrize("name", [
    "load_intents", "load_safety_config", "load_persona_definitions",
])
def test_repeated_call_is_consistent(seeded_store, name):
    fn = getattr(cl, name)
    assert fn() == fn()


def test_invalidate_then_reseed_preserves_shape(seeded_store):
    before = cl.load_safety_config()
    cl.invalidate_yaml_cache()  # full cache drop
    assert cl.load_safety_config() == {}  # DB-backed: empty until refill
    seeded_store.areas.update(_seed().areas)  # NEU refill = preload/NOTIFY
    after = cl.load_safety_config()
    assert type(before) is type(after)
    assert after == before


def test_read_config_file_rejects_traversal(seeded_store):
    with pytest.raises(ValueError):
        cl.read_config_file("../../../../etc/passwd")


def test_write_config_file_rejects_traversal(seeded_store):
    with pytest.raises(ValueError):
        asyncio.run(cl.write_config_file("../../../../tmp/evil.txt", "x"))


def test_write_then_read_roundtrip(seeded_store):
    asyncio.run(cl.write_config_file(
        "01-base/welcome-config.yaml",
        "welcome:\n  greeting: Servus\n  quick_replies: [x]\n  tour_reply: ''\n",
    ))
    cfg = cl.load_welcome_config()
    assert cfg["greeting"] == "Servus"
    assert cfg["quick_replies"] == ["x"]
    text = cl.read_config_file("01-base/welcome-config.yaml")
    assert "Servus" in text


# ── C1-g1a: die zweite Sprache als Suffix je Schluessel ────────────────────
# Nutzer-Entscheid 2026-08-04: „EN optional, Rueckfall auf DE je Schluessel".
# Ein LEERES ``*_en`` heisst deshalb nicht „leerer Text", sondern „nimm das
# deutsche Feld" — die Wahl trifft das Widget, der Loader liefert nur beides.

def test_welcome_liefert_beide_sprachen(seeded_store):
    asyncio.run(cl.write_config_file(
        "01-base/welcome-config.yaml",
        "welcome:\n"
        "  greeting: Servus\n"
        "  greeting_en: Hello there\n"
        "  quick_replies: [a, b]\n"
        "  quick_replies_en: [A, B]\n"
        "  tour_reply: Zeig mir alles\n"
        "  tour_reply_en: Show me around\n",
    ))
    cfg = cl.load_welcome_config()
    assert cfg["greeting"] == "Servus"
    assert cfg["greeting_en"] == "Hello there"
    assert cfg["quick_replies"] == ["a", "b"]
    assert cfg["quick_replies_en"] == ["A", "B"]
    assert cfg["tour_reply"] == "Zeig mir alles"
    assert cfg["tour_reply_en"] == "Show me around"


def test_welcome_ohne_englisch_liefert_leere_felder_statt_deutsch(seeded_store):
    """Der Loader setzt NICHT die deutschen Werte ein.

    Ersetzte er sie, koennte das Widget „bewusst gleich" nicht mehr von
    „nicht gepflegt" unterscheiden — und ein spaeterer Rueckfall auf den
    eingebauten englischen Katalog waere fuer immer verbaut.
    """
    asyncio.run(cl.write_config_file(
        "01-base/welcome-config.yaml",
        "welcome:\n  greeting: Servus\n  quick_replies: [a]\n  tour_reply: ''\n",
    ))
    cfg = cl.load_welcome_config()
    assert cfg["greeting"] == "Servus"
    assert cfg["greeting_en"] == ""
    assert cfg["quick_replies_en"] == []
    assert cfg["tour_reply_en"] == ""


def test_header_nav_buttons_tragen_label_en(seeded_store):
    asyncio.run(cl.write_config_file(
        "01-base/header-nav.yaml",
        "header_nav:\n"
        "  buttons:\n"
        "    - id: home\n"
        "      enabled: true\n"
        "      label: Startseite\n"
        "      label_en: Home\n"
        "      icon: home\n"
        "      url: https://example.org/\n"
        "      new_tab: false\n",
    ))
    buttons = cl.load_header_nav_config()["buttons"]
    assert buttons[0]["label"] == "Startseite"
    assert buttons[0]["label_en"] == "Home"


# ── C1-g2a: dieselbe Regel für die Lotsen-Beschriftungen ───────────────────

def test_guide_rules_tragen_label_en(seeded_store):
    asyncio.run(cl.write_config_file(
        "02-domain/guide-rules.yaml",
        "message_rules:\n"
        "  - pattern: oer\n"
        "    label: OER-Erklärung\n"
        "    label_en: What is OER?\n"
        "    url: https://wirlernenonline.de/oer\n"
        "    priority: 60\n"
        "  - pattern: mitmachen\n"
        "    label: Mitmachen-Seite\n"
        "    url: https://wirlernenonline.de/mitmachen\n"
        "    priority: 75\n",
    ))
    rules = cl.load_guide_rules_config()["message_rules"]
    assert rules[0]["label_en"] == "What is OER?"
    # Ohne gepflegte Fassung bleibt das Feld leer — der Loader setzt NICHT das
    # deutsche Label ein, sonst könnte niemand mehr „fehlt" von „gleich"
    # unterscheiden (dieselbe Regel wie bei der Begrüßung, C1-g1a).
    assert rules[1]["label_en"] == ""


# ── C1-g2b: Kontext-Begrüßungen und Chips ─────────────────────────────────

def test_context_actions_tragen_beide_sprachen(seeded_store):
    asyncio.run(cl.write_config_file(
        "01-base/context-actions.yaml",
        "context_actions:\n"
        "  greetings:\n"
        "    collection: Du bist in „{title}“.\n"
        "  greetings_en:\n"
        "    collection: You are in “{title}”.\n"
        "  pills:\n"
        "    collection:\n"
        "      - label: Sammlung erkunden\n"
        "        label_en: Explore collection\n"
        "        kind: action\n"
        "        action: browse_collection\n"
        "      - label: Inhalt melden\n"
        "        kind: report\n",
    ))
    cfg = cl.load_context_actions()
    assert cfg["greetings"]["collection"] == "Du bist in „{title}“."
    assert cfg["greetings_en"]["collection"] == "You are in “{title}”."
    pills = cfg["pills"]["collection"]
    assert pills[0]["label_en"] == "Explore collection"
    assert pills[1]["label_en"] == ""


def test_context_actions_ohne_englisch_liefern_leere_felder(seeded_store):
    """Die deutschen Vorgaben des Loaders bleiben einsprachig.

    Sie sind die Notbremse für eine leere Config, kein Pflegeort — genau wie
    `_RULES` im Lotsen-Injektor (C1-g2a). Ein englischer Wert hier hieße: zwei
    Wahrheiten pflegen.
    """
    asyncio.run(cl.write_config_file(
        "01-base/context-actions.yaml", "context_actions:\n  enabled: true\n",
    ))
    cfg = cl.load_context_actions()
    assert cfg["greetings"]["collection"]          # deutsche Vorgabe greift
    # Als Eigenschaft geprüft, nicht als Aufzählung: die Arten wachsen (die
    # Seitenkontext-Erweiterung brachte search/home/external), die Regel nicht.
    assert set(cfg["greetings_en"]) == set(cfg["greetings"])
    assert all(v == "" for v in cfg["greetings_en"].values())
    assert all(p["label_en"] == "" for p in cfg["pills"]["collection"])
