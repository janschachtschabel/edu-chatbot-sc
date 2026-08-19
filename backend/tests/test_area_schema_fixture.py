"""Das Studio-Formular kennt jedes Feld, das die Modelle erklaeren.

**Der Befund** (18.08.2026): ``area-schemas.fixture.ts`` ist nicht bloss ein
Testdatum — das Studio baut seine Bereichs-Formulare daraus. Sie lief seit
Paket H1 hinterher: das Modell kannte drei Maschinen (``pattern|agent|hybrid``),
die Fixture zwei, und im Studio fehlte ``hybrid`` in der Auswahl. Niemand merkte
es, weil nichts die beiden verglich — der Export war ein Skript, das jemand von
Hand ausfuehren musste.

Dieser Test ist das fehlende Glied. Er laeuft in derselben Suite wie die
Modelle, also genau dann, wenn jemand eines aendert.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_SKRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_area_schemas.py"


def test_die_fixture_traegt_die_felder_der_modelle() -> None:
    lauf = subprocess.run(  # noqa: S603 - fester Pfad, kein fremder Eingang
        [sys.executable, str(_SKRIPT), "--check"],
        capture_output=True, text=True, cwd=_SKRIPT.parents[1],
    )
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
