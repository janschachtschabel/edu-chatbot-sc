"""P2-7: config-snapshot ZIP build/parse with decompression caps.

The zip-bomb guard (_copy_zip_member_capped ported from ALT config_backup.py)
is the key acceptance: a small archive that expands past the budget is
rejected BEFORE RAM/disk fill. These are pure (no DB).
"""

from __future__ import annotations

import io
import zipfile

import pytest

from boerdi.services import snapshots


def test_build_and_parse_roundtrip() -> None:
    areas = {
        "01-base/welcome-config": {"welcome": {"greeting": "Hi", "quick_replies": ["a"]}},
        "04-personas/leh": {"frontmatter": {"id": "P-LEH"}, "body": "Prosa.\n"},
    }
    blob = snapshots.build_config_zip(areas)
    assert isinstance(blob, bytes) and blob[:2] == b"PK"
    parsed = snapshots.parse_config_zip(blob)
    assert parsed == areas


def test_parse_ignores_non_config_and_directories() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("config/01-base/welcome-config.yaml", "welcome:\n  greeting: X\n")
        z.writestr("db/dump.sql", "IGNORED")  # not config/
        z.writestr("config/sub/", "")  # directory entry
    parsed = snapshots.parse_config_zip(buf.getvalue())
    assert set(parsed) == {"01-base/welcome-config"}


def test_upload_size_cap_rejects_oversize(monkeypatch) -> None:
    monkeypatch.setattr(snapshots, "MAX_CONFIG_UPLOAD_BYTES", 10)
    with pytest.raises(snapshots.SnapshotTooLarge):
        snapshots.parse_config_zip(b"x" * 11)


def test_zip_bomb_rejected_by_decompression_budget(monkeypatch) -> None:
    # 5 MB of zeros compresses tiny but blows a small budget on extract.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("config/01-base/welcome-config.yaml", b"\0" * (5 * 1024 * 1024))
    bomb = buf.getvalue()
    assert len(bomb) < 50_000  # compressed is tiny
    monkeypatch.setattr(snapshots, "MAX_DECOMPRESSED_BYTES", 1 * 1024 * 1024)
    with pytest.raises(snapshots.SnapshotTooLarge):
        snapshots.parse_config_zip(bomb)


def test_copy_zip_member_capped_streams_within_budget() -> None:
    src = io.BytesIO(b"abcdef")
    dst = io.BytesIO()
    snapshots._copy_zip_member_capped(src, dst, [100], chunk=2)
    assert dst.getvalue() == b"abcdef"


def test_copy_zip_member_capped_raises_over_budget() -> None:
    with pytest.raises(snapshots.SnapshotTooLarge):
        snapshots._copy_zip_member_capped(io.BytesIO(b"abcdef"), io.BytesIO(), [3], chunk=2)
