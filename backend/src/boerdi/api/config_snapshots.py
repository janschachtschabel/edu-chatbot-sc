"""Config snapshots + backup/restore + factory (P2-7).

Snapshots are config-area ZIP blobs in the config_snapshots table (spec §6);
restore/upload stream every member against a decompression budget (zip-bomb
guard). All endpoints are Studio-gated; ALT's finer 'builder' role maps to
the P9 studio-bff and is deferred.

DB-include (full Postgres dump) is deferred to P10 — backups here carry the
config areas, which is what the Studio edits.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Security, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from boerdi.api.deps import require_studio_key
from boerdi.services import config_loader as cl
from boerdi.services import snapshots

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


async def _apply_config(blob: bytes) -> int:
    """Parse a config ZIP (with caps) and write every area. 413 on cap breach."""
    try:
        areas = snapshots.parse_config_zip(blob)
    except snapshots.SnapshotTooLarge as e:
        raise HTTPException(status_code=413, detail=str(e)) from None
    for key, data in areas.items():
        await cl.write_area(key, data, updated_by="restore")
    return len(areas)


async def _read_upload_capped(file: UploadFile) -> bytes:
    raw = await file.read(snapshots.MAX_CONFIG_UPLOAD_BYTES + 1)
    if len(raw) > snapshots.MAX_CONFIG_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Datei zu groß (max {snapshots.MAX_CONFIG_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )
    return raw


# ── snapshots ──────────────────────────────────────────────────────────────
@router.get("/snapshots")
async def list_snapshots() -> list[dict]:
    return await snapshots.list_snapshots(cl.store_engine())


@router.post("/snapshots")
async def create_snapshot(payload: SnapshotCreate) -> dict:
    engine = cl.store_engine()
    if await snapshots.count_snapshots(engine) >= snapshots.MAX_SNAPSHOTS:
        raise HTTPException(
            status_code=400,
            detail=f"Snapshot-Limit erreicht (max {snapshots.MAX_SNAPSHOTS}) — "
            "alte Snapshots löschen.",
        )
    snap_id = f"snap-{uuid.uuid4().hex[:12]}"
    blob = snapshots.build_config_zip(cl.current_config())
    await snapshots.save_snapshot(engine, snap_id, payload.label.strip(), blob)
    return {"id": snap_id, "label": payload.label.strip()}


@router.delete("/snapshots/{snap_id}")
async def delete_snapshot(snap_id: str) -> dict:
    if not await snapshots.delete_snapshot(cl.store_engine(), snap_id):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"status": "deleted", "id": snap_id}


@router.get("/snapshots/{snap_id}/download")
async def download_snapshot(snap_id: str) -> StreamingResponse:
    snap = await snapshots.get_snapshot(cl.store_engine(), snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return _zip_response(snap["blob"], f"{snap_id}.zip")


@router.post("/snapshots/{snap_id}/restore")
async def restore_snapshot(snap_id: str) -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snap_id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {"status": "restored", "areas": await _apply_config(snap["blob"])}


# ── factory (the row with id 'factory') ────────────────────────────────────
@router.get("/factory")
async def factory_status() -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        return {"exists": False}
    return {"exists": True, "created_at": snap["created_at"].isoformat(),
            "label": snap["label"]}


@router.get("/factory/download")
async def download_factory() -> StreamingResponse:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        raise HTTPException(status_code=404, detail="Kein Factory-Stand gesetzt")
    return _zip_response(snap["blob"], "factory.zip")


@router.post("/factory/save")
async def save_factory() -> dict:
    blob = snapshots.build_config_zip(cl.current_config())
    await snapshots.save_snapshot(cl.store_engine(), snapshots.FACTORY_ID, "factory", blob)
    return {"status": "saved", "id": snapshots.FACTORY_ID}


@router.post("/factory/restore")
async def restore_factory() -> dict:
    snap = await snapshots.get_snapshot(cl.store_engine(), snapshots.FACTORY_ID)
    if snap is None:
        raise HTTPException(status_code=404, detail="Kein Factory-Stand gesetzt")
    return {"status": "restored", "areas": await _apply_config(snap["blob"])}


@router.post("/factory/upload")
async def upload_factory(file: UploadFile) -> dict:
    blob = await _read_upload_capped(file)
    # validate it parses (caps) before persisting as the factory baseline
    try:
        snapshots.parse_config_zip(blob)
    except snapshots.SnapshotTooLarge as e:
        raise HTTPException(status_code=413, detail=str(e)) from None
    await snapshots.save_snapshot(cl.store_engine(), snapshots.FACTORY_ID, "factory", blob)
    return {"status": "saved", "id": snapshots.FACTORY_ID}


# ── full backup / restore (live config ZIP) ────────────────────────────────
@router.get("/backup")
async def download_backup() -> StreamingResponse:
    blob = snapshots.build_config_zip(cl.current_config())
    return _zip_response(blob, "boerdi-config-backup.zip")


@router.post("/restore")
async def restore_backup(file: UploadFile) -> dict:
    blob = await _read_upload_capped(file)
    return {"status": "restored", "areas": await _apply_config(blob)}
