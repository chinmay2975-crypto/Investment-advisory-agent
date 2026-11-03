from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.countries import list_countries, normalize_country_code


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
    risk_cadence: str = Field(examples=["Balanced"])
    horizon_years: int | None = Field(default=None, examples=[15])
    preferences: dict = {}
    restrictions: dict = {}
    country: str | None = Field(default=None, examples=["IN"])
    base_currency: str | None = Field(default=None, examples=["INR"])

    @field_validator("country")
    @classmethod
    def _valid_country(cls, value: str | None) -> str | None:
        return normalize_country_code(value) if value else None

    @field_validator("base_currency")
    @classmethod
    def _valid_currency(cls, value: str | None) -> str | None:
        if not value:
            return None
        supported = {c.currency for c in list_countries()}
        if value.strip().upper() not in supported:
            raise ValueError(f"Unsupported base currency; supported: {sorted(supported)}")
        return value.strip().upper()


class InvestorProfileRead(InvestorProfileUpsert):
    model_config = ConfigDict(from_attributes=True)

    id: int
    investor_id: int
    updated_at: datetime
