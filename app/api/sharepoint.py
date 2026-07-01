"""
REST endpoints for SharePoint file inventory:
- POST /sharepoint/sync       — full walk of the configured site, upsert into Postgres.
- GET  /sharepoint/files      — paginated list with filter by name and drive.
- GET  /sharepoint/drives     — distinct libraries indexed + file counts.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import SharePointFile, get_session
from app.services.sharepoint.connector import sharepoint

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sharepoint", tags=["sharepoint"])


# ── Pydantic schemas ──────────────────────────────────────────────

class SharePointFileOut(BaseModel):
    id: str
    drive_id: str
    drive_name: str
    name: str
    path: str
    parent_path: Optional[str]
    is_folder: bool
    size: Optional[int]
    mime_type: Optional[str]
    file_extension: Optional[str]
    web_url: Optional[str]
    sp_created_at: Optional[datetime]
    sp_modified_at: Optional[datetime]
    last_synced_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SharePointSyncResult(BaseModel):
    drives: list[str]
    items_seen: int
    files_added: int
    files_updated: int
    took_seconds: float


class DriveSummary(BaseModel):
    drive_name: str
    items: int
    files: int
    folders: int


# ── Endpoints ─────────────────────────────────────────────────────

@router.post("/sync", response_model=SharePointSyncResult)
async def sync_sharepoint(session: AsyncSession = Depends(get_session)):
    """Walk every drive of the configured site and upsert metadata."""
    if not sharepoint.is_configured:
        raise HTTPException(
            status_code=400,
            detail="SharePoint not configured. Set AZURE_* and SHAREPOINT_* in .env",
        )

    start = time.perf_counter()
    items_seen = 0
    added = 0
    updated = 0
    drive_names: list[str] = []

    async with httpx.AsyncClient() as client:
        try:
            drives = await sharepoint.list_drives(client)
        except ConnectionError as e:
            raise HTTPException(status_code=502, detail=str(e))

        for d in drives:
            drive_id = d["id"]
            drive_name = d.get("name", "(unknown)")
            drive_names.append(drive_name)
            logger.info(f"SharePoint sync: walking drive {drive_name!r}")

            async for sp_item in sharepoint.walk_drive(client, drive_id, drive_name):
                items_seen += 1
                existed = await session.get(SharePointFile, sp_item.id)
                if existed is None:
                    session.add(SharePointFile(
                        id=sp_item.id,
                        drive_id=sp_item.drive_id,
                        drive_name=sp_item.drive_name,
                        name=sp_item.name,
                        path=sp_item.path,
                        parent_path=sp_item.parent_path,
                        is_folder=sp_item.is_folder,
                        size=sp_item.size,
                        mime_type=sp_item.mime_type,
                        file_extension=sp_item.file_extension,
                        web_url=sp_item.web_url,
                        sp_created_at=sp_item.sp_created_at,
                        sp_modified_at=sp_item.sp_modified_at,
                    ))
                    added += 1
                else:
                    existed.drive_name = sp_item.drive_name
                    existed.name = sp_item.name
                    existed.path = sp_item.path
                    existed.parent_path = sp_item.parent_path
                    existed.is_folder = sp_item.is_folder
                    existed.size = sp_item.size
                    existed.mime_type = sp_item.mime_type
                    existed.file_extension = sp_item.file_extension
                    existed.web_url = sp_item.web_url
                    existed.sp_created_at = sp_item.sp_created_at
                    existed.sp_modified_at = sp_item.sp_modified_at
                    updated += 1

                if (items_seen % 200) == 0:
                    await session.commit()

    await session.commit()
    return SharePointSyncResult(
        drives=drive_names,
        items_seen=items_seen,
        files_added=added,
        files_updated=updated,
        took_seconds=round(time.perf_counter() - start, 2),
    )


@router.get("/files", response_model=list[SharePointFileOut])
async def list_files(
    q: Optional[str] = Query(None, description="Filtra por nombre o ruta (ILIKE)."),
    drive: Optional[str] = Query(None, description="Filtra por drive_name exacto."),
    only_files: bool = Query(True, description="Si true, oculta carpetas."),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(SharePointFile)
    if only_files:
        stmt = stmt.where(SharePointFile.is_folder.is_(False))
    if drive:
        stmt = stmt.where(SharePointFile.drive_name == drive)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(SharePointFile.name.ilike(like), SharePointFile.path.ilike(like))
        )
    stmt = (stmt.order_by(SharePointFile.drive_name, SharePointFile.path)
                .offset(offset).limit(limit))

    rows = (await session.execute(stmt)).scalars().all()
    return [SharePointFileOut.model_validate(r) for r in rows]


@router.get("/drives", response_model=list[DriveSummary])
async def list_drives(session: AsyncSession = Depends(get_session)):
    stmt = (
        select(SharePointFile.drive_name)
        .group_by(SharePointFile.drive_name)
        .order_by(SharePointFile.drive_name)
    )
    names = [r[0] for r in (await session.execute(stmt)).all()]

    out: list[DriveSummary] = []
    for n in names:
        files = (await session.execute(
            select(func.count(SharePointFile.id))
            .where(SharePointFile.drive_name == n,
                   SharePointFile.is_folder.is_(False))
        )).scalar_one()
        folders = (await session.execute(
            select(func.count(SharePointFile.id))
            .where(SharePointFile.drive_name == n,
                   SharePointFile.is_folder.is_(True))
        )).scalar_one()
        out.append(DriveSummary(
            drive_name=n,
            items=files + folders,
            files=files,
            folders=folders,
        ))
    return out
