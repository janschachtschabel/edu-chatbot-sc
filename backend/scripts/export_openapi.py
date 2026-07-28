"""Export/check the frozen OpenAPI contract (P0-4, spec §5.1).

Usage (from backend/):
    uv run python scripts/export_openapi.py           # (re)write the contract
    uv run python scripts/export_openapi.py --check   # CI diff gate, exit 1 on drift
"""

import json
import sys
from pathlib import Path

from boerdi.main import create_app

OUT = Path(__file__).resolve().parents[2] / "docs" / "api" / "openapi-v1.json"


def render() -> str:
    spec = create_app().openapi()
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        if not OUT.exists():
            print(f"MISSING: {OUT} — run scripts/export_openapi.py")
            return 1
        if OUT.read_text(encoding="utf-8") != text:
            print("DRIFT: live OpenAPI differs from docs/api/openapi-v1.json")
            print("If deliberate, regenerate: uv run python scripts/export_openapi.py")
            return 1
        print("openapi contract unchanged")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
