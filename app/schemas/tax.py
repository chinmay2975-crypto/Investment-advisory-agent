from pydantic import BaseModel


class TaxAnalysisRequest(BaseModel):
    ordinary_income_tax_rate: float
    taxable_income: float
    filing_status: str = "single"


class HoldingTaxDetail(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float | None
    current_price: float
    unrealized_gain: float
    holding_period: str
    estimated_tax_rate: float
    estimated_tax: float


class TaxAnalysisResult(BaseModel):
    total_unrealized_gain: float
    total_estimated_tax: float
    holdings: list[HoldingTaxDetail]
