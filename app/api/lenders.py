"""
CRUD endpoints for Lender management.
Serves the lender management UI at GET /lenders/form.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from app.models.database import get_session, Lender, LenderAlias, LenderDomain, Waiver

router = APIRouter(prefix="/lenders", tags=["lenders"])
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# ── Pydantic schemas ──────────────────────────────────────────────

class WaiverIn(BaseModel):
    id: Optional[int] = None
    waiver_type: str
    triggers: Optional[str] = None
    evidence_required_ops: Optional[str] = None
    evidence_required_insurance: Optional[str] = None
    documents_expected: Optional[str] = None
    actions_to_automate: Optional[str] = None
    waiver_pack: Optional[str] = None
    is_active: bool = True


class WaiverOut(BaseModel):
    id: int
    waiver_type: str
    triggers: Optional[str]
    evidence_required_ops: Optional[str]
    evidence_required_insurance: Optional[str]
    documents_expected: Optional[str]
    actions_to_automate: Optional[str]
    waiver_pack: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class LenderIn(BaseModel):
    name: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool = True
    aliases: list[str] = []
    domains: list[str] = []
    waivers: list[WaiverIn] = []


class LenderOut(BaseModel):
    id: int
    name: str
    first_name: Optional[str]
    last_name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    is_active: bool
    aliases: list[str]
    domains: list[str]
    waivers: list[WaiverOut]

    model_config = {"from_attributes": True}


def _to_out(lender: Lender) -> LenderOut:
    return LenderOut(
        id=lender.id,
        name=lender.name,
        first_name=lender.first_name,
        last_name=lender.last_name,
        email=lender.email,
        phone=lender.phone,
        notes=lender.notes,
        is_active=lender.is_active,
        aliases=[a.alias for a in lender.aliases],
        domains=[d.domain for d in lender.domains],
        waivers=[WaiverOut.model_validate(w) for w in lender.waivers],
    )


# ── Form UI ───────────────────────────────────────────────────────

@router.get("/form", response_class=HTMLResponse)
async def lenders_form(request: Request):
    return templates.TemplateResponse("lenders.html", {"request": request})


# ── REST CRUD ─────────────────────────────────────────────────────

@router.get("", response_model=list[LenderOut])
async def list_lenders(session: AsyncSession = Depends(get_session)):
    rows = await session.scalars(select(Lender).order_by(Lender.name))
    return [_to_out(r) for r in rows.all()]


@router.get("/{lender_id}", response_model=LenderOut)
async def get_lender(lender_id: int, session: AsyncSession = Depends(get_session)):
    lender = await session.get(Lender, lender_id)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    return _to_out(lender)


@router.post("", response_model=LenderOut, status_code=201)
async def create_lender(payload: LenderIn, session: AsyncSession = Depends(get_session)):
    existing = await session.scalar(select(Lender).where(Lender.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Lender name already exists")

    lender = Lender(
        name=payload.name,
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        phone=payload.phone,
        notes=payload.notes,
        is_active=payload.is_active,
    )
    session.add(lender)
    await session.flush()

    _sync_children(session, lender.id, payload)

    await session.commit()
    await session.refresh(lender)
    return _to_out(lender)


@router.put("/{lender_id}", response_model=LenderOut)
async def update_lender(
    lender_id: int,
    payload: LenderIn,
    session: AsyncSession = Depends(get_session),
):
    lender = await session.get(Lender, lender_id)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")

    conflict = await session.scalar(
        select(Lender).where(Lender.name == payload.name, Lender.id != lender_id)
    )
    if conflict:
        raise HTTPException(status_code=409, detail="Another lender with that name already exists")

    lender.name       = payload.name
    lender.first_name = payload.first_name
    lender.last_name  = payload.last_name
    lender.email      = payload.email
    lender.phone      = payload.phone
    lender.notes      = payload.notes
    lender.is_active  = payload.is_active

    await session.execute(delete(LenderAlias).where(LenderAlias.lender_id == lender_id))
    await session.execute(delete(LenderDomain).where(LenderDomain.lender_id == lender_id))
    await session.execute(delete(Waiver).where(Waiver.lender_id == lender_id))

    _sync_children(session, lender_id, payload)

    await session.commit()
    await session.refresh(lender)
    return _to_out(lender)


@router.delete("/{lender_id}", status_code=204)
async def delete_lender(lender_id: int, session: AsyncSession = Depends(get_session)):
    lender = await session.get(Lender, lender_id)
    if not lender:
        raise HTTPException(status_code=404, detail="Lender not found")
    await session.delete(lender)
    await session.commit()


# ── Seed ─────────────────────────────────────────────────────────

@router.post("/seed", response_model=dict, status_code=201)
async def seed_lenders(session: AsyncSession = Depends(get_session)):
    """Populate from knowledge_base.py (skips existing lender names)."""
    from app.core.knowledge_base import LENDER_WAIVER_MATRIX, DOMAIN_LENDER_MAP

    domain_map: dict[str, list[str]] = {}
    for domain, lender_name in DOMAIN_LENDER_MAP.items():
        domain_map.setdefault(lender_name, []).append(domain)

    inserted = skipped = 0

    for entry in LENDER_WAIVER_MATRIX:
        name = entry["lender"]
        existing = await session.scalar(select(Lender).where(Lender.name == name))
        if existing:
            skipped += 1
            continue

        lender = Lender(name=name, is_active=True)
        session.add(lender)
        await session.flush()

        for alias in entry.get("lender_aliases", []):
            session.add(LenderAlias(lender_id=lender.id, alias=alias))

        for domain in domain_map.get(name, []):
            session.add(LenderDomain(lender_id=lender.id, domain=domain))

        session.add(Waiver(
            lender_id=lender.id,
            waiver_type=entry.get("waiver_type", ""),
            triggers=entry.get("triggers"),
            evidence_required_ops=entry.get("evidence_required_ops"),
            evidence_required_insurance=entry.get("evidence_required_insurance"),
            documents_expected=entry.get("documents_expected"),
            actions_to_automate=entry.get("actions_to_automate"),
            waiver_pack=entry.get("waiver_pack"),
            is_active=True,
        ))

        inserted += 1

    await session.commit()
    return {"inserted": inserted, "skipped": skipped}


# ── Internal helper ───────────────────────────────────────────────

def _sync_children(session: AsyncSession, lender_id: int, payload: LenderIn) -> None:
    for alias in payload.aliases:
        alias = alias.strip()
        if alias:
            session.add(LenderAlias(lender_id=lender_id, alias=alias))

    for domain in payload.domains:
        domain = domain.strip().lower()
        if domain:
            session.add(LenderDomain(lender_id=lender_id, domain=domain))

    for w in payload.waivers:
        if w.waiver_type.strip():
            session.add(Waiver(
                lender_id=lender_id,
                waiver_type=w.waiver_type.strip(),
                triggers=w.triggers,
                evidence_required_ops=w.evidence_required_ops,
                evidence_required_insurance=w.evidence_required_insurance,
                documents_expected=w.documents_expected,
                actions_to_automate=w.actions_to_automate,
                waiver_pack=w.waiver_pack,
                is_active=w.is_active,
            ))
