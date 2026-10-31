"""boerdi CLI (P2-4, spec §9): import-config / export-config / import-rag / rag-einbettung-wechseln.

    uv run boerdi import-config --from <badboerdi/backend/chatbots/wlo/v1>
    uv run boerdi import-config --werksabgleich       # beim Start (migrate): Werk nachziehen
    uv run boerdi import-config --only-missing        # nur Fehlendes anlegen
    uv run boerdi import-config --exact [--dry-run]   # Werkszustand wie im Studio
    uv run boerdi export-config --to <dir>

Uses DATABASE_URL from settings/env; the plain import stamps updated_by='import-cli'
(Paket 12: 'import' counted as untouched factory content and stays for pre-0011 rows only).

``--only-missing`` exists because the plain import writes every area
unconditionally. That is right for the one-off install step and destructive as
an automatic one: each restart would roll editorial work in the Studio back to
the seed. With the flag the import only fills gaps, so it may run on every
start (compose ``migrate``) without touching what is already there.

``--exact`` is the factory reset without the Studio (Paket 6, W3): the same flow
as „Alles auf Auslieferungsstand“ (``seed_sync.herstellen``) — the seed is
checked like a restore, a snapshot of the live state is taken, then new and
differing areas are written AND areas found only in the database are deleted,
in one transaction. The plain import overwrites but deletes nothing, so a
pattern created in the Studio survived it. ``--dry-run`` only lists what would
happen.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from boerdi.db.notify import asyncpg_dsn
from boerdi.db.session import make_engine, make_session_factory
from boerdi.services import seed_io
from boerdi.services.config_store import ConfigStore
from boerdi.services.werkfassung import pruefsumme
from boerdi.settings import get_settings


async def _import_config(src: Path, only_missing: bool = False) -> int:
    settings = get_settings()
    engine = make_engine(settings, fristen=False)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
    try:
        kept: list[str] = []
        items: dict[str, dict] = {}
        entfernt = await store.entfernte() if only_missing else set()

        async def put(area: str, data: dict) -> None:
            # Once an area exists, the database is the truth (Studio editing) —
            # the seed is a starting point, not a runtime dependency.
            if only_missing and (await store.get(area) is not None or area in entfernt):
                # Paket 12 (Review 2 #7): im Studio Gelöschtes bleibt gelöscht.
                kept.append(area)
                return
            items[area] = data

        stats = await seed_io.import_tree(src, put)
        # Paket 12 (Review #3): nur ein Import aus dem Seed-Ordner ist Werksfassung und merkt die
        # Basis; ein anderer Baum (Server-Umzug, ALT) gilt als eigen — sonst hielte der nächste
        # Start ihn für unberührt und hübe ihn auf das Werk.
        aus_dem_werk = _ist_seed(src)
        await store.put_many(items, updated_by="import-cli", werk_hashes=(
            {a: pruefsumme(d) for a, d in items.items()} if aus_dem_werk else None))
        print(f"imported {stats['areas'] - len(kept)} areas "
              f"({stats['yaml']} yaml, {stats['md']} md) from {src}"
              + (f"; kept {len(kept)} existing" if kept else ""))
        return 0
    finally:
        await engine.dispose()


async def _werksabgleich(src: Path) -> int:
    """Werksfassung nachziehen, Angepasstes lassen (Paket 12) — der Schritt beim Hochfahren
    (``migrate``-Dienst)."""
    from boerdi.api.config_guards import pruefe_bereiche
    from boerdi.api.config_kennungen import kennungs_kollisionen
    from boerdi.services import seed_sync

    settings = get_settings()
    engine = make_engine(settings, fristen=False)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))

    async def schreiben(eintraege: dict) -> dict[str, int]:
        return await store.werk_schreiben(eintraege, updated_by="werksabgleich")

    try:
        bericht = await seed_sync.werksabgleich(
            src, pruefen=lambda seed: pruefe_bereiche(seed, "de"), lesen=store.fassungen,
            entfernte=store.entfernte, schreiben=schreiben, zuordnen=store.werk_hashes_setzen,
            kollisionen=kennungs_kollisionen)
    except Exception as fehler:  # noqa: BLE001 — eine Zeile statt Stacktrace, Exit 1
        detail = getattr(fehler, "detail", None)
        print(f"Werksabgleich abgebrochen: {_einwaende(detail) if detail else fehler}",
              file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print("Werksabgleich: {neu} neu, {aktualisiert} aktualisiert, {zugeordnet} zugeordnet, "
          "{neues_werk} angepasst mit neuer Werksfassung, {uebersprungen} übersprungen "
          "(inzwischen geändert), {konflikt} mit nicht verwendbarer Kennung".format(**bericht))
    return 0


def _ist_seed(src: Path) -> bool:
    """Zeigt ``src`` auf den ausgelieferten Seed-Baum (``CONFIG_SEED_DIR``)?"""
    from boerdi.services import seed_sync

    seed = seed_sync.seed_pfad(get_settings().config_seed_dir)
    return seed is not None and seed.resolve() == src.resolve()


class _Abbruch(Exception):
    """Ein Lauf, der vor dem Schreiben endet — die Meldung geht an stderr."""


def _einwaende(detail: Any) -> str:
    """Die Einwände einer Prüfung lesbar, je Bereich eine Angabe."""
    if isinstance(detail, list):
        return "; ".join(f"{f.get('area', '?')}: {f.get('msg', f)}" for f in detail)
    return str(detail)


async def _import_exact(src: Path, *, dry_run: bool) -> int:
    """Den Auslieferungsstand herstellen wie im Studio (Paket 6, W3)."""
    from fastapi import HTTPException

    from boerdi.api.config_guards import pruefe_bereiche
    from boerdi.services import seed_sync, snapshots

    settings = get_settings()
    engine = make_engine(settings, fristen=False)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))

    def pruefen(seed: dict[str, dict]) -> dict[str, dict]:
        return pruefe_bereiche(seed, "de")

    async def sichern(stand: dict[str, dict]) -> str:
        try:
            return await snapshots.schnappschuss_anlegen(
                engine, "vor Werksfassung (Kommandozeile)", stand, art="auto")
        except snapshots.SchnappschussGrenze:
            raise _Abbruch(f"Schnappschuss-Grenze erreicht ({snapshots.MAX_SNAPSHOTS}): "
                           "erst alte Schnappschüsse löschen, nichts geändert.") from None

    async def schreiben(bereiche: dict[str, dict], loeschen: list[str]) -> None:
        # Alles Geschriebene ist Werksfassung: die Basis gleich mitmerken (Paket 12).
        await store.put_many(bereiche, updated_by="seed-apply-cli", delete=loeschen,
                             werk_hashes={a: pruefsumme(d) for a, d in bereiche.items()})

    mit_eigener = {z["area"] for z in await store.fassungen() if z["hat_eigene_fassung"]}
    try:
        if dry_run:
            diff = seed_sync.vergleiche(pruefen(await seed_sync.seed_lesen(src)),
                                        await store.all_data())
            for titel, liste in (("neu (würde angelegt)", diff.neu),
                                 ("abweichend (würde überschrieben)", diff.abweichend),
                                 ("nur in der Datenbank (würde gelöscht)", diff.nur_in_db)):
                print(f"{titel}: {len(liste)}")
                for area in liste:
                    print(f"  {area}")
            print(f"gleich: {len(diff.gleich)} — Probelauf, nichts geändert")
            return 0
        bericht = await seed_sync.herstellen(src, "exact", pruefen=pruefen, lesen=store.all_data,
                                             sichern=sichern, schreiben=schreiben,
                                             geschuetzt=mit_eigener)
        print(f"Auslieferungsstand hergestellt: {bericht['written']} geschrieben, "
              f"{bericht['deleted']} gelöscht. Rückweg: Schnappschuss {bericht['snapshot_id']} "
              "(Studio → Sicherung).")
        return 0
    except HTTPException as e:
        print(f"Seed abgewiesen, nichts geändert — {_einwaende(e.detail)}", file=sys.stderr)
        return 1
    except _Abbruch as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


async def _export_config(dst: Path) -> int:
    settings = get_settings()
    engine = make_engine(settings, fristen=False)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
    try:
        areas: dict[str, dict] = {}
        for meta in await store.list_areas():
            data = await store.get(meta["area"])
            if data is not None:
                areas[meta["area"]] = data
        seed_io.export_tree(areas, dst)
        print(f"exported {len(areas)} areas to {dst}")
        return 0
    finally:
        await engine.dispose()


async def _import_rag(sqlite_path: Path) -> int:
    from boerdi.services.rag.import_rag import import_rag_from_sqlite

    engine = make_engine(get_settings(), fristen=False)
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            stats = await import_rag_from_sqlite(session, sqlite_path)
        print(f"imported {stats['chunks']} chunks in {stats['documents']} documents "
              f"from {sqlite_path}")
        return 0
    finally:
        await engine.dispose()


async def _import_rag_seed(seed_dir: Path, *, force: bool) -> int:
    from boerdi.services.rag.import_rag import import_rag_from_seed

    engine = make_engine(get_settings(), fristen=False)
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            stats = await import_rag_from_seed(session, seed_dir, force=force)
        print(f"imported {stats['chunks']} chunks in {stats['documents']} documents "
              f"from {seed_dir}")
        if stats.get("skipped"):
            print("skipped (already populated, use --force to replace): "
                  + ", ".join(stats["skipped"]))
        return 0
    finally:
        await engine.dispose()


async def _einbettung_wechseln(*, probe: bool, fortsetzen: bool) -> int:
    """Wissensbasis in den Raum des eingestellten Einbettungsmodells überführen (Paket 11, D)."""
    from boerdi.services.rag import einbettung_wechsel as ew

    engine = make_engine(get_settings(), fristen=False)
    try:
        try:
            b = await ew.wechseln(engine, probe=probe, fortsetzen=fortsetzen)
        except ew.Abbruch as grund:
            print(f"abgebrochen, nichts geändert: {grund}", file=sys.stderr)
            return 2
        if probe:
            print(f"Spalte vector({b.spalte_vorher}) → Modell {b.dimension} Dimensionen; "
                  f"{b.abschnitte} Abschnitte, davon {b.fehlend} ohne Vektor"
                  " — Probe, nichts geändert")
            return 0
        print(f"vector({b.dimension}): {b.eingebettet} von {b.abschnitte} Abschnitten eingebettet")
        if b.fehlend:
            print(f"{b.fehlend} Abschnitte noch ohne Vektor"
                  " — mit --fortsetzen erneut laufen lassen",
                  file=sys.stderr)
            return 1
        return 0
    finally:
        await engine.dispose()


def _rag_seed_default() -> Path:
    """``<CONFIG_SEED_DIR>/rag`` — der Seed liegt neben dem der Konfiguration."""
    return Path(get_settings().config_seed_dir) / "rag"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boerdi")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import-config", help="import a config tree into config_areas")
    p_imp.add_argument("--from", dest="src", default=get_settings().config_seed_dir,
                       help="source tree (default: CONFIG_SEED_DIR)")
    p_imp.add_argument("--only-missing", dest="only_missing", action="store_true",
                       help="only create areas that do not exist yet (idempotent; "
                            "safe to run on every start)")
    p_imp.add_argument("--exact", dest="exact", action="store_true",
                       help="factory reset: snapshot first, then write new and differing "
                            "areas and delete areas found only in the database")
    p_imp.add_argument("--werksabgleich", dest="werksabgleich", action="store_true",
                       help="create missing areas, lift untouched ones to a new factory version, "
                            "never touch customized or deleted ones (the migrate step)")
    p_imp.add_argument("--dry-run", dest="dry_run", action="store_true",
                       help="with --exact: only list what would change")

    p_exp = sub.add_parser("export-config", help="export config_areas as YAML/MD tree")
    p_exp.add_argument("--to", dest="dst", required=True)

    p_rag = sub.add_parser(
        "import-rag",
        help="fill rag_chunks: from the repo seed (default) or from an ALT sqlite")
    p_rag.add_argument("--seed", dest="seed", nargs="?", const="", default=None,
                       help="seed tree with *.jsonl (default: <CONFIG_SEED_DIR>/rag)")
    p_rag.add_argument("--sqlite", dest="sqlite", default=None,
                       help="path to a COPY of the ALT badboerdi.db (opened read-only)")
    p_rag.add_argument("--force", dest="force", action="store_true",
                       help="empty the seeded areas first (default: skip populated ones)")

    p_emb = sub.add_parser(
        "rag-einbettung-wechseln",
        help="re-embed every rag chunk with the configured embedding model (new vector space)")
    p_emb.add_argument("--probe", action="store_true",
                       help="only measure the model's dimension and count chunks")
    p_emb.add_argument("--fortsetzen", action="store_true",
                       help="after an interrupted run: only embed chunks still without a vector")

    args = parser.parse_args(argv)
    if args.command == "rag-einbettung-wechseln":
        if args.probe and args.fortsetzen:
            print("--probe and --fortsetzen are mutually exclusive", file=sys.stderr)
            return 2
        return asyncio.run(_einbettung_wechseln(probe=args.probe, fortsetzen=args.fortsetzen))
    if args.command == "import-config":
        if not args.src:
            print("--from (or CONFIG_SEED_DIR) required", file=sys.stderr)
            return 2
        src = Path(args.src)
        if not src.is_dir():
            print(f"source tree not found: {src}", file=sys.stderr)
            return 2
        if sum((args.exact, args.only_missing, args.werksabgleich)) > 1:
            print("--exact, --only-missing and --werksabgleich are mutually exclusive",
                  file=sys.stderr)
            return 2
        if args.dry_run and not args.exact:
            print("--dry-run needs --exact", file=sys.stderr)
            return 2
        if args.exact:
            return asyncio.run(_import_exact(src, dry_run=args.dry_run))
        if args.werksabgleich:
            return asyncio.run(_werksabgleich(src))
        return asyncio.run(_import_config(src, only_missing=args.only_missing))
    if args.command == "import-rag":
        # Zwei Quellen, eine Wahl: ``--sqlite`` ist die einmalige Bruecke aus ALT,
        # der Seed der Dauerzustand. Beides zusammen waere zweideutig, keins von
        # beidem heisst „nimm den Seed".
        if args.sqlite and args.seed is not None:
            print("--seed and --sqlite are mutually exclusive", file=sys.stderr)
            return 2
        if args.sqlite:
            sqlite_path = Path(args.sqlite)
            if not sqlite_path.is_file():
                print(f"sqlite db not found: {sqlite_path}", file=sys.stderr)
                return 2
            return asyncio.run(_import_rag(sqlite_path))
        seed_dir = Path(args.seed) if args.seed else _rag_seed_default()
        if not seed_dir.is_dir():
            print(f"seed tree not found: {seed_dir}", file=sys.stderr)
            return 2
        return asyncio.run(_import_rag_seed(seed_dir, force=args.force))
    return asyncio.run(_export_config(Path(args.dst)))


if __name__ == "__main__":
    raise SystemExit(main())
