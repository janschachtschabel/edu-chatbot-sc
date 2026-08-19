#!/usr/bin/env python
"""Schreibt ``docs/dimensionen/`` aus ``backend/seeds/`` (Nutzer-Wunsch 2026-08-18).

Dünner Einstieg — die Arbeit steht in ``boerdi.services.dimension_export``,
damit sie ohne Unterprozess prüfbar ist (dieselbe Aufteilung wie bei
``scripts/export_openapi.py``).

    uv run python scripts/export_dimensions.py [ziel]
"""

from __future__ import annotations

import sys
from pathlib import Path

from boerdi.services.dimension_export import exportiere

_BACKEND = Path(__file__).resolve().parents[1]


def main() -> int:
    ziel = Path(sys.argv[1]) if len(sys.argv) > 1 else _BACKEND.parent / "docs" / "dimensionen"
    dateien = exportiere(_BACKEND / "seeds", ziel)
    print(f"{len(dateien)} Dateien geschrieben nach {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
