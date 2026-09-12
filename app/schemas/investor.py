from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class InvestorCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None


class InvestorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None
    created_at: datetime


class InvestorProfileUpsert(BaseModel):
    risk_cadence: str
    horizon_years: int | None = None
    preferences: dict = {}
    restrictions: dict = {}


class InvestorProfileRead(InvestorProfileUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    updated_at: datetime
