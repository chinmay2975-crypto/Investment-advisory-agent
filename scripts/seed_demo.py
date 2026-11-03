"""Create (or reset) a demo account with a realistic Indian + US portfolio and two goals.

    .venv/Scripts/python.exe scripts/seed_demo.py           # create, or reset if it exists
    .venv/Scripts/python.exe scripts/seed_demo.py --remove  # delete the demo account and its data

Writes to whatever DATABASE_URL points at. It also adds one suggestion dated 45 days ago, so the
self-assessment page can be run during a demo without waiting 30 days. That suggestion is marked
`seeded_for_demo` and its provider is recorded as "seed", so it is never mistaken for a real LLM output.
"""

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.models import Goal, Holding, Investor, InvestorProfile, Recommendation  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.services.account import delete_investor_account  # noqa: E402

EMAIL = "demo@investad.app"
PASSWORD = "demo-investad-2026"

HOLDINGS = [  # ticker, quantity, per-unit cost (own currency, split-adjusted), months ago bought
    ("RELIANCE.NS", 40, 1180.0, 30),
    ("TCS.NS", 12, 2900.0, 26),
    ("INFY.NS", 35, 1250.0, 20),
    ("HDFCBANK.NS", 60, 640.0, 14),
    ("NIFTYBEES.NS", 250, 240.0, 9),
    ("GOLDBEES.NS", 300, 85.0, 7),
    ("AAPL", 2, 180.0, 18),
]


def remove(db) -> bool:
    investor = db.query(Investor).filter(Investor.email == EMAIL).first()
    if investor is None:
        return False
    delete_investor_account(db, investor)
    return True


def seed(db) -> Investor:
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # columns are naive UTC
    investor = Investor(email=EMAIL, hashed_password=hash_password(PASSWORD), full_name="Demo Investor")
    db.add(investor)
    db.flush()
    db.add(InvestorProfile(investor_id=investor.id, risk_cadence="Balanced", horizon_years=15, country="IN",
                           base_currency="INR", preferences={"esg": False}, restrictions={}))
    for ticker, quantity, cost, months in HOLDINGS:
        db.add(Holding(investor_id=investor.id, ticker=ticker, quantity=quantity, cost_basis=cost,
                       acquired_at=now - timedelta(days=30 * months), source="demo_seed"))
    retirement = Goal(investor_id=investor.id, category="Retirement", target_amount=20_000_000, current_amount=1_500_000,
                      target_date=datetime(2045, 4, 1), contribution_cadence="monthly", contribution_amount=25_000)
    home = Goal(investor_id=investor.id, category="Home", target_amount=3_000_000, current_amount=800_000,
                target_date=datetime(2030, 6, 1), contribution_cadence="monthly", contribution_amount=30_000)
    db.add_all([retirement, home])
    db.flush()
    db.add(Recommendation(
        investor_id=investor.id,
        goal_id=retirement.id,
        status="approved",
        llm_provider="seed",
        generated_at=now - timedelta(days=45),
        payload={
            "seeded_for_demo": True,
            "what": "Hold a 65/25/10 mix of Indian equity, Indian bonds and gold via NIFTYBEES, a gilt fund and GOLDBEES",
            "target_allocation": {"Indian equity": 65, "Indian bonds": 25, "Gold": 10},
            "suggested_instruments": ["NIFTYBEES.NS", "GOLDBEES.NS", "RELIANCE.NS"],
            "why": "A long horizon supports an equity tilt; bonds and gold dampen drawdowns before retirement.",
            "expected_behavior": "Should broadly track the Nifty 50 with somewhat lower volatility.",
            "goal_probability": 0.62,
            "risks": ["Equity drawdowns", "Interest-rate moves affecting bond prices", "Concentration in a few stocks"],
        },
    ))
    db.commit()
    return investor


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="delete the demo account instead of creating it")
    args = parser.parse_args()
    with SessionLocal() as db:
        existed = remove(db)
        if args.remove:
            print("Demo account removed." if existed else "No demo account to remove.")
            return
        investor = seed(db)
        print(f"{'Reset' if existed else 'Created'} demo account #{investor.id}")
        print(f"  email:    {EMAIL}\n  password: {PASSWORD}")
        print(f"  {len(HOLDINGS)} holdings, 2 goals, 1 suggestion from 45 days ago (for self-assessment)")


if __name__ == "__main__":
    main()
