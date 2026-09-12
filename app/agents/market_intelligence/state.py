import operator
from typing import Annotated, TypedDict

from app.schemas.market_intelligence import GroundingDocument


class MarketIntelligenceState(TypedDict, total=False):
    market_behavior: Annotated[list[GroundingDocument], operator.add]
    sector_performance: Annotated[list[GroundingDocument], operator.add]
    rates: Annotated[list[GroundingDocument], operator.add]
    inflation: Annotated[list[GroundingDocument], operator.add]
    news: Annotated[list[GroundingDocument], operator.add]
    geopolitical: Annotated[list[GroundingDocument], operator.add]
    documents_ingested: int
