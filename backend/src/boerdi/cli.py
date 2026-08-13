"""boerdi CLI (P2-4, spec §9): import-config / export-config.

    uv run boerdi import-config --from <badboerdi/backend/chatbots/wlo/v1>
    uv run boerdi import-config --only-missing        # idempotent, für den Installationslauf
    uv run boerdi export-config --to <dir>

Uses DATABASE_URL from settings/env; import stamps updated_by='import'.

``--only-missing`` exists because the plain import writes every area
unconditionally. That is right for the one-off install step and destructive as
an automatic one: each restart would roll editorial work in the Studio back to
the seed. With the flag the import only fills gaps, so it may run on every
start (compose ``migrate``) without touching what is already there.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from boerdi.db.notify import asyncpg_dsn
from boerdi.db.session import make_engine, make_session_factory
from boerdi.services import seed_io
from boerdi.services.config_store import ConfigStore
from boerdi.settings import get_settings


async def _import_config(src: Path, only_missing: bool = False) -> int:
    settings = get_settings()
    engine = make_engine(settings)
    store = ConfigStore(engine, listen_dsn=asyncpg_dsn(settings.database_url))
    try:
        kept: list[str] = []

        async def put(area: str, data: dict) -> None:
            # Once an area exists, the database is the truth (Studio editing) —
            # the seed is a starting point, not a runtime dependency.
            if only_missing and await store.get(area) is not None:
                kept.append(area)
                return
            await store.put(area, data, updated_by="import")

        stats = await seed_io.import_tree(src, put)
        print(f"imported {stats['areas'] - len(kept)} areas "
              f"({stats['yaml']} yaml, {stats['md']} md) from {src}"
              + (f"; kept {len(kept)} existing" if kept else ""))
        return 0
    finally:
        await engine.dispose()


async def _export_config(dst: Path) -> int:
    settings = get_settings()
    engine = make_engine(settings)
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

    engine = make_engine(get_settings())
    try:
        factory = make_session_factory(engine)
        async with factory() as session:
            stats = await import_rag_from_sqlite(session, sqlite_path)
        print(f"imported {stats['chunks']} chunks in {stats['documents']} documents "
              f"from {sqlite_path}")
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="boerdi")
    sub = parser.add_subparsers(dest="command", required=True)

    p_imp = sub.add_parser("import-config", help="import a config tree into config_areas")
    p_imp.add_argument("--from", dest="src", default=get_settings().config_seed_dir,
                       help="source tree (default: CONFIG_SEED_DIR)")
    p_imp.add_argument("--only-missing", dest="only_missing", action="store_true",
                       help="only create areas that do not exist yet (idempotent; "
                            "safe to run on every start)")

    p_exp = sub.add_parser("export-config", help="export config_areas as YAML/MD tree")
    p_exp.add_argument("--to", dest="dst", required=True)

    p_rag = sub.add_parser("import-rag", help="re-ingest ALT sqlite rag_chunks into pgvector")
    p_rag.add_argument("--sqlite", dest="sqlite", required=True,
                       help="path to a COPY of the ALT badboerdi.db (opened read-only)")

    args = parser.parse_args(argv)
    if args.command == "import-config":
        if not args.src:
            print("--from (or CONFIG_SEED_DIR) required", file=sys.stderr)
            return 2
        src = Path(args.src)
        if not src.is_dir():
            print(f"source tree not found: {src}", file=sys.stderr)
            return 2
        return asyncio.run(_import_config(src, only_missing=args.only_missing))
    if args.command == "import-rag":
        sqlite_path = Path(args.sqlite)
        if not sqlite_path.is_file():
            print(f"sqlite db not found: {sqlite_path}", file=sys.stderr)
            return 2
        return asyncio.run(_import_rag(sqlite_path))
    return asyncio.run(_export_config(Path(args.dst)))


if __name__ == "__main__":
    raise SystemExit(main())
