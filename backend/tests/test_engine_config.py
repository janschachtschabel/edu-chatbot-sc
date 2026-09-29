"""01-base/engine — welche Maschine einen Zug beantwortet.

Ein eigener Bereich und kein Feld in ``01-base/policy``: „welche Maschine
antwortet" ist ein neuer Begriff, er wird wachsen (die Deckel der Agent-Schleife
wohnen mit), und ihn in ``policy`` zu verstecken machte diesen Bereich
zweideutig. Präzedenz für den Zusatz: ``01-base/pricing`` (K3).

Der letzte Test ist der wichtige. Die Kostentafel hat die Lektion einmal bezahlt:
der Studio-Editor rendert **selbst**, aus einer gemessenen Teilmenge von
JSON-Schema (``schema-form/json-schema.ts``), und der Mapper schaltet auf
``type``. Was er dort nicht findet, fällt auf ein rohes JSON-Feld zurück — und
ein Umschalter, den man nur noch als JSON tippen kann, verfehlt den Zweck dieses
Bereichs.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from boerdi.domain.config_models import AREA_MODELS
from boerdi.domain.config_models.engine import EngineArea


def test_bereich_ist_registriert() -> None:
    assert AREA_MODELS["01-base/engine"] is EngineArea


def test_vorgabe_ist_die_muster_engine() -> None:
    """Der Nutzer-Entscheid als Zusicherung: ohne Pflege ändert sich nichts."""
    bereich = EngineArea()
    assert bereich.mode == "pattern"
    assert bereich.agent.write_mode == "propose", "Schreiben ist nie die Vorgabe"
    assert bereich.agent.safety is True
    # E-6: die Skill-Brücke im Muster-Modus schaltet der Betreiber zu.
    assert bereich.muster_skills is False


def test_der_skill_schalter_ist_im_studio_ein_haken() -> None:
    """Ein ``bool`` rendert der Studio-Mapper als Kontrollkästchen."""
    feld = EngineArea.model_json_schema()["properties"]["muster_skills"]
    assert feld.get("type") == "boolean"


def test_unbekannter_modus_wird_abgewiesen() -> None:
    with pytest.raises(ValidationError):
        EngineArea(mode="turbo")


def test_unsinnige_deckel_werden_abgewiesen() -> None:
    """Das Studio schreibt direkt gegen dieses Modell (``PUT /config/data/…``).
    Eine Frist von 0 s beendete jeden Lauf vor dem ersten Werkzeug."""
    with pytest.raises(ValidationError):
        EngineArea(agent={"max_iterations": 0})
    with pytest.raises(ValidationError):
        EngineArea(agent={"deadline_s": 0})


def test_das_schema_bleibt_im_studio_bedienbar() -> None:
    schema = EngineArea.model_json_schema()
    mode = schema["properties"]["mode"]
    assert mode.get("type") == "string", (
        "ohne ``type`` fällt der Studio-Mapper auf ein rohes JSON-Feld zurück"
    )
    # ``agent`` ist ein verschachteltes Modell → $ref auf $defs, die im Mapper
    # gemessene Form (26 von 32 Bereichsmodellen nutzen sie).
    assert "$ref" in schema["properties"]["agent"]


def test_die_auswahl_kennt_nur_noch_zwei_maschinen() -> None:
    """K1-1 (2026-09-27): der Hybrid ist entfernt, das Studio bietet ihn nicht an."""
    assert EngineArea.model_json_schema()["properties"]["mode"]["enum"] == [
        "pattern", "agent"]


def test_ein_gespeichertes_hybrid_wird_als_agent_gelesen() -> None:
    """Ohne diese Umdeutung schlüge die Prüfung fehl, ``load_engine`` fiele auf
    die Vorgabe zurück — und die Anlage liefe still als Muster-Maschine, samt
    zurückgesetzter Deckel."""
    engine = EngineArea.model_validate({"mode": "hybrid", "agent": {"max_iterations": 7}})
    assert engine.mode == "agent"
    assert engine.agent.max_iterations == 7


def test_ein_gespeichertes_hybrid_warnt_einmal_je_prozess(caplog) -> None:
    """``load_engine`` liest den Bereich in jedem Zug — eine Warnung je Zug wäre
    Rauschen, keine je Prozess wäre unsichtbar."""
    from boerdi.domain.config_models.engine import warne_hybrid_einmal

    warne_hybrid_einmal.cache_clear()
    with caplog.at_level("WARNING"):
        EngineArea.model_validate({"mode": "hybrid"})
        EngineArea.model_validate({"mode": "hybrid"})
    assert sum("hybrid" in r.getMessage() for r in caplog.records) == 1
