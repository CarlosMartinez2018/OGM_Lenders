"""
LLM-based email classifier using Ollama.
v3: KB loaded from PostgreSQL (lenders/waivers tables). Fallback to knowledge_base.py if DB empty.
"""
import json
import re
import logging
from ollama import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.models.schemas import EmailData, ClassificationResult

logger = logging.getLogger(__name__)

INTERNAL_DOMAINS = {"acentopartners.com", "captiveadvisorypartners.com"}

CLASSIFICATION_PROMPT = """You are an expert insurance compliance email classifier for AcentoPartners, a residential insurance company in the United States.

Your job is to analyze emails related to lender insurance compliance and classify them by Lender and Waiver/Issue Type.

=== CRITICAL CONTEXT ===
These emails are typically RESPONSES from the insurance agent (e.g., Terri Schell at Captive Advisory Partners) TO the lender/servicer. This means:
- The TO field often identifies the LENDER (not the FROM field)
- The CC field may include lender-insurance@acentopartners.com (the borrower's team)
- The FROM field is usually the insurance agent responding

=== DOMAIN HINT ===
Based on email addresses, the system has pre-identified a likely lender:
Lender hint: {domain_lender_hint}
Source: {domain_hint_source}
IMPORTANT: Use this hint as strong evidence, but verify against the email content. The hint may be wrong if the email was forwarded.

=== KNOWLEDGE BASE ===
{knowledge_base}

=== VALID LENDERS ===
{lender_list}

=== VALID WAIVER TYPES ===
{waiver_type_list}

=== CLASSIFICATION INSTRUCTIONS ===
1. LENDER: Identify which lender/servicer this email involves. Use the domain hint plus email content.
2. PRIMARY WAIVER TYPE: The most prominent compliance issue (use exact names from list above).
3. SECONDARY ISSUES: List any OTHER compliance issues mentioned in the email (can be empty).
4. TRIGGER: What specifically triggered this compliance request.
5. CONFIDENCE: 0.0-1.0 based on clarity of match to knowledge base.
   - 0.85-1.0: Clear lender + clear waiver type match
   - 0.60-0.84: Lender is clear but waiver type is ambiguous, or vice versa
   - Below 0.60: Neither is clear, or lender is not in the knowledge base

Respond ONLY with valid JSON:
{{
    "lender": "<lender name from the valid list>",
    "waiver_type": "<primary waiver type from the valid list>",
    "secondary_issues": ["<other issue 1>", "<other issue 2>"],
    "trigger_description": "<what triggered this>",
    "confidence_score": <0.0 to 1.0>,
    "reasoning": "<explain: how you identified the lender, why this waiver type>"
}}

=== EMAIL TO CLASSIFY ===
From: {sender}
To: {to_recipients}
CC: {cc_recipients}
Subject: {subject}
Date: {date}
Attachments: {attachments}

Body:
{body}
"""

# Keyword → partial waiver type string (matched against exact DB values via substring)
_WAIVER_KEYWORDS: list[tuple[list[str], str]] = [
    (["assault", "a&b", "a & b", "sublimit"],                          "Assault & Battery"),
    (["molestation", "sexual abuse", "sam coverage", "sam policy"],    "Sexual Abuse & Molestation"),
    (["equipment breakdown", "eb limit", "breakdown limit"],           "Equipment Breakdown"),
    (["full policy", "90 days", "policy package", "non-compliance",
      "noncompliance"],                                                 "Full Policy Package"),
    (["mortgagee", "isaoa", "atima", "wording deficiency",
      "additional insured", "ai wording"],                             "Additional Insured"),
    (["ol/bi", "ol / bi", "ordinance", "business interruption",
      " epi ", " opi "],                                               "OL / BI"),
    (["invoice", "terrorism component", "excess component"],           "Invoice components"),
    (["address correction", "excess line", "address mismatch",
      "excess lines"],                                                 "Address / Excess"),
    (["acord 25", "acord 28", "payment hold", "umbrella clarity"],    "ACORD-gate"),
    (["multi-issue", "first notice of non", "second notice of non",
      "multiple requirements", "multiple deficienc"],                  "Multi-issue"),
    (["general compliance", "compliance deficiency",
      "compliance notice"],                                            "General compliance"),
]


class EmailClassifier:
    def __init__(self):
        self.client = AsyncClient(host=settings.ollama_base_url)
        self.model  = settings.ollama_model

    # ── Model check ───────────────────────────────────────────────

    async def check_model_available(self) -> bool:
        if settings.use_mock_llm:
            logger.info("Using MOCK LLM. Skipping Ollama model check.")
            return True
        try:
            models    = await self.client.list()
            available = [m.model for m in models.models]
            if not any(self.model in m for m in available):
                logger.warning(f"Model {self.model} not found. Run: ollama pull {self.model}")
                return False
            return True
        except Exception as e:
            logger.error(f"Cannot connect to Ollama at {settings.ollama_base_url}: {e}")
            return False

    # ── KB loading ────────────────────────────────────────────────

    async def _load_kb(self, session: AsyncSession) -> dict:
        """Load KB from PostgreSQL. Falls back to knowledge_base.py if DB has no lenders."""
        from app.models.database import Lender

        lenders = (await session.scalars(
            select(Lender).where(Lender.is_active == True)
        )).all()

        if not lenders:
            return self._kb_fallback()

        lender_names, waiver_types, domain_map, kb_entries = [], [], {}, []
        kb_lines = ["=== LENDER/WAIVER CLASSIFICATION KNOWLEDGE BASE ===\n"]

        for lender in lenders:
            lender_names.append(lender.name)
            aliases = [a.alias for a in lender.aliases]
            for d in lender.domains:
                domain_map[d.domain] = lender.name

            for waiver in lender.waivers:
                if not waiver.is_active:
                    continue
                waiver_types.append(waiver.waiver_type)
                entry = {
                    "lender":                       lender.name,
                    "lender_aliases":               aliases,
                    "waiver_type":                  waiver.waiver_type,
                    "triggers":                     waiver.triggers,
                    "evidence_required_ops":        waiver.evidence_required_ops,
                    "evidence_required_insurance":  waiver.evidence_required_insurance,
                    "documents_expected":           waiver.documents_expected,
                    "waiver_pack":                  waiver.waiver_pack,
                    "actions_to_automate":          waiver.actions_to_automate,
                }
                kb_entries.append(entry)

                kb_lines += [
                    f"Lender: {lender.name}",
                    f"Also known as: {', '.join(aliases)}",
                    f"Waiver Type: {waiver.waiver_type}",
                    f"Triggers: {waiver.triggers or '—'}",
                    f"Evidence (Ops): {waiver.evidence_required_ops or '—'}",
                    f"Evidence (Insurance): {waiver.evidence_required_insurance or '—'}",
                    f"Documents: {waiver.documents_expected or '—'}",
                    "",
                ]

        logger.info(f"KB loaded from DB: {len(lender_names)} lenders, {len(waiver_types)} waivers")
        return {
            "lender_names": lender_names,
            "waiver_types": waiver_types,
            "domain_map":   domain_map,
            "kb_entries":   kb_entries,
            "kb_text":      "\n".join(kb_lines),
            "source":       "database",
        }

    def _kb_fallback(self) -> dict:
        from app.core.knowledge_base import (
            LENDER_WAIVER_MATRIX, DOMAIN_LENDER_MAP,
            get_knowledge_base_text, get_lender_names, get_waiver_types,
        )
        logger.warning("KB fallback: DB has no active lenders — using knowledge_base.py")
        return {
            "lender_names": get_lender_names(),
            "waiver_types": get_waiver_types(),
            "domain_map":   DOMAIN_LENDER_MAP,
            "kb_entries":   LENDER_WAIVER_MATRIX,
            "kb_text":      get_knowledge_base_text(),
            "source":       "fallback",
        }

    # ── Domain detection ──────────────────────────────────────────

    def _identify_lender(self, email: EmailData, domain_map: dict) -> tuple[str | None, str]:
        for d in email.to_domains:
            if d not in INTERNAL_DOMAINS and d in domain_map:
                return domain_map[d], f"TO domain: {d}"
        for d in email.cc_domains:
            if d not in INTERNAL_DOMAINS and d in domain_map:
                return domain_map[d], f"CC domain: {d}"
        from_d = email.sender_domain or ""
        if from_d and from_d not in INTERNAL_DOMAINS and from_d in domain_map:
            return domain_map[from_d], f"FROM domain: {from_d}"
        return None, "no domain match"

    # ── KB enrichment lookup ──────────────────────────────────────

    def _find_kb_entry(self, lender: str, waiver_type: str, kb_entries: list) -> dict | None:
        ll, wl = lender.lower(), waiver_type.lower()
        for e in kb_entries:
            aliases = [e["lender"].lower()] + [a.lower() for a in e.get("lender_aliases", [])]
            if any(ll in a for a in aliases) and wl in e["waiver_type"].lower():
                return e
        for e in kb_entries:
            aliases = [e["lender"].lower()] + [a.lower() for a in e.get("lender_aliases", [])]
            if any(ll in a for a in aliases):
                return e
        return None

    # ── Main classify ─────────────────────────────────────────────

    async def classify(self, email: EmailData, session: AsyncSession) -> ClassificationResult:
        kb = await self._load_kb(session)
        domain_hint, hint_source = self._identify_lender(email, kb["domain_map"])

        logger.info(
            f"Classify '{(email.subject or '')[:50]}' | "
            f"KB source: {kb['source']} | domain hint: {domain_hint or 'NONE'} ({hint_source})"
        )

        if settings.use_mock_llm:
            return self._mock_classification(email, domain_hint, kb)

        body_text = email.body_text[:5000] if email.body_text else "(empty body)"
        to_str  = ", ".join(email.to_recipients[:5])  if email.to_recipients  else "unknown"
        cc_str  = ", ".join(email.cc_recipients[:5])  if email.cc_recipients  else "none"
        att_str = ", ".join(email.attachment_names[:8]) if email.attachment_names else "none"

        prompt = CLASSIFICATION_PROMPT.format(
            knowledge_base     = kb["kb_text"],
            lender_list        = "\n".join(f"- {n}" for n in kb["lender_names"]),
            waiver_type_list   = "\n".join(f"- {w}" for w in kb["waiver_types"]),
            domain_lender_hint = domain_hint or "UNKNOWN - lender domain not recognized",
            domain_hint_source = hint_source,
            sender             = email.sender or "unknown",
            to_recipients      = to_str,
            cc_recipients      = cc_str,
            subject            = email.subject or "(no subject)",
            date               = str(email.received_date or "unknown"),
            attachments        = att_str,
            body               = body_text,
        )

        try:
            response = await self.client.chat(
                model    = self.model,
                messages = [{"role": "user", "content": prompt}],
                options  = {"temperature": 0.1, "num_predict": 600},
                format   = "json",
            )
            return self._parse_response(response.message.content, domain_hint, kb["kb_entries"])

        except Exception as e:
            logger.error(f"LLM classification failed for '{email.subject}': {e}")
            return ClassificationResult(
                lender             = domain_hint or "UNKNOWN",
                waiver_type        = "UNKNOWN",
                trigger_description= f"Classification error: {e}",
                confidence_score   = 0.1 if domain_hint else 0.0,
                confidence_level   = "low",
                reasoning          = f"LLM error. Domain hint: {domain_hint} ({hint_source})",
            )

    # ── Response parser ───────────────────────────────────────────

    def _parse_response(
        self, raw: str, domain_hint: str | None, kb_entries: list
    ) -> ClassificationResult:
        try:
            cleaned = re.sub(r"^```json\s*", "", raw.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            data = json.loads(cleaned)

            confidence = max(0.0, min(1.0, float(data.get("confidence_score", 0.5))))
            confidence_level = "high" if confidence > 0.85 else ("medium" if confidence > 0.60 else "low")

            lender      = data.get("lender", "UNKNOWN")
            waiver_type = data.get("waiver_type", "UNKNOWN")
            secondary   = data.get("secondary_issues", [])
            if isinstance(secondary, str):
                secondary = [secondary] if secondary else []

            result = ClassificationResult(
                lender              = lender,
                waiver_type         = waiver_type,
                trigger_description = data.get("trigger_description", ""),
                confidence_score    = confidence,
                confidence_level    = confidence_level,
                secondary_issues    = secondary,
                reasoning           = data.get("reasoning", ""),
            )

            kb_entry = self._find_kb_entry(lender, waiver_type, kb_entries)
            if kb_entry:
                result.required_evidence_ops        = kb_entry.get("evidence_required_ops")
                result.required_evidence_insurance  = kb_entry.get("evidence_required_insurance")
                result.documents_expected           = kb_entry.get("documents_expected")
                result.waiver_pack                  = kb_entry.get("waiver_pack")
                result.actions_to_automate          = kb_entry.get("actions_to_automate")

            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e} | Raw: {raw[:300]}")
            return ClassificationResult(
                lender              = domain_hint or "PARSE_ERROR",
                waiver_type         = "PARSE_ERROR",
                trigger_description = f"Could not parse LLM response: {e}",
                confidence_score    = 0.1 if domain_hint else 0.0,
                confidence_level    = "low",
                reasoning           = f"Parse error. Raw: {raw[:200]}",
            )

    # ── Mock classifier ───────────────────────────────────────────

    def _mock_classification(
        self, email: EmailData, domain_hint: str | None, kb: dict
    ) -> ClassificationResult:
        text = f"{(email.subject or '').lower()} {(email.body_text or '').lower()}"

        # --- Waiver type detection via keyword patterns ---
        waiver_type = "UNKNOWN"
        for keywords, partial_match in _WAIVER_KEYWORDS:
            if any(kw in text for kw in keywords):
                # Find exact waiver type in KB that contains this partial string
                for wt in kb["waiver_types"]:
                    if partial_match.lower() in wt.lower():
                        waiver_type = wt
                        break
                if waiver_type != "UNKNOWN":
                    break

        # --- Lender detection (domain hint first, then alias scan) ---
        lender = domain_hint or "UNKNOWN"
        if lender == "UNKNOWN":
            for entry in kb["kb_entries"]:
                candidates = [entry["lender"].lower()] + [
                    a.lower() for a in entry.get("lender_aliases", [])
                ]
                if any(c in text for c in candidates):
                    lender = entry["lender"]
                    break

        # --- Confidence: honest about mock limitations ---
        lender_ok = lender != "UNKNOWN"
        waiver_ok  = waiver_type != "UNKNOWN"
        if lender_ok and waiver_ok:
            confidence, level = 0.80, "medium"   # mock can't claim high confidence
        elif lender_ok or waiver_ok:
            confidence, level = 0.62, "medium"
        else:
            confidence, level = 0.35, "low"

        result = ClassificationResult(
            lender              = lender,
            waiver_type         = waiver_type,
            trigger_description = "[MOCK] Identified via keyword matching",
            confidence_score    = confidence,
            confidence_level    = level,
            reasoning           = (
                f"[MOCK] lender={'found' if lender_ok else 'not found'} | "
                f"waiver={'found' if waiver_ok else 'not found'} | "
                f"domain_hint={domain_hint} | KB source: {kb['source']}"
            ),
        )

        kb_entry = self._find_kb_entry(lender, waiver_type, kb["kb_entries"])
        if kb_entry:
            result.required_evidence_ops        = kb_entry.get("evidence_required_ops")
            result.required_evidence_insurance  = kb_entry.get("evidence_required_insurance")
            result.documents_expected           = kb_entry.get("documents_expected")
            result.waiver_pack                  = kb_entry.get("waiver_pack")
            result.actions_to_automate          = kb_entry.get("actions_to_automate")

        return result


# Singleton instance
classifier = EmailClassifier()
