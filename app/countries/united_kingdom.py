from app.countries.base import (
    CapitalGainsTaxRules,
    CountryConfig,
    RiskFreeRateSource,
    TaxAdvantagedAccount,
)

UNITED_KINGDOM = CountryConfig(
    code="GB",
    name="United Kingdom",
    currency="GBP",
    currency_symbol="£",
    benchmark_ticker="^FTSE",
    benchmark_name="FTSE 100",
    risk_free_rate=RiskFreeRateSource(
        label="UK 10-year gilt yield",
        fred_series="IRLTLT01GBM156N",
        fallback_rate=0.045,
    ),
    ticker_suffixes=(".L", ".IL"),
    exchanges=("LSE", "IOB", "LON"),
    capital_gains_tax=CapitalGainsTaxRules(
        as_of="2024-25 tax year (rates from 30 October 2024)",
        short_term_holding_months=None,
        summary=(
            "Gains on shares are taxed at 18% (basic-rate taxpayers) or 24% (higher and "
            "additional-rate taxpayers); there is no short/long-term distinction.",
            "Annual exempt amount: £3,000 of gains per tax year.",
            "Gains inside an ISA or SIPP are not subject to Capital Gains Tax.",
        ),
    ),
    tax_advantaged_accounts=(
        TaxAdvantagedAccount("Stocks & Shares ISA", "Tax-free growth and withdrawals, annual allowance."),
        TaxAdvantagedAccount("Lifetime ISA", "Government bonus for first home or retirement, age limits apply."),
        TaxAdvantagedAccount("SIPP", "Self-invested personal pension with tax relief on contributions."),
        TaxAdvantagedAccount("Workplace pension", "Employer pension with auto-enrolment contributions."),
    ),
    regulatory_disclaimer=(
        "InvestAd provides general information only and is not authorised or regulated by the "
        "Financial Conduct Authority (FCA). It does not provide regulated financial advice."
    ),
    minor_currency_units={"GBp": 100, "GBX": 100},
    exchange_suffixes={"LSE": ".L", "LON": ".L", "IOB": ".IL"},
    aliases=("UK",),
)
