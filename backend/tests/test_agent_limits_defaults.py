"""Die Deckel der Schleife stehen an DREI Orten — hier wird gemessen, dass zwei
davon sich einig sind.

Modell-Vorgabe (``domain/config_models/engine.py``), Seed
(``seeds/01-base/engine.yaml``) und die Live-Zeile im Config-Store muessen
denselben Wert tragen. Die Live-Zeile kann ein Test ohne Datenbank nicht sehen —
die beiden anderen schon, und genau ihr Auseinanderlaufen ist der Fehler, der am
2026-08-18 schon einmal passiert ist (CORS-Schalter, Paket K3): gepflegt, aber
nirgends wirksam.

30 Zuege sind der Nutzer-Entscheid vom 2026-08-18. Frist und Budget wandern
mit, sonst greift einer von ihnen vorher und die 30 sind Zierde.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from boerdi.domain.config_models.engine import AgentLimits

_SEED = Path(__file__).resolve().parents[1] / "seeds" / "01-base" / "engine.yaml"


def test_die_deckel_der_modell_vorgabe() -> None:
    vorgabe = AgentLimits()
    assert vorgabe.max_iterations == 30
    assert vorgabe.deadline_s == 900
    assert vorgabe.token_budget == 900_000


def test_seed_und_modell_vorgabe_sind_sich_einig() -> None:
    seed = yaml.safe_load(_SEED.read_text(encoding="utf-8"))["agent"]
    vorgabe = AgentLimits()
    for feld in ("max_iterations", "deadline_s", "token_budget"):
        assert seed[feld] == getattr(vorgabe, feld), (
            f"{feld}: Seed {seed[feld]} != Modell-Vorgabe {getattr(vorgabe, feld)} — "
            f"einer der drei Orte ist nicht mitgewandert"
        )
