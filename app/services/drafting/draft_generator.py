"""
Draft response generation (pipeline Stage 5 — Respond).

Builds a suggested email reply for a classified lender email. The draft is a
*suggestion* for a human operator to review — it is never sent automatically.

Compared to the previous fixed one-liner template, this generator uses the full
classification context:
  • the trigger the lender raised,
  • the documents the KB says are expected for this lender/waiver,
  • the documents actually retrieved from the library (attachments),
  • secondary issues detected in the email,
  • and, most importantly, escalation state: covenant-breach / prompt-injection
    emails produce a conservative acknowledgment with a clear DO-NOT-SEND banner
    instead of a "please find attached" reply.

Deterministic and dependency-free (no LLM / DB / network) so it is fully unit
testable. It is also a natural seam to later swap in an LLM-generated draft.
"""
from __future__ import annotations

import os
import re

from app.models.schemas import ClassificationResult

_UNKNOWN_VALUES = {"", "unknown", "parse_error", "none", "n/a"}

_ESCALATION_BANNER = (
    "[⚠ ESCALATED — REQUIRES HUMAN REVIEW BEFORE SENDING]\n"
    "This email was flagged (possible covenant breach, default notice, or "
    "prompt-injection attempt). The draft below is a conservative acknowledgment "
    "only; do not send without review by a compliance officer.\n"
    "----------------------------------------------------------------------\n\n"
)

_SIGNATURE = (
    "Best regards,\n"
    "AcentoPartners Insurance Compliance Team\n"
    "on behalf of Captive Advisory Partners"
)


def _is_unknown(value: str | None) -> bool:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip() in _UNKNOWN_VALUES


def _greeting(lender: str | None) -> str:
    return f"Dear {lender} Team," if not _is_unknown(lender) else "Dear Team,"


def build_draft_response(
    result: ClassificationResult,
    attachments: list[str] | None = None,
) -> str:
    """Return a context-aware draft reply for a classified email."""
    attachments = attachments or []
    lender = result.lender
    waiver = None if _is_unknown(result.waiver_type) else result.waiver_type

    lines: list[str] = [_greeting(lender), ""]

    # ── Escalated: conservative acknowledgment, no commitments ──────────────
    if result.escalate_for_review:
        lines.append(
            "Thank you for your notice. Please be advised that this matter has "
            "been received and is currently under review by our team. We will "
            "follow up with a detailed response as soon as our review is complete."
        )
        lines += ["", _SIGNATURE]
        return _ESCALATION_BANNER + "\n".join(lines)

    # ── Normal reply: acknowledge the trigger and provide documentation ─────
    trigger = (result.trigger_description or "").strip()
    if trigger and not _is_unknown(trigger):
        opener = f"Thank you for your notice regarding {trigger}."
    elif waiver:
        opener = f"Thank you for your notice regarding the {waiver} requirement."
    else:
        opener = "Thank you for your notice regarding the insurance compliance requirement."
    lines.append(
        opener + " We are writing to provide the requested insurance compliance "
        "documentation."
    )

    # Attachments retrieved from the document library.
    if attachments:
        lines += ["", "Please find the following documents attached:"]
        lines += [f"  • {os.path.basename(a)}" for a in attachments]
    elif result.documents_expected and not _is_unknown(result.documents_expected):
        # Nothing on hand yet — tell them what we are compiling.
        lines += [
            "",
            "We are compiling the following documentation to resolve this item:",
            f"  {result.documents_expected}",
        ]

    # Secondary issues detected in the same email.
    secondary = [s for s in (result.secondary_issues or []) if s and not _is_unknown(s)]
    if secondary:
        lines += [
            "",
            "We are additionally addressing the following related item(s): "
            + ", ".join(secondary) + ".",
        ]

    lines += [
        "",
        "Please let us know if any further information is required.",
        "",
        _SIGNATURE,
    ]
    return "\n".join(lines)
