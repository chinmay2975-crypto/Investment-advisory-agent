from datetime import datetime

from pydantic import BaseModel, EmailStr


class InvestorCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class InvestorRead(BaseModel):
    id: int
    email: EmailStr
    full_name: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class InvestorProfileUpsert(BaseModel):
    risk_cadence: str
    horizon_years: int | None = None
    preferences: dict = {}
    restrictions: dict = {}


class InvestorProfileRead(InvestorProfileUpsert):
    id: int
    investor_id: int
    updated_at: datetime

    class Config:
        from_attributes = True
