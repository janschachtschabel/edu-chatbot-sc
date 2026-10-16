"""Tote Auslöser gestrichen (Paket 7, K4 — Nutzer-Entscheid 2026-10-09).

``05-canvas/create-triggers`` und ``05-canvas/edit-triggers`` standen im Studio,
ihre einzigen Leser (``looks_like_create_intent``, ``looks_like_edit_intent``,
``has_explicit_new_create_override``) rief aber kein Produktionscode: Material
entsteht über die Klassifikation (I05) und den Typ-Aliasen in
``05-canvas/type-aliases``, die Web-Tour über ihren eigenen Bereich. Wer dort
pflegte, änderte nichts.

Mit dem Bereich fallen Modell, Lader, Getter, Seed und Studio-Abschnitt; eine
Migration räumt die Zeilen bestehender Datenbanken ab, damit „Alle Bereiche“ und
der Abgleich mit dem Auslieferungsstand sie nicht ewig weiterführen.
"""

from __future__ import annotations

import asyncio

import asyncpg
import pytest

from boerdi.domain import area_effects
from boerdi.domain.canvas import intent, types
from boerdi.domain.config_models import AREA_MODELS
from boerdi.services import config_loader, seed_sync
from tests import pg_utils

_GESTRICHEN = ("05-canvas/create-triggers", "05-canvas/edit-triggers")


def test_die_bereiche_haben_kein_modell_und_keine_wirkungszeile():
    for area in _GESTRICHEN:
        assert area not in AREA_MODELS, area
        assert area not in area_effects.AREA_EFFECTS, area


def test_der_seed_liefert_sie_nicht_mehr_aus():
    seed = asyncio.run(seed_sync.seed_lesen(seed_sync.seed_pfad("seeds")))
    assert not set(_GESTRICHEN) & set(seed)


def test_lader_getter_und_heuristiken_sind_weg():
    for name in ("load_canvas_create_triggers", "load_canvas_edit_triggers"):
        assert not hasattr(config_loader, name), name
    for name in ("get_create_triggers", "get_edit_triggers", "get_explicit_create_overrides"):
        assert not hasattr(types, name), name
    for name in ("looks_like_create_intent", "looks_like_edit_intent",
                 "has_explicit_new_create_override"):
        assert not hasattr(intent, name), name


# ── Migration 0007 räumt bestehende Zeilen ab ──────────────────────────────

_TEST_DB = "boerdi_k4_test"


@pytest.mark.pg
@pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON)
def test_die_migration_loescht_nur_die_beiden_zeilen():
    pg_utils.create_migrated_db(_TEST_DB, revision="0006")
    dsn = pg_utils.asyncpg_dsn(_TEST_DB)

    async def _vorher() -> None:
        conn = await asyncpg.connect(dsn)
        try:
            for area in (*_GESTRICHEN, "05-canvas/type-aliases"):
                await conn.execute(
                    "INSERT INTO config_areas (area, data) VALUES ($1, '{}'::jsonb)", area)
        finally:
            await conn.close()

    async def _nachher() -> set[str]:
        conn = await asyncpg.connect(dsn)
        try:
            return {r[0] for r in await conn.fetch("SELECT area FROM config_areas")}
        finally:
            await conn.close()

    try:
        asyncio.run(_vorher())
        pg_utils.upgrade_db(_TEST_DB, "head")
        assert asyncio.run(_nachher()) == {"05-canvas/type-aliases"}
    finally:
        pg_utils.drop_db(_TEST_DB)
