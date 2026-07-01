"""
Unit tests for the document retrieval module (pipeline Stage 3).

Uses pytest's tmp_path fixture to build a fake document library on disk, so no
external documents, DB, or network are required.
"""
from app.services.retrieval.document_finder import find_documents


def _build_library(root):
    """Create a small document tree and return the root path (str)."""
    (root / "JLL").mkdir()
    (root / "JLL" / "AB_Sublimit_Endorsement.pdf").write_text("x")
    (root / "JLL" / "SAM_Coverage_Form.pdf").write_text("x")
    (root / "JLL" / "notes.txt").write_text("x")            # non-PDF, ignored
    (root / "Capital_One").mkdir()
    (root / "Capital_One" / "Full_Policy_Package.pdf").write_text("x")
    (root / "MT_Bank").mkdir()
    (root / "MT_Bank" / "Compliance_Notice.pdf").write_text("x")
    return str(root)


def test_finds_documents_under_lender_folder(tmp_path):
    base = _build_library(tmp_path)
    results = find_documents("JLL", "UNKNOWN", base)
    assert len(results) == 2
    assert all(r.endswith(".pdf") for r in results)
    assert all("JLL" in r for r in results)


def test_ignores_non_pdf_files(tmp_path):
    base = _build_library(tmp_path)
    results = find_documents("JLL", "UNKNOWN", base)
    assert not any(r.endswith(".txt") for r in results)


def test_waiver_type_ranks_matching_document_first(tmp_path):
    base = _build_library(tmp_path)
    # "Sublimit" appears in the A&B filename → should outrank the SAM form.
    results = find_documents("JLL", "A&B Sublimit Deficiency", base)
    assert results[0].endswith("AB_Sublimit_Endorsement.pdf")


def test_punctuation_insensitive_lender_match(tmp_path):
    base = _build_library(tmp_path)
    # "M&T Bank" must match the "MT_Bank" folder despite punctuation/spacing.
    results = find_documents("M&T Bank", "Compliance", base)
    assert len(results) == 1
    assert results[0].endswith("Compliance_Notice.pdf")


def test_multiword_lender_match(tmp_path):
    base = _build_library(tmp_path)
    results = find_documents("Capital One", "Full Policy Package", base)
    assert len(results) == 1
    assert results[0].endswith("Full_Policy_Package.pdf")


def test_unknown_lender_returns_empty(tmp_path):
    base = _build_library(tmp_path)
    assert find_documents("UNKNOWN", "A&B Sublimit", base) == []
    assert find_documents("", "A&B Sublimit", base) == []


def test_missing_base_path_returns_empty(tmp_path):
    assert find_documents("JLL", "A&B", str(tmp_path / "does_not_exist")) == []
    assert find_documents("JLL", "A&B", None) == []


def test_no_match_returns_empty(tmp_path):
    base = _build_library(tmp_path)
    assert find_documents("Berkadia", "Invoice", base) == []


def test_max_results_is_respected(tmp_path):
    lender_dir = tmp_path / "JLL"
    lender_dir.mkdir()
    for i in range(10):
        (lender_dir / f"doc_{i}.pdf").write_text("x")
    results = find_documents("JLL", "UNKNOWN", str(tmp_path), max_results=3)
    assert len(results) == 3
