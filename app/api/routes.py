"""
API routes for the AcentoPartners Email Classifier.
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pathlib import Path
import json

from app.models.database import get_session, EmailClassification
from app.models.schemas import (
    ClassificationResponse, BatchClassifyRequest, BatchClassifyResponse,
    OutlookTestRequest, ClassificationStats, CorrectionRequest,
    CorrectionResponse, ReviewQueueResponse,
)
from app.services.email_parser.parser import parse_eml_bytes
from app.services.classifier.llm_classifier import classifier
from app.services.outlook.connector import outlook
from app.services import orchestrator
from app.core.knowledge_base import find_matching_entry, get_lender_names, get_waiver_types

router = APIRouter()


# ----------------------------------------------------------------
# Health & Status
# ----------------------------------------------------------------

@router.get("/health")
async def health_check():
    """Check system health: Ollama connection and model availability."""
    ollama_ok = await classifier.check_model_available()
    outlook_status = await outlook.test_connection()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama": {
            "connected": ollama_ok,
            "model": classifier.model,
            "base_url": classifier.client._client._base_url if hasattr(classifier.client, '_client') else "unknown",
        },
        "outlook": outlook_status,
    }


# ----------------------------------------------------------------
# Single Email Classification
# ----------------------------------------------------------------

@router.post("/classify/upload", response_model=ClassificationResponse)
async def classify_uploaded_email(
    file: UploadFile = File(..., description="Upload a .eml file"),
    session: AsyncSession = Depends(get_session),
):
    """Upload and classify a single .eml file."""
    if not file.filename.endswith(".eml"):
        raise HTTPException(400, "Only .eml files are supported")

    raw_bytes = await file.read()
    email_data = parse_eml_bytes(raw_bytes, filename=file.filename)
    result = await orchestrator.classify_single_email(email_data, session)
    return result


# ----------------------------------------------------------------
# Batch Classification (from folder)
# ----------------------------------------------------------------

@router.post("/classify/batch", response_model=BatchClassifyResponse)
async def classify_email_batch(
    request: BatchClassifyRequest,
    session: AsyncSession = Depends(get_session),
):
    """Classify all .eml files in a local folder."""
    folder = Path(request.folder_path)
    if not folder.exists():
        raise HTTPException(404, f"Folder not found: {request.folder_path}")
    if not folder.is_dir():
        raise HTTPException(400, f"Path is not a directory: {request.folder_path}")

    result = await orchestrator.classify_email_folder(folder, request.max_emails, session)
    return result


# ----------------------------------------------------------------
# Outlook Integration
# ----------------------------------------------------------------

@router.post("/classify/outlook", response_model=BatchClassifyResponse)
async def classify_from_outlook(
    request: OutlookTestRequest,
    session: AsyncSession = Depends(get_session),
):
    """Fetch recent emails from Outlook and classify them."""
    if not outlook.is_configured:
        raise HTTPException(
            400,
            "Outlook not configured. Set AZURE_TENANT_ID, AZURE_CLIENT_ID, "
            "AZURE_CLIENT_SECRET, and OUTLOOK_MAILBOX in .env file.",
        )

    result = await orchestrator.classify_from_outlook(
        folder=request.folder, count=request.num_emails, session=session
    )
    return result


@router.get("/outlook/test")
async def test_outlook_connection():
    """Test the Microsoft Graph API connection."""
    return await outlook.test_connection()


# ----------------------------------------------------------------
# Classification History & Stats
# ----------------------------------------------------------------

@router.get("/classifications", response_model=list[ClassificationResponse])
async def list_classifications(
    limit: int = 50,
    lender: str | None = None,
    confidence_level: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """List classification results with optional filters."""
    query = select(EmailClassification).order_by(
        EmailClassification.created_at.desc()
    ).limit(limit)

    if lender:
        query = query.where(EmailClassification.lender.ilike(f"%{lender}%"))
    if confidence_level:
        query = query.where(EmailClassification.confidence_level == confidence_level)

    result = await session.execute(query)
    records = result.scalars().all()

    return [
        ClassificationResponse(
            id=r.id,
            source=r.source,
            filename=r.filename,
            subject=r.subject,
            sender=r.sender,
            classification={
                "lender": r.lender,
                "waiver_type": r.waiver_type,
                "trigger_description": r.trigger_description or "",
                "confidence_score": r.confidence_score or 0.0,
                "confidence_level": r.confidence_level or "low",
                "secondary_issues": json.loads(r.secondary_issues) if r.secondary_issues else [],
                "required_evidence_ops": r.required_evidence_ops,
                "required_evidence_insurance": r.required_evidence_insurance,
                "documents_expected": r.documents_expected,
                "waiver_pack": r.waiver_pack,
                "actions_to_automate": r.actions_to_automate,
            },
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]


@router.get("/stats", response_model=ClassificationStats)
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Get classification statistics."""
    return await orchestrator.get_classification_stats(session)


# ----------------------------------------------------------------
# Human-in-the-Loop: Review Queue & Corrections
# ----------------------------------------------------------------

@router.get("/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    session: AsyncSession = Depends(get_session),
):
    """Get emails pending human review (medium/low confidence + classified status)."""
    query = (
        select(EmailClassification)
        .where(
            EmailClassification.status == "classified",
            EmailClassification.confidence_level.in_(["medium", "low"]),
        )
        .order_by(EmailClassification.confidence_score.asc())
    )
    result = await session.execute(query)
    records = result.scalars().all()

    items = [
        ClassificationResponse(
            id=r.id,
            source=r.source,
            filename=r.filename,
            subject=r.subject,
            sender=r.sender,
            classification={
                "lender": r.lender,
                "waiver_type": r.waiver_type,
                "trigger_description": r.trigger_description or "",
                "confidence_score": r.confidence_score or 0.0,
                "confidence_level": r.confidence_level or "low",
                "secondary_issues": json.loads(r.secondary_issues) if r.secondary_issues else [],
                "required_evidence_ops": r.required_evidence_ops,
                "required_evidence_insurance": r.required_evidence_insurance,
                "documents_expected": r.documents_expected,
                "waiver_pack": r.waiver_pack,
                "actions_to_automate": r.actions_to_automate,
                "reasoning": r.raw_llm_response,
            },
            status=r.status,
            created_at=r.created_at,
        )
        for r in records
    ]

    return ReviewQueueResponse(total_pending=len(items), items=items)


@router.get("/classifications/{classification_id}")
async def get_classification_detail(
    classification_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get full details for a single classification including body preview."""
    record = await session.get(EmailClassification, classification_id)
    if not record:
        raise HTTPException(404, "Classification not found")

    return {
        "id": record.id,
        "source": record.source,
        "filename": record.filename,
        "message_id": record.message_id,
        "subject": record.subject,
        "sender": record.sender,
        "sender_domain": record.sender_domain,
        "received_date": str(record.received_date) if record.received_date else None,
        "body_preview": record.body_preview,
        "lender": record.lender,
        "waiver_type": record.waiver_type,
        "trigger_description": record.trigger_description,
        "confidence_score": record.confidence_score,
        "confidence_level": record.confidence_level,
        "required_evidence_ops": record.required_evidence_ops,
        "required_evidence_insurance": record.required_evidence_insurance,
        "documents_expected": record.documents_expected,
        "waiver_pack": record.waiver_pack,
        "actions_to_automate": record.actions_to_automate,
        "raw_llm_response": record.raw_llm_response,
        "status": record.status,
        "reviewed_by": record.reviewed_by,
        "corrected_lender": record.corrected_lender,
        "corrected_waiver_type": record.corrected_waiver_type,
        "correction_notes": record.correction_notes,
        "created_at": str(record.created_at),
        "updated_at": str(record.updated_at),
    }


@router.post("/classifications/{classification_id}/correct", response_model=CorrectionResponse)
async def correct_classification(
    classification_id: str,
    correction: CorrectionRequest,
    session: AsyncSession = Depends(get_session),
):
    """Apply a human correction to a classification."""
    record = await session.get(EmailClassification, classification_id)
    if not record:
        raise HTTPException(404, "Classification not found")

    original_lender = record.lender
    original_waiver = record.waiver_type

    # Look up KB entry for the corrected values to enrich
    kb_entry = find_matching_entry(correction.corrected_lender, correction.corrected_waiver_type)

    # Apply correction
    record.corrected_lender = correction.corrected_lender
    record.corrected_waiver_type = correction.corrected_waiver_type
    record.reviewed_by = correction.reviewed_by
    record.correction_notes = correction.notes
    record.status = "corrected"

    # Update the main fields with corrected values
    record.lender = correction.corrected_lender
    record.waiver_type = correction.corrected_waiver_type

    # Re-enrich from KB if match found
    if kb_entry:
        record.required_evidence_ops = kb_entry["evidence_required_ops"]
        record.required_evidence_insurance = kb_entry["evidence_required_insurance"]
        record.documents_expected = kb_entry["documents_expected"]
        record.waiver_pack = kb_entry["waiver_pack"]
        record.actions_to_automate = kb_entry["actions_to_automate"]

    await session.commit()
    await session.refresh(record)

    return CorrectionResponse(
        id=record.id,
        original_lender=original_lender,
        original_waiver_type=original_waiver,
        corrected_lender=record.lender,
        corrected_waiver_type=record.waiver_type,
        status=record.status,
        reviewed_by=record.reviewed_by,
        required_evidence_ops=record.required_evidence_ops,
        required_evidence_insurance=record.required_evidence_insurance,
        documents_expected=record.documents_expected,
        waiver_pack=record.waiver_pack,
        actions_to_automate=record.actions_to_automate,
    )


@router.post("/classifications/{classification_id}/approve")
async def approve_classification(
    classification_id: str,
    reviewed_by: str = "operator",
    session: AsyncSession = Depends(get_session),
):
    """Approve a classification as correct (mark as reviewed)."""
    record = await session.get(EmailClassification, classification_id)
    if not record:
        raise HTTPException(404, "Classification not found")

    record.status = "reviewed"
    record.reviewed_by = reviewed_by
    await session.commit()

    return {"id": record.id, "status": "reviewed", "reviewed_by": reviewed_by}


@router.get("/lenders-and-waivers")
async def get_lenders_and_waivers():
    """Get valid lender names and waiver types for correction dropdowns."""
    from app.core.knowledge_base import LENDER_WAIVER_MATRIX
    return {
        "lenders": get_lender_names(),
        "waiver_types": get_waiver_types(),
        "combinations": [
            {"lender": e["lender"], "waiver_type": e["waiver_type"]}
            for e in LENDER_WAIVER_MATRIX
        ],
    }


# ----------------------------------------------------------------
# Knowledge Base Info
# ----------------------------------------------------------------

@router.get("/knowledge-base")
async def get_knowledge_base():
    """View the current lender/waiver classification matrix."""
    from app.core.knowledge_base import LENDER_WAIVER_MATRIX, get_lender_names, get_waiver_types
    return {
        "total_entries": len(LENDER_WAIVER_MATRIX),
        "lenders": get_lender_names(),
        "waiver_types": get_waiver_types(),
        "matrix": LENDER_WAIVER_MATRIX,
    }
