"""
Unit tests for the draft response generator (pipeline Stage 5).

Deterministic — no LLM, DB, or network involved.
"""
from app.services.drafting.draft_generator import build_draft_response
from app.models.schemas import ClassificationResult


def _result(**kwargs) -> ClassificationResult:
    base = dict(
        lender="JLL",
        waiver_type="Assault & Battery",
        trigger_description="A&B sublimit below the required $1M",
        confidence_score=0.9,
        confidence_level="high",
    )
    base.update(kwargs)
    return ClassificationResult(**base)


def test_greeting_uses_lender_name():
    draft = build_draft_response(_result(), [])
    assert draft.startswith("Dear JLL Team,")


def test_unknown_lender_uses_generic_greeting():
    draft = build_draft_response(_result(lender="UNKNOWN"), [])
    assert draft.startswith("Dear Team,")


def test_trigger_is_referenced():
    draft = build_draft_response(_result(), [])
    assert "A&B sublimit below the required $1M" in draft


def test_attachments_are_listed_by_basename():
    draft = build_draft_response(
        _result(),
        ["/docs/JLL/AB_Sublimit_Endorsement.pdf", "/docs/JLL/COI.pdf"],
    )
    assert "Please find the following documents attached:" in draft
    assert "• AB_Sublimit_Endorsement.pdf" in draft
    assert "• COI.pdf" in draft
    # basename only — no directory leakage
    assert "/docs/JLL/" not in draft


def test_documents_expected_shown_when_no_attachments():
    draft = build_draft_response(
        _result(documents_expected="ACORD 25, endorsement page, SOV"),
        [],
    )
    assert "We are compiling the following documentation" in draft
    assert "ACORD 25, endorsement page, SOV" in draft


def test_attachments_take_precedence_over_expected():
    draft = build_draft_response(
        _result(documents_expected="ACORD 25"),
        ["/docs/JLL/endorsement.pdf"],
    )
    assert "endorsement.pdf" in draft
    assert "We are compiling" not in draft


def test_secondary_issues_are_mentioned():
    draft = build_draft_response(
        _result(secondary_issues=["SAM coverage", "EB limit"]),
        [],
    )
    assert "SAM coverage, EB limit" in draft


def test_escalated_email_produces_banner_and_conservative_body():
    draft = build_draft_response(
        _result(escalate_for_review=True, communication_category="COVENANT_BREACH"),
        ["/docs/JLL/should_not_be_listed.pdf"],
    )
    assert "REQUIRES HUMAN REVIEW BEFORE SENDING" in draft
    assert "currently under review" in draft
    # Conservative: never promises/attaches documents on an escalated matter.
    assert "Please find the following documents attached" not in draft
    assert "should_not_be_listed.pdf" not in draft


def test_signature_present():
    draft = build_draft_response(_result(), [])
    assert "AcentoPartners Insurance Compliance Team" in draft
