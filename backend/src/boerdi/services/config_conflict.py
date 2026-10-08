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

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
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


class BereichNichtSpeicherbar(Exception):
    """Postgres weist den Inhalt eines Bereichs zurück (Paket 4b, A4).

    SQLSTATE-Klasse 22, etwa ``\\u0000`` in jsonb (``22P05``): ein Fehler der
    Daten, nicht der Datenbank. Bis dahin endete er als 500 ohne Hinweis, welcher
    Bereich es war. Die Transaktion fällt ganz zurück.

    ``ganzer_vorgang``: Die Transaktion trug mehr als diesen Bereich
    (Wiederherstellen, Seed), verworfen ist also der ganze Vorgang. Sonst war
    es nur dieser Bereich; eine Route, die je Bereich schreibt, hat davor schon
    gespeichert (Review 4b).

    ``sqlstate``: der Code der Datenbank, fürs Log. Klasse 22 ist mehr als ein
    Nullzeichen, etwa ``NaN`` in jsonb (``22P02``) — zweites Review 4b.
    """

    def __init__(self, area: str, *, ganzer_vorgang: bool = False, sqlstate: str = "") -> None:
        super().__init__(f"config area {area!r} cannot be stored")
        self.area = area
        self.ganzer_vorgang = ganzer_vorgang
        self.sqlstate = sqlstate


@contextmanager
def als_bereichsfehler(area: str, *, ganzer_vorgang: bool = False) -> Iterator[None]:
    """Einen Datenfehler beim Schreiben von ``area`` als :class:`BereichNichtSpeicherbar`.

    Erkannt am SQLSTATE: Der asyncpg-Adapter reicht ihn als allgemeinen
    ``DBAPIError`` durch, nicht als ``DataError``. Andere Fehler (Verbindung,
    Sperren) gehen unverändert weiter.
    """
    try:
        yield
    except DBAPIError as err:
        sqlstate = str(getattr(err.orig, "sqlstate", "") or "")
        if sqlstate.startswith("22"):
            raise BereichNichtSpeicherbar(
                area, ganzer_vorgang=ganzer_vorgang, sqlstate=sqlstate) from err
        raise


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
