"""
LLM-based email classifier using Ollama.
v2: Multi-label support, TO/CC domain awareness, improved prompt.
"""
import json
import re
import logging
from ollama import AsyncClient
from app.core.config import settings
from app.core.knowledge_base import (
    get_knowledge_base_text,
    get_lender_names,
    get_waiver_types,
    find_matching_entry,
    identify_lender_from_domains,
)
from app.models.schemas import EmailData, ClassificationResult

logger = logging.getLogger(__name__)

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


class EmailClassifier:
    def __init__(self):
        self.client = AsyncClient(host=settings.ollama_base_url)
        self.model = settings.ollama_model
        self.knowledge_base = get_knowledge_base_text()
        self.lender_names = get_lender_names()
        self.waiver_types = get_waiver_types()

    async def check_model_available(self) -> bool:
        """Check if the Ollama model is available."""
        try:
            models = await self.client.list()
            available = [m.model for m in models.models]
            if not any(self.model in m for m in available):
                logger.warning(
                    f"Model {self.model} not found. Available: {available}. "
                    f"Run: ollama pull {self.model}"
                )
                return False
            return True
        except Exception as e:
            logger.error(f"Cannot connect to Ollama at {settings.ollama_base_url}: {e}")
            return False

    async def classify(self, email: EmailData) -> ClassificationResult:
        """Classify a single email using the LLM with domain-aware hints."""
        # Pre-identify lender from domains
        domain_hint, hint_source = identify_lender_from_domains(
            from_domain=email.sender_domain,
            to_domains=email.to_domains,
            cc_domains=email.cc_domains,
        )

        logger.info(
            f"Domain hint for '{email.subject[:50]}': "
            f"{domain_hint or 'NONE'} ({hint_source})"
        )

        # Truncate body to fit context window
        body_text = email.body_text[:5000] if email.body_text else "(empty body)"

        # Format recipients for prompt
        to_str = ", ".join(email.to_recipients[:5]) if email.to_recipients else "unknown"
        cc_str = ", ".join(email.cc_recipients[:5]) if email.cc_recipients else "none"
        att_str = ", ".join(email.attachment_names[:8]) if email.attachment_names else "none"

        prompt = CLASSIFICATION_PROMPT.format(
            knowledge_base=self.knowledge_base,
            lender_list="\n".join(f"- {name}" for name in self.lender_names),
            waiver_type_list="\n".join(f"- {wt}" for wt in self.waiver_types),
            domain_lender_hint=domain_hint or "UNKNOWN - lender domain not recognized",
            domain_hint_source=hint_source,
            sender=email.sender or "unknown",
            to_recipients=to_str,
            cc_recipients=cc_str,
            subject=email.subject or "(no subject)",
            date=str(email.received_date or "unknown"),
            attachments=att_str,
            body=body_text,
        )

        try:
            response = await self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={
                    "temperature": 0.1,
                    "num_predict": 600,
                },
                format="json",
            )

            raw_response = response.message.content
            result = self._parse_response(raw_response, domain_hint)
            return result

        except Exception as e:
            logger.error(f"LLM classification failed for '{email.subject}': {e}")
            # Fallback: use domain hint if available
            fallback_lender = domain_hint or "UNKNOWN"
            return ClassificationResult(
                lender=fallback_lender,
                waiver_type="UNKNOWN",
                trigger_description=f"Classification error: {str(e)}",
                confidence_score=0.1 if domain_hint else 0.0,
                confidence_level="low",
                reasoning=f"LLM error. Domain hint: {domain_hint} ({hint_source})",
            )

    def _parse_response(
        self, raw_response: str, domain_hint: str | None
    ) -> ClassificationResult:
        """Parse the LLM JSON response into a ClassificationResult."""
        try:
            cleaned = raw_response.strip()
            cleaned = re.sub(r"^```json\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

            data = json.loads(cleaned)

            confidence = float(data.get("confidence_score", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            if confidence > 0.85:
                confidence_level = "high"
            elif confidence > 0.60:
                confidence_level = "medium"
            else:
                confidence_level = "low"

            lender = data.get("lender", "UNKNOWN")
            waiver_type = data.get("waiver_type", "UNKNOWN")
            secondary = data.get("secondary_issues", [])
            if isinstance(secondary, str):
                secondary = [secondary] if secondary else []

            # Enrich with knowledge base data
            kb_entry = find_matching_entry(lender, waiver_type)

            result = ClassificationResult(
                lender=lender,
                waiver_type=waiver_type,
                trigger_description=data.get("trigger_description", ""),
                confidence_score=confidence,
                confidence_level=confidence_level,
                secondary_issues=secondary,
                reasoning=data.get("reasoning", ""),
            )

            if kb_entry:
                result.required_evidence_ops = kb_entry["evidence_required_ops"]
                result.required_evidence_insurance = kb_entry["evidence_required_insurance"]
                result.documents_expected = kb_entry["documents_expected"]
                result.waiver_pack = kb_entry["waiver_pack"]
                result.actions_to_automate = kb_entry["actions_to_automate"]

            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f"Failed to parse LLM response: {e}\nRaw: {raw_response[:500]}")
            fallback_lender = domain_hint or "PARSE_ERROR"
            return ClassificationResult(
                lender=fallback_lender,
                waiver_type="PARSE_ERROR",
                trigger_description=f"Could not parse LLM response: {str(e)}",
                confidence_score=0.1 if domain_hint else 0.0,
                confidence_level="low",
                reasoning=f"Parse error. Domain hint used: {domain_hint}. Raw: {raw_response[:200]}",
            )


# Singleton instance
classifier = EmailClassifier()
