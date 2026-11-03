"""Check every country's live data sources exist (needs network and FRED_API_KEY).

Run: python scripts/check_data_sources.py   -- exits non-zero if any source is missing.
Catches mistakes like a wrong FRED series ID, which would otherwise fall back silently.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.countries import list_countries  # noqa: E402
from app.services import price_data  # noqa: E402
from app.services.macro_data import _fetch_latest_observation  # noqa: E402

failures = 0
for country in list_countries():
    checks = {
        f"benchmark {country.benchmark_ticker}": not price_data.fetch_price_history(country.benchmark_ticker, "5d").closes.empty,
    }
    try:
        observation = _fetch_latest_observation(country.risk_free_rate.fred_series)
        checks[f"FRED {country.risk_free_rate.fred_series}"] = bool(observation and observation.get("value") not in (None, "."))
    except Exception as exc:  # noqa: BLE001
        checks[f"FRED {country.risk_free_rate.fred_series} ({exc.__class__.__name__})"] = False
    if country.risk_free_rate.yfinance_ticker:
        checks[f"yfinance {country.risk_free_rate.yfinance_ticker}"] = not price_data.fetch_price_history(
            country.risk_free_rate.yfinance_ticker, "5d"
        ).closes.empty
    for name, ok in checks.items():
        print(f"{'OK  ' if ok else 'FAIL'} {country.code} {name}")
        failures += not ok
sys.exit(1 if failures else 0)
