from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Investor
from app.security import hash_password


def _investor(db):
    investor = Investor(email="g@example.com", hashed_password=hash_password("password-123"))
    db.add(investor)
    db.commit()
    return investor


def _goal(**overrides):
    goal = {
        "category": "Home",
        "target_amount": 3_000_000,
        "current_amount": 500_000,
        "target_date": (datetime.now(timezone.utc) + timedelta(days=5 * 365)).isoformat(),
        "contribution_cadence": "monthly",
        "contribution_amount": 20_000,
    }
    goal.update(overrides)
    return goal


def test_valid_goal_is_created(client, db_session, auth_headers):
    investor = _investor(db_session)
    response = client.post(f"/investors/{investor.id}/goals/", json=_goal(), headers=auth_headers(investor.id))
    assert response.status_code == 200


@pytest.mark.parametrize(
    "overrides",
    [
        {"target_date": "9999-12-31T00:00:00"},  # would have needed ~3.8 GB to simulate
        {"target_date": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()},
        {"target_amount": 0},
        {"target_amount": -5},
        {"target_amount": 1e300},
        {"current_amount": -1},
        {"contribution_amount": -100},
        {"category": ""},
        {"category": "x" * 500},
    ],
)
def test_unreasonable_goals_are_rejected(client, db_session, auth_headers, overrides):
    investor = _investor(db_session)
    response = client.post(f"/investors/{investor.id}/goals/", json=_goal(**overrides), headers=auth_headers(investor.id))
    assert response.status_code == 422


def test_many_goals_list_quickly(client, db_session, auth_headers):
    from app.db.models import Goal

    investor = _investor(db_session)
    target = datetime.now(timezone.utc) + timedelta(days=3650)
    db_session.add_all(
        Goal(investor_id=investor.id, category=f"Goal {i}", target_amount=1e6, target_date=target) for i in range(500)
    )
    db_session.commit()
    response = client.get(f"/investors/{investor.id}/goals/", headers=auth_headers(investor.id))
    assert response.status_code == 200
    assert len(response.json()) == 500
