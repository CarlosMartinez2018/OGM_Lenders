"""
Email parser service - handles .eml files and raw email data.
Extracts FROM, TO, CC, body, attachments for classification.
"""
import re
import mailparser
from pathlib import Path
from datetime import datetime, timezone
from app.models.schemas import EmailData
import logging

logger = logging.getLogger(__name__)


def clean_html(html_str: str) -> str:
    """Strip HTML, CSS and comments; return clean readable plain text."""
    if not html_str:
        return ""
    import html as _html
    try:
        s = html_str
        # 1. Remove entire blocks whose content is never readable text
        s = re.sub(r"<style[^>]*>.*?</style>",   "", s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(r"<script[^>]*>.*?</script>",  "", s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(r"<head[^>]*>.*?</head>",       "", s, flags=re.DOTALL | re.IGNORECASE)
        s = re.sub(r"<noscript[^>]*>.*?</noscript>","", s, flags=re.DOTALL | re.IGNORECASE)
        # 2. Remove ALL HTML comments (<!-- ... -->) including CSS resets / @font-face blocks
        s = re.sub(r"<!--.*?-->", "", s, flags=re.DOTALL)
        # 3. Turn block-level tags into newlines before stripping
        _BLOCK = r"(?:p|div|br|tr|li|h[1-6]|blockquote|article|section|header|footer|pre|td|th)"
        s = re.sub(rf"</?{_BLOCK}(?:\s[^>]*)?>", "\n", s, flags=re.IGNORECASE)
        # 4. Strip every remaining tag
        s = re.sub(r"<[^>]+>", "", s)
        # 5. Decode HTML entities (&amp; &nbsp; &#160; etc.)
        s = _html.unescape(s)
        # 6. Normalise whitespace
        s = re.sub(r"[ \t\xa0]+", " ", s)
        lines = [ln.strip() for ln in s.splitlines()]
        out, prev_blank = [], False
        for ln in lines:
            blank = not ln
            if blank and prev_blank:
                continue
            out.append(ln)
            prev_blank = blank
        return "\n".join(out).strip()
    except Exception:
        s = re.sub(r"<!--.*?-->", " ", html_str, flags=re.DOTALL)
        s = re.sub(r"<[^>]+>", " ", s)
        return re.sub(r"\s+", " ", s).strip()


def _extract_emails(recipients: list) -> tuple[list[str], list[str]]:
    """Extract email addresses and domains from recipient tuples."""
    emails = [r[1] for r in recipients if r[1]] if recipients else []
    domains = []
    for e in emails:
        if "@" in e:
            d = e.split("@")[1].lower()
            if d not in domains:
                domains.append(d)
    return emails, domains


def _parse_mail_object(mail, source: str, filename: str = None) -> EmailData:
    """Shared parsing logic for mail objects."""
    sender = mail.from_[0][1] if mail.from_ else ""
    sender_domain = sender.split("@")[1].lower() if "@" in sender else ""

    to_emails, to_domains = _extract_emails(mail.to_)
    cc_emails, cc_domains = _extract_emails(mail.cc_)

    body_text = mail.text_plain[0] if mail.text_plain else ""
    body_html = mail.text_html[0] if mail.text_html else ""

    if not body_text and body_html:
        body_text = mail.text_html_no_urls[0] if mail.text_html_no_urls else body_html

    received_date = None
    if mail.date:
        if isinstance(mail.date, datetime):
            received_date = mail.date
        else:
            try:
                received_date = datetime.fromisoformat(str(mail.date))
            except (ValueError, TypeError):
                received_date = datetime.now(timezone.utc)

    attachment_names = []
    for att in mail.attachments:
        fn = att.get("filename", "")
        if fn and not fn.startswith("image"):
            attachment_names.append(fn)

    return EmailData(
        source=source,
        filename=filename,
        message_id=mail.message_id or "",
        subject=mail.subject or "(no subject)",
        sender=sender,
        sender_domain=sender_domain,
        to_recipients=to_emails,
        to_domains=to_domains,
        cc_recipients=cc_emails,
        cc_domains=cc_domains,
        received_date=received_date,
        body_text=body_text.strip(),
        body_html=body_html,
        has_attachments=len(attachment_names) > 0,
        attachment_names=attachment_names,
    )


def parse_eml_file(file_path: Path) -> EmailData:
    """Parse a .eml file and extract structured email data."""
    mail = mailparser.parse_from_file(str(file_path))
    return _parse_mail_object(mail, source="file", filename=file_path.name)


def parse_eml_bytes(raw_bytes: bytes, filename: str = "uploaded.eml") -> EmailData:
    """Parse email from raw bytes (for upload endpoint)."""
    mail = mailparser.parse_from_bytes(raw_bytes)
    return _parse_mail_object(mail, source="file", filename=filename)


def scan_email_folder(folder_path: Path, max_files: int = 500) -> list[Path]:
    """Scan a folder for .eml files."""
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")

    eml_files = sorted(folder_path.glob("*.eml"))[:max_files]
    logger.info(f"Found {len(eml_files)} .eml files in {folder_path}")
    return eml_files
