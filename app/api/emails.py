"""
Endpoints for parsed email management and ingestion.
Wraps the logic from ingest_today.py for use via the API.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, Query, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from pydantic import BaseModel
from typing import Optional
from pathlib import Path
from datetime import datetime, timezone

from app.models.database import get_session, ParsedEmail
from app.core.config import settings

router = APIRouter(prefix="/emails", tags=["emails"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ── Pydantic schemas ──────────────────────────────────────────────

class IngestFileRequest(BaseModel):
    folder: str = str(settings.sample_emails_path)
    all_dates: bool = False


class IngestOutlookRequest(BaseModel):
    month: Optional[int] = None
    year: Optional[int] = None
    all_dates: bool = False


class IngestResult(BaseModel):
    total: int
    inserted: int
    duplicates: int
    skipped_internal: int
    skipped_date: int
    errors: int
    details: list[dict] = []


# ── UI ────────────────────────────────────────────────────────────

@router.get("/form", response_class=HTMLResponse)
async def emails_form(request: Request):
    return templates.TemplateResponse("emails.html", {"request": request})


# ── List & detail ─────────────────────────────────────────────────

@router.get("")
async def list_emails(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    source: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(ParsedEmail).order_by(ParsedEmail.ingested_at.desc())

    if source:
        query = query.where(ParsedEmail.source == source)
    if status:
        query = query.where(ParsedEmail.status == status)
    if search:
        term = f"%{search}%"
        query = query.where(
            ParsedEmail.subject.ilike(term) |
            ParsedEmail.sender.ilike(term) |
            ParsedEmail.sender_domain.ilike(term)
        )

    total = await session.scalar(
        select(func.count()).select_from(query.subquery())
    )
    rows = await session.scalars(query.limit(limit).offset(offset))

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [_row_to_dict(r) for r in rows.all()],
    }


@router.get("/stats")
async def email_stats(session: AsyncSession = Depends(get_session)):
    total = await session.scalar(select(func.count(ParsedEmail.id))) or 0

    by_source = await session.execute(
        select(ParsedEmail.source, func.count()).group_by(ParsedEmail.source)
    )
    by_status = await session.execute(
        select(ParsedEmail.status, func.count()).group_by(ParsedEmail.status)
    )
    return {
        "total": total,
        "by_source": {r[0]: r[1] for r in by_source.all()},
        "by_status": {(r[0] or "unknown"): r[1] for r in by_status.all()},
    }


@router.get("/{email_id}")
async def get_email(email_id: str, session: AsyncSession = Depends(get_session)):
    record = await session.get(ParsedEmail, email_id)
    if not record:
        raise HTTPException(404, "Email not found")
    return _row_to_dict(record, full=True)


@router.delete("/{email_id}", status_code=204)
async def delete_email(email_id: str, session: AsyncSession = Depends(get_session)):
    record = await session.get(ParsedEmail, email_id)
    if not record:
        raise HTTPException(404, "Email not found")
    await session.delete(record)
    await session.commit()


# ── Recompute body_clean ─────────────────────────────────────────

@router.post("/recompute-clean")
async def recompute_body_clean(session: AsyncSession = Depends(get_session)):
    """Recompute body_clean for all emails that have an HTML body."""
    from app.services.email_parser.parser import clean_html

    rows = (await session.scalars(
        select(ParsedEmail).where(ParsedEmail.body_html.isnot(None))
    )).all()

    updated = 0
    for r in rows:
        cleaned = clean_html(r.body_html)
        r.body_clean = cleaned[:10_000] if cleaned else None
        updated += 1

    await session.commit()
    return {"updated": updated}


# ── Upload .eml files ────────────────────────────────────────────

@router.post("/upload-eml", response_model=IngestResult)
async def upload_eml_files(
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
):
    """Save uploaded .eml files to sample_emails folder and ingest them."""
    from app.services.email_parser.parser import parse_eml_file
    from ingest_today import _find_existing, _store, _is_internal

    folder = Path(settings.sample_emails_path)
    folder.mkdir(exist_ok=True)

    rows = []
    for upload in files:
        fname = upload.filename or ""
        if not fname.lower().endswith(".eml"):
            rows.append({"file": fname, "status": "error", "error": "Not a .eml file",
                         "subject": None, "sender": None, "received_date": None})
            continue

        dest = folder / fname
        dest.write_bytes(await upload.read())

        row = {"file": fname, "status": None, "subject": None,
               "sender": None, "received_date": None, "error": None}
        try:
            email = parse_eml_file(dest)
            row["subject"] = (email.subject or "")[:60]
            row["sender"] = email.sender
            row["received_date"] = (
                email.received_date.strftime("%Y-%m-%d") if email.received_date else "unknown"
            )
            if _is_internal(email):
                row["status"] = "skipped_internal"
            elif await _find_existing(session, email):
                row["status"] = "duplicate"
            else:
                await _store(session, email)
                row["status"] = "inserted"
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)

        rows.append(row)

    await session.commit()
    return _summarise(rows)


# ── Ingest ────────────────────────────────────────────────────────

@router.post("/ingest/file", response_model=IngestResult)
async def ingest_from_files(
    payload: IngestFileRequest,
    session: AsyncSession = Depends(get_session),
):
    """Ingest .eml files from a local folder into parsed_emails."""
    from ingest_today import ingest_files

    folder = Path(payload.folder)
    if not folder.exists():
        raise HTTPException(404, f"Folder not found: {payload.folder}")

    rows = await ingest_files(session, folder, filter_today=not payload.all_dates)
    return _summarise(rows)


@router.post("/ingest/outlook", response_model=IngestResult)
async def ingest_from_outlook(
    payload: IngestOutlookRequest,
    session: AsyncSession = Depends(get_session),
):
    """Ingest emails from Outlook via Microsoft Graph API."""
    from app.services.outlook.connector import outlook
    from ingest_today import ingest_outlook

    if not outlook.is_configured:
        raise HTTPException(
            400,
            "Outlook not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
            "AZURE_CLIENT_SECRET and OUTLOOK_MAILBOX in .env",
        )

    rows = await ingest_outlook(
        session,
        filter_today=not payload.all_dates and not payload.month,
        month=payload.month,
        year=payload.year,
    )
    return _summarise(rows)


# ── Helpers ───────────────────────────────────────────────────────

def _row_to_dict(r: ParsedEmail, full: bool = False) -> dict:
    d = {
        "id": r.id,
        "source": r.source,
        "filename": r.filename,
        "subject": r.subject,
        "sender": r.sender,
        "sender_domain": r.sender_domain,
        "to_recipients": r.to_recipients or [],
        "to_domains": r.to_domains or [],
        "cc_recipients": r.cc_recipients or [],
        "cc_domains": r.cc_domains or [],
        "received_date": r.received_date.isoformat() if r.received_date else None,
        "has_attachments": r.has_attachments,
        "attachment_names": r.attachment_names or [],
        "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None,
        "status": r.status,
    }
    if full:
        d["body_text"] = r.body_text
        d["body_html"] = r.body_html
        d["body_clean"] = r.body_clean
        d["message_id"] = r.message_id
    return d


def _summarise(rows: list[dict]) -> IngestResult:
    return IngestResult(
        total=len(rows),
        inserted=sum(1 for r in rows if r["status"] == "inserted"),
        duplicates=sum(1 for r in rows if r["status"] == "duplicate"),
        skipped_internal=sum(1 for r in rows if r["status"] == "skipped_internal"),
        skipped_date=sum(1 for r in rows if r["status"] == "skipped_date"),
        errors=sum(1 for r in rows if r["status"] == "error"),
        details=rows,
    )
