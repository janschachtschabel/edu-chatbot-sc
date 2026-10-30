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


class YamlAlias(ValueError):
    """An alias in a backup (Paket 9, V5). Not a ``yaml.YAMLError`` on purpose:
    :func:`split_frontmatter` tolerates those and would read the head as body."""


class _OhneAlias(yaml.SafeLoader):
    """SafeLoader that refuses aliases. The loader shares the aliased objects, but
    normalising and storing copies them — nine levels of nine references are
    nine to the ninth entries (billion laughs)."""

    def compose_node(self, parent: Any, index: Any) -> Any:  # type: ignore[override]
        if self.check_event(yaml.AliasEvent):
            raise YamlAlias("YAML aliases are not allowed")
        return super().compose_node(parent, index)


def lade_ohne_alias(text: str) -> Any:
    """``yaml.safe_load`` without aliases — for files that come from outside
    (a backup upload), not for the seed tree in the image."""
    return yaml.load(text, Loader=_OhneAlias)  # noqa: S506 — a SafeLoader subclass


def split_frontmatter(
    text: str, *, laden: Callable[[str], Any] = yaml.safe_load, streng: bool = False,
) -> tuple[dict[str, Any], str]:
    """'---\\n<yaml>\\n---\\n<body>' -> (frontmatter, body). No marker or
    broken YAML head => ({}, whole text) — mirrors ALT's tolerant parser.
    ``laden`` parses the head; a backup passes :func:`lade_ohne_alias`.

    ``streng`` (Paket 18E, C4) — saving raw text in the Studio and restoring a backup:
    a broken head, a head that is no mapping, or a missing closing ``---`` raises
    ``yaml.YAMLError`` instead of silently becoming ``{}`` (the pattern then lost its id
    and tools live; the model gate let it pass, all fields have defaults). The seed
    import stays tolerant."""
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines[1:], start=1):
        # Nur in Spalte 0 (Review 18E-1): ``join_frontmatter`` schreibt eine Zeile ``---``
        # eines mehrzeiligen Werts eingerückt — mit ``strip()`` endete der Kopf dort.
        # Leerraum am Ende zählt nicht (Review 2026-10-30): ``--- `` aus einem Editor ließ
        # den Kopf sonst offen.
        if line.rstrip() == "---":
            head = "".join(lines[1:i])
            body = "".join(lines[i + 1:])
            try:
                fm = laden(head)
                # Nur ein LEERER Kopf ist ``{}`` (Review 2026-10-30): ``false``, ``0`` oder
                # ``[]`` sind keine Zuordnung und fallen unten wie jede andere durch.
                if fm is None:
                    fm = {}
            except yaml.YAMLError:
                if streng:
                    raise
                return {}, text
            if isinstance(fm, dict):
                return fm, body
            if streng:
                raise yaml.YAMLError("Frontmatter ist keine Zuordnung (Schlüssel: Wert)")
            return {}, body
    if streng:
        raise yaml.YAMLError("Frontmatter ohne schließendes ---")
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
    """Write every area back as a file (MD areas -> .md, others -> .yaml).

    Raises ``ValueError`` before writing anything if a key would land outside
    ``dst`` (audit 2026-09-29, A-M7): a half-written export looks complete.
    """
    base = dst.resolve()
    targets: list[tuple[Path, str, dict[str, Any]]] = []
    for key, data in sorted(areas.items()):
        suffix = ".md" if is_md_area(data) else ".yaml"
        path = dst / f"{key}{suffix}"
        if not path.resolve().is_relative_to(base):
            raise ValueError(f"area key escapes the export folder: {key!r}")
        targets.append((path, suffix, data))
    for path, suffix, data in targets:
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
