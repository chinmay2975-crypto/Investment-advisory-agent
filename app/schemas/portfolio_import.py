from typing import Literal

from pydantic import BaseModel, Field


class ImportedHolding(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float | None = Field(default=None, description="Per-unit cost, in the holding's own currency")
    name: str | None = None
    source_ticker: str | None = Field(default=None, description="The ticker as written in the file, if we changed it")
    price_found: bool | None = Field(
        default=None, description="Whether market data exists for `ticker` (None if not checked)"
    )


class SkippedRow(BaseModel):
    row: int
    reason: str


class PortfolioImportResult(BaseModel):
    holdings: list[ImportedHolding]
    source_format: Literal["csv", "excel", "json", "pdf", "word", "html", "image", "text"]
    method: Literal["columns", "lines", "ai"] = Field(
        description="columns: matched table headers; lines: 'TICKER QTY [COST]' lines; ai: extracted by the LLM -- review carefully"
    )
    column_mapping: dict[str, str] = Field(default_factory=dict, description="Our field -> the header it was read from")
    skipped: list[SkippedRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# Structured output requested from the LLM when a document has no usable table.
class ExtractedHolding(BaseModel):
    ticker: str
    quantity: float
    cost_basis: float | None = None
    exchange: str | None = None  # e.g. NSE, BSE, LSE, NYSE, NASDAQ -- lets us add the right suffix


class ExtractedPortfolio(BaseModel):
    holdings: list[ExtractedHolding]
