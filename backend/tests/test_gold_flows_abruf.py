"""Gold-Flows „auf Abruf“ (Paket 7, K3 — Nutzer-Entscheid 2026-10-09).

GV-RED-1 nimmt real Inhalte auf Staging auf. Die Vergleichs-Matrix ließ ihn
schon weg (``--exclude``), ein Lauf über „alle Flows“ — im Studio die leere
Auswahl, in der Kommandozeile ohne ``--only`` — nahm ihn mit. Jetzt läuft ein
Flow mit ``auf_abruf: true`` nur, wenn man ihn ausdrücklich wählt.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from boerdi.domain.config_models.knowledge import GoldFlow
from boerdi.services import seed_sync
from boerdi.services.eval.flow_wahl import flows_waehlen

_FLOWS = [
    {"id": "GV-LEH-1", "turns": [{}]},
    {"id": "GV-RED-1", "turns": [{}], "auf_abruf": True},
    {"id": "GV-LER-1", "turns": [{}]},
]


def test_ohne_auswahl_laufen_alle_ausser_denen_auf_abruf():
    flows, warnungen = flows_waehlen(_FLOWS, [])
    assert [f["id"] for f in flows] == ["GV-LEH-1", "GV-LER-1"]
    assert warnungen == []


def test_ausdruecklich_gewaehlt_laeuft_auch_ein_flow_auf_abruf():
    flows, _ = flows_waehlen(_FLOWS, ["GV-RED-1", "GV-LEH-1"])
    assert [f["id"] for f in flows] == ["GV-LEH-1", "GV-RED-1"]


def test_eine_unbekannte_kennung_wird_gemeldet():
    flows, warnungen = flows_waehlen(_FLOWS, ["GV-LEH-1", "GV-XYZ"])
    assert [f["id"] for f in flows] == ["GV-LEH-1"]
    assert warnungen == ["Unbekannte Flow-IDs ignoriert: ['GV-XYZ']"]


def test_das_modell_kennt_das_feld_und_der_seed_setzt_es_fuer_gv_red_1():
    assert GoldFlow().auf_abruf is False
    seed = asyncio.run(seed_sync.seed_lesen(seed_sync.seed_pfad("seeds")))
    abruf = {f["id"] for f in seed["eval/gold-flows"]["flows"] if f.get("auf_abruf")}
    assert abruf == {"GV-RED-1"}


def test_die_kommandozeile_folgt_derselben_regel():
    # Der Gold-Runner ist eine framework-freie Datei (``evals/run_golden.py``)
    # und trägt die Regel als Zwilling.
    pfad = Path(__file__).resolve().parents[2] / "evals" / "run_golden.py"
    spec = importlib.util.spec_from_file_location("run_golden_k3", pfad)
    modul = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(modul)
    assert [f["id"] for f in modul.flows_fuer_lauf(_FLOWS, "")] == ["GV-LEH-1", "GV-LER-1"]
    assert [f["id"] for f in modul.flows_fuer_lauf(_FLOWS, "GV-RED-1")] == ["GV-RED-1"]
