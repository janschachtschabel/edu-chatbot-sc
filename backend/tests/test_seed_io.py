"""P2-4: YAML/MD import + export (seed_io) — area key = ALT path without
extension; MD areas = {"frontmatter": {...}, "body": "..."} (spec §5.3/§6).

Unit tests run without DB (import_tree takes an async put callable);
the full ALT-tree roundtrip runs against the live PG and skips when the
ALT sibling repo is not present (CI).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

from boerdi.services import seed_io

ALT_TREE = Path(r"C:\Users\jan\staging\Windsurf\wlo-suche\badboerdi\backend\chatbots\wlo\v1")


def test_split_frontmatter_roundtrip() -> None:
    text = "---\nid: P-LEH\nlabel: Lehrkraft\n---\n# Titel\n\nBody **fett**.\n"
    fm, body = seed_io.split_frontmatter(text)
    assert fm == {"id": "P-LEH", "label": "Lehrkraft"}
    assert body == "# Titel\n\nBody **fett**.\n"
    rejoined = seed_io.join_frontmatter(fm, body)
    fm2, body2 = seed_io.split_frontmatter(rejoined)
    assert (fm2, body2) == (fm, body)


def test_yaml_bool_keys_are_normalized_to_json_strings(tmp_path: Path) -> None:
    """ALT quirk: safety-config presets use unquoted ``off:`` which YAML 1.1
    parses as bool False — JSON (jsonb) requires string keys. Import
    normalizes deterministically (False->'false'); P3's safety loader owns
    the 'off'-level lookup semantics."""
    (tmp_path / "x.yaml").write_text(
        "presets:\n  off: {a: 1}\n  standard: {a: 2}\n", encoding="utf-8"
    )
    stored: dict[str, dict] = {}

    async def put(area: str, data: dict) -> None:
        stored[area] = data

    asyncio.run(seed_io.import_tree(tmp_path, put))
    assert set(stored["x"]["presets"]) == {"false", "standard"}


def test_split_frontmatter_without_marker_is_pure_body() -> None:
    fm, body = seed_io.split_frontmatter("# Nur Markdown\n")
    assert fm == {}
    assert body == "# Nur Markdown\n"


def test_import_tree_maps_yaml_and_md(tmp_path: Path) -> None:
    (tmp_path / "01-base").mkdir()
    (tmp_path / "01-base" / "welcome-config.yaml").write_text(
        "welcome:\n  greeting: Moin\n  quick_replies: [a, b]\n", encoding="utf-8"
    )
    (tmp_path / "01-base" / "base-persona.md").write_text(
        "---\nid: base\nlayer: 1\n---\nIch bin Boerdi.\n", encoding="utf-8"
    )

    stored: dict[str, dict] = {}

    async def put(area: str, data: dict) -> None:
        stored[area] = data

    stats = asyncio.run(seed_io.import_tree(tmp_path, put))
    assert stats == {"areas": 2, "yaml": 1, "md": 1}
    assert stored["01-base/welcome-config"] == {
        "welcome": {"greeting": "Moin", "quick_replies": ["a", "b"]}
    }
    assert stored["01-base/base-persona"] == {
        "frontmatter": {"id": "base", "layer": 1},
        "body": "Ich bin Boerdi.\n",
    }


def test_export_tree_writes_back_structurally_equal(tmp_path: Path) -> None:
    areas = {
        "01-base/welcome-config": {"welcome": {"greeting": "Moin", "quick_replies": ["a"]}},
        "01-base/base-persona": {"frontmatter": {"id": "base"}, "body": "Text.\n"},
    }
    out = tmp_path / "export"
    seed_io.export_tree(areas, out)

    yml = yaml.safe_load((out / "01-base" / "welcome-config.yaml").read_text(encoding="utf-8"))
    assert yml == areas["01-base/welcome-config"]
    fm, body = seed_io.split_frontmatter(
        (out / "01-base" / "base-persona.md").read_text(encoding="utf-8")
    )
    assert fm == {"id": "base"} and body == "Text.\n"


@pytest.mark.skipif(not ALT_TREE.exists(), reason="ALT-Baum nicht vorhanden (CI)")
def test_alt_tree_import_export_roundtrip(tmp_path: Path) -> None:
    """Acceptance (spec 2-4): import of the REAL ALT tree (55 files), export,
    re-import — structurally identical."""
    first: dict[str, dict] = {}

    async def put1(area: str, data: dict) -> None:
        first[area] = data

    stats = asyncio.run(seed_io.import_tree(ALT_TREE, put1))
    assert stats["areas"] == 55, stats
    assert "03-patterns/m16-themenseiten-inhalt" in first
    assert "04-personas/and" in first
    assert first["05-knowledge/rag-config"]["WirLernenOnline"]["mode"]

    out = tmp_path / "roundtrip"
    seed_io.export_tree(first, out)

    second: dict[str, dict] = {}

    async def put2(area: str, data: dict) -> None:
        second[area] = data

    stats2 = asyncio.run(seed_io.import_tree(out, put2))
    assert stats2["areas"] == 55
    assert second == first  # structural equality after full roundtrip
