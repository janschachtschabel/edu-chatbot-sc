"""Export/check the frozen OpenAPI contract (P0-4, spec §5.1) and the public spec (Paket 17).

Usage (from backend/):
    uv run python scripts/export_openapi.py           # (re)write the contract
    uv run python scripts/export_openapi.py --check   # CI diff gate, exit 1 on drift
"""

import json
import sys
from pathlib import Path

from boerdi.api.openapi_public import oeffentliche_spec
from boerdi.main import create_app

OUT = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-v1.json"
#: Paket 17 (D5): die öffentliche Chat-API für die b-api — abgeleitet, eigenes Gate.
OUT_PUBLIC = OUT.with_name("openapi-public.json")


def _dump(spec: dict) -> str:
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render() -> str:
    return _dump(create_app().openapi())


def render_public() -> str:
    # Version fest: die Datei soll nicht mit jedem Build-Tag driften.
    spec = oeffentliche_spec(create_app())
    spec["info"]["version"] = "1"
    return _dump(spec)


def main() -> int:
    paare = ((OUT, render()), (OUT_PUBLIC, render_public()))
    if "--check" in sys.argv:
        for ziel, text in paare:
            if not ziel.exists():
                print(f"MISSING: {ziel} — run scripts/export_openapi.py")
                return 1
            if ziel.read_text(encoding="utf-8") != text:
                print(f"DRIFT: live OpenAPI differs from docs/api/{ziel.name}")
                print("If deliberate, regenerate: uv run python scripts/export_openapi.py")
                return 1
        print("openapi contract unchanged")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for ziel, text in paare:
        ziel.write_text(text, encoding="utf-8")
        print(f"wrote {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
