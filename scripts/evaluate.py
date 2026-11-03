"""Evaluation metrics for the project report. Writes docs/evaluation.md and prints it.

    .venv/Scripts/python.exe scripts/evaluate.py            # offline sections (deterministic, no keys)
    .venv/Scripts/python.exe scripts/evaluate.py --db       # + self-assessment stats from DATABASE_URL
    .venv/Scripts/python.exe scripts/evaluate.py --live 3   # + 3 real calls per LLM provider (uses quota)

Sections
 1. Portfolio import: ticker precision/recall and quantity/cost accuracy across file formats,
    with the LLM fallback disabled, so it measures only the deterministic parsers (plus the live
    ticker verification step unless --offline).
 2. Country inference accuracy on labelled portfolios.
 3. Monte Carlo goal simulation: agreement with the closed-form lognormal answer, seed stability
    vs number of paths, and runtime.
 4. (--db) Self-assessment outcomes recorded so far.
 5. (--live) LLM providers: latency and structured-output validity.
"""

import argparse
import io
import json
import math
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services import goal_simulation, portfolio_import  # noqa: E402
from app.services.portfolio_import import PortfolioImportError, import_portfolio  # noqa: E402

# --------------------------------------------------------------------------- 1. import
TRUTH = [  # (ticker as the evaluation expects it, quantity, per-unit cost)
    ("RELIANCE.NS", 20, 2400.0),
    ("TCS.NS", 10, 3650.5),
    ("INFY.NS", 35, 1480.0),
    ("HDFCBANK.NS", 15, 1610.25),
    ("AAPL", 5, 180.0),
    ("VWRL.L", 12, 98.4),
]
# How a broker export might write each ticker (default market for bare tickers = India).
WRITTEN = {"RELIANCE.NS": "RELIANCE", "TCS.NS": "NSE:TCS", "INFY.NS": "INFY", "HDFCBANK.NS": "HDFCBANK.NS",
           "AAPL": "AAPL", "VWRL.L": "VWRL.L"}
HEADER_STYLES = [
    ("Symbol", "Quantity", "Avg Cost"),
    ("Instrument", "Qty.", "Avg. cost"),
    ("Ticker", "Units", "Buy Price"),
    ("Scrip", "Shares", "Average Price"),
]


def _rows(header):
    return [list(header)] + [[WRITTEN[t], q, c] for t, q, c in TRUTH]


def _csv(header, sep=","):
    return "\n".join(sep.join(str(c) for c in r) for r in _rows(header)).encode()


def _xlsx(header):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Holdings statement as of 31-Mar"])  # junk line above the header
    for r in _rows(header):
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _json(header):
    keys = header
    return json.dumps({"holdings": [dict(zip(keys, [WRITTEN[t], q, c])) for t, q, c in TRUTH]}).encode()


def _html(header):
    cells = "".join(f"<tr>{''.join(f'<td>{c}</td>' for c in r)}</tr>" for r in _rows(header))
    return f"<html><body><h1>My portfolio</h1><table>{cells}</table></body></html>".encode()


def _docx(header):
    from docx import Document

    doc = Document()
    doc.add_paragraph("Portfolio summary")
    rows = _rows(header)
    table = doc.add_table(rows=len(rows), cols=3)
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            table.cell(i, j).text = str(c)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _pdf(header):
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

    buf = io.BytesIO()
    table = Table([[str(c) for c in r] for r in _rows(header)])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buf).build([table])
    return buf.getvalue()


def _paste(_header):
    return "\n".join(f"{WRITTEN[t]} {q} {c}" for t, q, c in TRUTH).encode()


FORMATS = [("CSV", "holdings.csv", _csv), ("TSV", "holdings.tsv", lambda h: _csv(h, "\t")),
           ("Excel", "holdings.xlsx", _xlsx), ("JSON", "holdings.json", _json), ("HTML", "holdings.html", _html),
           ("Word", "holdings.docx", _docx), ("PDF", "holdings.pdf", _pdf), ("Pasted text", None, _paste)]


def _no_ai(*_args, **_kwargs):
    raise PortfolioImportError("LLM fallback disabled for offline evaluation")


def evaluate_import(verify: bool) -> tuple[str, dict]:
    from app.services.portfolio_import import verify_tickers

    portfolio_import._ai_extract = _no_ai
    truth = {t: (q, c) for t, q, c in TRUTH}
    lines = ["| Format | Header styles parsed | Ticker precision | Ticker recall | Recall after verification | "
             "Quantity exact | Cost exact | Method |",
             "|---|---|---|---|---|---|---|---|"]
    totals = {"tp": 0, "fp": 0, "fn": 0, "qty": 0, "cost": 0, "cases": 0, "ok": 0, "vtp": 0}
    for label, filename, build in FORMATS:
        tp = fp = fn = qty_ok = cost_ok = parsed = verified_tp = 0
        methods = set()
        styles = [HEADER_STYLES[0]] if filename is None else HEADER_STYLES
        for header in styles:
            totals["cases"] += 1
            try:
                if filename is None:
                    result = import_portfolio(text=build(header).decode(), default_country="IN")
                else:
                    result = import_portfolio(content=build(header), filename=filename, default_country="IN")
            except PortfolioImportError:
                fn += len(truth)
                continue
            parsed += 1
            totals["ok"] += 1
            methods.add(result.method)
            got = {h.ticker: h for h in result.holdings}
            for ticker, holding in got.items():
                if ticker in truth:
                    tp += 1
                    qty_ok += holding.quantity == truth[ticker][0]
                    cost_ok += holding.cost_basis is not None and abs(holding.cost_basis - truth[ticker][1]) < 1e-6
                else:
                    fp += 1
            fn += len(set(truth) - set(got))
            if verify:  # the live price check the API runs before showing the preview
                verified_tp += len(set(truth) & {h.ticker for h in verify_tickers(result, "IN").holdings})
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        verified = f"{verified_tp / (len(truth) * len(styles)):.0%}" if verify else "-"
        lines.append(f"| {label} | {parsed}/{len(styles)} | {precision:.0%} | {recall:.0%} | {verified} | "
                     f"{qty_ok}/{tp} | {cost_ok}/{tp} | {', '.join(sorted(methods)) or '-'} |")
        for k, v in (("tp", tp), ("fp", fp), ("fn", fn), ("qty", qty_ok), ("cost", cost_ok), ("vtp", verified_tp)):
            totals[k] += v
    p = totals["tp"] / max(totals["tp"] + totals["fp"], 1)
    r = totals["tp"] / max(totals["tp"] + totals["fn"], 1)
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    all_verified = f"{totals['vtp'] / (totals['cases'] * len(truth)):.1%}" if verify else "-"
    lines.append(f"| **All** | {totals['ok']}/{totals['cases']} | {p:.1%} | {r:.1%} | {all_verified} | "
                 f"{totals['qty']}/{totals['tp']} | {totals['cost']}/{totals['tp']} | F1 = {f1:.3f} |")
    note = (f"\n{len(TRUTH)} holdings per file, mixing bare NSE symbols, `NSE:` prefixes, explicit `.NS`, a US "
            "and a London ticker; default market India. Scanned PDFs and screenshots need the LLM and are "
            "not part of this offline table.\n")
    return "\n".join(lines) + note, {"f1": f1}


# --------------------------------------------------------------------------- 2. country inference
LABELLED = [
    (["RELIANCE.NS", "TCS.NS", "INFY.NS"], "IN"), (["HDFCBANK.BO", "SBIN.BO"], "IN"),
    (["NIFTYBEES.NS", "GOLDBEES.NS", "ITC.NS", "LT.NS"], "IN"), (["AAPL", "MSFT", "NVDA"], "US"),
    (["VTI", "BND", "VXUS"], "US"), (["SPY", "QQQ", "GLD", "TLT"], "US"), (["VWRL.L", "HSBA.L", "BP.L"], "GB"),
    (["ISF.L", "VUKE.L"], "GB"), (["LLOY.L", "BARC.L", "AZN.L", "ULVR.L"], "GB"),
    (["RELIANCE.NS", "TCS.NS", "AAPL"], "IN"), (["AAPL", "MSFT", "INFY.NS"], "US"), (["VWRL.L", "BP.L", "AAPL"], "GB"),
]


def evaluate_country() -> tuple[str, dict]:
    from app.countries import infer_portfolio_country
    from app.schemas.country import HoldingCountryInput

    correct, rows = 0, ["| Portfolio | Expected | Inferred | Confidence | Mixed |", "|---|---|---|---|---|"]
    for tickers, expected in LABELLED:
        inference = infer_portfolio_country([HoldingCountryInput(ticker=t) for t in tickers])
        correct += inference.inferred_country == expected
        mark = "" if inference.inferred_country == expected else " ✗"
        rows.append(f"| {', '.join(tickers)} | {expected} | {inference.inferred_country}{mark} | "
                    f"{inference.confidence} | {'yes' if inference.is_mixed else 'no'} |")
    accuracy = correct / len(LABELLED)
    return "\n".join(rows) + f"\n\n**Accuracy: {correct}/{len(LABELLED)} ({accuracy:.0%})**, offline (suffix rules only).\n", {
        "accuracy": accuracy}


# --------------------------------------------------------------------------- 3. Monte Carlo
def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def evaluate_simulation() -> tuple[str, dict]:
    target_date = (datetime.now(timezone.utc) + timedelta(days=int(10 * 365.25))).isoformat()
    lump_goal = {"target_amount": 200_000, "current_amount": 100_000, "target_date": target_date}
    allocations = {"Conservative 30/60/10": {"equity": 30, "bonds": 60, "cash": 10},
                   "Balanced 60/40": {"equity": 60, "bonds": 40},
                   "Aggressive 90/10": {"equity": 90, "gold": 10}}

    rows = ["| Allocation | E[return] | Volatility | Simulated P(goal) | Closed-form P(goal) | Abs. error |",
            "|---|---|---|---|---|---|"]
    errors = []
    for name, allocation in allocations.items():
        sim = goal_simulation.simulate_goal(allocation, lump_goal, country="US")
        years = sim["months"] / 12
        mu = math.log1p(sim["expected_return"]) - 0.5 * sim["volatility"] ** 2
        z = (math.log(2.0) - mu * years) / (sim["volatility"] * math.sqrt(years))
        exact = 1 - _phi(z)
        errors.append(abs(sim["probability"] - exact))
        rows.append(f"| {name} | {sim['expected_return']:.1%} | {sim['volatility']:.1%} | {sim['probability']:.3f} | "
                    f"{exact:.3f} | {errors[-1]:.3f} |")

    saving_goal = {"target_amount": 1_000_000, "current_amount": 50_000, "target_date": target_date,
                   "contribution_cadence": "monthly", "contribution_amount": 5_000}
    stab = ["| Paths | Std. dev. of P(goal) over 20 seeds | Mean runtime |", "|---|---|---|"]
    original = (goal_simulation.PATHS, goal_simulation.SEED)
    try:
        for paths in (500, 1000, 5000, 20000):
            goal_simulation.PATHS = paths
            probs, times = [], []
            for seed in range(20):
                goal_simulation.SEED = seed
                start = time.perf_counter()
                probs.append(goal_simulation.simulate_goal(allocations["Balanced 60/40"], saving_goal, "IN")["probability"])
                times.append(time.perf_counter() - start)
            stab.append(f"| {paths:,} | {statistics.pstdev(probs):.4f} | {statistics.mean(times) * 1000:.1f} ms |")
    finally:
        goal_simulation.PATHS, goal_simulation.SEED = original

    text = ("Lump sum of 100,000 needing to double in 10 years (no contributions), where a closed form exists:\n\n"
            + "\n".join(rows)
            + f"\n\nMean absolute error vs closed form: **{statistics.mean(errors):.4f}**.\n\n"
            "Stability with monthly contributions (Balanced 60/40, India assumptions); the app uses 5,000 paths:\n\n"
            + "\n".join(stab) + "\n")
    return text, {"mae": statistics.mean(errors)}


# --------------------------------------------------------------------------- 4. self-assessment
def evaluate_self_assessment() -> str:
    from app.db.models import RecommendationEvaluation
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        evaluations = db.query(RecommendationEvaluation).all()
    if not evaluations:
        return "No evaluations recorded yet (they run 30 days after a suggestion is generated).\n"
    held = sum(1 for e in evaluations if e.assumptions_held)
    deviations = [e.deviation.get("deviation_pct") for e in evaluations if (e.deviation or {}).get("deviation_pct") is not None]
    excess = [e.deviation.get("excess_vs_benchmark_pct") for e in evaluations
              if (e.deviation or {}).get("excess_vs_benchmark_pct") is not None]
    lines = [f"- Evaluations: {len(evaluations)}",
             f"- Assumptions held: {held}/{len(evaluations)} ({held / len(evaluations):.0%})"]
    if deviations:
        lines.append(f"- Mean deviation from expected return: {statistics.mean(deviations):+.2f} pp "
                     f"(mean absolute {statistics.mean(abs(d) for d in deviations):.2f} pp)")
    if excess:
        beat = sum(1 for x in excess if x >= 0)
        lines.append(f"- Versus the market benchmark: beat it in {beat}/{len(excess)}, mean excess {statistics.mean(excess):+.2f} pp")
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- 5. live LLM
LIVE_PROMPT = """You are an investment information assistant. A Balanced-risk investor in India with a
15-year retirement goal holds RELIANCE.NS, TCS.NS and NIFTYBEES.NS. Propose a target allocation by
asset class, 2-4 suggested instruments, why, expected behaviour, an estimated goal probability (0-1)
and key risks. This is general information, not advice."""


def evaluate_live(n: int) -> str:
    from app.config import settings
    from app.llm.gemini_client import GeminiClient
    from app.llm.groq_client import GroqClient
    from app.schemas.recommendation import RecommendationOutput

    from collections import Counter

    from app.llm.base import ProviderError

    rows = ["| Provider | Calls | Valid structured output | Provider unavailable | Median latency (answered) |",
            "|---|---|---|---|---|"]
    for client in (GeminiClient(api_key=settings.gemini_api_key), GroqClient(api_key=settings.groq_api_key)):
        latencies, ok, outages = [], 0, Counter()
        for _ in range(n):
            start = time.perf_counter()
            try:
                output = client.generate(LIVE_PROMPT, RecommendationOutput)
                ok += bool(output.target_allocation) and 0 <= output.goal_probability <= 1
                latencies.append(time.perf_counter() - start)
            except ProviderError as exc:  # rate limit / overload: the router's fallback handles these
                outages[getattr(exc, "status_code", None) or "error"] += 1
            except Exception as exc:  # noqa: BLE001 - malformed output counts against validity
                print(f"  {client.name}: {type(exc).__name__}: {exc}"[:200], file=sys.stderr)
                latencies.append(time.perf_counter() - start)
        outage_text = ", ".join(f"{count}× HTTP {code}" for code, count in outages.items()) or "0"
        median = f"{statistics.median(latencies):.1f} s" if latencies else "-"
        answered = n - sum(outages.values())
        rows.append(f"| {client.name} | {n} | {ok}/{answered} answered | {outage_text} | {median} |")
    return ("\n".join(rows) + f"\n\nMeasured {datetime.now():%Y-%m-%d %H:%M}. Outages (429 rate limit, 503 overload) are "
            "what the router's alternation and fallback absorb: a request fails only if both providers are down.\n")


# --------------------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", action="store_true", help="include self-assessment stats from DATABASE_URL")
    parser.add_argument("--live", type=int, default=0, metavar="N", help="N real calls per LLM provider")
    parser.add_argument("--offline", action="store_true", help="skip the network ticker-verification column")
    parser.add_argument("--out", default=str(ROOT / "docs" / "evaluation.md"))
    args = parser.parse_args()

    import logging

    logging.disable(logging.WARNING)
    sections = [f"# InvestAd evaluation\n\nGenerated {datetime.now():%Y-%m-%d %H:%M} by `scripts/evaluate.py`."]
    text, _ = evaluate_import(verify=not args.offline)
    sections.append("## 1. Portfolio import accuracy (deterministic parsers)\n\n" + text)
    text, _ = evaluate_country()
    sections.append("## 2. Country inference\n\n" + text)
    text, _ = evaluate_simulation()
    sections.append("## 3. Monte Carlo goal probability\n\n" + text)
    if args.db:
        sections.append("## 4. Self-assessment outcomes\n\n" + evaluate_self_assessment())
    if args.live:
        sections.append("## 5. LLM providers (live)\n\n" + evaluate_live(args.live))

    report = "\n\n".join(sections)
    Path(args.out).write_text(report, encoding="utf-8")
    print(report)
    print(f"\nWrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
