from fastapi import APIRouter, Depends, HTTPException
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db.models import Investor, InvestorProfile
from app.db.session import get_db
from app.schemas.investor import (
    InvestorCreate,
    InvestorRead,
    InvestorProfileRead,
    InvestorProfileUpsert,
)
from app.services.allocation import get_default_allocation

router = APIRouter(prefix="/investors", tags=["investors"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/", response_model=InvestorRead)
def create_investor(payload: InvestorCreate, db: Session = Depends(get_db)):
    if db.query(Investor).filter(Investor.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    investor = Investor(
        email=payload.email,
        hashed_password=pwd_context.hash(payload.password),
        full_name=payload.full_name,
    )
    db.add(investor)
    db.commit()
    db.refresh(investor)
    return investor


@router.get("/{investor_id}", response_model=InvestorRead)
def get_investor(investor_id: int, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")
    return investor


@router.put("/{investor_id}/profile", response_model=InvestorProfileRead)
def upsert_profile(investor_id: int, payload: InvestorProfileUpsert, db: Session = Depends(get_db)):
    investor = db.get(Investor, investor_id)
    if investor is None:
        raise HTTPException(status_code=404, detail="Investor not found")

    profile = db.query(InvestorProfile).filter(InvestorProfile.investor_id == investor_id).first()
    if profile is None:
        profile = InvestorProfile(investor_id=investor_id, **payload.model_dump())
        db.add(profile)
    else:
        for field, value in payload.model_dump().items():
            setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


@router.get("/{investor_id}/profile/allocation-template")
def get_allocation_template(investor_id: int, db: Session = Depends(get_db)):
    profile = db.query(InvestorProfile).filter(InvestorProfile.investor_id == investor_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Investor profile not found")

    try:
        return get_default_allocation(profile.risk_cadence)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
