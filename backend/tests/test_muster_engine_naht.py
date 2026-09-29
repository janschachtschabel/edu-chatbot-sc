"""Die Naht zwischen Muster-Engine und Antwort-Prompt (Befunde 2026-09-27).

Die Bestandstests bauen ``pattern_output`` von Hand — mit ``"label": "M05
(Material)"``, ``"output_mode": "rerender"`` oder ``"id": "PAT-9"``. Im Betrieb
baut es ``phase3_modulate``, und das schrieb bis 2026-09-27 keinen dieser drei
Schlüssel:

* ``output_mode`` kannte ``PatternDef`` gar nicht (pydantic verwirft Unbekanntes
  still) — der M11-Block „Aktueller Inhalt zum Editieren" stand nie im Prompt;
* ``label`` fehlte — der Musterkopf lautete „## Aktives Pattern: ?";
* ``id`` fehlte — ``prompt_anzeige_konsistenz.exclude_patterns`` griff nie.

Dazu wählte der Rückfall von ``select_pattern`` den Klärer M03, obwohl
Docstring und Klassifikator-Prompt M15 versprechen: er nahm das erste Muster
der nach Schlüssel SORTIERTEN Liste, das in der Rückfall-Liste steht.

Der ALT hatte alle vier Lücken (gleicher Code). Diese Datei fährt deshalb vom
ausgelieferten Seed über den echten Lader und ``select_pattern`` bis in den
Prompt; nur der Speicher ist eine Attrappe — mit dem echten Seed-Inhalt.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from boerdi.domain.pattern_engine import select_pattern
from boerdi.services import config_loader as cl
from boerdi.services import seed_io
from boerdi.services.classify_prompt_blocks import _render_personas_block
from boerdi.services.config_loader import tone
from boerdi.services.response_prompt_builder import _build_system_prompt
from boerdi.services.response_prompt_display_blocks import render_card_text_mode_block
from boerdi.services.response_prompt_pattern import render_pattern_layer

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


class _SeedStore:
    """Speicher-Attrappe mit dem Inhalt des ausgelieferten Seeds."""

    def __init__(self) -> None:
        self.areas: dict[str, dict[str, Any]] = {}

    async def put(self, area: str, data: dict, updated_by: str = "") -> int:
        self.areas[area] = data
        return 1

    def get_cached(self, area: str) -> dict | None:
        return self.areas.get(area)

    def cached_areas(self) -> list[str]:
        return list(self.areas)


@pytest.fixture(scope="module")
def seed_store():
    store = _SeedStore()
    asyncio.run(seed_io.import_tree(_SEEDS, store.put))
    cl.bind_store(store)
    yield store
    cl.bind_store(None)


def _waehle(hint: str | None, persona_id: str = "P-AND"):
    """``select_pattern`` so, wie der ``route``-Knoten es ruft."""
    return select_pattern(
        persona_id, "S1", "I01", [], "/", "desktop", {}, pattern_id_hint=hint,
    )


# ── Befund 1: output_mode ──────────────────────────────────────────────────
def test_output_mode_aus_dem_seed_kommt_im_pattern_output_an(seed_store):
    _w, out, *_ = _waehle("M11")
    assert out.get("output_mode") == "rerender"


def test_muster_ohne_output_mode_bleibt_ohne(seed_store):
    # M05 führt im Seed keinen Ausgabemodus — dann darf auch keiner erscheinen.
    _w, out, *_ = _waehle("M05")
    assert out.get("output_mode") is None


def test_m11_bearbeitungsblock_steht_im_prompt(seed_store):
    """Die eigentliche Folge: der Block, der M11 den Vor-Inhalt zeigt."""
    w, out, *_ = _waehle("M11")
    system, *_ = _build_system_prompt(
        {"persona_id": "P-AND", "entities": {}, "signals": [], "next_state": "S3"},
        out, w.label,
        {"entities": {"_canvas_last_markdown": "# Quiz Brüche\n1. Was ist 1/2 + 1/4?"}},
        {}, "", None, None,
    )
    assert "## Aktueller Inhalt zum Editieren" in system
    assert "1. Was ist 1/2 + 1/4?" in system


# ── Befund 2: Mustername im Prompt ─────────────────────────────────────────
def test_musterkopf_nennt_das_gewaehlte_muster(seed_store):
    w, out, *_ = _waehle("M05")
    kopf = render_pattern_layer(out, "P-AND").splitlines()[0]
    assert kopf == f"## Aktives Pattern: {w.label}"
    assert w.label == "Material-Suche gefiltert"  # Seed-Annahme, sonst prüft der Test nichts


# ── Befund 3: Rückfall ─────────────────────────────────────────────────────
def test_rueckfall_ohne_hinweis_ist_die_orientierung(seed_store):
    # Der Klassifikator-Prompt sagt: „Lass das Feld nur leer, wenn keine
    # Pattern-Beschreibung wirklich passt — dann greift M15 (Orientierung)".
    w, *_ = _waehle(None)
    assert w.id == "M15"


def test_rueckfall_bei_unbekanntem_hinweis_ist_die_orientierung(seed_store):
    w, *_ = _waehle("M99")
    assert w.id == "M15"


# ── Befund 4: ein Kachel-Vokabular ─────────────────────────────────────────
@pytest.mark.parametrize("persona", ["P-AND", "P-ELT", "P-ENT", "P-LEH", "P-LER", "P-RED"])
def test_jede_seed_persona_bekommt_eine_kachelregel(seed_store, persona):
    # Bis 2026-09-27 standen P-ELT und P-LER (``explanation``) ohne jede
    # Kachel-Regel im Prompt.
    _w, out, *_ = _waehle("M05", persona)
    assert render_card_text_mode_block(out["card_text_mode"]), out["card_text_mode"]


def test_persona_seeds_sprechen_das_vokabular_des_laders(seed_store):
    fremd = {
        p["id"]: p["card_text_mode"] for p in cl.load_persona_definitions()
        if p.get("card_text_mode") not in tone._CARD_TEXT_MODES
    }
    assert fremd == {}


# ── Befund 8: Anti-Marker im Klassifikator-Prompt ──────────────────────────
def test_anti_marker_ohne_umleitung_traegt_seine_begruendung(seed_store):
    """„Arbeitsblatt" steht bei P-LEH als Anti-Marker ohne ``redirect_to``, im
    Seed begründet mit „Allein kein Lehrkraft-Signal". Bis 2026-09-27 kam
    davon nur „NICHT diese Persona" im Klassifikator an."""
    block = _render_personas_block(cl.load_persona_definitions())
    leh = block.split("### P-LEH")[1].split("\n### ")[0]
    assert '  - "Arbeitsblatt" — Allein kein Lehrkraft-Signal' in leh
    assert "NICHT diese Persona" not in block


# ── Befund 7: Kennung für die Anzeige-Konsistenz ───────────────────────────
def test_konsistenz_ausnahme_trifft_die_musterkennung(seed_store):
    """Beide Seiten des Vergleichs in ``tool_loop`` aus dem Betrieb: die
    Kennung aus ``phase3_modulate`` und die Liste aus dem echten Lader."""
    _w, out, *_ = _waehle("M04")
    ausnahmen = cl.load_display_rules_config()["prompt_anzeige_konsistenz"][
        "exclude_patterns"]
    assert "M04" in ausnahmen  # Seed-Annahme
    assert out.get("id") == "M04"
