"""``import-config --only-missing`` — der Seed, den man automatisieren darf.

Der gewöhnliche Import schreibt JEDEN Bereich unbedingt. Als einmaliger
Installationsschritt ist das richtig; als automatischer Schritt beim Hochfahren
wäre es zerstörerisch — jeder Neustart drehte die im Studio gepflegte
Konfiguration auf den Seed-Stand zurück. INSTALL.md warnt deshalb ausdrücklich
davor, ihn ein zweites Mal laufen zu lassen.

``--only-missing`` löst genau diesen Konflikt: er ergänzt, was fehlt, und rührt
Bestehendes nicht an. Damit wird der Seed idempotent und darf in den
Installationslauf. Der letzte Test hält fest, dass der Standard sich NICHT
geändert hat — ein ausdrücklicher Voll-Import überschreibt weiterhin.
"""

from __future__ import annotations

import asyncio

import pytest

from tests import pg_utils

pytestmark = [
    pytest.mark.pg,
    pytest.mark.skipif(not pg_utils.pg_available(), reason=pg_utils.SKIP_REASON),
]

_DB = "boerdi_cli_seed_test"


@pytest.fixture
def seed_db(monkeypatch):
    """Frische migrierte Wegwerf-DB, auf die die CLI über die Settings zeigt."""
    from boerdi.settings import get_settings

    pg_utils.create_migrated_db(_DB)
    monkeypatch.setenv("DATABASE_URL", pg_utils.sqlalchemy_url(_DB))
    get_settings.cache_clear()
    yield _DB
    get_settings.cache_clear()
    pg_utils.drop_db(_DB)


@pytest.fixture
def seed_tree(tmp_path):
    """Winziger Seed-Baum: zwei Bereiche, einer davon wird später redigiert."""
    base = tmp_path / "seeds" / "01-base"
    base.mkdir(parents=True)
    (base / "welcome-config.yaml").write_text(
        "greeting: aus dem Seed\n", encoding="utf-8")
    (base / "device-config.yaml").write_text(
        "mobile_breakpoint: 640\n", encoding="utf-8")
    return tmp_path / "seeds"


def _store():
    from boerdi.db.notify import asyncpg_dsn
    from boerdi.db.session import make_engine
    from boerdi.services.config_store import ConfigStore
    from boerdi.settings import get_settings

    settings = get_settings()
    engine = make_engine(settings)
    return ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url)), engine


def _read_all() -> dict[str, dict]:
    async def scenario():
        store, engine = _store()
        try:
            out = {}
            for meta in await store.list_areas():
                out[meta["area"]] = await store.get(meta["area"])
            return out
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def _edit(area: str, data: dict) -> None:
    async def scenario():
        store, engine = _store()
        try:
            await store.put(area, data, updated_by="redaktion")
        finally:
            await engine.dispose()

    asyncio.run(scenario())


def test_only_missing_seeds_the_empty_database(seed_db, seed_tree) -> None:
    from boerdi.cli import main

    assert main(["import-config", "--from", str(seed_tree), "--only-missing"]) == 0
    areas = _read_all()
    assert len(areas) == 2, "beide Bereiche fehlten, beide müssen angelegt werden"
    assert any(d.get("greeting") == "aus dem Seed" for d in areas.values())


def test_only_missing_laesst_redaktionelle_arbeit_stehen(seed_db, seed_tree) -> None:
    from boerdi.cli import main

    main(["import-config", "--from", str(seed_tree), "--only-missing"])
    area = next(a for a, d in _read_all().items() if d.get("greeting"))
    _edit(area, {"greeting": "von der Redaktion"})

    # Zweiter Lauf, wie ihn ein Neustart auslösen würde.
    assert main(["import-config", "--from", str(seed_tree), "--only-missing"]) == 0
    assert _read_all()[area]["greeting"] == "von der Redaktion"


def test_only_missing_ergaenzt_einen_neu_hinzugekommenen_bereich(
    seed_db, seed_tree) -> None:
    from boerdi.cli import main

    main(["import-config", "--from", str(seed_tree), "--only-missing"])
    (seed_tree / "01-base" / "intents.yaml").write_text(
        "intents: [suchen]\n", encoding="utf-8")

    assert main(["import-config", "--from", str(seed_tree), "--only-missing"]) == 0
    areas = _read_all()
    assert len(areas) == 3, "der neue Bereich fehlte und muss dazukommen"


def test_ohne_flag_bleibt_der_voll_import_wie_er_war(seed_db, seed_tree) -> None:
    """Kein stiller Verhaltenswechsel: der ausdrückliche Import überschreibt."""
    from boerdi.cli import main

    main(["import-config", "--from", str(seed_tree), "--only-missing"])
    area = next(a for a, d in _read_all().items() if d.get("greeting"))
    _edit(area, {"greeting": "von der Redaktion"})

    assert main(["import-config", "--from", str(seed_tree)]) == 0
    assert _read_all()[area]["greeting"] == "aus dem Seed"


# ── Paket 6, W3: ``--exact`` — der Werkszustand ohne Studio ────────────────
#
# Der Voll-Import überschreibt, löscht aber nichts und legt keinen Schnappschuss
# an — ein im Studio angelegtes Muster überlebte ihn. ``--exact`` ist derselbe
# Ablauf wie „Alles auf Auslieferungsstand“ im Studio (``seed_sync.herstellen``):
# prüfen, sichern, schreiben UND löschen in einer Transaktion. ``--dry-run``
# zeigt nur, was geschähe.


@pytest.fixture
def exakt_baum(tmp_path):
    """Seed-Baum ohne Modell-Bereiche: geprüft wird der Ablauf, nicht der Inhalt."""
    base = tmp_path / "seeds" / "01-base"
    base.mkdir(parents=True)
    (base / "neu.yaml").write_text("a: 1\n", encoding="utf-8")
    (base / "anders.yaml").write_text("b: 2\n", encoding="utf-8")
    return tmp_path / "seeds"


def _schnappschuesse() -> int:
    async def scenario():
        from boerdi.db.session import make_engine
        from boerdi.services import snapshots
        from boerdi.settings import get_settings

        engine = make_engine(get_settings())
        try:
            return await snapshots.count_snapshots(engine)
        finally:
            await engine.dispose()

    return asyncio.run(scenario())


def test_exact_schreibt_loescht_und_sichert_vorher(seed_db, exakt_baum, capsys) -> None:
    from boerdi.cli import main

    _edit("01-base/anders", {"b": 1})
    _edit("01-base/eigenbau", {"x": 1})  # nur in der Datenbank, etwa im Studio angelegt

    assert main(["import-config", "--from", str(exakt_baum), "--exact"]) == 0
    assert _read_all() == {"01-base/neu": {"a": 1}, "01-base/anders": {"b": 2}}
    assert _schnappschuesse() == 1, "ohne Schnappschuss kein verlustbehafteter Lauf"
    ausgabe = capsys.readouterr().out
    assert "2 geschrieben" in ausgabe and "1 gelöscht" in ausgabe


def test_exact_mit_dry_run_aendert_nichts(seed_db, exakt_baum, capsys) -> None:
    from boerdi.cli import main

    _edit("01-base/eigenbau", {"x": 1})
    assert main(["import-config", "--from", str(exakt_baum), "--exact", "--dry-run"]) == 0
    assert _read_all() == {"01-base/eigenbau": {"x": 1}}
    assert _schnappschuesse() == 0
    ausgabe = capsys.readouterr().out
    assert "01-base/neu" in ausgabe and "01-base/eigenbau" in ausgabe


def test_exact_weist_einen_ungueltigen_seed_ab(seed_db, exakt_baum, capsys) -> None:
    from boerdi.cli import main

    (exakt_baum / "01-base" / "engine.yaml").write_text("mode: kaputt\n", encoding="utf-8")
    _edit("01-base/eigenbau", {"x": 1})
    assert main(["import-config", "--from", str(exakt_baum), "--exact"]) == 1
    assert _read_all() == {"01-base/eigenbau": {"x": 1}}, "nichts geschrieben, nichts gelöscht"
    assert _schnappschuesse() == 0
    assert "01-base/engine" in capsys.readouterr().err


def test_exact_und_only_missing_schliessen_sich_aus(seed_db, exakt_baum) -> None:
    from boerdi.cli import main

    assert main(["import-config", "--from", str(exakt_baum), "--exact", "--only-missing"]) == 2


def test_dry_run_gibt_es_nur_mit_exact(seed_db, exakt_baum) -> None:
    from boerdi.cli import main

    assert main(["import-config", "--from", str(exakt_baum), "--dry-run"]) == 2
