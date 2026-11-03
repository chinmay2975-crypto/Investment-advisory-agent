from app.countries.base import (
    CapitalGainsTaxRules,
    CountryConfig,
    RiskFreeRateSource,
    TaxAdvantagedAccount,
)

UNITED_STATES = CountryConfig(
    code="US",
    name="United States",
    currency="USD",
    currency_symbol="$",
    benchmark_ticker="^GSPC",
    benchmark_name="S&P 500",
    risk_free_rate=RiskFreeRateSource(
        label="US 10-year Treasury yield",
        fred_series="IRLTLT01USM156N",
        fallback_rate=0.042,
        yfinance_ticker="^TNX",
    ),
    # US listings carry no yfinance suffix; inference treats "no recognised suffix" as US.
    ticker_suffixes=(),
    exchanges=("NMS", "NYQ", "NGM", "NCM", "ASE", "PCX", "BTS", "NASDAQ", "NYSE", "AMEX"),
    capital_gains_tax=CapitalGainsTaxRules(
        as_of="2024 federal rules",
        short_term_holding_months=12,
        summary=(
            "Held more than 1 year: long-term capital gains taxed federally at 0%, 15% or 20% "
            "depending on taxable income.",
            "Held 1 year or less: short-term gains taxed at ordinary income rates.",
            "A 3.8% Net Investment Income Tax may apply above certain income thresholds.",
            "Most states also tax capital gains; rates vary by state.",
        ),
    ),
    tax_advantaged_accounts=(
        TaxAdvantagedAccount("401(k)", "Employer-sponsored retirement plan, pre-tax or Roth."),
        TaxAdvantagedAccount("Traditional IRA", "Tax-deferred individual retirement account."),
        TaxAdvantagedAccount("Roth IRA", "After-tax contributions, tax-free qualified withdrawals."),
        TaxAdvantagedAccount("HSA", "Health Savings Account with triple tax advantage."),
    ),
    regulatory_disclaimer=(
        "InvestAd provides general information only and is not registered with the SEC or any "
        "state as an investment adviser. Nothing here is a recommendation to buy or sell a "
        "security."
    ),
)
