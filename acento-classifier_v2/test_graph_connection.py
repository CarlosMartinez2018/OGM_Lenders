"""
Microsoft Graph API - Validation Test
======================================
Run this script to verify that the Azure app credentials in .env
can authenticate and read emails from the configured mailbox.

Usage:
    python test_graph_connection.py                        # last 5 emails
    python test_graph_connection.py --from 2026-03-01      # from date onwards
    python test_graph_connection.py --from 2026-03-01 --to 2026-03-31
    python test_graph_connection.py --from 2026-03-01 --to 2026-03-31 --count 20

Exit codes:
    0 - All tests passed
    1 - One or more tests failed
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone, timedelta

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv()

import os
import httpx

# ──────────────────────────────────────────
# Config  (reads from .env automatically)
# ──────────────────────────────────────────
TENANT_ID     = os.getenv("AZURE_TENANT_ID", "")
CLIENT_ID     = os.getenv("AZURE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET", "")
MAILBOX       = os.getenv("OUTLOOK_MAILBOX", "")
GRAPH_BASE    = "https://graph.microsoft.com/v1.0"

# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

results: list[dict] = []


def ok(label: str, detail: str = ""):
    results.append({"status": "PASS", "label": label, "detail": detail})
    print(f"  {GREEN}[PASS]{RESET} {label}" + (f"  ->  {detail}" if detail else ""))


def fail(label: str, detail: str = ""):
    results.append({"status": "FAIL", "label": label, "detail": detail})
    print(f"  {RED}[FAIL]{RESET} {label}" + (f"  ->  {detail}" if detail else ""))


def info(msg: str):
    print(f"         {YELLOW}{msg}{RESET}")


def section(title: str):
    print(f"\n{BOLD}{'-'*55}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'-'*55}{RESET}")


# ──────────────────────────────────────────
# Test 1 – Env vars present
# ──────────────────────────────────────────
def test_env_vars():
    section("1 · Environment variables")
    missing = []
    for name, value in [
        ("AZURE_TENANT_ID", TENANT_ID),
        ("AZURE_CLIENT_ID", CLIENT_ID),
        ("AZURE_CLIENT_SECRET", CLIENT_SECRET),
        ("OUTLOOK_MAILBOX", MAILBOX),
    ]:
        if value:
            ok(name, value[:8] + "..." if len(value) > 8 else value)
        else:
            fail(name, "not set in .env")
            missing.append(name)
    return len(missing) == 0


# ──────────────────────────────────────────
# Test 2 – MSAL token acquisition
# ──────────────────────────────────────────
def test_get_token() -> str | None:
    section("2a · Network connectivity to login.microsoftonline.com")
    token_url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    info(f"Token URL: {token_url}")
    try:
        with httpx.Client(timeout=10.0) as client:
            # Just check the OIDC discovery endpoint
            discovery = f"https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration"
            r = client.get(discovery)
            if r.status_code == 200:
                ok("Reached OIDC discovery endpoint", f"HTTP {r.status_code}")
            else:
                fail("OIDC discovery endpoint", f"HTTP {r.status_code} - {r.text[:100]}")
                info("Check that the TENANT_ID is correct and login.microsoftonline.com is reachable")
    except Exception as e:
        fail("Network connectivity", str(e))
        info("Cannot reach login.microsoftonline.com - check internet/proxy settings")

    section("2b · Token acquisition (direct OAuth2 client credentials POST)")
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            body = r.json()
            if "access_token" in body:
                expires_in = body.get("expires_in", "?")
                ok("Token acquired", f"expires_in={expires_in}s  (HTTP {r.status_code})")
                return body["access_token"]
            else:
                err = body.get("error_description") or body.get("error", "unknown")
                fail("Token acquisition", f"HTTP {r.status_code} - {err[:200]}")
                return None
    except Exception as e:
        fail("Token acquisition", str(e))
        return None


# ──────────────────────────────────────────
# Test 3 – Inbox messages (async)
# ──────────────────────────────────────────
async def test_graph_calls(token: str, date_from: str | None, date_to: str | None, count: int):
    headers = {"Authorization": f"Bearer {token}"}

    # Build $filter for date range if provided
    filters = []
    if date_from:
        filters.append(f"receivedDateTime ge {date_from}T00:00:00Z")
    if date_to:
        filters.append(f"receivedDateTime le {date_to}T23:59:59Z")
    filter_str = " and ".join(filters)

    label = f"3 · Inbox messages (last {count}"
    label += f", from {date_from}" if date_from else ""
    label += f" to {date_to}" if date_to else ""
    label += ")  [requires Mail.Read]"

    async with httpx.AsyncClient(timeout=15.0) as client:
        section(label)
        url = (
            f"{GRAPH_BASE}/users/{MAILBOX}/mailFolders/Inbox/messages"
            f"?$top={count}&$orderby=receivedDateTime desc"
            f"&$select=id,subject,from,receivedDateTime,hasAttachments"
        )
        if filter_str:
            url += f"&$filter={filter_str}"
            info(f"Filter: {filter_str}")
        try:
            r = await client.get(url, headers=headers)
            if r.status_code == 200:
                msgs = r.json().get("value", [])
                ok("Inbox accessible", f"{len(msgs)} message(s) returned")
                for i, m in enumerate(msgs, 1):
                    subj   = m.get("subject", "(no subject)")[:60]
                    sender = m.get("from", {}).get("emailAddress", {}).get("address", "?")
                    rcvd   = m.get("receivedDateTime", "?")[:10]
                    info(f"  [{i}] {rcvd}  {sender:<35}  {subj}")
            else:
                fail("Inbox messages", f"HTTP {r.status_code} - {r.text[:200]}")
        except Exception as e:
            fail("Inbox messages", str(e))


# ──────────────────────────────────────────
# Summary
# ──────────────────────────────────────────
def print_summary():
    section("Summary")
    total  = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed

    for r in results:
        color = GREEN if r["status"] == "PASS" else RED
        print(f"  {color}{r['status']}{RESET}  {r['label']}")

    print()
    if failed == 0:
        print(f"  {GREEN}{BOLD}All {total} checks passed.{RESET}")
        print(f"  {GREEN}The Azure app is correctly configured.{RESET}")
        print(f"  {GREEN}The ticket can be CLOSED.{RESET}")
    else:
        print(f"  {RED}{BOLD}{failed}/{total} checks failed.{RESET}")
        print(f"  {RED}Review the errors above before closing the ticket.{RESET}")
    print()


# ──────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="Microsoft Graph API - Connection Validation")
    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD",
                        help="Filter emails received on or after this date")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD",
                        help="Filter emails received on or before this date")
    parser.add_argument("--count", type=int, default=5, metavar="N",
                        help="Max number of emails to retrieve (default: 5)")
    return parser.parse_args()


async def main():
    args = parse_args()

    print(f"\n{BOLD}Microsoft Graph API - Connection Validation{RESET}")
    print(f"Timestamp : {datetime.now(timezone.utc).isoformat()}")
    print(f"Mailbox   : {MAILBOX or '(not set)'}")
    if args.date_from or args.date_to:
        print(f"Date range: {args.date_from or '*'} -> {args.date_to or '*'}")

    env_ok = test_env_vars()
    if not env_ok:
        print_summary()
        sys.exit(1)

    token = test_get_token()
    if not token:
        print_summary()
        sys.exit(1)

    await test_graph_calls(token, args.date_from, args.date_to, args.count)
    print_summary()
    sys.exit(0 if all(r["status"] == "PASS" for r in results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
