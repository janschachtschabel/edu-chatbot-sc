"""Config snapshots / backup / factory (P2-7).

Config areas are packed into a ZIP (``config/<key>.<ext>``) stored as a
``bytea`` blob in the ``config_snapshots`` table (spec §6); factory is the
row with id ``factory``. Restore streams every member against a shared
decompression budget (``_copy_zip_member_capped``, ported from ALT
config_backup.py) so a zip bomb is rejected before RAM/disk fill.

DB-include (full Postgres dump) is deferred to P10 operational backup —
``include_db`` is carried through the schema but only config is packed here.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import PurePosixPath
from typing import Any

import yaml
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from boerdi.services import seed_io

# Caps (ALT config_backup.py:48-55).
MAX_SNAPSHOTS = 50                          # non-factory rows (disk/DB growth)
MAX_CONFIG_UPLOAD_BYTES = 150 * 1024 * 1024  # compressed upload (memory)
MAX_DECOMPRESSED_BYTES = 600 * 1024 * 1024   # unzip budget (zip-bomb guard)

_CONFIG_PREFIX = "config/"
FACTORY_ID = "factory"


class SnapshotTooLarge(Exception):
    """Upload exceeds a size/decompression cap (maps to HTTP 413)."""


def _copy_zip_member_capped(src, dst, budget: list[int], chunk: int = 1 << 20) -> None:
    """Stream src->dst against a shared, mutable decompression budget
    (``budget[0]``). Raises before the budget goes negative (ALT parity)."""
    while True:
        block = src.read(chunk)
        if not block:
            break
        budget[0] -= len(block)
        if budget[0] < 0:
            raise SnapshotTooLarge("Backup entpackt zu groß (mögliche Zip-Bombe).")
        dst.write(block)


def build_config_zip(areas: dict[str, dict[str, Any]]) -> bytes:
    """Pack config areas into an in-memory ZIP under ``config/``."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for key, data in sorted(areas.items()):
            if seed_io.is_md_area(data):
                z.writestr(f"{_CONFIG_PREFIX}{key}.md",
                           seed_io.join_frontmatter(data["frontmatter"], data["body"]))
            else:
                z.writestr(f"{_CONFIG_PREFIX}{key}.yaml",
                           yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return buf.getvalue()


def parse_config_zip(blob: bytes) -> dict[str, dict[str, Any]]:
    """Extract config areas from a ZIP with upload + decompression caps."""
    if len(blob) > MAX_CONFIG_UPLOAD_BYTES:
        raise SnapshotTooLarge(
            f"Upload zu groß (max {MAX_CONFIG_UPLOAD_BYTES // (1024 * 1024)} MB).")
    budget = [MAX_DECOMPRESSED_BYTES]
    areas: dict[str, dict[str, Any]] = {}
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise SnapshotTooLarge("Keine gültige ZIP-Datei.") from None
    with zf:
        for name in zf.namelist():
            if not name.startswith(_CONFIG_PREFIX) or name.endswith("/"):
                continue
            out = io.BytesIO()
            with zf.open(name) as src:
                _copy_zip_member_capped(src, out, budget)
            text_content = out.getvalue().decode("utf-8")
            rel = name[len(_CONFIG_PREFIX):]
            key = PurePosixPath(rel).with_suffix("").as_posix()
            if rel.endswith(".md"):
                fm, body = seed_io.split_frontmatter(text_content)
                areas[key] = {"frontmatter": seed_io.normalize_json_keys(fm), "body": body}
            else:
                parsed = yaml.safe_load(text_content) or {}
                if isinstance(parsed, dict):
                    areas[key] = seed_io.normalize_json_keys(parsed)
    return areas


# ── config_snapshots table CRUD ────────────────────────────────────────────
_INSERT = text("""
    INSERT INTO config_snapshots (id, label, include_db, blob)
    VALUES (:id, :label, :include_db, :blob)
    ON CONFLICT (id) DO UPDATE
      SET label = EXCLUDED.label, include_db = EXCLUDED.include_db,
          blob = EXCLUDED.blob, created_at = now()
""")
_LIST = text("""
    SELECT id, created_at, label, include_db FROM config_snapshots
    WHERE id <> :factory ORDER BY created_at DESC
""")
_GET = text("SELECT id, created_at, label, include_db, blob FROM config_snapshots WHERE id = :id")
_DELETE = text("DELETE FROM config_snapshots WHERE id = :id RETURNING id")
_COUNT = text("SELECT count(*) FROM config_snapshots WHERE id <> :factory")


async def save_snapshot(
    engine: AsyncEngine, snap_id: str, label: str, blob: bytes, include_db: bool = False,
) -> None:
    async with engine.begin() as conn:
        await conn.execute(_INSERT, {
            "id": snap_id, "label": label, "include_db": include_db, "blob": blob,
        })


async def list_snapshots(engine: AsyncEngine) -> list[dict[str, Any]]:
    async with engine.connect() as conn:
        rows = (await conn.execute(_LIST, {"factory": FACTORY_ID})).mappings().all()
    return [dict(r) for r in rows]


async def get_snapshot(engine: AsyncEngine, snap_id: str) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        row = (await conn.execute(_GET, {"id": snap_id})).mappings().first()
    return dict(row) if row else None


async def delete_snapshot(engine: AsyncEngine, snap_id: str) -> bool:
    async with engine.begin() as conn:
        row = (await conn.execute(_DELETE, {"id": snap_id})).first()
    return row is not None


async def count_snapshots(engine: AsyncEngine) -> int:
    async with engine.connect() as conn:
        return (await conn.execute(_COUNT, {"factory": FACTORY_ID})).scalar_one()
