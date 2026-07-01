"""
WaiverPack assembly (pipeline Stage 4 — Assemble).

Bridges Retrieve (Stage 3) and Respond (Stage 5): it takes what the knowledge
base says is required for a lender/waiver combination (``waiver_pack`` and
``documents_expected``) and reconciles it against the documents actually
retrieved from the library, producing a completeness checklist.

Pure and dependency-free (no LLM / DB / network), so it is fully unit testable
and can be called both from the classification flow and from an API endpoint
that recomputes the pack from a stored record.
"""
from __future__ import annotations

import os
import re

from app.models.schemas import WaiverPack, WaiverPackComponent

# Split requirement text into items on these separators. Note: '/' is NOT a
# separator so tokens like "ACORD 25/28" stay intact.
_ITEM_SPLIT = re.compile(r"[;\n\r•·|,]+")

# Low-signal words ignored when matching a required item to a filename.
_GENERIC_TOKENS = {
    "the", "and", "for", "with", "copy", "page", "form", "of", "a", "an",
    "required", "current", "updated", "signed", "full", "all",
}

_UNKNOWN_VALUES = {"", "unknown", "parse_error", "none", "n/a"}


def _is_unknown(value: str | None) -> bool:
    return _normalize(value or "") in _UNKNOWN_VALUES


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _item_tokens(name: str) -> list[str]:
    return [t for t in _normalize(name).split() if len(t) >= 3 and t not in _GENERIC_TOKENS]


def _parse_items(text: str | None) -> list[str]:
    """Split a KB requirement string into individual, de-duplicated item names."""
    if _is_unknown(text):
        return []
    items = []
    for raw in _ITEM_SPLIT.split(text):
        name = raw.strip(" .-–—\t")
        if len(name) >= 2:
            items.append(name)
    return items


def _matches(item_name: str, filename_norm: str) -> bool:
    """True if a required item's significant tokens appear in a filename."""
    tokens = _item_tokens(item_name)
    if not tokens:
        return False
    # Require every significant token to appear when there are few of them
    # (e.g. "ACORD 25" → both "acord" and "25"); otherwise at least half,
    # so a multi-word item isn't matched by a single incidental word.
    hits = sum(1 for t in tokens if t in filename_norm)
    if len(tokens) <= 2:
        return hits == len(tokens)
    return hits >= (len(tokens) + 1) // 2


def assemble_waiver_pack(
    lender: str,
    waiver_type: str,
    waiver_pack: str | None,
    documents_expected: str | None,
    attachments: list[str] | None = None,
    evidence_ops: str | None = None,
    evidence_insurance: str | None = None,
) -> WaiverPack:
    """Assemble a WaiverPack, matching required items against retrieved documents."""
    attachments = attachments or []
    basenames = [os.path.basename(a) for a in attachments]
    norm_names = [_normalize(b) for b in basenames]

    # Build the ordered, de-duplicated list of required items (waiver_pack first).
    seen: set[str] = set()
    required: list[tuple[str, str]] = []  # (name, source)
    for source, text in (("waiver_pack", waiver_pack), ("documents_expected", documents_expected)):
        for name in _parse_items(text):
            key = _normalize(name)
            if key and key not in seen:
                seen.add(key)
                required.append((name, source))

    used_indices: set[int] = set()
    components: list[WaiverPackComponent] = []
    for name, source in required:
        matched_doc = None
        for i, fn_norm in enumerate(norm_names):
            if _matches(name, fn_norm):
                matched_doc = basenames[i]
                used_indices.add(i)
                break
        components.append(WaiverPackComponent(
            name=name,
            satisfied=matched_doc is not None,
            matched_document=matched_doc,
            source=source,
        ))

    total_required = len(components)
    total_satisfied = sum(1 for c in components if c.satisfied)
    missing = [c.name for c in components if not c.satisfied]
    unmatched = [basenames[i] for i in range(len(basenames)) if i not in used_indices]

    if total_required == 0:
        readiness = "empty"
        summary = (
            "No document requirements are defined in the knowledge base for "
            f"{lender} / {waiver_type}."
            + (f" {len(basenames)} document(s) retrieved." if basenames else "")
        )
    elif total_satisfied == total_required:
        readiness = "complete"
        summary = f"All {total_required} required component(s) satisfied. Ready to assemble."
    else:
        readiness = "partial"
        summary = (
            f"{total_satisfied} of {total_required} required component(s) satisfied. "
            f"Missing: {', '.join(missing)}."
        )

    return WaiverPack(
        lender=lender,
        waiver_type=waiver_type,
        readiness=readiness,
        total_required=total_required,
        total_satisfied=total_satisfied,
        components=components,
        missing=missing,
        unmatched_attachments=unmatched,
        evidence_ops=None if _is_unknown(evidence_ops) else evidence_ops,
        evidence_insurance=None if _is_unknown(evidence_insurance) else evidence_insurance,
        summary=summary,
    )
