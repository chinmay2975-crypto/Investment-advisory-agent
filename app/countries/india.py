from app.countries.base import (
    CapitalGainsTaxRules,
    CountryConfig,
    RiskFreeRateSource,
    TaxAdvantagedAccount,
)

INDIA = CountryConfig(
    code="IN",
    name="India",
    currency="INR",
    currency_symbol="₹",
    benchmark_ticker="^NSEI",
    benchmark_name="Nifty 50",
    risk_free_rate=RiskFreeRateSource(
        label="India 10-year government bond yield",
        fred_series="INDIRLTLT01STM",
        fallback_rate=0.068,
    ),
    ticker_suffixes=(".NS", ".BO"),
    exchanges=("NSI", "NSE", "BSE", "BOM"),
    capital_gains_tax=CapitalGainsTaxRules(
        as_of="FY 2024-25 (after the July 2024 Union Budget)",
        short_term_holding_months=12,
        summary=(
            "Listed equity shares and equity mutual funds held more than 12 months: long-term "
            "capital gains taxed at 12.5% on gains above ₹1.25 lakh per financial year.",
            "Held 12 months or less: short-term capital gains taxed at 20%.",
            "Debt mutual funds bought on or after 1 April 2023 are generally taxed at slab rates "
            "regardless of holding period.",
            "Securities Transaction Tax (STT) applies to listed equity trades.",
        ),
    ),
    tax_advantaged_accounts=(
        TaxAdvantagedAccount("PPF", "Public Provident Fund: long lock-in, tax-exempt returns."),
        TaxAdvantagedAccount("EPF", "Employees' Provident Fund: salaried retirement savings."),
        TaxAdvantagedAccount("NPS", "National Pension System: market-linked retirement scheme."),
        TaxAdvantagedAccount("ELSS", "Equity-linked savings scheme with a 3-year lock-in."),
    ),
    regulatory_disclaimer=(
        "InvestAd provides general information only and is not a SEBI-registered investment "
        "adviser. Personalised investment advice in India is regulated by SEBI under the "
        "Investment Advisers Regulations, 2013."
    ),
    exchange_suffixes={"NSE": ".NS", "NSI": ".NS", "BSE": ".BO", "BOM": ".BO"},
)
