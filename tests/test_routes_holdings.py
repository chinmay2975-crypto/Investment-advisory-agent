import io
from unittest.mock import patch

from app.db.models import Investor


def _seed_investor(db_session):
    investor = Investor(email="holdings@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.commit()
    return investor


def test_create_and_list_holdings(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    headers = auth_headers(investor.id)

    response = client.post(
        f"/investors/{investor.id}/holdings/",
        json={"ticker": "vti", "quantity": 10, "cost_basis": 180.0},
        headers=headers,
    )
    assert response.status_code == 200
    created = response.json()
    assert created["ticker"] == "vti"
    assert created["source"] == "manual"

    list_response = client.get(f"/investors/{investor.id}/holdings/", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_holdings_require_auth(client, db_session):
    investor = _seed_investor(db_session)
    response = client.get(f"/investors/{investor.id}/holdings/")
    assert response.status_code == 401


def test_holdings_reject_other_investors_token(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    other = Investor(email="other@example.com", hashed_password="x")
    db_session.add(other)
    db_session.commit()

    response = client.get(f"/investors/{investor.id}/holdings/", headers=auth_headers(other.id))
    assert response.status_code == 403


def test_csv_upload_creates_holdings(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    headers = auth_headers(investor.id)

    csv_content = "ticker,quantity,cost_basis\nVTI,10,180.0\nBND,20,70.0\n"
    files = {"file": ("holdings.csv", io.BytesIO(csv_content.encode()), "text/csv")}

    response = client.post(f"/investors/{investor.id}/holdings/csv-upload", files=files, headers=headers)
    assert response.status_code == 200
    holdings = response.json()
    assert len(holdings) == 2
    assert {h["ticker"] for h in holdings} == {"VTI", "BND"}
    assert all(h["source"] == "csv_upload" for h in holdings)


def test_csv_upload_rejects_missing_columns(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    headers = auth_headers(investor.id)

    csv_content = "symbol,shares\nVTI,10\n"
    files = {"file": ("holdings.csv", io.BytesIO(csv_content.encode()), "text/csv")}

    response = client.post(f"/investors/{investor.id}/holdings/csv-upload", files=files, headers=headers)
    assert response.status_code == 400


def test_delete_holding(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    headers = auth_headers(investor.id)

    created = client.post(
        f"/investors/{investor.id}/holdings/",
        json={"ticker": "VTI", "quantity": 10},
        headers=headers,
    ).json()

    delete_response = client.delete(f"/investors/{investor.id}/holdings/{created['id']}", headers=headers)
    assert delete_response.status_code == 204

    list_response = client.get(f"/investors/{investor.id}/holdings/", headers=headers)
    assert list_response.json() == []


def test_portfolio_analysis_endpoint(client, db_session, auth_headers):
    investor = _seed_investor(db_session)
    headers = auth_headers(investor.id)
    client.post(
        f"/investors/{investor.id}/holdings/",
        json={"ticker": "VTI", "quantity": 10, "cost_basis": 180.0},
        headers=headers,
    )

    fake_info = {
        "currentPrice": 200.0,
        "quoteType": "ETF",
        "category": "Large Blend",
        "sector": "Diversified",
        "dividendYield": 0.015,
    }
    with patch("app.services.portfolio_analysis.yf.Ticker") as mock_ticker:
        mock_ticker.return_value.info = fake_info
        response = client.get(f"/investors/{investor.id}/holdings/analysis", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total_market_value"] == 2000.0
    assert body["asset_allocation"] == {"stocks": 100.0}
    assert body["risk_profile"] == "Aggressive"
