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

logger = logging.getLogger(__name__)


async def classify_single_email(
    email: EmailData, session: AsyncSession
) -> ClassificationResponse:
    """Classify a single email and save to database."""
    # Run LLM classification
    result = await classifier.classify(email)

    # Persist to database
    record = EmailClassification(
        source=email.source,
        filename=email.filename,
        message_id=email.message_id,
        subject=email.subject,
        sender=email.sender,
        sender_domain=email.sender_domain,
        received_date=email.received_date,
        body_preview=email.body_text[:500] if email.body_text else None,
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
