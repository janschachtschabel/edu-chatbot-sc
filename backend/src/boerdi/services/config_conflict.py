"""Optimistic concurrency for config writes (Paket 4, D5; external audit F14).

Two editors load the same version; whoever saves second must learn about the
first instead of silently overwriting them. A writer therefore names the version
it started from (``expected_version``) or says it creates a new area
(``create_only``); the write lands only if the row still matches, otherwise
:class:`ConfigConflict` carries what is stored now.

Writers that name neither keep the unconditional upsert — the version stays
optional on the server, the Studio always sends it.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

# A new row continues the count of a deleted one — history survives the DELETE.
# Restarting at 1 gave one number two states: a save against the deleted state
# passed the version check (ABA), and a resync dropped the new row as "older".
FIRST_VERSION = "COALESCE((SELECT max(version) FROM config_history WHERE area = :area), 0) + 1"

_UPDATE_IF_VERSION = text("""
    UPDATE config_areas
       SET data = CAST(:data AS jsonb),
           version = version + 1,
           updated_at = now(),
           updated_by = :updated_by
     WHERE area = :area AND version = :expected
    RETURNING version
""")

_INSERT_IF_ABSENT = text(f"""
    INSERT INTO config_areas (area, data, updated_by, version)
    VALUES (:area, CAST(:data AS jsonb), :updated_by, {FIRST_VERSION})
    ON CONFLICT (area) DO NOTHING
    RETURNING version
""")

_SELECT_META = text(
    "SELECT version, updated_at, updated_by FROM config_areas WHERE area = :area"
)


class ConfigConflict(Exception):
    """The area is not in the state the writer started from.

    ``current`` holds ``version``, ``updated_at`` and ``updated_by`` of the
    stored row, or is ``None`` when the row is gone (deleted meanwhile).
    """

    def __init__(self, area: str, current: dict[str, Any] | None) -> None:
        super().__init__(f"config conflict on {area!r}")
        self.area = area
        self.current = current


async def write_checked(
    conn: AsyncConnection, *, area: str, payload: str, updated_by: str,
    expected_version: int | None, create_only: bool,
) -> int:
    """Run the conditional write inside the caller's transaction.

    Returns the new version, or raises :class:`ConfigConflict` — the caller's
    transaction then rolls back, nothing is written.
    """
    params = {"area": area, "data": payload, "updated_by": updated_by}
    if create_only:
        row = (await conn.execute(_INSERT_IF_ABSENT, params)).first()
    else:
        row = (await conn.execute(
            _UPDATE_IF_VERSION, {**params, "expected": expected_version})).first()
    if row is None:
        meta = (await conn.execute(_SELECT_META, {"area": area})).mappings().first()
        raise ConfigConflict(area, dict(meta) if meta is not None else None)
    return int(row[0])
