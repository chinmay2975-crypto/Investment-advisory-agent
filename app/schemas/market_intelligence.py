from datetime import datetime

from pydantic import BaseModel, Field


class GroundingDocument(BaseModel):
    """A normalized piece of market/macro/news context ready for ChromaDB ingestion."""

    id: str
    text: str
    source: str
    category: str  # market_behavior / sector_performance / rates / inflation / news / geopolitical
    as_of: datetime
    metadata: dict = Field(default_factory=dict)
