import json
import os
import re
import logging
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from ollama import AsyncClient

from app.models.schemas import EmailData, ClassificationResult

# Ollama settings – read from env vars (same defaults as app/core/config.py)
_OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database connection settings  (same as base_concimiento_lenders_weivers.py)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "0.tcp.ngrok.io",
    "port": 16661,
    "dbname": "acento_db",
    "user": "acento",
    "password": "acento_secure_pass",
    "connect_timeout": 10,
}


@contextmanager
def _db_cursor():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# DBKnowledgeBase – loads everything from Postgres and replicates the
# interface of app.core.knowledge_base (get_knowledge_base_text, etc.)
# ---------------------------------------------------------------------------
class DBKnowledgeBase:
    """
    Loads lender/waiver knowledge from PostgreSQL at init time and caches it
    in memory.  The public methods mirror the interface in knowledge_base.py
    so that EmailClassifier can call them without modification.
    """

    def __init__(self) -> None:
        self._entries: list[dict] = []     # rows: lender + waiver fields
        self._domain_map: dict[str, str] = {}  # domain -> lender name
        self._refresh()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        """Create schema + seed data if the tables do not exist yet."""
        try:
            import base_concimiento_lenders_weivers as seeder
        except ImportError as exc:
            raise RuntimeError(
                "Cannot auto-initialize: base_concimiento_lenders_weivers.py not found. "
                "Run it manually first."
            ) from exc

        logger.warning(
            "lender_kb schema not found – running auto-setup from "
            "base_concimiento_lenders_weivers.py …"
        )
        conn = psycopg2.connect(**DB_CONFIG)
        try:
            seeder.create_schema(conn)
            seeder.seed_data(conn)
            conn.commit()
        finally:
            conn.close()
        logger.info("Auto-setup complete.")

    def _refresh(self) -> None:
        """(Re)load all data from the database, auto-creating schema if needed."""
        try:
            self._load_from_db()
        except psycopg2.errors.UndefinedTable:
            self._ensure_schema()
            self._load_from_db()

    def _load_from_db(self) -> None:
        with _db_cursor() as cur:
            cur.execute(
                """
                SELECT
                    l.name                                                      AS lender,
                    ARRAY_AGG(DISTINCT la.alias)
                        FILTER (WHERE la.alias IS NOT NULL)                     AS lender_aliases,
                    w.waiver_type,
                    w.triggers,
                    w.evidence_required_ops,
                    w.evidence_required_insurance,
                    w.documents_expected,
                    w.actions_to_automate,
                    w.waiver_pack
                FROM public.lenders l
                JOIN public.waivers w
                    ON w.lender_id = l.id  AND w.is_active = TRUE
                LEFT JOIN public.lender_aliases la
                    ON la.lender_id = l.id
                WHERE l.is_active = TRUE
                GROUP BY
                    l.id, l.name,
                    w.id, w.waiver_type, w.triggers,
                    w.evidence_required_ops, w.evidence_required_insurance,
                    w.documents_expected, w.actions_to_automate, w.waiver_pack
                ORDER BY l.id, w.id
                """
            )
            raw = cur.fetchall()
            self._entries = []
            for row in raw:
                entry = dict(row)
                # Ensure aliases is always a list
                entry["lender_aliases"] = list(entry["lender_aliases"] or [])
                self._entries.append(entry)

            cur.execute(
                """
                SELECT ld.domain, l.name
                FROM public.lender_domains ld
                JOIN public.lenders l ON l.id = ld.lender_id
                WHERE l.is_active = TRUE
                """
            )
            self._domain_map = {r["domain"]: r["name"] for r in cur.fetchall()}

        logger.info(
            "DBKnowledgeBase loaded from Postgres: %d waiver entries, %d domains",
            len(self._entries),
            len(self._domain_map),
        )

    # ------------------------------------------------------------------
    # Public API  (mirrors knowledge_base.py)
    # ------------------------------------------------------------------
    def get_knowledge_base_text(self) -> str:
        lines = ["=== LENDER/WAIVER CLASSIFICATION KNOWLEDGE BASE ===\n"]
        for i, e in enumerate(self._entries, 1):
            aliases = ", ".join(e["lender_aliases"]) if e["lender_aliases"] else "N/A"
            lines += [
                f"--- Entry {i} ---",
                f"Lender: {e['lender']}",
                f"Also known as: {aliases}",
                f"Waiver Type: {e['waiver_type']}",
                f"Triggers: {e['triggers']}",
                f"Evidence Required (Ops): {e['evidence_required_ops']}",
                f"Evidence Required (Insurance): {e['evidence_required_insurance']}",
                f"Documents Expected: {e['documents_expected']}",
                f"WaiverPack: {e['waiver_pack']}",
                f"Actions to Automate: {e['actions_to_automate']}",
                "",
            ]
        return "\n".join(lines)

    def get_lender_names(self) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for e in self._entries:
            if e["lender"] not in seen:
                seen.add(e["lender"])
                names.append(e["lender"])
        return names

    def get_waiver_types(self) -> list[str]:
        return [e["waiver_type"] for e in self._entries]

    def find_matching_entry(self, lender: str, waiver_type: str) -> dict | None:
        lender_lc = lender.lower()
        waiver_lc = waiver_type.lower()

        # Exact lender + waiver match
        for e in self._entries:
            lender_match = (
                lender_lc in e["lender"].lower()
                or any(lender_lc in a.lower() for a in e["lender_aliases"])
            )
            if lender_match and waiver_lc in e["waiver_type"].lower():
                return e

        # Fallback: lender only
        for e in self._entries:
            lender_match = (
                lender_lc in e["lender"].lower()
                or any(lender_lc in a.lower() for a in e["lender_aliases"])
            )
            if lender_match:
                return e

        return None

    def identify_lender_from_domains(
        self,
        from_domain: str,
        to_domains: list[str],
        cc_domains: list[str],
    ) -> tuple[str | None, str]:
        internal = {"acentopartners.com", "captiveadvisorypartners.com"}

        for d in to_domains:
            if d not in internal and d in self._domain_map:
                return self._domain_map[d], f"TO domain: {d}"

        for d in cc_domains:
            if d not in internal and d in self._domain_map:
                return self._domain_map[d], f"CC domain: {d}"

        if from_domain and from_domain not in internal:
            if from_domain in self._domain_map:
                return self._domain_map[from_domain], f"FROM domain: {from_domain}"

        return None, "no domain match"


# ---------------------------------------------------------------------------
# Prompt template  (identical to llm_classifier.py)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Classifier  (identical logic to EmailClassifier, uses DBKnowledgeBase)
# ---------------------------------------------------------------------------
class EmailClassifierDB:
    """
    Drop-in replacement for EmailClassifier that sources its knowledge
    base from PostgreSQL instead of the static knowledge_base.py module.
    """

    def __init__(self) -> None:
        self.client = AsyncClient(host=_OLLAMA_BASE_URL)
        self.model = _OLLAMA_MODEL
        self._kb = DBKnowledgeBase()
        # Pre-render text and lists once (same pattern as the original)
        self.knowledge_base = self._kb.get_knowledge_base_text()
        self.lender_names = self._kb.get_lender_names()
        self.waiver_types = self._kb.get_waiver_types()

    async def check_model_available(self) -> bool:
        try:
            models = await self.client.list()
            available = [m.model for m in models.models]
            if not any(self.model in m for m in available):
                logger.warning(
                    "Model %s not found. Available: %s. Run: ollama pull %s",
                    self.model, available, self.model,
                )
                return False
            return True
        except Exception as e:
            logger.error("Cannot connect to Ollama at %s: %s", _OLLAMA_BASE_URL, e)
            return False

    async def classify(self, email: EmailData) -> ClassificationResult:
        domain_hint, hint_source = self._kb.identify_lender_from_domains(
            from_domain=email.sender_domain,
            to_domains=email.to_domains,
            cc_domains=email.cc_domains,
        )

        logger.info(
            "Domain hint for '%s': %s (%s)",
            email.subject[:50],
            domain_hint or "NONE",
            hint_source,
        )

        body_text = email.body_text[:5000] if email.body_text else "(empty body)"
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
                options={"temperature": 0.1, "num_predict": 600},
                format="json",
            )
            return self._parse_response(response.message.content, domain_hint)

        except Exception as e:
            logger.error("LLM classification failed for '%s': %s", email.subject, e)
            fallback_lender = domain_hint or "UNKNOWN"
            return ClassificationResult(
                lender=fallback_lender,
                waiver_type="UNKNOWN",
                trigger_description=f"Classification error: {e}",
                confidence_score=0.1 if domain_hint else 0.0,
                confidence_level="low",
                reasoning=f"LLM error. Domain hint: {domain_hint} ({hint_source})",
            )

    def _parse_response(
        self, raw_response: str, domain_hint: str | None
    ) -> ClassificationResult:
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

            kb_entry = self._kb.find_matching_entry(lender, waiver_type)

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
            logger.warning("Failed to parse LLM response: %s\nRaw: %s", e, raw_response[:500])
            fallback_lender = domain_hint or "PARSE_ERROR"
            return ClassificationResult(
                lender=fallback_lender,
                waiver_type="PARSE_ERROR",
                trigger_description=f"Could not parse LLM response: {e}",
                confidence_score=0.1 if domain_hint else 0.0,
                confidence_level="low",
                reasoning=f"Parse error. Domain hint used: {domain_hint}. Raw: {raw_response[:200]}",
            )


# Singleton instance
classifier = EmailClassifierDB()


# ---------------------------------------------------------------------------
# __main__  – run sample classifications and print results to console
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import textwrap
    from datetime import datetime

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    SAMPLE_EMAILS = [
        EmailData(
            source="test",
            subject="Non-Compliance Notice – Assault & Battery Sublimit | 4521 Riverside Apartments",
            sender="terri.schell@captiveadvisorypartners.com",
            sender_domain="captiveadvisorypartners.com",
            to_recipients=["compliance@jll.com"],
            to_domains=["jll.com"],
            cc_recipients=["lender-insurance@acentopartners.com"],
            cc_domains=["acentopartners.com"],
            received_date=datetime(2024, 11, 14, 10, 30),
            body_text=(
                "Dear JLL Insurance Servicing Team,\n\n"
                "Please find attached the documentation requested regarding the Assault & Battery "
                "sublimit deficiency for the above-referenced property.\n\n"
                "Our General Liability policy carries an A&B sublimit of $250,000 per occurrence. "
                "We are providing the following to support a waiver request:\n\n"
                "1. Security Fact Sheet – On-site cameras covering all entry points, parking "
                "garage, gym, and common areas. Gated access with key-fob entry. Security guard "
                "on site 6pm–6am seven days a week (contract with SecureGuard Inc., expires "
                "12/31/2025).\n"
                "2. Background check policy – all tenants and employees screened at move-in.\n"
                "3. Attached: ACORD 25, A&B endorsement page, declination letters from 3 markets, "
                "and 3-year loss runs (zero A&B claims).\n\n"
                "Please let us know if additional information is needed.\n\n"
                "Best regards,\nTerri Schell\nCaptive Advisory Partners"
            ),
            attachment_names=[
                "ACORD_25.pdf", "AB_Endorsement.pdf",
                "Declination_Letter_1.pdf", "Declination_Letter_2.pdf",
                "Loss_Runs_2021_2023.pdf", "Security_Fact_Sheet.pdf",
            ],
        ),
        EmailData(
            source="test",
            subject="FW: Insurance Deficiency – M&T Bank Loan #78812 – SAM / BI / OL Issues",
            sender="terri.schell@captiveadvisorypartners.com",
            sender_domain="captiveadvisorypartners.com",
            to_recipients=["insurance-compliance@mtb.com"],
            to_domains=["mtb.com"],
            cc_recipients=["lender-insurance@acentopartners.com"],
            cc_domains=["acentopartners.com"],
            received_date=datetime(2024, 11, 20, 9, 0),
            body_text=(
                "M&T Bank Insurance Compliance Team,\n\n"
                "This email responds to your Second Notice of Non-Compliance dated November 15, 2024 "
                "for Loan #78812 (Sunset Pines Apartments, 820 N. Oak St.).\n\n"
                "We are addressing each item:\n\n"
                "1. Sexual Abuse & Molestation (SAM): Standalone SAM policy attached – $2M limit, "
                "carrier: Markel Specialty. Endorsement pages included.\n\n"
                "2. Business Interruption (BI) waiting period: Policy endorsement confirms 72-hour "
                "waiting period – within M&T's 72hr maximum.\n\n"
                "3. Ordinance or Law (OL) A/B/C: Policy carries 10% each for OL A, B, and C "
                "of insured value. Endorsement pages attached.\n\n"
                "4. Aggregate deductible detail: No aggregate deductible applies – per-occurrence "
                "deductible only ($5,000).\n\n"
                "5. ACORD 25, 28, and 101 attached. SOV with all 12 locations included.\n\n"
                "Please confirm receipt and advise if this resolves the notice.\n\n"
                "Regards,\nTerri Schell"
            ),
            attachment_names=[
                "ACORD_25.pdf", "ACORD_28.pdf", "ACORD_101.pdf",
                "SAM_Policy.pdf", "BI_Endorsement.pdf",
                "OL_Endorsement.pdf", "SOV_12_Locations.pdf",
            ],
        ),
        EmailData(
            source="test",
            subject="Insurance Document Submission – Capital One Loan Renewal – Full Policy Package",
            sender="terri.schell@captiveadvisorypartners.com",
            sender_domain="captiveadvisorypartners.com",
            to_recipients=["insuranceteam@cmservicing.com"],
            to_domains=["cmservicing.com"],
            cc_recipients=["lender-insurance@acentopartners.com"],
            cc_domains=["acentopartners.com"],
            received_date=datetime(2024, 11, 25, 14, 15),
            body_text=(
                "Capital One Insurance Servicing Team,\n\n"
                "We are writing in response to the Non-Compliance notice issued on November 1, 2024 "
                "regarding the delayed delivery of full policy documents for Loan #CO-4492.\n\n"
                "Policy renewal effective date was September 1, 2024. We acknowledge that the full "
                "policy package was not delivered within the required 90-day window.\n\n"
                "Attached please find:\n"
                "- ACORD 25 (GL + Umbrella/Excess)\n"
                "- ACORD 28 (Property)\n"
                "- ACORD 101 (Additional Remarks)\n"
                "- SOV with all buildings, unit counts, and stories\n"
                "- Corrected Additional Insured clause (Capital One / Freddie Mac wording – ISAOA/ATIMA)\n"
                "- Commitment letter confirming full policy PDFs will be delivered by December 15, 2024\n\n"
                "We apologize for the delay and are committed to full compliance going forward.\n\n"
                "Sincerely,\nTerri Schell\nCaptive Advisory Partners"
            ),
            attachment_names=[
                "ACORD_25_GL_Umbrella.pdf", "ACORD_28_Property.pdf",
                "ACORD_101.pdf", "SOV_All_Buildings.pdf",
                "AI_Clause_CapOne_Freddie.pdf", "Policy_Delivery_Commitment.pdf",
            ],
        ),
    ]

    def _print_result(idx: int, email: EmailData, result) -> None:
        sep = "=" * 72
        print(f"\n{sep}")
        print(f"  TEST EMAIL #{idx}  |  Subject: {email.subject[:60]}")
        print(sep)
        print(f"  Lender          : {result.lender}")
        print(f"  Waiver Type     : {result.waiver_type}")
        print(f"  Confidence      : {result.confidence_score:.2f}  [{result.confidence_level.upper()}]")
        if result.secondary_issues:
            print(f"  Secondary Issues: {', '.join(result.secondary_issues)}")
        print(f"  Trigger         : {textwrap.fill(result.trigger_description or '', 60, subsequent_indent=' ' * 20)}")
        print(f"  Reasoning       :")
        for line in textwrap.wrap(result.reasoning or "(none)", 68):
            print(f"    {line}")
        if result.waiver_pack:
            print(f"  Waiver Pack     :")
            for line in textwrap.wrap(result.waiver_pack, 68):
                print(f"    {line}")
        if result.documents_expected:
            print(f"  Docs Expected   :")
            for line in textwrap.wrap(result.documents_expected, 68):
                print(f"    {line}")
        print(sep)

    async def main() -> None:
        print("\n" + "=" * 72)
        print("  llm_pueba_clasifier.py  –  Classification Test")
        print("  Knowledge base sourced from PostgreSQL (acento_db)")
        print("=" * 72)

        ok = await classifier.check_model_available()
        if not ok:
            print(
                "\n[ERROR] Ollama model not available. "
                f"Run:  ollama pull {classifier.model}\n"
            )
            return

        for idx, email in enumerate(SAMPLE_EMAILS, 1):
            print(f"\n[{idx}/{len(SAMPLE_EMAILS)}] Classifying: {email.subject[:55]} …")
            result = await classifier.classify(email)
            _print_result(idx, email, result)

        print("\nDone.\n")

    asyncio.run(main())
