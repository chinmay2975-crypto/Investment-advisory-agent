from dataclasses import dataclass, field

GENERAL_INFORMATION_NOTICE = (
    "General information only, not personalised tax or investment advice. Rules change "
    "frequently and depend on individual circumstances; verify with official sources or a "
    "qualified adviser before acting."
)


@dataclass(frozen=True)
class RiskFreeRateSource:
    label: str
    fred_series: str
    fallback_rate: float  # annual decimal, used when live data is unavailable
    yfinance_ticker: str | None = None  # preferred live source when available (e.g. ^TNX)


@dataclass(frozen=True)
class CapitalGainsTaxRules:
    as_of: str
    short_term_holding_months: int | None  # None = no short/long-term distinction
    summary: tuple[str, ...]
    notice: str = GENERAL_INFORMATION_NOTICE


@dataclass(frozen=True)
class TaxAdvantagedAccount:
    name: str
    summary: str


@dataclass(frozen=True)
class CountryConfig:
    """One market's conventions. Add a country by creating a new instance in its own module
    and registering it in `registry.py` -- nothing else in the analysis code should need to
    change, since analysis reads every country-specific value from this object.
    """

    code: str
    name: str
    currency: str
    currency_symbol: str
    benchmark_ticker: str
    benchmark_name: str
    risk_free_rate: RiskFreeRateSource
    ticker_suffixes: tuple[str, ...]
    exchanges: tuple[str, ...]
    capital_gains_tax: CapitalGainsTaxRules
    tax_advantaged_accounts: tuple[TaxAdvantagedAccount, ...]
    regulatory_disclaimer: str
    # Quote currencies yfinance may report for this market in minor units, mapped to the
    # divisor that converts them to the major currency (e.g. LSE prices in pence: GBp -> /100).
    minor_currency_units: dict[str, int] = field(default_factory=dict)
    # yfinance suffix for an exchange named in an import file (e.g. "BSE" -> ".BO"); exchanges not
    # listed here fall back to the first entry of `ticker_suffixes` ("" when there is none, as for US).
    exchange_suffixes: dict[str, str] = field(default_factory=dict)
    aliases: tuple[str, ...] = ()

    @property
    def default_suffix(self) -> str:
        return self.ticker_suffixes[0] if self.ticker_suffixes else ""

    def suffix_for_exchange(self, exchange: str) -> str:
        return self.exchange_suffixes.get(exchange.strip().upper(), self.default_suffix)

    def matches_suffix(self, ticker: str) -> bool:
        upper = ticker.upper()
        return any(upper.endswith(suffix) for suffix in self.ticker_suffixes)

    def matches_exchange(self, exchange: str) -> bool:
        return exchange.strip().upper() in self.exchanges

    def matches_currency(self, currency: str) -> bool:
        return currency.strip().upper() == self.currency or currency.strip() in self.minor_currency_units

    def to_major_units(self, price: float, quote_currency: str | None) -> float:
        divisor = self.minor_currency_units.get((quote_currency or "").strip(), 1)
        return price / divisor
