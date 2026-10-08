"""``als_bereichsfehler`` without a database (Paket 4b, second review).

Only SQLSTATE class 22 (a value Postgres will not store) becomes
``BereichNichtSpeicherbar`` and thus a 400. Every other database error — a
deadlock, a unique violation, a lost connection — stays the ``DBAPIError`` it
was and ends as a 500 (plan A4). Before this file no test pinned that half.
"""

from types import SimpleNamespace

import pytest
from sqlalchemy.exc import DBAPIError

from boerdi.services.config_conflict import BereichNichtSpeicherbar, als_bereichsfehler


def _db_fehler(sqlstate: str | None) -> DBAPIError:
    """What the asyncpg dialect raises: a generic error, the code on ``orig``."""
    return DBAPIError("INSERT INTO config_areas …", None, SimpleNamespace(sqlstate=sqlstate))


def test_ein_datenfehler_wird_zum_bereichsfehler_und_traegt_den_sqlstate() -> None:
    with pytest.raises(BereichNichtSpeicherbar) as fehler:
        with als_bereichsfehler("01-base/x"):
            raise _db_fehler("22P02")
    assert (fehler.value.area, fehler.value.sqlstate) == ("01-base/x", "22P02")


@pytest.mark.parametrize("sqlstate", ["40P01", "23505", "08006", None])
def test_andere_datenbankfehler_reichen_unveraendert_durch(sqlstate: str | None) -> None:
    original = _db_fehler(sqlstate)
    with pytest.raises(DBAPIError) as fehler:
        with als_bereichsfehler("01-base/x"):
            raise original
    assert fehler.value is original
