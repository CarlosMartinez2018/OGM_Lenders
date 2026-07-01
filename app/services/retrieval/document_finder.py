"""
Document retrieval (pipeline Stage 3 — Retrieve).

Finds candidate supporting documents (PDFs) for a classified email by matching
the identified lender and waiver type against the document library on disk.

Design goals vs. the previous inline implementation:
  • Uses the waiver_type as a ranking signal (it was ignored before).
  • Punctuation/spacing-insensitive lender matching ("M&T Bank" ↔ "MT_Bank",
    "Capital One" ↔ "CapitalOne") via a compacted, normalized key.
  • Requires a lender association so unrelated PDFs are never returned.
  • Ranks results (best matches first) and caps the number returned.
  • Single directory walk, guarded against a missing base path.

Returns a list of absolute file paths (str) — same shape the API/frontend
already consume via `suggested_attachments`.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Generic tokens that carry little signal for lender/waiver identification.
_GENERIC_TOKENS = {
    "the", "and", "via", "inc", "llc", "co", "corp", "group", "servicing",
    "insurance", "mortgage", "financial", "company", "capital", "real",
    "estate", "bank", "of", "for", "type", "limit", "coverage", "policy",
}

_UNKNOWN_VALUES = {"", "unknown", "parse_error", "none", "n/a"}


def _normalize(text: str) -> str:
    """Lowercase and replace every non-alphanumeric run with a single space."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _compact(text: str) -> str:
    """Normalized text with all separators removed: 'M&T Bank' -> 'mtbank'."""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _significant_tokens(text: str) -> list[str]:
    return [
        t for t in _normalize(text).split()
        if len(t) >= 3 and t not in _GENERIC_TOKENS
    ]


def _is_unknown(value: str | None) -> bool:
    return _normalize(value or "") in _UNKNOWN_VALUES


def _score_file(
    rel_norm: str,
    rel_compact: str,
    lender_compact: str,
    lender_tokens: list[str],
    waiver_tokens: list[str],
) -> int:
    """Return a match score for one file, or 0 if the lender doesn't match."""
    lender_hit = False
    score = 0

    # Strong lender signal: compacted key appears in the compacted path.
    if len(lender_compact) >= 3 and lender_compact in rel_compact:
        lender_hit = True
        score += 4

    # Weaker lender signal: an individual significant token appears.
    token_hits = sum(1 for t in lender_tokens if t in rel_norm)
    if token_hits:
        lender_hit = True
        score += token_hits

    if not lender_hit:
        return 0

    # Waiver type refines the ranking (never required, only additive).
    score += 2 * sum(1 for t in waiver_tokens if t in rel_norm)
    return score


def find_documents(
    lender: str | None,
    waiver_type: str | None,
    base_path: str | os.PathLike | None,
    max_results: int = 20,
) -> list[str]:
    """
    Find and rank candidate PDF documents for a lender/waiver combination.

    Returns absolute file paths, best matches first. Empty list if the lender
    is unknown, the base path is missing, or nothing matches.
    """
    if not base_path or _is_unknown(lender):
        return []

    root = Path(base_path)
    if not root.exists() or not root.is_dir():
        return []

    lender_compact = _compact(lender)
    lender_tokens = _significant_tokens(lender)
    waiver_tokens = [] if _is_unknown(waiver_type) else _significant_tokens(waiver_type)

    # Nothing to match on (e.g. lender was only generic words).
    if not lender_compact and not lender_tokens:
        return []

    scored: list[tuple[int, str, str]] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            abs_path = os.path.join(dirpath, name)
            rel = os.path.relpath(abs_path, root)
            rel_norm = _normalize(rel)
            rel_compact = _compact(rel)
            score = _score_file(
                rel_norm, rel_compact, lender_compact, lender_tokens, waiver_tokens
            )
            if score > 0:
                scored.append((score, name.lower(), abs_path))

    # Highest score first; tie-break by filename for stable, deterministic output.
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [path for _score, _name, path in scored[:max_results]]
