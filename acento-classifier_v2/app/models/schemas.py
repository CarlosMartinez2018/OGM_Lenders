from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class EmailData(BaseModel):
    """Parsed email data ready for classification."""
    source: str  # "file" or "outlook"
    filename: Optional[str] = None
    message_id: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    sender_domain: Optional[str] = None
    to_recipients: list[str] = []
    to_domains: list[str] = []
    cc_recipients: list[str] = []
    cc_domains: list[str] = []
    received_date: Optional[datetime] = None
    body_text: str
    body_html: Optional[str] = None
    has_attachments: bool = False
    attachment_names: list[str] = []


class ClassificationResult(BaseModel):
    """LLM classification output."""
    lender: str = Field(description="Identified lender name")
    waiver_type: str = Field(description="Primary waiver type")
    trigger_description: str = Field(description="What triggered this waiver request")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Classification confidence 0-1")
    confidence_level: str = Field(description="high (>0.85), medium (0.60-0.85), low (<0.60)")
    secondary_issues: list[str] = Field(default=[], description="Additional waiver issues found in the email")
    required_evidence_ops: Optional[str] = Field(None, description="Evidence required from Operations")
    required_evidence_insurance: Optional[str] = Field(None, description="Evidence required for Insurance")
    documents_expected: Optional[str] = Field(None, description="Documents expected to resolve")
    waiver_pack: Optional[str] = Field(None, description="Components of the WaiverPack to assemble")
    actions_to_automate: Optional[str] = Field(None, description="Suggested automation actions")
    reasoning: Optional[str] = Field(None, description="LLM reasoning for this classification")


class ClassificationResponse(BaseModel):
    """API response for a classified email."""
    id: str
    source: str
    filename: Optional[str] = None
    subject: Optional[str] = None
    sender: Optional[str] = None
    classification: ClassificationResult
    status: str
    created_at: datetime


class BatchClassifyRequest(BaseModel):
    """Request to classify a batch of emails from a folder."""
    folder_path: str
    max_emails: int = Field(default=50, ge=1, le=500)


class BatchClassifyResponse(BaseModel):
    """Response for batch classification."""
    total_processed: int
    total_success: int
    total_failed: int
    classifications: list[ClassificationResponse]
    errors: list[dict] = []


class OutlookTestRequest(BaseModel):
    """Request to test classification with a real Outlook email."""
    num_emails: int = Field(default=5, ge=1, le=50, description="Number of recent emails to fetch")
    folder: str = Field(default="Inbox", description="Outlook folder to read from")


class ClassificationStats(BaseModel):
    """Statistics about classifications."""
    total_classified: int
    by_lender: dict[str, int]
    by_waiver_type: dict[str, int]
    by_confidence_level: dict[str, int]
    by_status: dict[str, int] = {}
    avg_confidence: float
    correction_rate: float = 0.0


class CorrectionRequest(BaseModel):
    """Request to correct a classification."""
    corrected_lender: str = Field(description="Corrected lender name")
    corrected_waiver_type: str = Field(description="Corrected waiver type")
    reviewed_by: str = Field(default="operator", description="Who reviewed this")
    notes: Optional[str] = Field(None, description="Optional correction notes")


class CorrectionResponse(BaseModel):
    """Response after applying a correction."""
    id: str
    original_lender: str
    original_waiver_type: str
    corrected_lender: str
    corrected_waiver_type: str
    status: str
    reviewed_by: str
    # Enriched fields from KB based on correction
    required_evidence_ops: Optional[str] = None
    required_evidence_insurance: Optional[str] = None
    documents_expected: Optional[str] = None
    waiver_pack: Optional[str] = None
    actions_to_automate: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    """Items pending human review."""
    total_pending: int
    items: list[ClassificationResponse]
