import pytest

from app.db.models import Investor
from tests import market_fakes


@pytest.fixture(autouse=True)
def fake_market(monkeypatch):
    market_fakes.install(monkeypatch)


def _investor(db_session, email="portfolio@example.com"):
    investor = Investor(email=email, hashed_password="x")
    db_session.add(investor)
    db_session.commit()
    return investor


def test_list_countries_is_public(client):
    response = client.get("/countries")
    assert response.status_code == 200
    codes = {c["code"] for c in response.json()}
    assert codes == {"IN", "US", "GB"}
    india = next(c for c in response.json() if c["code"] == "IN")
    assert india["benchmark_ticker"] == "^NSEI"
    assert india["capital_gains_tax"]["summary"]


def test_infer_country_endpoint(client):
    response = client.post(
        "/countries/infer",
        json={"holdings": [{"ticker": "RELIANCE.NS", "market_value": 70}, {"ticker": "AAPL", "market_value": 30}]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["inferred_country"] == "IN"
    assert body["is_mixed"] is True


def test_analyze_requires_auth(client):
    response = client.post("/portfolio/analyze", json={"holdings": [{"ticker": "AAPL", "quantity": 1}]})
    assert response.status_code == 401


def test_analyze_mixed_portfolio(client, db_session, auth_headers):
    investor = _investor(db_session)
    response = client.post(
        "/portfolio/analyze",
        json={
            "holdings": [{"ticker": "RELIANCE.NS", "quantity": 10}, {"ticker": "AAPL", "quantity": 5}],
            "base_currency": "INR",
        },
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "INR"
    assert {c["country"] for c in body["per_country"]} == {"IN", "US"}
    assert body["combined_metrics"]["benchmark_ticker"] == "^NSEI"


@pytest.mark.parametrize(
    "payload",
    [
        {"holdings": []},  # nothing to infer from and no country
        {"holdings": [{"ticker": "AAPL", "quantity": 1}], "country": "FR"},
        {"holdings": [{"ticker": "AAPL", "quantity": 1}], "base_currency": "EUR"},
    ],
)
def test_analyze_bad_input_is_400(client, db_session, auth_headers, payload):
    investor = _investor(db_session)
    response = client.post("/portfolio/analyze", json=payload, headers=auth_headers(investor.id))
    assert response.status_code == 400


def test_profile_persists_normalised_country_and_currency(client, db_session, auth_headers):
    investor = _investor(db_session)
    headers = auth_headers(investor.id)
    response = client.put(
        f"/investors/{investor.id}/profile",
        json={"risk_cadence": "Balanced", "country": "uk", "base_currency": "gbp"},
        headers=headers,
    )
    assert response.status_code == 200
    assert (response.json()["country"], response.json()["base_currency"]) == ("GB", "GBP")


def test_profile_rejects_unsupported_country(client, db_session, auth_headers):
    investor = _investor(db_session)
    response = client.put(
        f"/investors/{investor.id}/profile",
        json={"risk_cadence": "Balanced", "country": "FR"},
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 422
