"""
Unit tests for WaiverPack assembly (pipeline Stage 4).

Deterministic — no LLM, DB, or network involved.
"""
from app.services.assembly.waiver_pack_builder import assemble_waiver_pack


def test_complete_when_all_items_matched():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="Assault & Battery",
        waiver_pack="ACORD 25; A&B Endorsement",
        documents_expected=None,
        attachments=["/docs/JLL/ACORD_25.pdf", "/docs/JLL/AB_Sublimit_Endorsement.pdf"],
    )
    assert pack.readiness == "complete"
    assert pack.total_required == 2
    assert pack.total_satisfied == 2
    assert pack.missing == []


def test_partial_lists_missing_items():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="Assault & Battery",
        waiver_pack="ACORD 25; A&B Endorsement; SOV",
        documents_expected=None,
        attachments=["/docs/JLL/ACORD_25.pdf"],
    )
    assert pack.readiness == "partial"
    assert pack.total_required == 3
    assert pack.total_satisfied == 1
    assert "A&B Endorsement" in pack.missing
    assert "SOV" in pack.missing


def test_matched_document_is_recorded_by_basename():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="A&B",
        waiver_pack="ACORD 25",
        documents_expected=None,
        attachments=["/docs/JLL/ACORD_25.pdf"],
    )
    comp = pack.components[0]
    assert comp.satisfied is True
    assert comp.matched_document == "ACORD_25.pdf"


def test_empty_when_no_requirements_defined():
    pack = assemble_waiver_pack(
        lender="Berkadia",
        waiver_type="UNKNOWN",
        waiver_pack=None,
        documents_expected="unknown",
        attachments=["/docs/Berkadia/random.pdf"],
    )
    assert pack.readiness == "empty"
    assert pack.total_required == 0
    assert pack.components == []


def test_requirements_merged_from_both_sources_without_duplicates():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="A&B",
        waiver_pack="ACORD 25",
        documents_expected="ACORD 25, SOV",   # ACORD 25 duplicated across sources
        attachments=[],
    )
    names = [c.name for c in pack.components]
    # "ACORD 25" appears once; SOV added from documents_expected.
    assert sum(1 for n in names if "acord" in n.lower()) == 1
    assert any("SOV" in n for n in names)
    assert pack.components[0].source == "waiver_pack"


def test_unmatched_attachments_are_reported():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="A&B",
        waiver_pack="ACORD 25",
        documents_expected=None,
        attachments=["/docs/JLL/ACORD_25.pdf", "/docs/JLL/unexpected_extra.pdf"],
    )
    assert "unexpected_extra.pdf" in pack.unmatched_attachments
    assert "ACORD_25.pdf" not in pack.unmatched_attachments


def test_single_incidental_word_does_not_over_match():
    # "Certificate of Insurance Page" -> significant tokens {certificate, insurance}
    # A file that only contains "insurance" should NOT satisfy a 2-token item
    # (both required when there are <= 2 significant tokens).
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="A&B",
        waiver_pack="Certificate of Insurance Page",
        documents_expected=None,
        attachments=["/docs/JLL/insurance_notice.pdf"],
    )
    assert pack.total_satisfied == 0
    assert pack.readiness == "partial"


def test_evidence_fields_passthrough():
    pack = assemble_waiver_pack(
        lender="JLL",
        waiver_type="A&B",
        waiver_pack="ACORD 25",
        documents_expected=None,
        attachments=[],
        evidence_ops="Property SOV from Ops",
        evidence_insurance="Bound policy from carrier",
    )
    assert pack.evidence_ops == "Property SOV from Ops"
    assert pack.evidence_insurance == "Bound policy from carrier"
