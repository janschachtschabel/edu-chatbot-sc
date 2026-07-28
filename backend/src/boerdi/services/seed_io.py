"""YAML/MD seed import + export (P2-4, spec §5.3/§9.1).

Area key = source-relative path without extension ('01-base/welcome-config').
YAML areas store the parsed mapping verbatim; MD areas store
{"frontmatter": {...}, "body": "..."}. Export writes the same structure back —
comments are NOT preserved (spec asks for STRUCTURAL equality, roundtrip-tested).
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_EXTS = {".yaml", ".yml", ".md"}


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """'---\\n<yaml>\\n---\\n<body>' -> (frontmatter, body). No marker or
    broken YAML head => ({}, whole text) — mirrors ALT's tolerant parser."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            head = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            try:
                fm = yaml.safe_load(head) or {}
            except yaml.YAMLError:
                return {}, text
            return (fm if isinstance(fm, dict) else {}), body
    return {}, text


def join_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    head = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{head}\n---\n{body}"


def area_key(rel_path: Path) -> str:
    return rel_path.with_suffix("").as_posix()


def normalize_json_keys(value: Any) -> Any:
    """jsonb requires string keys. YAML 1.1 parses unquoted ``off``/``on``/
    ``yes``/``no`` mapping keys as bools (ALT quirk: safety-config preset
    ``off``) — normalize deterministically: False->'false', True->'true',
    None->'null', numbers->str. Applied recursively on import."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str):
                key = k
            elif isinstance(k, bool):
                key = "true" if k else "false"
            elif k is None:
                key = "null"
            else:
                key = str(k)
            out[key] = normalize_json_keys(v)
        return out
    if isinstance(value, list):
        return [normalize_json_keys(v) for v in value]
    return value


def is_md_area(data: dict[str, Any]) -> bool:
    """MD areas are exactly the {frontmatter, body} shape (spec §6)."""
    return set(data.keys()) == {"frontmatter", "body"}


async def import_tree(
    src: Path, put: Callable[[str, dict[str, Any]], Awaitable[None]]
) -> dict[str, int]:
    """Walk the config tree and put every YAML/MD file as one area."""
    stats = {"areas": 0, "yaml": 0, "md": 0}
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _EXTS:
            continue
        rel = path.relative_to(src)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".md":
            frontmatter, body = split_frontmatter(text)
            data: dict[str, Any] = {
                "frontmatter": normalize_json_keys(frontmatter),
                "body": body,
            }
            stats["md"] += 1
        else:
            parsed = yaml.safe_load(text) or {}
            if not isinstance(parsed, dict):
                logger.warning("skipping %s: YAML root is not a mapping", rel)
                continue
            data = normalize_json_keys(parsed)
            stats["yaml"] += 1
        await put(area_key(rel), data)
        stats["areas"] += 1
    return stats


def export_tree(areas: dict[str, dict[str, Any]], dst: Path) -> None:
    """Write every area back as a file (MD areas -> .md, others -> .yaml)."""
    for key, data in sorted(areas.items()):
        suffix = ".md" if is_md_area(data) else ".yaml"
        path = dst / f"{key}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == ".md":
            path.write_text(
                join_frontmatter(data["frontmatter"], data["body"]), encoding="utf-8"
            )
        else:
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
