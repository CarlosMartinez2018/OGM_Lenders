"""
Unit tests for the EmailClassifier that do NOT require Ollama or PostgreSQL.

They exercise the pure logic: domain-based lender detection, LLM response
parsing, keyword-based escalation, and KB-entry matching.
"""
import json

from app.services.classifier.llm_classifier import EmailClassifier
from app.models.schemas import EmailData


def _email(**kwargs) -> EmailData:
    base = dict(source="file", body_text="")
    base.update(kwargs)
    return EmailData(**base)


# ── Domain-based lender detection (TO > CC > FROM, ignore internal) ──────────

def test_identify_lender_prefers_to_over_from():
    clf = EmailClassifier()
    domain_map = {"jll.com": "JLL", "capitalone.com": "Capital One"}
    email = _email(
        sender_domain="capitalone.com",
        to_domains=["jll.com"],
    )
    lender, source = clf._identify_lender(email, domain_map)
    assert lender == "JLL"
    assert "TO" in source


def test_identify_lender_ignores_internal_domains():
    clf = EmailClassifier()
    domain_map = {"jll.com": "JLL"}
    email = _email(
        to_domains=["acentopartners.com"],   # internal, must be skipped
        cc_domains=["jll.com"],
    )
    lender, source = clf._identify_lender(email, domain_map)
    assert lender == "JLL"
    assert "CC" in source


def test_identify_lender_no_match():
    clf = EmailClassifier()
    email = _email(to_domains=["unknown.com"])
    lender, source = clf._identify_lender(email, {"jll.com": "JLL"})
    assert lender is None


# ── _parse_response: regression test for the email/body_text scope bug ──────

def test_parse_response_parses_valid_json():
    clf = EmailClassifier()
    raw = json.dumps({
        "lender": "JLL",
        "waiver_type": "Assault & Battery",
        "communication_category": "WAIVER_REQUEST",
        "secondary_issues": [],
        "trigger_description": "A&B sublimit deficiency",
        "confidence_score": 0.92,
        "escalate_for_review": False,
        "reasoning": "Clear match",
    })
    email = _email(subject="A&B Sublimit", body_text="Please increase the sublimit.")
    result = clf._parse_response(raw, "JLL", [], email, email.body_text)
    assert result.lender == "JLL"
    assert result.confidence_level == "high"
    assert result.escalate_for_review is False


def test_parse_response_forces_escalation_on_critical_keyword():
    """
    Regression: _parse_response previously referenced `email`/`body_text`
    which were not in scope, raising NameError on every real classification.
    This confirms the keyword-based escalation now works.
    """
    clf = EmailClassifier()
    raw = json.dumps({
        "lender": "Capital One",
        "waiver_type": "UNKNOWN",
        "confidence_score": 0.7,
        "escalate_for_review": False,   # LLM said no...
    })
    email = _email(subject="Notice of Default", body_text="This is a notice of default.")
    # ...but "default" is a critical keyword → escalation must be forced True
    result = clf._parse_response(raw, "Capital One", [], email, email.body_text)
    assert result.escalate_for_review is True


def test_parse_response_handles_malformed_json():
    clf = EmailClassifier()
    email = _email(body_text="whatever")
    result = clf._parse_response("not json at all", "JLL", [], email, email.body_text)
    assert result.waiver_type == "PARSE_ERROR"
    assert result.confidence_level == "low"


# ── KB entry matching by alias ──────────────────────────────────────────────

def test_find_kb_entry_matches_alias():
    clf = EmailClassifier()
    kb_entries = [{
        "lender": "KeyBank",
        "lender_aliases": ["Grandbridge", "Wells Fargo"],
        "waiver_type": "OL / BI",
        "evidence_required_ops": "SOV",
    }]
    entry = clf._find_kb_entry("Grandbridge", "OL / BI", kb_entries)
    assert entry is not None
    assert entry["lender"] == "KeyBank"
