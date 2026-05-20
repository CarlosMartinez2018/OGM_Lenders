from sqlalchemy import Column, String, Float, DateTime, Text, Integer, JSON, Boolean, ForeignKey, UniqueConstraint, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
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
    communication_category = Column(String, nullable=True)   # LENDER_COMPLIANCE | WAIVER_REQUEST | etc.
    escalate_for_review = Column(Boolean, default=False)

    # Status tracking
    status = Column(String, default="classified")  # classified, reviewed, corrected, processed
    reviewed_by = Column(String, nullable=True)
    corrected_lender = Column(String, nullable=True)
    corrected_waiver_type = Column(String, nullable=True)
    correction_notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ParsedEmail(Base):
    """Raw parsed email stored before classification. Stage 1 of the pipeline."""
    __tablename__ = "parsed_emails"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source = Column(String, nullable=False)           # "file" | "outlook"
    filename = Column(String, nullable=True)
    message_id = Column(String, nullable=True, index=True)
    subject = Column(String, nullable=True)
    sender = Column(String, nullable=True)
    sender_domain = Column(String, nullable=True)
    to_recipients = Column(JSON, default=list)
    to_domains = Column(JSON, default=list)
    cc_recipients = Column(JSON, default=list)
    cc_domains = Column(JSON, default=list)
    received_date = Column(DateTime(timezone=True), nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    body_clean = Column(Text, nullable=True)
    has_attachments = Column(Boolean, default=False)
    attachment_names = Column(JSON, default=list)
    ingested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="pending")  # pending | classified | processed


class Lender(Base):
    __tablename__ = "lenders"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String(255), nullable=False, unique=True)
    first_name = Column(String(100), nullable=True)
    last_name  = Column(String(100), nullable=True)
    email      = Column(String(255), nullable=True)
    phone      = Column(String(50),  nullable=True)
    notes      = Column(Text,        nullable=True)
    is_active  = Column(Boolean,     nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    aliases  = relationship("LenderAlias",  back_populates="lender",
                            cascade="all, delete-orphan", lazy="selectin")
    domains  = relationship("LenderDomain", back_populates="lender",
                            cascade="all, delete-orphan", lazy="selectin")
    waivers  = relationship("Waiver",       back_populates="lender",
                            cascade="all, delete-orphan", lazy="selectin")


class LenderAlias(Base):
    __tablename__ = "lender_aliases"
    __table_args__ = (UniqueConstraint("lender_id", "alias"),)

    id        = Column(Integer, primary_key=True, autoincrement=True)
    lender_id = Column(Integer, ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False)
    alias     = Column(String(255), nullable=False)

    lender = relationship("Lender", back_populates="aliases")


class LenderDomain(Base):
    __tablename__ = "lender_domains"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    lender_id = Column(Integer, ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False)
    domain    = Column(String(255), nullable=False, unique=True)

    lender = relationship("Lender", back_populates="domains")


class Waiver(Base):
    __tablename__ = "waivers"
    __table_args__ = (UniqueConstraint("lender_id", "waiver_type"),)

    id                          = Column(Integer, primary_key=True, autoincrement=True)
    lender_id                   = Column(Integer, ForeignKey("lenders.id", ondelete="CASCADE"), nullable=False)
    waiver_type                 = Column(String(255), nullable=False)
    triggers                    = Column(Text, nullable=True)
    evidence_required_ops       = Column(Text, nullable=True)
    evidence_required_insurance = Column(Text, nullable=True)
    documents_expected          = Column(Text, nullable=True)
    actions_to_automate         = Column(Text, nullable=True)
    waiver_pack                 = Column(Text, nullable=True)
    is_active                   = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    lender = relationship("Lender", back_populates="waivers")


engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE parsed_emails ADD COLUMN IF NOT EXISTS body_clean TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE email_classifications ADD COLUMN IF NOT EXISTS communication_category VARCHAR"
        ))
        await conn.execute(text(
            "ALTER TABLE email_classifications ADD COLUMN IF NOT EXISTS escalate_for_review BOOLEAN DEFAULT FALSE"
        ))


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
