"""Der Dimensionen-Export nach ``docs/dimensionen/`` (Nutzer-Wunsch 2026-08-18).

Was hier geprüft wird, ist NICHT die Formatierung — die darf sich ändern —,
sondern die zwei Zusagen, ohne die der Export wertlos wäre: **Vollständigkeit**
(jede Dimension, jedes Muster) und **Wiederholbarkeit** (zweimal laufen ergibt
dasselbe, sonst rauscht jeder Lauf in den Diff).
"""

from __future__ import annotations

from pathlib import Path

from boerdi.services import dimension_export as ex

_SEEDS = Path(__file__).resolve().parents[1] / "seeds"


def test_jedes_muster_wird_eine_datei(tmp_path: Path) -> None:
    ex.exportiere(_SEEDS, tmp_path)
    dateien = sorted((tmp_path / "muster").glob("*.md"))
    quellen = sorted((_SEEDS / "03-patterns").glob("*.md"))
    assert len(dateien) == len(quellen) == 20
    # Die Anweisung selbst muss ankommen, nicht nur die Kopfdaten.
    m06 = next(d for d in dateien if d.name.startswith("M06"))
    text = m06.read_text(encoding="utf-8")
    assert "Kuratiertes vor Algorithmischem" in text     # core_rule
    assert "search_wlo_all" in text                      # tools
    assert "## Wann aktiv" in text                       # Rumpf des Seeds


def test_alle_dimensionen_haben_eine_seite(tmp_path: Path) -> None:
    ex.exportiere(_SEEDS, tmp_path)
    erwartet = {"README.md", "muster.md", "intents.md", "personas.md",
                "states.md", "entities.md", "signale.md"}
    assert erwartet <= {p.name for p in tmp_path.glob("*.md")}
    index = (tmp_path / "muster.md").read_text(encoding="utf-8")
    for mid in ("M01", "M06", "M20"):
        assert mid in index


def test_zweimal_exportieren_ergibt_dasselbe(tmp_path: Path) -> None:
    ex.exportiere(_SEEDS, tmp_path)
    erst = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.md")}
    ex.exportiere(_SEEDS, tmp_path)
    zweit = {p.name: p.read_text(encoding="utf-8") for p in tmp_path.rglob("*.md")}
    assert erst == zweit
