"""Config snapshots + backup/restore + factory (P2-7).

Snapshots are config-area ZIP blobs in the config_snapshots table (spec §6);
restore/upload stream every member against a decompression budget (zip-bomb
guard). All endpoints are Studio-gated; ALT's finer 'builder' role maps to
the P9 studio-bff and is deferred.

DB-include (full Postgres dump) is deferred to P10 — backups here carry the
config areas, which is what the Studio edits.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Security, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from boerdi.api.config_guards import pruefe_bereiche
from boerdi.api.config_kennungen import (
    SICHERHEIT,
    kennungs_einwand,
    loeschbar,
    sicherheits_kennungen_aus,
)
from boerdi.api.deps import Lang, require_studio_key
from boerdi.i18n import Locale, msg
from boerdi.services import config_loader as cl
from boerdi.services import seed_sync, snapshots
from boerdi.services.werkfassung import pruefsumme
from boerdi.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/config", tags=["config-snapshots"],
    dependencies=[Security(require_studio_key)],
)


class SnapshotCreate(BaseModel):
    label: str = ""


def _zip_response(blob: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        iter([blob]), media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


#: Paket 7 (P5, P5-5): ``merge`` (Vorgabe) schreibt die Bereiche der Sicherung und
#: lässt alles andere stehen; ``exact`` löscht dazu, was seitdem neu angelegt wurde
#: (etwa ein neues Muster) — nach einem Schnappschuss des Stands davor.
Wiederherstellen = Literal["merge", "exact"]


def _lies_zip(blob: bytes, lang: Locale) -> dict[str, dict]:
    """The areas of a backup — 413 over the caps, 400 for an unreadable member."""
    try:
        return snapshots.parse_config_zip(blob)
    except snapshots.SnapshotTooLarge as e:
        raise HTTPException(status_code=413, detail=str(e)) from None
    except snapshots.SicherungUngueltig as e:
        raise HTTPException(400, msg(lang, "snapshots.invalidFile", file=e.datei)) from None


async def _apply_config(blob: bytes, lang: Locale, mode: Wiederherstellen = "merge") -> dict:
    """Parse a config ZIP (with caps) and write its areas. 413 on cap breach.

    Three checks, all over ALL areas before anything is written — a
    half-restored store would be worse than none: keys must be valid area paths
    (audit 2026-09-29, A-M7; others are skipped with a warning), documents pass
    the egress checks of a Studio write (``_assert_area_document_safe``, review
    2026-10-03; a failure answers 400), and every area with a model passes it
    (Paket 4, D3; one 422 listing all objections, each with its ``area``).

    ``mode="exact"`` also deletes the live areas the ZIP does not carry — after a
    snapshot of the state before (refused with 400 when no slot is left, like the
    seed's exact run: no lossy run without a way back). Returns the response body;
    ``snapshot_id`` names that snapshot, ``None`` when nothing was deleted.

    Review Paket 7, A-4: "carry" means any key in the ZIP, not only the writable
    ones — an area skipped for its path is still in the backup. And exact mode
    refuses a ZIP without a single writable area (400): a wrong file would
    otherwise delete the whole configuration.

    Paket 9 (review Paket 7, MAJOR 5 / MINOR 32): exact mode deletes only what the
    Studio's delete would (``config_kennungen.loeschbar``; a partial backup took the
    safety config and M01 along), and ids pass the editor's rules (400).
    """
    areas = _lies_zip(blob, lang)
    valid = pruefe_bereiche(areas, lang)
    loeschen: list[str] = []
    sicherung: str | None = None
    live = await cl.current_config()
    if mode == "exact":
        if not valid:
            raise HTTPException(400, msg(lang, "snapshots.exactEmpty"))
        geschuetzt = (sicherheits_kennungen_aus(live.get(SICHERHEIT))
                      | sicherheits_kennungen_aus(areas.get(SICHERHEIT)))
        loeschen = sorted(k for k in set(live) - set(areas)
                          if loeschbar(k, live[k], geschuetzt))
    store = cl.bound_store()
    # Paket 12, Review 2 #1: ein Bereich mit stillgelegter eigener Fassung wird nie gelöscht —
    # sie steht in keinem Schnappschuss. Er bleibt und wird gemeldet.
    mit_eigener = {z["area"] for z in await store.fassungen() if z["hat_eigene_fassung"]}
    behalten = sorted(set(loeschen) & mit_eigener)
    loeschen = [k for k in loeschen if k not in mit_eigener]
    bleibt = {k: v for k, v in live.items() if k not in loeschen}
    einwand = kennungs_einwand(valid, bleibt, sicherheits_kennungen_aus(live.get(SICHERHEIT)))
    if einwand:
        raise HTTPException(400, msg(lang, einwand.meldung, **einwand.werte))
    if loeschen:
        try:
            sicherung = await snapshots.schnappschuss_anlegen(
                cl.store_engine(), msg(lang, "snapshots.label.exactRestore"), live, art="auto")
        except snapshots.SchnappschussGrenze:
            raise _grenze(lang) from None
    # One transaction for all (Paket 4, D4): a failing area leaves none written.
    werk = await seed_sync.werk_bereiche(get_settings().config_seed_dir)
    await cl.write_areas(valid, updated_by="restore", delete=loeschen, werk_bereiche=werk)
    return {"status": "restored", "areas": len(valid), "deleted": len(loeschen),
            "snapshot_id": sicherung, "behalten": behalten}


async def _read_upload_capped(file: UploadFile, lang: Locale) -> bytes:
    raw = await file.read(snapshots.MAX_CONFIG_UPLOAD_BYTES + 1)
    if len(raw) > snapshots.MAX_CONFIG_UPLOAD_BYTES:
        raise HTTPException(
            413,
            msg(lang, "upload.tooLarge", mb=snapshots.MAX_CONFIG_UPLOAD_BYTES // (1024 * 1024)),
        )
    return raw


# ── snapshots ──────────────────────────────────────────────────────────────
@router.get("/snapshots")
async def list_snapshots() -> list[dict]:
    return await snapshots.list_snapshots(cl.store_engine())


def _grenze(lang: Locale) -> HTTPException:
    return HTTPException(400, msg(lang, "snapshots.limitReached", max=snapshots.MAX_SNAPSHOTS))


@router.post("/snapshots")
async def create_snapshot(payload: SnapshotCreate, lang: Lang) -> dict:
    try:
        snap_id = await snapshots.schnappschuss_anlegen(
            cl.store_engine(), payload.label.strip(), await cl.current_config())
    except snapshots.SchnappschussGrenze:
        raise _grenze(lang) from None
    return {"id": snap_id, "label": payload.label.strip()}


@router.delete("/snapshots/{snap_id}")
async def delete_snapshot(snap_id: str, lang: Lang) -> dict:
    if not await snapshots.delete_snapshot(cl.store_engine(), snap_id):
        raise HTTPException(
            status_code=404, detail=msg(lang, "snapshots.notFound"),
        )
    return {"status": "deleted", "id": snap_id}


@router.get("/snapshots/{snap_id}/download")
async def download_snapshot(snap_id: str, lang: Lang) -> StreamingResponse:
    snap = await snapshots.get_snapshot(cl.store_engine(), snap_id)
    if snap is None:
        raise HTTPException(
            status_code=404, detail=msg(lang, "snapshots.notFound"),
        )
    return _zip_response(snap["blob"], f"{snap_id}.zip")


@router.post("/snapshots/{snap_id}/restore")
async def restore_snapshot(snap_id: str, lang: Lang, mode: Wiederherstellen = "merge") -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snap_id)
    if snap is None:
        raise HTTPException(
            status_code=404, detail=msg(lang, "snapshots.notFound"),
        )
    return await _apply_config(snap["blob"], lang, mode)


# ── factory (the row with id 'factory') ────────────────────────────────────
@router.get("/factory")
async def factory_status() -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        return {"exists": False}
    return {"exists": True, "created_at": snap["created_at"].isoformat(),
            "label": snap["label"]}


@router.get("/factory/download")
async def download_factory(lang: Lang) -> StreamingResponse:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        raise HTTPException(404, msg(lang, "factory.missing"))
    return _zip_response(snap["blob"], "factory.zip")


@router.post("/factory/save")
async def save_factory() -> dict:
    blob = snapshots.build_config_zip(await cl.current_config())
    await snapshots.save_snapshot(cl.store_engine(), snapshots.FACTORY_ID, "factory", blob)
    return {"status": "saved", "id": snapshots.FACTORY_ID}


@router.post("/factory/restore")
async def restore_factory(lang: Lang, mode: Wiederherstellen = "merge") -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        raise HTTPException(404, msg(lang, "factory.missing"))
    return await _apply_config(snap["blob"], lang, mode)


@router.post("/factory/upload")
async def upload_factory(file: UploadFile, lang: Lang) -> dict:
    blob = await _read_upload_capped(file, lang)
    _lies_zip(blob, lang)  # parses within the caps before it becomes the factory baseline
    await snapshots.save_snapshot(cl.store_engine(), snapshots.FACTORY_ID, "factory", blob)
    return {"status": "saved", "id": snapshots.FACTORY_ID}


# ── Auslieferungsstand aus dem Bild (S3) ───────────────────────────────────
# Der Seed-Baum reist im Bild mit; bisher kam er nur über die CLI und damit nur
# über SSH in die Datenbank. Plan: docs/plans/2026-08-17-werkszustand-im-studio.md
#
# **Der Werksstand darüber ist etwas anderes.** Er ist eine Momentaufnahme des
# gelebten Standes; dies hier ist der Stand, mit dem das Bild gebaut wurde.
# Beide bleiben nebeneinander — sie beantworten verschiedene Fragen.

class SeedApply(BaseModel):
    mode: seed_sync.Modus = "missing"


def _seed_dir() -> Path | None:
    return seed_sync.seed_pfad(get_settings().config_seed_dir)


@router.get("/seed")
async def seed_status() -> dict:
    """Zählung des Auslieferungsstandes gegen den gelebten — ohne etwas zu ändern.

    Verglichen wird gegen ``current_config()``, also gegen genau die Quelle, aus
    der auch der Rückweg-Schnappschuss gebaut wird. Zwei Quellen wären hier ein
    stiller Fehler: der Schnappschuss deckte dann womöglich nicht ab, was der
    Lauf löscht.
    """
    pfad = _seed_dir()
    if pfad is None:
        return {"available": False, "area_count": 0,
                "neu": [], "gleich": [], "abweichend": [], "nur_in_db": []}
    seed = await seed_sync.seed_lesen(pfad)
    diff = seed_sync.vergleiche(seed, await cl.current_config())
    # Im Studio gelöschte Werksbereiche fehlen gewollt (Paket 12) — „Fehlende nachziehen“ holt
    # sie nicht zurück, also zählen sie hier auch nicht als fehlend.
    entfernt = await cl.bound_store().entfernte()
    return {"available": True, "area_count": len(seed),
            "neu": [a for a in diff.neu if a not in entfernt],
            "gleich": diff.gleich, "abweichend": diff.abweichend,
            "nur_in_db": diff.nur_in_db}


@router.post("/seed/apply")
async def seed_apply(payload: SeedApply, lang: Lang) -> dict:
    """``missing`` zieht Fehlendes nach; ``exact`` stellt den Stand her.

    ``exact`` überschreibt gepflegte Bereiche und löscht, was nur in der
    Datenbank steht — deshalb vorher der Schnappschuss. Ist kein Platz mehr für
    ihn, wird der Lauf verweigert statt ohne Rückweg ausgeführt. Der Ablauf
    steht in ``seed_sync.herstellen`` (Paket 6, W2), geteilt mit ``boerdi
    import-config --exact``: erst prüfen wie ein Wiederherstellen (422 mit
    allen Einwänden, nichts geschrieben, kein Schnappschuss), dann Schnappschuss
    und Vergleich aus EINEM Lesevorgang, dann alles in einer Transaktion.
    """
    pfad = _seed_dir()
    if pfad is None:
        raise HTTPException(404, msg(lang, "seed.missing"))

    async def sichern(stand: dict[str, dict]) -> str:
        try:
            return await snapshots.schnappschuss_anlegen(
                cl.store_engine(), msg(lang, "snapshots.label.seedApply"), stand, art="auto")
        except snapshots.SchnappschussGrenze:
            raise _grenze(lang) from None

    async def schreiben(bereiche: dict[str, dict], loeschen: list[str]) -> None:
        # Alles Geschriebene ist Werksfassung: die Basis gleich mitmerken (Paket 12).
        await cl.write_areas(bereiche, updated_by="seed-apply", delete=loeschen,
                             werk_hashes={a: pruefsumme(d) for a, d in bereiche.items()})

    store = cl.bound_store()
    mit_eigener = {z["area"] for z in await store.fassungen() if z["hat_eigene_fassung"]}
    return await seed_sync.herstellen(
        pfad, payload.mode, pruefen=lambda seed: pruefe_bereiche(seed, lang),
        lesen=cl.current_config, sichern=sichern, schreiben=schreiben,
        entfernt=await store.entfernte(), geschuetzt=mit_eigener)


# ── full backup / restore (live config ZIP) ────────────────────────────────
@router.get("/backup")
async def download_backup() -> StreamingResponse:
    blob = snapshots.build_config_zip(await cl.current_config())
    return _zip_response(blob, "boerdi-config-backup.zip")


@router.post("/restore")
async def restore_backup(file: UploadFile, lang: Lang, mode: Wiederherstellen = "merge") -> dict:
    blob = await _read_upload_capped(file, lang)
    return await _apply_config(blob, lang, mode)
