from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.models import Investor


def _seed_investor_with_holding(db_session):
    from app.db.models import Holding

    investor = Investor(email="tax@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()

    holding = Holding(
        investor_id=investor.id,
        ticker="VTI",
        quantity=10,
        cost_basis=150.0,
        acquired_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=400),
        source="manual",
    )
    db_session.add(holding)
    db_session.commit()
    return investor


def test_tax_analysis_endpoint_returns_estimated_tax(client, db_session, auth_headers):
    investor = _seed_investor_with_holding(db_session)

    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = {"currentPrice": 200.0}
        response = client.post(
            f"/investors/{investor.id}/holdings/tax-analysis",
            json={"ordinary_income_tax_rate": 0.24, "taxable_income": 100000, "filing_status": "single"},
            headers=auth_headers(investor.id),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_unrealized_gain"] == 500.0
    assert body["holdings"][0]["holding_period"] == "long_term"
    assert body["holdings"][0]["estimated_tax_rate"] == 0.15


def test_tax_analysis_rejects_unknown_filing_status(client, db_session, auth_headers):
    investor = _seed_investor_with_holding(db_session)

    response = client.post(
        f"/investors/{investor.id}/holdings/tax-analysis",
        json={"ordinary_income_tax_rate": 0.24, "taxable_income": 100000, "filing_status": "bogus"},
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 400
