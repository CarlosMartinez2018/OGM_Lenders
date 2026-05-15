"""
Email ingestion script — reads emails and stores them parsed in PostgreSQL.

Modes:
  file    — reads .eml files from a local folder
  outlook — reads from Outlook mailbox via Microsoft Graph API

Usage:
  # Hoy (file)
  python ingest_today.py --source file

  # Todos los archivos sin filtro de fecha
  python ingest_today.py --source file --all-dates

  # Hoy (Outlook)
  python ingest_today.py --source outlook

  # Mes y año específico (Outlook)
  python ingest_today.py --source outlook --month 4 --year 2026
  python ingest_today.py --source outlook --month 3 --year 2026

  # Carpeta personalizada
  python ingest_today.py --source file --folder /path/to/emails

Requires:
  - DATABASE_URL en .env apuntando a PostgreSQL
  - docker-compose up postgres -d
"""
import asyncio
import argparse
import calendar
import logging
import sys
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from rich.console import Console
from rich.table import Table

from app.core.config import settings
from app.models.database import Base, ParsedEmail
from app.models.schemas import EmailData
from app.services.email_parser.parser import parse_eml_file, scan_email_folder, clean_html
from app.services.outlook.connector import outlook

console = Console()


def _is_today(dt: Optional[datetime]) -> bool:
    if dt is None:
        return False
    local_date = dt.astimezone().date() if dt.tzinfo else dt.date()
    return local_date == date.today()


def _month_range(month: int, year: int) -> tuple[datetime, datetime]:
    """Return (start, end) UTC datetimes for the given month/year."""
    last_day = calendar.monthrange(year, month)[1]
    start = datetime(year, month, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
    return start, end


INTERNAL_DOMAINS = {"acentopartners.com"}


def _is_internal(email: EmailData) -> bool:
    """Return True if the sender belongs to an internal domain."""
    return (email.sender_domain or "").lower() in INTERNAL_DOMAINS


async def _find_existing(session: AsyncSession, email: EmailData) -> bool:
    """Return True if this email is already stored (dedup by message_id o filename)."""
    if email.message_id:
        row = await session.scalar(
            select(ParsedEmail.id).where(ParsedEmail.message_id == email.message_id).limit(1)
        )
        if row:
            return True

    if email.source == "file" and email.filename:
        row = await session.scalar(
            select(ParsedEmail.id)
            .where(ParsedEmail.source == "file", ParsedEmail.filename == email.filename)
            .limit(1)
        )
        if row:
            return True

    return False


async def _store(session: AsyncSession, email: EmailData) -> ParsedEmail:
    _clean = clean_html(email.body_html) if email.body_html else (email.body_text or "")
    record = ParsedEmail(
        source=email.source,
        filename=email.filename,
        message_id=email.message_id or None,
        subject=email.subject,
        sender=email.sender,
        sender_domain=email.sender_domain,
        to_recipients=email.to_recipients,
        to_domains=email.to_domains,
        cc_recipients=email.cc_recipients,
        cc_domains=email.cc_domains,
        received_date=email.received_date,
        body_text=email.body_text[:10_000] if email.body_text else None,
        body_html=email.body_html[:10_000] if email.body_html else None,
        body_clean=_clean[:10_000] if _clean else None,
        has_attachments=email.has_attachments,
        attachment_names=email.attachment_names,
    )
    session.add(record)
    await session.flush()
    return record


async def ingest_files(
    session: AsyncSession,
    folder: Path,
    filter_today: bool,
) -> list[dict]:
    eml_files = scan_email_folder(folder, max_files=500)

    results = []
    for eml_file in eml_files:
        row: dict = {"file": eml_file.name, "status": None, "subject": None,
                     "sender": None, "received_date": None, "error": None}
        try:
            email = parse_eml_file(eml_file)
            row["subject"] = (email.subject or "")[:60]
            row["sender"] = email.sender
            row["received_date"] = (
                email.received_date.strftime("%Y-%m-%d") if email.received_date else "unknown"
            )

            if filter_today:
                is_from_today = _is_today(email.received_date)
                if not is_from_today:
                    mtime = datetime.fromtimestamp(eml_file.stat().st_mtime, tz=timezone.utc)
                    is_from_today = _is_today(mtime)
                if not is_from_today:
                    row["status"] = "skipped_date"
                    results.append(row)
                    continue

            if _is_internal(email):
                row["status"] = "skipped_internal"
            elif await _find_existing(session, email):
                row["status"] = "duplicate"
            else:
                await _store(session, email)
                row["status"] = "inserted"

        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)
            logging.getLogger(__name__).error(f"Error processing {eml_file.name}: {exc}")

        results.append(row)

    await session.commit()
    return results


async def ingest_outlook(
    session: AsyncSession,
    filter_today: bool,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> list[dict]:
    """
    Fetch emails from Outlook and store in PostgreSQL.
    Priority: --month/--year > --today > --all-dates
    """
    since: Optional[datetime] = None
    until: Optional[datetime] = None
    label = "all dates"

    if month and year:
        since, until = _month_range(month, year)
        label = f"{calendar.month_name[month]} {year}"
    elif filter_today:
        since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"today ({date.today()})"

    console.print(f"  Period  : [yellow]{label}[/yellow]\n")

    emails = await outlook.fetch_recent_emails(
        folder="Inbox",
        count=500,
        since_datetime=since,
        until_datetime=until,
    )

    results = []
    for email in emails:
        row: dict = {
            "file": email.message_id or "(no-id)",
            "subject": (email.subject or "")[:60],
            "sender": email.sender,
            "received_date": (
                email.received_date.strftime("%Y-%m-%d") if email.received_date else "unknown"
            ),
            "status": None,
            "error": None,
        }
        try:
            if _is_internal(email):
                row["status"] = "skipped_internal"
            elif await _find_existing(session, email):
                row["status"] = "duplicate"
            else:
                await _store(session, email)
                row["status"] = "inserted"
        except Exception as exc:
            row["status"] = "error"
            row["error"] = str(exc)

        results.append(row)

    await session.commit()
    return results


async def main(args: argparse.Namespace) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    # Validar month/year
    if args.month and not args.year:
        console.print("[red]--month requiere también --year[/red]")
        sys.exit(1)
    if args.year and not args.month:
        console.print("[red]--year requiere también --month[/red]")
        sys.exit(1)
    if args.month and not (1 <= args.month <= 12):
        console.print("[red]--month debe ser un número entre 1 y 12[/red]")
        sys.exit(1)

    db_display = settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url
    if "sqlite" in settings.database_url:
        console.print(
            "\n[bold yellow]Warning:[/bold yellow] DATABASE_URL apunta a SQLite, no PostgreSQL.\n"
            "Actualiza DATABASE_URL en tu .env file.\n"
        )

    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    console.print(f"\n[bold blue]AcentoPartners — Email Ingestion[/bold blue]")
    console.print(f"  DB      : [dim]{db_display}[/dim]")
    console.print(f"  Source  : [cyan]{args.source}[/cyan]")

    async with session_factory() as session:
        if args.source == "file":
            folder = Path(args.folder)
            if not folder.exists():
                console.print(f"[red]Folder not found: {folder}[/red]")
                await engine.dispose()
                sys.exit(1)
            filter_today = not args.all_dates and not args.month
            console.print(
                f"  Filter  : [yellow]{'today (' + str(date.today()) + ')' if filter_today else 'all dates'}[/yellow]\n"
            )
            rows = await ingest_files(session, folder, filter_today=filter_today)

        else:
            if not outlook.is_configured:
                console.print(
                    "[red]Outlook no configurado.[/red]\n"
                    "Agrega AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET "
                    "y OUTLOOK_MAILBOX en tu .env."
                )
                await engine.dispose()
                sys.exit(1)
            filter_today = not args.all_dates and not args.month
            rows = await ingest_outlook(
                session,
                filter_today=filter_today,
                month=args.month,
                year=args.year,
            )

    _print_results(rows, args.source)
    await engine.dispose()


def _print_results(rows: list[dict], source: str) -> None:
    inserted  = [r for r in rows if r["status"] == "inserted"]
    duplicates = [r for r in rows if r["status"] == "duplicate"]
    skipped   = [r for r in rows if r["status"] == "skipped_date"]
    internal  = [r for r in rows if r["status"] == "skipped_internal"]
    errors    = [r for r in rows if r["status"] == "error"]

    summary = Table(title="Ingestion Summary", show_header=True, header_style="bold")
    summary.add_column("Metric", style="cyan")
    summary.add_column("Count", justify="right")
    summary.add_row("Total found",                           str(len(rows)))
    summary.add_row("[green]Inserted (new)[/green]",         f"[green]{len(inserted)}[/green]")
    summary.add_row("Duplicate (skipped)",                   str(len(duplicates)))
    summary.add_row("Date filter (skipped)",                 str(len(skipped)))
    summary.add_row("Internal @acentopartners.com (skipped)", str(len(internal)))
    summary.add_row("[red]Errors[/red]",                     f"[red]{len(errors)}[/red]")
    console.print(summary)

    if inserted:
        detail = Table(title=f"\nInserted Emails ({source})", show_header=True)
        detail.add_column("Subject", max_width=50)
        detail.add_column("Sender", max_width=35)
        detail.add_column("Received", justify="center")
        for r in inserted:
            detail.add_row(
                r.get("subject") or "",
                r.get("sender") or "",
                r.get("received_date") or "",
            )
        console.print(detail)

    if errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for r in errors:
            console.print(f"  • [dim]{r['file']}[/dim] — {r['error']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest emails into PostgreSQL (parsed, sin clasificación).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--source",
        choices=["file", "outlook"],
        default="file",
        help="Fuente: 'file' (.eml local) o 'outlook' (Microsoft Graph API). Default: file",
    )
    parser.add_argument(
        "--folder",
        default="./sample_emails",
        help="Carpeta con archivos .eml cuando --source=file. Default: ./sample_emails",
    )
    parser.add_argument(
        "--all-dates",
        action="store_true",
        default=False,
        help="Sin filtro de fecha. Útil para datos de prueba.",
    )
    parser.add_argument(
        "--month",
        type=int,
        default=None,
        metavar="1-12",
        help="Mes a ingestar (1-12). Requiere --year. Solo con --source outlook.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        metavar="YYYY",
        help="Año a ingestar (ej. 2026). Requiere --month. Solo con --source outlook.",
    )

    asyncio.run(main(parser.parse_args()))
