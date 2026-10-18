"""Paket 13 (B): Anwendungsfall je Golden-Zug, Erwartung je Ablauf.

Die Abläufe sind mehrstufig (Suche → Lernpfad → Arbeitsblatt), deshalb gehört der
Anwendungsfall an den Zug; die Matrix „Zielgruppe × Anwendungsfall“ mittelt die Zug-Noten.
Die ``erwartung`` sagt dem Ablauf-Judge in ein bis drei Sätzen, was ein guter Verlauf leistet.
Beide Felder sind Pflicht, sobald ein Ablauf Züge hat. Geprüft wird beim Laufstart im Runner
(``validate_flows``, vor dem ersten bezahlten Zug) — das Modell bietet nur die Auswahl an
(``Choices``, bewusst keine harte Prüfung beim Speichern; siehe ``config_models/_shared``).
"""

from __future__ import annotations

import asyncio
import importlib.util
from collections import Counter
from pathlib import Path

import pytest
import yaml

from boerdi.domain.config_models.knowledge import ANWENDUNGSFAELLE, GoldFlow, GoldFlowsArea

_EVALS = Path(__file__).resolve().parents[2] / "evals"
_SEED = Path(__file__).resolve().parents[1] / "seeds" / "eval" / "gold-flows.yaml"
_spec = importlib.util.spec_from_file_location("run_golden_b", _EVALS / "run_golden.py")
rg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rg)


def _flow(**ueber) -> dict:
    flow = {"id": "GV-X", "zielgruppe": "P-LEH", "title": "T", "erwartung": "Sucht Material.",
            "turns": [{"message": "hallo", "anwendungsfall": "suchen", "expect": {}}]}
    flow.update(ueber)
    return flow


def test_ein_vollstaendiger_ablauf_ist_gueltig() -> None:
    flow = GoldFlow.model_validate(_flow())
    assert flow.erwartung == "Sucht Material."
    assert flow.turns[0].anwendungsfall == "suchen"
    rg.validate_flows([_flow()])


def test_das_studio_bietet_die_anwendungsfaelle_zur_auswahl() -> None:
    from boerdi.domain.config_models.knowledge import GoldTurn

    feld = GoldTurn.model_json_schema()["properties"]["anwendungsfall"]
    assert feld["x-choices"] == list(ANWENDUNGSFAELLE)


def test_ein_leerer_ablauf_bleibt_gueltig() -> None:
    assert GoldFlow().turns == []


@pytest.mark.parametrize("kaputt", [
    {"erwartung": ""},
    {"turns": [{"message": "hallo", "expect": {}}]},
    {"turns": [{"message": "hallo", "anwendungsfall": "raten", "expect": {}}]},
])
def test_fehlende_oder_unbekannte_angaben_werden_vor_dem_lauf_abgelehnt(kaputt: dict) -> None:
    with pytest.raises(ValueError, match="GV-X"):
        rg.validate_flows([_flow(**kaputt)])


def test_modell_und_runner_kennen_dieselben_anwendungsfaelle() -> None:
    assert set(ANWENDUNGSFAELLE) == set(rg.ANWENDUNGSFAELLE)


def test_der_seed_ist_vollstaendig() -> None:
    daten = yaml.safe_load(_SEED.read_text(encoding="utf-8"))
    bereich = GoldFlowsArea.model_validate(daten)
    rg.validate_flows(daten["flows"])
    zuege = [t for f in bereich.flows for t in f.turns]
    assert len(zuege) == 46
    assert all(t.anwendungsfall for t in zuege)
    assert all(f.erwartung.strip() for f in bereich.flows)
    zielgruppen = Counter(f.zielgruppe for f in bereich.flows)
    for gruppe in ("P-LEH", "P-LER", "P-ELT", "P-ENT", "P-RED", "P-AND"):
        assert zielgruppen[gruppe] >= 1, gruppe


def test_run_flows_traegt_anwendungsfall_und_erwartung(monkeypatch) -> None:
    async def fake_post(url, message, session_id, headers=None, environment=None):
        return {"content": "ok", "cards": [], "quick_replies": [], "debug": {}}

    monkeypatch.setattr(rg, "post_chat", fake_post)
    conv = asyncio.run(rg.run_flows("http://x/api/chat", [_flow()]))[0]
    assert conv["erwartung"] == "Sucht Material."
    assert conv["turns"][0]["anwendungsfall"] == "suchen"


def test_die_zielgruppe_steht_im_modell() -> None:
    """Rundgang 3: das Studio meldete „22 Schlüssel nicht angezeigt“ — 22× ``zielgruppe``, das
    tragende Feld (Judge, Laufstart, Matrix). Das Modell kannte nur das alte ``persona``; ein im
    Formular angelegter Flow bekam so keine Zielgruppe."""
    from boerdi.domain.config_models.schema import area_schema

    schema = area_schema(GoldFlowsArea)
    flow = schema["$defs"]["GoldFlow"]["properties"]
    assert "zielgruppe" in flow
    assert flow["zielgruppe"].get("x-catalog") == "personas"
    seed = Path(__file__).resolve().parents[1] / "seeds" / "eval" / "gold-flows.yaml"
    for f in yaml.safe_load(seed.read_text(encoding="utf-8"))["flows"]:
        unbekannt = set(f) - set(GoldFlow.model_fields)
        assert not unbekannt, (f.get("id"), unbekannt)
