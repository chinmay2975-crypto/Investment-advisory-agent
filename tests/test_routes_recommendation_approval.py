from datetime import datetime, timedelta, timezone

from app.db.models import Goal, Investor, Recommendation

SAMPLE_PAYLOAD = {
    "what": "Shift to a 70/30 stock/bond split using VTI and BND",
    "target_allocation": {"stocks": 70, "bonds": 30},
    "suggested_instruments": ["VTI", "BND"],
    "why": "Balances growth with risk cadence",
    "expected_behavior": "Grows with market volatility",
    "goal_probability": 0.82,
    "risks": ["Market downturn risk"],
}


def _seed_investor_goal_recommendation(db_session):
    investor = Investor(email="approve@example.com", hashed_password="x")
    db_session.add(investor)
    db_session.flush()

    goal = Goal(
        investor_id=investor.id,
        category="Retirement",
        target_amount=50000,
        current_amount=5000,
        target_date=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=365 * 15),
        contribution_cadence="monthly",
        contribution_amount=200,
    )
    db_session.add(goal)
    db_session.flush()

    recommendation = Recommendation(
        investor_id=investor.id,
        goal_id=goal.id,
        status="pending",
        payload=SAMPLE_PAYLOAD,
        llm_provider="fake",
    )
    db_session.add(recommendation)
    db_session.commit()

    return investor, goal, recommendation


def test_approve_then_confirm_transitions_status_forward(client, db_session, auth_headers):
    investor, goal, recommendation = _seed_investor_goal_recommendation(db_session)
    headers = auth_headers(investor.id)

    approve_response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/approve", headers=headers
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "approved"

    confirm_response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/confirm", headers=headers
    )
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"


def test_confirm_before_approve_is_rejected(client, db_session, auth_headers):
    investor, goal, recommendation = _seed_investor_goal_recommendation(db_session)

    response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/confirm",
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 409


def test_approve_twice_is_rejected(client, db_session, auth_headers):
    investor, goal, recommendation = _seed_investor_goal_recommendation(db_session)
    headers = auth_headers(investor.id)

    first = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/approve", headers=headers
    )
    assert first.status_code == 200

    second = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/approve", headers=headers
    )
    assert second.status_code == 409


def test_export_pdf_returns_pdf_bytes(client, db_session, auth_headers):
    investor, goal, recommendation = _seed_investor_goal_recommendation(db_session)

    response = client.get(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/export-pdf",
        headers=auth_headers(investor.id),
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_recommendation_routes_reject_mismatched_investor_token(client, db_session, auth_headers):
    investor, goal, recommendation = _seed_investor_goal_recommendation(db_session)
    other = Investor(email="other-approver@example.com", hashed_password="x")
    db_session.add(other)
    db_session.commit()

    response = client.post(
        f"/investors/{investor.id}/recommendations/{recommendation.id}/approve",
        headers=auth_headers(other.id),
    )
    assert response.status_code == 403
