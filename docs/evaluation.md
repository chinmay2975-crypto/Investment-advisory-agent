# InvestAd evaluation

Generated 2026-11-03 19:00 by `scripts/evaluate.py`.

## 1. Portfolio import accuracy (deterministic parsers)

| Format | Header styles parsed | Ticker precision | Ticker recall | Recall after verification | Quantity exact | Cost exact | Method |
|---|---|---|---|---|---|---|---|
| CSV | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| TSV | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| Excel | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| JSON | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| HTML | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| Word | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| PDF | 4/4 | 83% | 83% | 100% | 20/20 | 20/20 | columns |
| Pasted text | 1/1 | 83% | 83% | 100% | 5/5 | 5/5 | lines |
| **All** | 29/29 | 83.3% | 83.3% | 100.0% | 145/145 | 145/145 | F1 = 0.833 |
6 holdings per file, mixing bare NSE symbols, `NSE:` prefixes, explicit `.NS`, a US and a London ticker; default market India. Scanned PDFs and screenshots need the LLM and are not part of this offline table.


## 2. Country inference

| Portfolio | Expected | Inferred | Confidence | Mixed |
|---|---|---|---|---|
| RELIANCE.NS, TCS.NS, INFY.NS | IN | IN | high | no |
| HDFCBANK.BO, SBIN.BO | IN | IN | high | no |
| NIFTYBEES.NS, GOLDBEES.NS, ITC.NS, LT.NS | IN | IN | high | no |
| AAPL, MSFT, NVDA | US | US | medium | no |
| VTI, BND, VXUS | US | US | medium | no |
| SPY, QQQ, GLD, TLT | US | US | medium | no |
| VWRL.L, HSBA.L, BP.L | GB | GB | high | no |
| ISF.L, VUKE.L | GB | GB | high | no |
| LLOY.L, BARC.L, AZN.L, ULVR.L | GB | GB | high | no |
| RELIANCE.NS, TCS.NS, AAPL | IN | IN | low | yes |
| AAPL, MSFT, INFY.NS | US | US | low | yes |
| VWRL.L, BP.L, AAPL | GB | GB | low | yes |

**Accuracy: 12/12 (100%)**, offline (suffix rules only).


## 3. Monte Carlo goal probability

Lump sum of 100,000 needing to double in 10 years (no contributions), where a closed form exists:

| Allocation | E[return] | Volatility | Simulated P(goal) | Closed-form P(goal) | Abs. error |
|---|---|---|---|---|---|
| Conservative 30/60/10 | 5.8% | 6.8% | 0.230 | 0.233 | 0.003 |
| Balanced 60/40 | 7.2% | 10.9% | 0.423 | 0.434 | 0.011 |
| Aggressive 90/10 | 8.6% | 15.4% | 0.504 | 0.510 | 0.006 |

Mean absolute error vs closed form: **0.0066**.

Stability with monthly contributions (Balanced 60/40, India assumptions); the app uses 5,000 paths:

| Paths | Std. dev. of P(goal) over 20 seeds | Mean runtime |
|---|---|---|
| 500 | 0.0192 | 2.8 ms |
| 1,000 | 0.0135 | 4.4 ms |
| 5,000 | 0.0062 | 15.2 ms |
| 20,000 | 0.0028 | 51.8 ms |


## 4. Self-assessment outcomes

- Evaluations: 2
- Assumptions held: 2/2 (100%)
- Mean deviation from expected return: -0.02 pp (mean absolute 0.02 pp)


## 5. LLM providers (live)

| Provider | Calls | Valid structured output | Provider unavailable | Median latency (answered) |
|---|---|---|---|---|
| gemini | 3 | 3/3 answered | 0 | 8.4 s |
| groq | 3 | 3/3 answered | 0 | 2.0 s |

Measured 2026-11-03 19:01. Outages (429 rate limit, 503 overload) are what the router's alternation and fallback absorb: a request fails only if both providers are down.
