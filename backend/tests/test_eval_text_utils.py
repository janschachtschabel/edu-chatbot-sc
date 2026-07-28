"""Port of ALT tests/test_eval_text_utils.py — the shared eval text helpers.

Only the two helpers the *generative* engine needs are ported:
``_strip_id`` (confusion matrices) and ``_has_persona_marker`` (scenario drift
telemetry), plus their two internals. ALT's ``_detect_register``/``_repo_host``
are golden-only and already live in the framework-free ``evals/run_golden.py``
(``detect_register``/``repo_host``) — porting them again would be a duplicate.

Adaptation to the DB-backed loader (documented, not a weakening): ALT read the
persona MDs off disk, so its marker tests hit real files. Here the marker logic
is pinned against a fake loader (deterministic, incl. the P-AND branch ALT
could not reach with real data), and one test seeds the REAL ALT tree through
the in-memory store to prove the wiring — the same split
test_config_loader_surface.py uses.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from boerdi.services import config_loader as cl
from boerdi.services import seed_io
from boerdi.services.eval import text_utils as tu

ALT_TREE = Path(r"C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\backend\chatbots\wlo\v1")


@pytest.fixture()
def fake_personas(monkeypatch):
    """Two markered personas + P-AND, which owns no markers of its own."""
    personas: list[dict[str, Any]] = [
        {"id": "P-LEH", "hints": ["für meinen Unterricht", "Klasse 7"]},
        {"id": "P-SUS", "hints": ["für die Schule", "Referat"]},
        {"id": "P-AND", "hints": []},
    ]
    monkeypatch.setattr(tu, "load_persona_definitions", lambda: personas)
    return personas


# ── _normalize_marker ───────────────────────────────────────────────


def test_normalize_marker_lowercases_without_stripping():
    # ALT-Ist-Verhalten: nur lowercase, KEIN strip der Ränder.
    assert tu._normalize_marker("Test-Marker.") == "test-marker."
    assert tu._normalize_marker("  Hallo ") == "  hallo "


def test_normalize_marker_folds_umlauts_so_fuer_matches_für():
    assert tu._normalize_marker("für") == tu._normalize_marker("fuer")
    assert tu._normalize_marker("Größe") == "groesse"


def test_normalize_marker_survives_empty():
    assert tu._normalize_marker("") == ""


# ── _strip_id ───────────────────────────────────────────────────────


def test_strip_id_keeps_bare_id_and_drops_label():
    assert tu._strip_id("M03 (Schritt-für-Schritt)") == "M03"


def test_strip_id_removes_uuid_tail():
    assert tu._strip_id("foo 12345678-1234-1234-1234-123456789abc bar") == "foo"


def test_strip_id_passes_through_undecorated_and_empty():
    assert tu._strip_id("M03") == "M03"
    assert tu._strip_id("") == ""


# ── _load_persona_markers / _has_persona_marker ─────────────────────


def test_load_persona_markers_normalizes_and_drops_empties(fake_personas):
    markers = tu._load_persona_markers()
    assert markers["P-LEH"] == ["fuer meinen unterricht", "klasse 7"]
    assert markers["P-AND"] == []


def test_load_persona_markers_skips_personas_without_id(monkeypatch):
    monkeypatch.setattr(
        tu, "load_persona_definitions",
        lambda: [{"id": "", "hints": ["x"]}, {"id": "P-LEH", "hints": ["y"]}],
    )
    assert tu._load_persona_markers() == {"P-LEH": ["y"]}


def test_has_persona_marker_matches_accent_folded(fake_personas):
    assert tu._has_persona_marker("Material fuer meinen Unterricht", "P-LEH") is True
    assert tu._has_persona_marker("Material für meinen Unterricht", "P-LEH") is True


def test_has_persona_marker_is_false_when_the_anchor_is_missing(fake_personas):
    # This is the drift signal: an LLM-generated scenario that lost its anchor.
    assert tu._has_persona_marker("Was ist OER?", "P-LEH") is False
    assert tu._has_persona_marker("", "P-LEH") is False


def test_has_persona_marker_p_and_is_true_only_without_foreign_markers(fake_personas):
    # P-AND owns no markers: drift means ANOTHER persona's marker leaked in.
    assert tu._has_persona_marker("Was ist OER?", "P-AND") is True
    assert tu._has_persona_marker("Etwas für die Schule", "P-AND") is False


def test_has_persona_marker_is_permissive_for_unknown_persona(fake_personas):
    # Neither block the eval nor fake a drift signal we cannot compute.
    assert tu._has_persona_marker("beliebiger Text", "P-NEU") is True


@pytest.mark.skipif(not ALT_TREE.exists(), reason="ALT-Baum nicht vorhanden (CI)")
def test_markers_come_from_the_real_persona_definitions():
    """Wiring proof: the markers really are the personas' Positiv-Marker."""
    class FakeStore:
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
            self.areas.clear() if area is None else self.areas.pop(area, None)

    store = FakeStore()
    asyncio.run(seed_io.import_tree(ALT_TREE, store.put))
    cl.bind_store(store)
    try:
        markers = tu._load_persona_markers()
        assert markers, "keine Personas geladen"
        pid, mlist = next((p, m) for p, m in markers.items() if m)
        assert tu._has_persona_marker(mlist[0], pid) is True
    finally:
        cl.bind_store(None)
