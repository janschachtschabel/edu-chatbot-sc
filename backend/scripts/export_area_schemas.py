"""Generate the studio spec fixture: every distinct area model's JSON schema."""
import json
import pathlib
import sys

from boerdi.domain.config_models import AREA_MODELS

by_model: dict[str, tuple[str, dict]] = {}
for key, model in AREA_MODELS.items():
    by_model.setdefault(model.__name__, (key, model.model_json_schema()))

payload = {area: schema for _name, (area, schema) in sorted(by_model.items())}
# NOT sort_keys: pydantic emits properties in field-definition order and
# that is the order the form renders — a sorted fixture would pin an order
# the real endpoint never serves.
blob = json.dumps(payload, indent=2, ensure_ascii=False)

# Anchored to this file, not to the CWD: resolving "../frontend/…" against
# the process directory silently wrote the fixture OUTSIDE the repository
# when the script was run from the repo root, and reported success.
out = pathlib.Path(__file__).resolve().parents[2] / (
    "frontend/projects/studio/src/app/schema-form/area-schemas.fixture.ts"
)
if not out.parent.is_dir():
    raise SystemExit(f"target directory missing: {out.parent}")
header = """// GENERATED — do not edit by hand.
//
// The JSON schema of every distinct config-area model, exactly as
// GET /api/config/schema/{area} serves it. Regenerate after changing an area
// model in backend/src/boerdi/domain/config_models/:
//
//   cd backend && uv run python scripts/export_area_schemas.py
//
// The point of testing against these instead of hand-written samples: the
// mapper must cope with what pydantic really emits, not with what we imagine
// it emits.
//
// AREA_SCHEMAS holds one key per distinct MODEL, so areas sharing a model
// (the four LayerDoc areas) appear once. AREA_KEYS holds ALL of them — it is
// what a view's configured area key is checked against.
import type { JsonSchema } from './json-schema';

export const AREA_SCHEMAS: Readonly<Record<string, JsonSchema>> =
"""
keys = json.dumps(sorted(AREA_MODELS), indent=2, ensure_ascii=False)
footer = f"""

/** Every registered config area — the registry keys, nothing derived. */
export const AREA_KEYS: readonly string[] = {keys} as const;
"""
text = header + blob + " as const;\n" + footer
if "--check" in sys.argv:
    if not out.exists():
        raise SystemExit(f"MISSING: {out} — run scripts/export_area_schemas.py")
    if out.read_text(encoding="utf-8") != text:
        raise SystemExit(
            "DRIFT: die Bereichs-Schemata der Modelle stehen nicht in der Fixture. "
            "Das Studio baut seine Formulare daraus — ein Feld, das hier fehlt, "
            "fehlt der Redaktion. Neu erzeugen: "
            "uv run python scripts/export_area_schemas.py"
        )
    print("area schemas unchanged")
else:
    out.write_text(text, encoding="utf-8")
    print(f"{out} — {len(by_model)} schemas, {len(AREA_MODELS)} keys, {len(blob)} chars")
