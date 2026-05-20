"""
Classification orchestration service.
Coordinates email parsing, LLM classification, and database persistence.
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.database import EmailClassification
from app.models.schemas import (
    EmailData, ClassificationResult, ClassificationResponse,
    BatchClassifyResponse, ClassificationStats,
)
from app.services.email_parser.parser import parse_eml_file, scan_email_folder
from app.services.classifier.llm_classifier import classifier
from app.services.outlook.connector import outlook
from app.core.config import settings
import os

logger = logging.getLogger(__name__)

def find_attachments(lender: str, waiver: str, base_path: str) -> list[str]:
    if not lender or not waiver or not base_path:
        return []
        
    path = Path(base_path)
    if not path.exists():
        return []
        
    found = []
    lender_lower = lender.lower()
    for root, dirs, files in os.walk(path):
        # Simplistic check: if lender name in folder path
        if lender_lower in root.lower() or lender_lower in os.path.basename(root).lower():
            for f in files:
                if f.lower().endswith(".pdf"):
                    found.append(os.path.join(root, f))
    return found

def generate_draft_response(lender: str, waiver: str, attachments: list[str]) -> str:
    msg = f"Hello {lender or 'Team'},\n\nPlease find attached the requested documents for the {waiver or 'insurance'} waiver.\n"
    if attachments:
        atts = "\n- ".join([os.path.basename(a) for a in attachments])
        msg += f"\nAttachments:\n- {atts}\n"
    msg += "\nBest regards,\nAcentoPartners Insurance Team"
    return msg


async def classify_single_email(
    email: EmailData, session: AsyncSession
) -> ClassificationResponse:
    """Classify a single email and save to database. Skips duplicates."""

    # Dedup: skip if already classified (same message_id or same filename+source)
    if email.message_id:
        existing = await session.scalar(
            select(EmailClassification.id)
            .where(EmailClassification.message_id == email.message_id)
            .limit(1)
        )
        if existing:
            logger.info(f"Skipping duplicate message_id: {email.message_id}")
            raise ValueError(f"Already classified (message_id: {email.message_id})")

    if email.source == "file" and email.filename:
        existing = await session.scalar(
            select(EmailClassification.id)
            .where(
                EmailClassification.source == "file",
                EmailClassification.filename == email.filename,
            )
            .limit(1)
        )
        if existing:
            logger.info(f"Skipping duplicate filename: {email.filename}")
            raise ValueError(f"Already classified (filename: {email.filename})")

    # Run LLM classification — session passed for KB loading from DB
    result = await classifier.classify(email, session)

    def strip_null(s: str | None) -> str | None:
        return s.replace("\x00", "") if s else None

    # Attachments & Response logic
    attachments = find_attachments(result.lender, result.waiver_type, settings.document_base_path)
    draft_msg = generate_draft_response(result.lender, result.waiver_type, attachments)

    # Persist to database
    record = EmailClassification(
        source=email.source,
        filename=email.filename,
        message_id=email.message_id,
        subject=strip_null(email.subject),
        sender=strip_null(email.sender),
        sender_domain=strip_null(email.sender_domain),
        received_date=email.received_date,
        body_preview=strip_null(email.body_text)[:500] if email.body_text else None,
        lender=result.lender,
        waiver_type=result.waiver_type,
        trigger_description=result.trigger_description,
        confidence_score=result.confidence_score,
        confidence_level=result.confidence_level,
        secondary_issues=json.dumps(result.secondary_issues) if result.secondary_issues else None,
        required_evidence_ops=result.required_evidence_ops,
        required_evidence_insurance=result.required_evidence_insurance,
        documents_expected=result.documents_expected,
        waiver_pack=result.waiver_pack,
        actions_to_automate=result.actions_to_automate,
        raw_llm_response=result.reasoning,
        communication_category=result.communication_category,
        escalate_for_review=result.escalate_for_review,
        suggested_attachments=attachments,
        draft_response=draft_msg,
        status="classified",
    )

    session.add(record)
    await session.commit()
    await session.refresh(record)

    return ClassificationResponse(
        id=record.id,
        source=record.source,
        filename=record.filename,
        subject=record.subject,
        sender=record.sender,
        classification=result,
        suggested_attachments=record.suggested_attachments,
        draft_response=record.draft_response,
        status=record.status,
        created_at=record.created_at,
    )


async def classify_email_folder(
    folder_path: Path, max_emails: int, session: AsyncSession
) -> BatchClassifyResponse:
    """Classify all .eml files in a folder."""
    eml_files = scan_email_folder(folder_path, max_files=max_emails)

    classifications = []
    errors = []
    success_count = 0

    for eml_file in eml_files:
        try:
            logger.info(f"Processing: {eml_file.name}")
            email_data = parse_eml_file(eml_file)
            result = await classify_single_email(email_data, session)
            classifications.append(result)
            success_count += 1
            logger.info(
                f"  → {result.classification.lender} | "
                f"{result.classification.waiver_type} | "
                f"confidence: {result.classification.confidence_score:.2f}"
            )
        except ValueError as e:
            logger.info(f"Skipped {eml_file.name}: {e}")
        except Exception as e:
            logger.error(f"Failed to process {eml_file.name}: {e}")
            errors.append({"file": eml_file.name, "error": str(e)})

    return BatchClassifyResponse(
        total_processed=len(eml_files),
        total_success=success_count,
        total_failed=len(errors),
        classifications=classifications,
        errors=errors,
    )


async def classify_from_outlook(
    folder: str, count: int, session: AsyncSession
) -> BatchClassifyResponse:
    """Fetch emails from Outlook and classify them."""
    emails = await outlook.fetch_recent_emails(folder=folder, count=count)

    classifications = []
    errors = []
    success_count = 0

    for email_data in emails:
        try:
            logger.info(f"Processing Outlook email: {email_data.subject}")
            result = await classify_single_email(email_data, session)
            classifications.append(result)
            success_count += 1
            logger.info(
                f"  → {result.classification.lender} | "
                f"{result.classification.waiver_type} | "
                f"confidence: {result.classification.confidence_score:.2f}"
            )
        except ValueError as e:
            logger.info(f"Skipped Outlook email '{email_data.subject}': {e}")
        except Exception as e:
            logger.error(f"Failed to classify Outlook email '{email_data.subject}': {e}")
            errors.append({"subject": email_data.subject, "error": str(e)})

    return BatchClassifyResponse(
        total_processed=len(emails),
        total_success=success_count,
        total_failed=len(errors),
        classifications=classifications,
        errors=errors,
    )


async def get_classification_stats(session: AsyncSession) -> ClassificationStats:
    """Get classification statistics from the database."""
    total = await session.scalar(select(func.count(EmailClassification.id)))

    lender_query = await session.execute(
        select(EmailClassification.lender, func.count(EmailClassification.id))
        .group_by(EmailClassification.lender)
    )
    by_lender = {row[0]: row[1] for row in lender_query.all()}

    waiver_query = await session.execute(
        select(EmailClassification.waiver_type, func.count(EmailClassification.id))
        .group_by(EmailClassification.waiver_type)
    )
    by_waiver_type = {row[0]: row[1] for row in waiver_query.all()}

    conf_query = await session.execute(
        select(EmailClassification.confidence_level, func.count(EmailClassification.id))
        .group_by(EmailClassification.confidence_level)
    )
    by_confidence = {row[0] or "unknown": row[1] for row in conf_query.all()}

    status_query = await session.execute(
        select(EmailClassification.status, func.count(EmailClassification.id))
        .group_by(EmailClassification.status)
    )
    by_status = {row[0] or "unknown": row[1] for row in status_query.all()}

    avg_conf = await session.scalar(
        select(func.avg(EmailClassification.confidence_score))
    )

    corrected_count = by_status.get("corrected", 0)
    reviewed_count = by_status.get("reviewed", 0)
    total_reviewed = corrected_count + reviewed_count
    correction_rate = (corrected_count / total_reviewed) if total_reviewed > 0 else 0.0

    return ClassificationStats(
        total_classified=total or 0,
        by_lender=by_lender,
        by_waiver_type=by_waiver_type,
        by_confidence_level=by_confidence,
        by_status=by_status,
        avg_confidence=round(avg_conf or 0.0, 3),
        correction_rate=round(correction_rate, 3),
    )
