"""ST-9: die Herkunft einer Sitzung steht nur in ihrer Kennung.

Keine Spalte und keine Kopfzeile sagt, ob eine Sitzung aus dem Widget, einem
Eval-Lauf oder dem Lasttest stammt — nur das Präfix. Bis ST-9 schloss
``production`` nur ``eval-`` aus; Lasttest-Züge zählten in der Analyse als
echte Gespräche.
"""

from sqlalchemy import column
from sqlalchemy.dialects.postgresql import asyncpg

from boerdi.services.session_origin import (
    EVAL_PREFIX,
    LOADTEST_PREFIX,
    STUDIO_PREFIX,
    scope_clause,
    scope_sql,
)


def _sql(clause) -> str:
    # asyncpg wie im Betrieb: der pyformat-Standarddialekt verdoppelte `%`
    return str(clause.compile(dialect=asyncpg.dialect(),
                              compile_kwargs={"literal_binds": True}))


def test_production_schliesst_eval_und_lasttest_aus() -> None:
    sql = scope_sql("production")
    assert f"session_id NOT LIKE '{EVAL_PREFIX}%'" in sql
    assert f"session_id NOT LIKE '{LOADTEST_PREFIX}%'" in sql


def test_eval_nimmt_nur_eval_sitzungen() -> None:
    assert scope_sql("eval") == f"session_id LIKE '{EVAL_PREFIX}%'"


def test_alle_und_unbekanntes_schraenken_nicht_ein() -> None:
    assert scope_sql("all") == ""
    assert scope_sql("irgendwas") == ""


def test_der_ausdruck_fuer_core_abfragen_sagt_dasselbe() -> None:
    produktion = _sql(scope_clause("production", column("session_id")))
    assert f"NOT LIKE '{EVAL_PREFIX}%'" in produktion
    assert f"NOT LIKE '{LOADTEST_PREFIX}%'" in produktion
    assert _sql(scope_clause("eval", column("session_id"))) == f"session_id LIKE '{EVAL_PREFIX}%'"
    assert scope_clause("all", column("session_id")) is None


def test_production_schliesst_probelaeufe_ohne_sitzung_aus() -> None:
    """Paket 9 (Review Paket 7, MINOR 31): Aufträge ohne Sitzung zählen zum Betrieb,
    Probeläufe des Studios (Quelle ``studio-probe``) nicht."""
    from sqlalchemy import Column, String
    from sqlalchemy.dialects import postgresql

    from boerdi.services.session_origin import STUDIO_QUELLE

    sitzung, quelle = Column("session_id", String), Column("quelle", String)
    sql = str(scope_clause("production", sitzung, quelle).compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert f"'{STUDIO_QUELLE}'" in sql and "quelle IS NULL" in sql


def test_production_schliesst_auch_den_studio_probelauf_aus() -> None:
    """ST-8e: der Chat-Probelauf der Agent-Seite ist Test-Verkehr des Betreibers."""
    assert STUDIO_PREFIX == "studio-"
    assert f"session_id NOT LIKE '{STUDIO_PREFIX}%'" in scope_sql("production")
    produktion = _sql(scope_clause("production", column("session_id")))
    assert f"NOT LIKE '{STUDIO_PREFIX}%'" in produktion
    # „Evaluation“ bleibt, was sie war: nur die Läufe der Evaluation.
    assert STUDIO_PREFIX not in scope_sql("eval")

