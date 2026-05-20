from sqlalchemy import Column, String, Float, DateTime, Text, Integer, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone
from app.core.config import settings
import uuid


class Base(DeclarativeBase):
    pass


class EmailClassification(Base):
    __tablename__ = "email_classifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Email metadata
    source = Column(String, nullable=False)  # "file", "outlook"
    filename = Column(String, nullable=True)
    message_id = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    sender_domain = Column(String, nullable=True)
    received_date = Column(DateTime, nullable=True)
    body_preview = Column(Text, nullable=True)  # first 500 chars

    # Classification results
    lender = Column(String, nullable=True)
    waiver_type = Column(String, nullable=True)
    trigger_description = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    confidence_level = Column(String, nullable=True)  # high, medium, low
    secondary_issues = Column(Text, nullable=True)  # JSON list of secondary issues
    required_evidence_ops = Column(Text, nullable=True)
    required_evidence_insurance = Column(Text, nullable=True)
    documents_expected = Column(Text, nullable=True)
    waiver_pack = Column(Text, nullable=True)
    actions_to_automate = Column(Text, nullable=True)
    raw_llm_response = Column(Text, nullable=True)

    # Status tracking
    status = Column(String, default="classified")  # classified, reviewed, corrected, processed
    reviewed_by = Column(String, nullable=True)
    corrected_lender = Column(String, nullable=True)
    corrected_waiver_type = Column(String, nullable=True)
    correction_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
