from datetime import datetime, timezone

import httpx

from app.config import settings
from app.schemas.market_intelligence import GroundingDocument

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

RATE_SERIES = {"DFF": "Federal Funds Effective Rate", "DGS10": "10-Year Treasury Constant Maturity Rate"}
INFLATION_SERIES = {"CPIAUCSL": "Consumer Price Index (All Urban Consumers)"}


def _fetch_latest_observation(series_id: str) -> dict | None:
    response = httpx.get(
        FRED_BASE_URL,
        params={
            "series_id": series_id,
            "api_key": settings.fred_api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 1,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    return observations[0] if observations else None


def _series_document(series_id: str, label: str, category: str) -> GroundingDocument | None:
    observation = _fetch_latest_observation(series_id)
    if observation is None or observation.get("value") in (None, "."):
        return None

    value = float(observation["value"])
    as_of = datetime.strptime(observation["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc)

    text = f"{label} ({series_id}) was {value:.2f} as of {observation['date']}."
    return GroundingDocument(
        id=f"{category}:{series_id}:{observation['date']}",
        text=text,
        source="FRED",
        category=category,
        as_of=as_of,
        metadata={"series_id": series_id, "label": label, "value": value},
    )


def fetch_rates() -> list[GroundingDocument]:
    docs = [_series_document(sid, label, "rates") for sid, label in RATE_SERIES.items()]
    return [d for d in docs if d is not None]


def fetch_inflation() -> list[GroundingDocument]:
    docs = [_series_document(sid, label, "inflation") for sid, label in INFLATION_SERIES.items()]
    return [d for d in docs if d is not None]
