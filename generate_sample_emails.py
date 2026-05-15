"""
Generate sample .eml files for testing the classification engine.
Creates realistic lender emails matching each entry in the knowledge base.

Usage:
    python generate_sample_emails.py
    python generate_sample_emails.py --output ./sample_emails --count 3
"""
import argparse
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime, timedelta
import random

SAMPLE_EMAILS = [
    # --- JLL: A&B Sublimit ---
    {
        "from": "insurance.compliance@jll.com",
        "to": "waivers@acentopartners.com",
        "subject": "Waiver Request - A&B Sublimit Deficiency - Maple Ridge Apartments",
        "body": """Hi Team,

We are reviewing the insurance package for Maple Ridge Apartments (Loan #MRA-2024-0891).

Upon review, we note that the General Liability policy includes an Assault & Battery sublimit of $250,000. Our lending requirements specify a minimum A&B coverage of $1,000,000 per occurrence.

To consider a waiver for this deficiency, we will need the following:
1. Property security assessment including camera locations, gated access details
2. Background check policies for tenants and employees
3. Security guard contracts (vendor name and terms)
4. GL endorsement pages showing the A&B sublimit
5. Declination letters from markets (if higher limits were pursued)
6. Loss runs for the past 2-3 years

Please provide the above documentation at your earliest convenience so we can evaluate the waiver request.

Best regards,
Sarah Mitchell
Insurance Compliance Analyst
JLL Insurance Servicing
""",
    },
    # --- JLL: SAM ---
    {
        "from": "compliance.team@am.jll.com",
        "to": "insurance@acentopartners.com",
        "subject": "RE: Sexual Abuse & Molestation Coverage - Sunset Gardens",
        "body": """Good morning,

During our annual insurance review for Sunset Gardens (Loan #SG-2023-4412), we identified that the GL/Excess policies are silent on Sexual Abuse & Molestation (SAM) coverage.

JLL requires either SAM coverage within the GL policy or evidence of a standalone SAM policy with minimum $2M limits.

Could you please provide:
- Standalone SAM policy (if available)
- GL/excess endorsements noting SAM coverage or exclusion
- Security measures and access controls at the property
- Hiring and background-check practices documentation
- Loss runs

If standalone SAM coverage cannot be obtained, we may consider a waiver with sufficient operational controls evidence.

Thank you,
David Chen
JLL Insurance Servicing
""",
    },
    # --- JLL: Equipment Breakdown ---
    {
        "from": "property.insurance@jll.com",
        "to": "insurance@acentopartners.com",
        "subject": "Equipment Breakdown Limit Deficiency - Industrial Park East",
        "body": """Hello,

We have flagged an Equipment Breakdown coverage deficiency for Industrial Park East (Loan #IPE-2024-1156).

The current EB limit is $1,000,000, which does not meet the requirement of 100% insurable value for the property's mechanical and electrical equipment.

To process a waiver consideration, please provide:
- Construction/engineering memo detailing central vs. distributed equipment
- Nameplate capacities for major HVAC systems
- Replacement cost breakdown by building
- Property policy EB endorsement
- SOV with EB-relevant assets identified
- Any engineering correspondence regarding equipment valuations

We need this information to assess whether the current EB limit is adequate relative to the actual equipment exposure.

Regards,
Amanda Torres
JLL Insurance Servicing - Property Division
""",
    },
    # --- Capital One: Full Policy Package ---
    {
        "from": "insurance.tracking@capitalone.com",
        "to": "renewals@acentopartners.com",
        "subject": "NON-COMPLIANCE NOTICE - Full Policy Documents Required - Riverstone Commons",
        "body": """IMPORTANT: NON-COMPLIANCE NOTIFICATION

Loan Number: RC-2024-7723
Property: Riverstone Commons
Borrower: Acentopartners LLC

This notice is to inform you that we have not received the full policy documents for the recent renewal. Per our servicing requirements, all complete policy documents must be received within 90 days of the renewal date.

We currently have on file:
- Certificate of Insurance (ACORD 25)
- Evidence of Property coverage

STILL REQUIRED:
- Full GL policy (not just COI)
- Excess/Umbrella full policy
- Property full policy document
- Terrorism coverage evidence
- Corrected Additional Insured clause (must reference Capital One as AI)
- SOV with all buildings and units

Please provide all outstanding documents within 30 days to avoid further compliance action. If full policies are not yet available from your carriers, please provide a commitment letter stating the expected delivery timeline.

Capital One Commercial Insurance Tracking
""",
    },
    # --- Freddie Mac: AI/Mortgagee Wording ---
    {
        "from": "real.estate.capital@jll.com",
        "to": "compliance@acentopartners.com",
        "subject": "Freddie Mac Wording Deficiency - Heritage Plaza Loan",
        "body": """Good afternoon,

We are servicing the Freddie Mac loan for Heritage Plaza (Loan #FRE-2024-0334) and have identified a wording deficiency on the Certificate of Insurance.

The Additional Insured / Mortgagee clause does not conform to Freddie Mac's required ISAOA/ATIMA wording. Specifically:
- The mortgagee clause must reference the exact Freddie Mac standard language
- Terrorism coverage must be explicitly shown (recommend using ACORD 101)
- The loan number must appear on all COIs

Please provide corrected COIs with the proper Freddie Mac wording, along with:
- Updated SOV
- Terrorism endorsement note (ACORD 101)
- Evidence of the wording correction

This is primarily a documentation correction issue. Once the wording is updated to match Freddie Mac standards, the deficiency will be resolved.

Thank you for your prompt attention.
Michael Rodriguez
JLL Real Estate Capital - Freddie Mac Servicing
""",
    },
    # --- Grandbridge/KeyBank: OL/BI/EPI ---
    {
        "from": "trustee.insurance@grandbridge.com",
        "to": "insurance@acentopartners.com",
        "subject": "OL/BI Structure Review - Gateway Office Complex - KeyBank Trust",
        "body": """Dear Insurance Team,

On behalf of KeyBank as trustee, we are reviewing the property insurance for Gateway Office Complex (Trust #KB-2024-5567, Wells Fargo Master Servicer).

We need clarification on the following policy structure items:

1. Ordinance or Law (OL) Coverage: We require OL A, B, and C at minimum 10% each. Please confirm the current OL structure and limits.

2. Business Income (BI) / Extra Expense: The BI waiting period appears to be 72 hours. Our requirement is documentation showing this meets or exceeds the lender standard.

3. Extended Period of Indemnity (EPI): Please provide the EPI length and any relevant endorsement pages.

Required documentation:
- ACORD 28 with OL/BI details
- Policy excerpts showing OL A/B/C percentages
- BI waiting period endorsement
- SOV with current values
- Explanation mapping your policy structure to our requirements

Please respond within 15 business days.

Regards,
Jennifer Walsh
Grandbridge Real Estate Capital - Insurance Compliance
""",
    },
    # --- Berkadia: Invoice Components ---
    {
        "from": "insurance.payments@berkadia.com",
        "to": "billing@acentopartners.com",
        "subject": "Invoice Clarification Needed - Terrorism/Excess Components - Oakwood Residences",
        "body": """Hi,

We received the insurance invoice for Oakwood Residences (Loan #BK-2024-8891) but need clarification before we can process payment.

Issues identified:
1. The invoice does not separately list Terrorism coverage as a line item
2. Excess liability is not broken out as a distinct component
3. The property address on the invoice (123 Oak St) does not match our loan file (123 Oakwood Street, Suite 100)

For Berkadia to process payment, we need:
- Revised invoice with explicit line items for: Property, GL, Umbrella, Excess, Terrorism
- Address corrected to match loan documents
- ACORD 25/28 as supporting evidence
- SOV showing the correct property address

Additionally, please confirm the escrow routing instructions for this loan.

Thank you,
Patricia Nguyen
Berkadia Servicing - Insurance Payments
""",
    },
    # --- NEWMARK: Address/Excess Lines ---
    {
        "from": "mcm.servicing@nmrk.com",
        "to": "insurance@acentopartners.com",
        "subject": "Address Correction & Excess Line Items - Parkview Towers",
        "body": """Hello,

Regarding Parkview Towers (Loan #NM-2024-2213), we need the following corrections:

1. PROPERTY ADDRESS: The address on file shows "456 Park Ave" but our records indicate the correct legal address is "456 Park Avenue, Building A & B, Parkview Towers." Please update all documentation to reflect the full address.

2. EXCESS COVERAGE: The invoice does not explicitly show the Excess liability line item. NEWMARK requires Excess to be listed as a separate line with the premium amount.

Please provide:
- Revised invoice showing Excess as a distinct line item
- SOV rows confirming the full property address for each building
- ACORDs if needed to support the address correction

Once documentation aligns with our records, we can proceed with processing.

Best,
Robert Kim
NEWMARK MCM Servicing
""",
    },
    # --- Greystone: ACORD-gate ---
    {
        "from": "insurance.ops@greystone.com",
        "to": "accounts@acentopartners.com",
        "subject": "ACORD 25/28 Required Before Payment Release - Marina Bay Apartments",
        "body": """Good morning,

We are holding payment for the insurance premium on Marina Bay Apartments (Loan #GS-2024-6645) pending receipt of required documentation.

Greystone requires ACORD 25 and ACORD 28 certificates to be bundled with every invoice before we can release payment.

Additionally, we need clarity on the GL vs. Umbrella breakdown:
- Is the Umbrella coverage included in the GL totals on the invoice?
- Please provide a clear breakout showing GL premium vs. Umbrella premium separately

Required before payment release:
- ACORD 25 (GL certificate)
- ACORD 28 (Property certificate)
- Invoice with GL vs. Umbrella premium breakout
- Paid receipt (if applicable)

Please submit at your earliest convenience.

Thank you,
Lisa Park
Greystone Insurance Operations
""",
    },
    # --- Additional JLL A&B variant ---
    {
        "from": "waiver.requests@jll.com",
        "to": "insurance@acentopartners.com",
        "subject": "Security Assessment Request - A&B Coverage Waiver - Pine Creek Village",
        "body": """Team,

Following up on the A&B sublimit issue for Pine Creek Village. The GL policy shows a $100,000 A&B sublimit which is well below our $1M standard.

Before we can grant a waiver, we need a comprehensive security assessment:
- Are there security cameras? If so, how many and where are they located?
- Is the property gated with controlled access?
- Do you employ security guards? Please provide the contract details.
- What background check procedures exist for residents and staff?
- Does the property have a gym, clubhouse, or pool area? What security measures are in place for those areas?

Also please include:
- ACORD 25 and 101
- Declination letters showing you attempted to obtain higher A&B limits
- 3 years of loss runs

Regards,
Tom Bradley
JLL Insurance Compliance
""",
    },
]


def create_eml(sample: dict, date: datetime) -> str:
    """Create a properly formatted .eml file content."""
    msg = MIMEMultipart()
    msg["From"] = sample["from"]
    msg["To"] = sample["to"]
    msg["Subject"] = sample["subject"]
    msg["Date"] = email.utils.formatdate(date.timestamp(), localtime=True)
    msg["Message-ID"] = f"<{random.randint(100000, 999999)}.{date.strftime('%Y%m%d')}@{sample['from'].split('@')[1]}>"

    body = MIMEText(sample["body"], "plain", "utf-8")
    msg.attach(body)

    return msg.as_string()


def main():
    parser = argparse.ArgumentParser(description="Generate sample .eml files for testing")
    parser.add_argument("--output", default="./sample_emails", help="Output directory")
    parser.add_argument("--count", type=int, default=1, help="Copies per template (for volume testing)")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_date = datetime(2025, 2, 1, 9, 0, 0)
    file_count = 0

    for i, sample in enumerate(SAMPLE_EMAILS):
        for copy in range(args.count):
            date = base_date + timedelta(days=i, hours=copy, minutes=random.randint(0, 59))

            # Generate filename from subject
            safe_subject = sample["subject"][:60].replace(" ", "_").replace("/", "-")
            safe_subject = "".join(c for c in safe_subject if c.isalnum() or c in "-_")
            filename = f"{i+1:02d}_{safe_subject}"
            if args.count > 1:
                filename += f"_v{copy+1}"
            filename += ".eml"

            eml_content = create_eml(sample, date)
            filepath = output_dir / filename
            filepath.write_text(eml_content, encoding="utf-8")
            file_count += 1

    print(f"Generated {file_count} sample .eml files in {output_dir}/")
    print(f"Templates used: {len(SAMPLE_EMAILS)}")
    print(f"\nFiles created:")
    for f in sorted(output_dir.glob("*.eml")):
        print(f"  {f.name}")


if __name__ == "__main__":
    main()
